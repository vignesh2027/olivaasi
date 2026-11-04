"""Take the screenshots in docs/screenshots (development tool).

Needs a running server: uv run olivaasi serve
    uv run python scripts/screenshots.py [--base http://127.0.0.1:8765]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from a11y_check import first_doc  # noqa: E402
from browser import Browser  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"


def highlight(b: Browser, steps: int) -> None:
    for _ in range(steps):
        b.eval("document.getElementById('next').click()")
        time.sleep(0.15)
    time.sleep(0.4)
    b.eval("document.getElementById('player').pause()")


def style(b: Browser, name: str, size: int) -> None:
    b.eval(f"document.querySelector('input[name=style][value={name}]').click();"
           f"var s=document.getElementById('size'); s.value='{size}'; s.dispatchEvent(new Event('change'))")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    doc = first_doc(args.base)
    url = f"{args.base}/doc/{doc}/"
    with Browser(1280, 900) as b:
        b.goto(f"{args.base}/")
        b.screenshot(OUT / "01-home.png", full=True)
        b.goto(url, wait=1.0)
        style(b, "standard", 100)
        highlight(b, 3)
        b.eval("window.scrollTo(0,0)")
        b.screenshot(OUT / "02-page-tamil-reading-along.png")
        style(b, "dyslexia", 200)
        b.eval("window.scrollTo(0,0)")
        b.screenshot(OUT / "03-page-wide-spacing-200.png")
        style(b, "dark", 150)
        highlight(b, 6)
        b.screenshot(OUT / "04-page-dark-high-contrast.png")
        style(b, "standard", 100)
        simple = first_doc(args.base, "en_water_photo", simple=True)
        b.goto(f"{args.base}/doc/{simple}/", wait=1.0)
        style(b, "standard", 100)
        b.eval("document.querySelector('input[name=version][value=simple]').click()")
        b.eval("window.scrollTo(0, 0)")
        b.screenshot(OUT / "06-page-english-simplified.png")
        b.eval("document.querySelector('input[name=version][value=original]').click()")
    with Browser(390, 844, scale=2) as b:
        b.send("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
        b.goto(url, wait=1.0)
        style(b, "standard", 100)
        b.goto(url, wait=1.0)
        b.screenshot(OUT / "05-page-phone-width.png")
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
