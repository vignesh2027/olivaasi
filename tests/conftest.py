import shutil
import subprocess
from pathlib import Path

import pytest

from padi import config

ROOT = Path(__file__).resolve().parent.parent


def _has_tamil_ocr() -> bool:
    try:
        exe = config.tesseract_bin()
    except RuntimeError:
        return False
    td = config.tessdata_dir()
    cmd = [exe, "--list-langs"] + (["--tessdata-dir", str(td)] if td else [])
    return "tam" in subprocess.run(cmd, capture_output=True, text=True).stdout.split()


needs_ocr = pytest.mark.skipif(not _has_tamil_ocr(), reason="Tesseract with Tamil model not installed")


@pytest.fixture
def work(tmp_path, monkeypatch):
    monkeypatch.setenv("PADI_WORK", str(tmp_path / "work"))
    monkeypatch.setenv("PADI_TTS", "none")  # keep tests fast and voice-independent
    return tmp_path


@pytest.fixture
def sample_image():
    return ROOT / "eval" / "images" / "ta_water_photo.jpg"


def has_voice() -> bool:
    return shutil.which("say") is not None or shutil.which("espeak-ng") is not None
