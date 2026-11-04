"""Command line: olivaasi serve | olivaasi convert PHOTO | olivaasi doctor"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from . import config, ocr, tts


def doctor() -> int:
    """Check that everything needed offline is installed."""
    ok = True
    try:
        exe = config.tesseract_bin()
        version = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
        print(f"[ok]   Tesseract: {version}")
    except RuntimeError as e:
        print(f"[fail] {e}")
        return 1
    td = config.tessdata_dir()
    cmd = [exe, "--list-langs"] + (["--tessdata-dir", str(td)] if td else [])
    langs = subprocess.run(cmd, capture_output=True, text=True).stdout.split()
    for lang in ("tam", "eng"):
        if lang in langs:
            print(f"[ok]   OCR model '{lang}' found in {td or 'the system tessdata folder'}")
        else:
            ok = False
            print(f"[fail] OCR model '{lang}' missing. Run: sh scripts/get_models.sh")
    backend = tts.pick_backend()
    if backend is None:
        print("[warn] No offline voice found. Pages will have no audio. Install espeak-ng, or use macOS.")
    else:
        for lang, label in (("ta", "Tamil"), ("en", "English")):
            v = backend.voice_for(lang)
            if v:
                print(f"[ok]   {label} voice: {v} ({backend.name})")
            else:
                print(f"[warn] No {label} voice in {backend.name}; the default voice will be used.")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="olivaasi", description="Turn a photo of a textbook page into an accessible page with audio, offline.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="start the local web app")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    c = sub.add_parser("convert", help="convert one photo")
    c.add_argument("photo", type=Path)
    c.add_argument("-o", "--out", type=Path, required=True, help="output folder")
    c.add_argument("--lang", choices=list(ocr.LANG_CHOICES), default="tam+eng")
    c.add_argument("--no-audio", action="store_true")
    c.add_argument("--simplify", action="store_true", help="also add simplified paragraphs (needs Ollama running locally)")
    sub.add_parser("doctor", help="check the offline setup")
    args = p.parse_args(argv)

    if args.cmd == "doctor":
        return doctor()
    if args.cmd == "convert":
        from .pipeline import convert

        r = convert(args.photo, args.out, langs=args.lang, audio=not args.no_audio, simplified=args.simplify)
        secs = ", ".join(f"{k} {v:.1f}s" for k, v in r.timings.items())
        print(f"Wrote {r.out_dir / 'index.html'}  ({len(r.doc.blocks)} blocks, {len(r.doc.sentences())} sentences; {secs})")
        return 0
    if args.cmd == "serve":
        import uvicorn

        print(f"Olivaasi is running. Open http://{args.host}:{args.port}/ in a browser. Press Ctrl+C to stop.")
        uvicorn.run("olivaasi.server:app", host=args.host, port=args.port, log_level="warning")
        return 0
    return 2
