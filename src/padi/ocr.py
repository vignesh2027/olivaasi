"""Run Tesseract and keep the layout it reports (blocks, paragraphs, lines, word boxes)."""

from __future__ import annotations

import csv
import io
import os
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass, field

import cv2
import numpy as np

from . import config

LANG_CHOICES = {
    "tam+eng": "Tamil and English",
    "tam": "Tamil only",
    "eng": "English only",
}


@dataclass
class Word:
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass
class Line:
    block: int
    par: int
    words: list[Word] = field(default_factory=list)
    stroke: float = 0.0  # typical pen width in pixels; bold text is thicker

    @property
    def text(self) -> str:
        return clean_text(" ".join(w.text for w in self.words))

    @property
    def left(self) -> int:
        return min(w.left for w in self.words)

    @property
    def right(self) -> int:
        return max(w.right for w in self.words)

    @property
    def top(self) -> int:
        return min(w.top for w in self.words)

    @property
    def bottom(self) -> int:
        return max(w.bottom for w in self.words)

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def conf(self) -> float:
        return float(np.mean([w.conf for w in self.words])) if self.words else 0.0


def clean_text(text: str) -> str:
    """Normalise OCR output.

    Tesseract's Tamil model writes a zero-width non-joiner after every pulli
    (for example பாடம்‌). It is invisible but breaks search, copying and
    some speech engines, so it is removed. Smart quotes are kept.
    """
    text = unicodedata.normalize("NFC", text)
    text = text.replace("‌", "").replace("‍", "")
    text = text.replace(" ", " ")
    return " ".join(text.split())


def _write_png(img: np.ndarray) -> str:
    fd, path = tempfile.mkstemp(suffix=".png", prefix="padi-")
    os.close(fd)
    cv2.imwrite(path, img)
    return path


def run_tsv(img: np.ndarray, langs: str = "tam+eng", psm: int = 3) -> list[Line]:
    """OCR an image and return its text lines in Tesseract's reading order."""
    path = _write_png(img)
    try:
        cmd = [config.tesseract_bin(), path, "stdout", "-l", langs, "--psm", str(psm)]
        td = config.tessdata_dir()
        if td is not None:
            cmd += ["--tessdata-dir", str(td)]
        # Set the variables directly: the "tsv" config file only exists in the
        # system tessdata folder, not in a local models folder.
        cmd += ["-c", "tessedit_create_tsv=1", "-c", "tessedit_create_txt=0"]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError(f"Tesseract failed: {proc.stderr.strip()[:400]}")
    finally:
        os.unlink(path)
    return parse_tsv(proc.stdout)


def add_strokes(gray: np.ndarray, lines: list[Line]) -> None:
    """Measure stroke width per line so bold headings can be told from body text."""
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    dist = cv2.distanceTransform(ink, cv2.DIST_L2, 3)
    for ln in lines:
        d = dist[ln.top : ln.bottom, ln.left : ln.right]
        m = ink[ln.top : ln.bottom, ln.left : ln.right] > 0
        ln.stroke = float(np.percentile(d[m], 90)) if m.any() else 0.0


def group_words_into_lines(words: list[Word]) -> list[list[Word]]:
    """Cluster loose words by vertical centre, then order each cluster left to right."""
    if not words:
        return []
    med_h = float(np.median([w.height for w in words]))
    rows: list[tuple[float, list[Word]]] = []
    for w in sorted(words, key=lambda w: w.top + w.height / 2):
        cy = w.top + w.height / 2
        if rows and abs(cy - rows[-1][0]) < 0.6 * med_h:
            cys, ws = rows[-1]
            ws.append(w)
            rows[-1] = ((cys * (len(ws) - 1) + cy) / len(ws), ws)
        else:
            rows.append((cy, [w]))
    return [sorted(ws, key=lambda w: w.left) for _, ws in rows]


def parse_tsv(tsv: str) -> list[Line]:
    lines: dict[tuple[int, int, int], Line] = {}
    reader = csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)
    for row in reader:
        if row.get("level") != "5":
            continue
        text = (row.get("text") or "").strip()
        if not text:
            continue
        key = (int(row["block_num"]), int(row["par_num"]), int(row["line_num"]))
        line = lines.setdefault(key, Line(block=key[0], par=key[1]))
        line.words.append(
            Word(
                text=text,
                left=int(row["left"]),
                top=int(row["top"]),
                width=int(row["width"]),
                height=int(row["height"]),
                conf=float(row["conf"]),
            )
        )
    return [ln for ln in lines.values() if ln.text]
