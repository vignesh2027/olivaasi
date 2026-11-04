"""Paths and external programs. Everything is local; nothing here touches the network."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_DIR = PACKAGE_DIR.parent.parent


def tessdata_dir() -> Path | None:
    """Folder holding tam.traineddata and eng.traineddata.

    PADI_TESSDATA wins, then ./models/tessdata in the repository (filled by
    scripts/get_models.sh), else None so Tesseract uses its built-in default.
    """
    env = os.environ.get("PADI_TESSDATA")
    if env:
        return Path(env)
    local = REPO_DIR / "models" / "tessdata"
    if (local / "tam.traineddata").exists():
        return local
    return None


def tesseract_bin() -> str:
    found = os.environ.get("PADI_TESSERACT") or shutil.which("tesseract")
    if not found:
        raise RuntimeError(
            "Tesseract is not installed. On macOS run: brew install tesseract. "
            "On Debian or Ubuntu run: sudo apt install tesseract-ocr"
        )
    return found


def work_dir() -> Path:
    """Where the server keeps converted pages."""
    d = Path(os.environ.get("PADI_WORK", REPO_DIR / "work"))
    d.mkdir(parents=True, exist_ok=True)
    return d
