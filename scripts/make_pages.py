"""Typeset the evaluation pages and make a clean scan and a simulated phone photo of each.

Each page in eval/pages/*.json is laid out as a printed textbook page in HTML,
rendered to PNG with headless Chrome (which shapes Tamil correctly), then
degraded into a phone-style photo with a fixed random seed.

The rendered images are committed, so running the evaluation does not need
Chrome. Run this only to regenerate them:

    uv run python scripts/make_pages.py
"""

from __future__ import annotations

import html
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "eval" / "pages"
IMAGES = ROOT / "eval" / "images"
CHROME = os.environ.get(
    "OLIVAASI_CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)
WIDTH, HEIGHT = 1240, 1754  # A4 at 150 dpi

CSS = """
body { margin: 0; background: #fffdf7; color: #1a1a1a; }
.page { width: 1040px; margin: 0 auto; padding: 90px 0 60px; font-family: '%(font)s', 'Tamil Sangam MN', serif; font-size: 25px; line-height: 1.6; }
h1 { font-size: 40px; margin: 0 0 26px; }
h2 { font-size: 31px; margin: 34px 0 14px; }
p { margin: 0 0 18px; text-align: justify; }
.verse { margin: 0 0 20px 70px; }
table { border-collapse: collapse; margin: 24px 0 10px 40px; }
td, th { border: 2px solid #333; padding: 8px 22px; text-align: left; }
th { font-weight: bold; }
ol { margin: 0; padding-left: 0; list-style: none; }
li { margin: 0 0 10px; }
"""


def page_html(spec: dict) -> str:
    out = []
    for b in spec["blocks"]:
        t = b["type"]
        if t in ("h1", "h2", "p"):
            out.append(f"<{t}>{html.escape(b['text'])}</{t}>")
        elif t == "verse":
            out.append('<div class="verse">' + "<br>".join(html.escape(x) for x in b["lines"]) + "</div>")
        elif t == "table":
            rows = b["rows"]
            head = "".join(f"<th>{html.escape(c)}</th>" for c in rows[0])
            body = "".join(
                "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in rows[1:]
            )
            out.append(f"<table><tr>{head}</tr>{body}</table>")
        elif t == "ol":
            out.append(
                "<ol>" + "".join(f"<li>{i}. {html.escape(x)}</li>" for i, x in enumerate(b["items"], 1)) + "</ol>"
            )
    css = CSS % {"font": spec.get("font", "serif")}
    lang = spec.get("lang", "ta")
    return f'<!doctype html><html lang="{lang}"><meta charset="utf-8"><style>{css}</style><div class="page">{"".join(out)}</div></html>'


def render(spec: dict, png: Path, profile: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(page_html(spec))
        src = f.name
    subprocess.run(
        [
            CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            f"--user-data-dir={profile}", f"--window-size={WIDTH},{HEIGHT}",
            "--force-device-scale-factor=1", f"--screenshot={png}", f"file://{src}",
        ],
        check=True, capture_output=True,
    )
    os.unlink(src)


def photo(scan: np.ndarray, seed: int) -> np.ndarray:
    """Simulate a handheld phone photo of the page lying on a desk."""
    rng = np.random.default_rng(seed)
    h, w = scan.shape[:2]
    # Paper shading: a soft light-to-dark gradient across the page.
    gx = np.linspace(1.0, 0.82, w)[None, :]
    gy = np.linspace(0.95, 1.0, h)[:, None]
    shaded = (scan.astype(np.float32) * (gx * gy)[..., None]).clip(0, 255)
    # Put the page on a darker desk and warp it with a mild perspective and tilt.
    cw, ch = int(w * 1.25), int(h * 1.2)
    desk = np.full((ch, cw, 3), (70, 85, 100), np.float32)
    desk += rng.normal(0, 8, desk.shape)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    ox, oy = (cw - w) / 2, (ch - h) / 2
    j = lambda s: rng.uniform(-s, s)
    dst = np.float32([
        [ox + j(40) + 30, oy + j(30)],
        [ox + w + j(40) - 10, oy + j(30) + 35],
        [ox + w + j(40) + 15, oy + h + j(30)],
        [ox + j(40) - 20, oy + h + j(30) - 20],
    ])
    m = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(shaded, m, (cw, ch), flags=cv2.INTER_CUBIC, borderValue=0)
    mask = cv2.warpPerspective(np.ones((h, w), np.float32), m, (cw, ch))[..., None]
    out = warped * mask + desk * (1 - mask)
    out = cv2.GaussianBlur(out, (0, 0), 1.1)
    out += rng.normal(0, 5, out.shape)
    out = out.clip(0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 72])
    assert ok
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def hard_photo(scan: np.ndarray, seed: int) -> np.ndarray:
    """A worse photo: page curl, a strong shadow, taken from further away, more blur and compression."""
    rng = np.random.default_rng(seed)
    h, w = scan.shape[:2]
    # Curl: the page bows, so straight text lines become arcs.
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    bow = 14 * np.sin(np.pi * xs / w) * (0.4 + 0.6 * ys / h)
    curled = cv2.remap(scan, xs, ys - bow, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    # A shadow from a hand or phone across one corner.
    shadow = 1 - 0.45 * np.clip(1 - np.hypot(xs - w, ys - h) / (0.9 * w), 0, 1)
    shaded = curled.astype(np.float32) * shadow[..., None] * np.linspace(1.0, 0.85, h)[:, None, None]
    out = photo(shaded.clip(0, 255).astype(np.uint8), seed)
    # Further away: the page is about 1100 px wide in the final image.
    f = 0.62
    out = cv2.resize(out, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    out = cv2.GaussianBlur(out.astype(np.float32), (0, 0), 0.9) + rng.normal(0, 7, out.shape)
    ok, buf = cv2.imencode(".jpg", out.clip(0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 55])
    assert ok
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def main() -> int:
    IMAGES.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="olivaasi-chrome-"))
    for i, path in enumerate(sorted(PAGES.glob("*.json"))):
        spec = json.loads(path.read_text(encoding="utf-8"))
        scan_png = IMAGES / f"{spec['id']}_scan.png"
        render(spec, scan_png, profile)
        scan = cv2.imread(str(scan_png))
        cv2.imwrite(str(IMAGES / f"{spec['id']}_photo.jpg"), photo(scan, seed=100 + i), [cv2.IMWRITE_JPEG_QUALITY, 85])
        cv2.imwrite(str(IMAGES / f"{spec['id']}_hard.jpg"), hard_photo(scan, seed=200 + i), [cv2.IMWRITE_JPEG_QUALITY, 90])
        print("made", spec["id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
