"""Keyboard-only walkthrough of the core task (development tool).

Needs a running server (uv run olivaasi serve). Converts the Tamil science
sample, then uses only the Tab, Shift+Tab, Space and Enter keys to:
  1. list every stop in the tab order with its accessible name and whether a
     focus outline is visible;
  2. do the learner's task: reach question 3 and hear it read, by moving
     sentence by sentence with the Next button.
It also prints the accessibility tree outline that a screen reader receives
(headings, lists, tables and the language of each block).

    uv run python scripts/keyboard_walk.py [--base http://127.0.0.1:8765]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from a11y_check import first_doc  # noqa: E402
from browser import Browser  # noqa: E402

FOCUS = """(() => { const e = document.activeElement; if (!e || e === document.body) return null;
  const cs = getComputedStyle(e); const name = (e.getAttribute('aria-label') || e.innerText || e.value || e.getAttribute('href') || '').trim().replace(/\\s+/g,' ').slice(0,60);
  const lbl = e.labels && e.labels[0] ? e.labels[0].innerText.trim() : '';
  return {tag: e.tagName.toLowerCase(), type: e.type || '', name: lbl || name, outline: cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2}; })()"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    args = ap.parse_args()
    doc = first_doc(args.base)
    with Browser(1280, 900) as b:
        b.goto(f"{args.base}/doc/{doc}/", wait=1.0)
        print("## Tab order on a converted page")
        seen = []
        for _ in range(40):
            b.key("Tab")
            f = b.eval(FOCUS)
            if not f or (seen and f == seen[0] and len(seen) > 3):
                break
            seen.append(f)
            print(f"{len(seen):2d}. {f['tag']}{'[' + f['type'] + ']' if f['type'] else ''}: {f['name']!r}  focus outline: {'yes' if f['outline'] else 'NO'}")
        print()
        print("## Task: reach question 3 and hear it, keyboard only")
        b.goto(f"{args.base}/doc/{doc}/", wait=1.0)
        q3 = b.eval("document.querySelectorAll('ol.questions li')[2].innerText.trim()")
        target = b.eval("[...document.querySelectorAll('[data-start]')].indexOf(document.querySelectorAll('ol.questions li')[2].querySelector('[data-start]'))")
        presses = 0
        while b.eval("document.activeElement && document.activeElement.id") != "nexth" and presses < 30:
            b.key("Tab")
            presses += 1
        jumps = 0
        while jumps < 10 and not b.eval("(document.querySelector('.now')||{}).closest && document.querySelector('.now').closest('h2') && document.querySelector('.now').closest('h2').nextElementSibling.matches('ol')"):
            b.key(" ", code="Space")
            jumps += 1
            time.sleep(0.15)
        print(f"Tab pressed {presses} times to reach Next heading; Space pressed {jumps} times to reach the questions heading.")
        b.key("Tab", shift=True)
        b.key("Tab", shift=True) if b.eval("document.activeElement.id") != "next" else None
        steps = 0
        while steps < 60:
            b.key(" ", code="Space")
            steps += 1
            time.sleep(0.15)
            now = b.eval("(document.querySelector('.now')||{}).innerText || ''")
            if b.eval(f"[...document.querySelectorAll('[data-start]')].indexOf(document.querySelector('.now')) === {target}"):
                break
        playing = b.eval("!document.getElementById('player').paused")
        status = b.eval("document.getElementById('where').textContent")
        print(f"Space pressed {steps} times on Next. Highlighted: {now!r}. Audio playing: {playing}. Status announced: {status!r}.")
        print(f"Question 3 as printed on the page: {q3!r}")
        b.eval("document.getElementById('player').pause()")
        print()
        print("## What a screen reader receives (Chrome accessibility tree, outline)")
        tree = b.send("Accessibility.getFullAXTree")["nodes"]
        roles = {"heading", "list", "listitem", "table", "row", "columnheader", "button", "radio", "combobox", "region", "group", "Audio"}
        for n in tree:
            role = n.get("role", {}).get("value")
            if role in roles and not n.get("ignored"):
                name = (n.get("name", {}) or {}).get("value", "")
                level = next((p["value"]["value"] for p in n.get("properties", []) if p["name"] == "level"), "")
                print(f"  {role}{' ' + str(level) if level else ''}: {name[:70]!r}")
        langs = b.eval("[...document.querySelectorAll('article [lang]')].map(e => e.getAttribute('lang')).reduce((a, l) => (a[l] = (a[l]||0)+1, a), {})")
        print(f"  lang attributes inside the lesson: {langs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
