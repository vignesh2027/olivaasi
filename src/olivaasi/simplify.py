"""Optional simplified reading of English prose paragraphs, with a local model through Ollama.

This is an extra, off by default. It talks only to an Ollama server on this
computer (127.0.0.1), so it stays offline. Only prose paragraphs are
simplified: never verse, questions, tables or headings, because a student must
answer the questions as printed and a poem cannot be paraphrased.

A small model can change facts. In our tests an unconstrained prompt turned
"1330 kurals" into "more than 3300". So the prompt forbids changing facts and
numbers, and every result is checked before it is shown: it is dropped if it
contains a number that is not in the original, if its length changes too much,
or if it is almost the same as the original (nothing to gain). Every shown
version is labelled as simplified by a computer, with the original one tap away.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

HOST = "http://127.0.0.1:11434"
MODEL = os.environ.get("OLIVAASI_SIMPLIFY_MODEL", "gemma3:4b")
# Tamil is off by default: with gemma3:4b, 3 of 4 Tamil test paragraphs came back
# with a changed meaning, a dropped fact or a grammar error. Set to 1 only to experiment.
TAMIL = os.environ.get("OLIVAASI_SIMPLIFY_TAMIL") == "1"

PROMPTS = {
    "ta": (
        "You simplify school textbook text for Tamil-medium students. Rewrite the Tamil paragraph below in "
        "simple written Tamil (எழுத்துத் தமிழ், not spoken Tamil). Rules: use short sentences; keep every fact; "
        "keep every number exactly as written, in the same form; do not add any fact, example or opinion; "
        "keep technical terms unchanged. Output only the rewritten Tamil paragraph.\n\nParagraph:\n"
    ),
    "en": (
        "You simplify school textbook text. Rewrite the paragraph below in plain English. Rules: use short "
        "sentences; keep every fact; keep every number exactly as written; do not add any fact, example or "
        "opinion; keep technical terms unchanged. Output only the rewritten paragraph.\n\nParagraph:\n"
    ),
}


@dataclass
class Simplified:
    text: str | None
    reason: str = ""


def available(model: str = MODEL) -> str | None:
    """None if simplification can run, else a short reason it cannot."""
    try:
        with urllib.request.urlopen(f"{HOST}/api/tags", timeout=1.5) as r:
            names = [m["name"] for m in json.load(r).get("models", [])]
    except (OSError, ValueError):
        return "Ollama is not running on this computer."
    if model not in names:
        return f"The model {model} is not installed in Ollama."
    return None


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", text))


def check(original: str, simple: str) -> str:
    """Empty string if the simplified text may be shown, else why not."""
    if not simple:
        return "empty"
    extra = numbers(simple) - numbers(original)
    if extra:
        return f"changed or added numbers ({', '.join(sorted(extra))})"
    ratio = len(simple) / max(1, len(original))
    if ratio > 1.6 or ratio < 0.4:
        return "length changed too much"
    if difflib.SequenceMatcher(None, original, simple).ratio() > 0.97:
        return "almost the same as the original"
    return ""


def simplify(text: str, lang: str, model: str = MODEL) -> Simplified:
    body = json.dumps({
        "model": model,
        "prompt": PROMPTS.get(lang, PROMPTS["en"]) + text,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 400},
    }).encode()
    req = urllib.request.Request(f"{HOST}/api/generate", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            out = json.load(r).get("response", "").strip()
    except (OSError, ValueError) as e:
        return Simplified(None, f"model error: {e}")
    out = " ".join(out.split())
    why = check(text, out)
    return Simplified(None if why else out, why)
