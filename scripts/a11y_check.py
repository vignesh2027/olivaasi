"""Run the axe-core accessibility checker on Olivaasi's own pages (development tool).

Needs a running server (uv run olivaasi serve) and axe.min.js, fetched by
scripts/get_models.sh into models/vendor/. Checks the WCAG 2.0, 2.1 and 2.2
A and AA rules that axe can test automatically, on:

  * the home page
  * the home page after a failed upload (error state)
  * one converted page in each reading style, at 100% and 300% text size

Automated checks find only part of the problems; see EVALUATION.md for the
manual keyboard and screen reader notes.

    uv run python scripts/a11y_check.py [--base http://127.0.0.1:8765] [--doc DOC_ID]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser import Browser  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
AXE = ROOT / "models" / "vendor" / "axe.min.js"
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]


def run_axe(b: Browser) -> list[dict]:
    b.eval(AXE.read_text(encoding="utf-8"))
    res = b.eval(
        "axe.run(document, {runOnly: {type: 'tag', values: %s}, resultTypes: ['violations']})"
        ".then(r => r.violations.map(v => ({id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.map(n => n.target.join(' ')).slice(0, 5)})))"
        % json.dumps(TAGS),
        await_promise=True,
    )
    return res or []


def first_doc(base: str, key: str = "ta_water_photo", simple: bool = False) -> str:
    data = f"key={key}&audio=1" + ("&simple=1" if simple else "")
    req = urllib.request.Request(f"{base}/sample", data=data.encode(), method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        opener.open(req, timeout=120)
    except urllib.error.HTTPError as e:
        return e.headers["Location"].rstrip("/").split("/")[-1]
    raise RuntimeError("sample conversion did not redirect")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--doc", help="id of an existing converted page")
    args = ap.parse_args()
    doc = args.doc or first_doc(args.base)
    checks: list[tuple[str, str, str | None]] = [
        ("home", f"{args.base}/", None),
        ("home, error state", f"{args.base}/", "error"),
    ]
    for style in ("standard", "dyslexia", "dark"):
        for size in (100, 300):
            checks.append((f"converted page, {style}, {size}%", f"{args.base}/doc/{doc}/", f"{style}:{size}"))
    simple_doc = first_doc(args.base, "en_water_photo", simple=True)
    checks.append(("English page, simplified version shown", f"{args.base}/doc/{simple_doc}/", "simple"))
    checks.append(("converted page at phone width (settings folded)", f"{args.base}/doc/{doc}/", "phone"))
    total = 0
    with Browser() as b:
        for name, url, mode in checks:
            b.goto(url)
            if mode == "error":
                b.eval("document.querySelector('form[action=\"/convert\"]').removeAttribute('enctype');"
                       "document.getElementById('photo').removeAttribute('required');"
                       "document.querySelector('form[action=\"/convert\"]').submit()")
                import time
                time.sleep(1.5)
            elif mode == "simple":
                b.eval("document.querySelector('input[name=style][value=standard]').click();"
                       "var v=document.querySelector('input[name=version][value=simple]'); if(!v) throw new Error('no simplified version'); v.click()")
            elif mode == "phone":
                b.send("Emulation.setDeviceMetricsOverride", width=360, height=740, deviceScaleFactor=2, mobile=True)
                b.goto(url)
            elif mode:
                style, size = mode.split(":")
                b.eval(f"document.querySelector('input[name=style][value={style}]').click();"
                       f"var s=document.getElementById('size'); s.value='{size}'; s.dispatchEvent(new Event('change'))")
            v = run_axe(b)
            total += len(v)
            print(f"{name}: {len(v)} violation(s)")
            for item in v:
                print(f"   [{item['impact']}] {item['id']}: {item['help']}: {item['nodes']}")
        # Reflow: no sideways scrolling at phone widths, even at 300% text.
        reflow_fail = 0
        for w in (320, 360, 390):
            b.send("Emulation.setDeviceMetricsOverride", width=w, height=800, deviceScaleFactor=1, mobile=True)
            b.goto(f"{args.base}/doc/{doc}/")
            for size in (100, 200, 300):
                b.eval(f"var s=document.getElementById('size'); s.value='{size}'; s.dispatchEvent(new Event('change'))")
                sw = b.eval("document.documentElement.scrollWidth")
                cw = b.eval("document.documentElement.clientWidth")
                if sw > cw + 1:
                    reflow_fail += 1
                    print(f"reflow: {w}px wide at {size}% text scrolls sideways ({sw}px of content)")
        print(f"reflow at 320, 360 and 390 px, text 100/200/300%: {'all fit' if not reflow_fail else str(reflow_fail) + ' failure(s)'}")
        total += reflow_fail
    print(f"TOTAL {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
