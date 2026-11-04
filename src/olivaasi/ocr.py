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
from .preprocess import letter_mask

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
    fd, path = tempfile.mkstemp(suffix=".png", prefix="olivaasi-")
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


def ink_rows(gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Horizontal bands that contain printed text: (top, bottom, left, right)."""
    ink = letter_mask(gray)
    h, w = ink.shape
    on = (ink > 0).sum(axis=1) > max(3, int(0.004 * w))
    runs: list[list[int]] = []
    for y in np.nonzero(on)[0]:
        if runs and y - runs[-1][1] <= 4:  # Tamil vowel signs sit just above or below the line
            runs[-1][1] = int(y)
        else:
            runs.append([int(y), int(y)])
    out = []
    for y0, y1 in runs:
        if y1 - y0 < 8:
            continue
        cols = np.nonzero((ink[y0 : y1 + 1] > 0).any(axis=0))[0]
        x0, x1 = int(cols[0]), int(cols[-1])
        density = (ink[y0 : y1 + 1, x0 : x1 + 1] > 0).mean()
        if density > 0.5:
            continue  # a dark edge or shadow, not text
        out.append((y0, y1 + 1, x0, x1 + 1))
    return out


def recover_missed(gray: np.ndarray, lines: list[Line], langs: str) -> tuple[list[Line], int]:
    """Read text rows that Tesseract's page layout step skipped.

    On blurred or low-resolution photos Tesseract sometimes drops a whole
    paragraph without any warning, and a blind reader cannot notice that.
    Every band of ink that no recognised line overlaps is read again on its
    own and put back in reading order. Returns the merged lines and how many
    lines were recovered.
    """
    def covered(y0: int, y1: int) -> bool:
        for ln in lines:
            overlap = min(y1, ln.bottom) - max(y0, ln.top)
            if overlap > 0.4 * (y1 - y0):
                return True
        return False

    missed = [r for r in ink_rows(gray) if not covered(r[0], r[1])][:MAX_RECOVER]
    h, w = gray.shape
    added: list[Line] = []
    for k, (y0, y1, x0, x1) in enumerate(missed):
        line = _read_row(gray, max(0, y0 - 3), min(h, y1 + 3), max(0, x0 - 12), min(w, x1 + 12), langs)
        if line is not None:
            line.block, line.par = 10_000 + k, 1
            added.append(line)
    if not added:
        return lines, 0
    merged = list(lines)
    for ln in added:
        pos = next((i for i, other in enumerate(merged) if other.top > ln.top), len(merged))
        before = merged[pos - 1] if pos > 0 else None
        after = merged[pos] if pos < len(merged) else None
        if before and after and (before.block, before.par) == (after.block, after.par):
            ln.block, ln.par = before.block, before.par  # it was a line inside that paragraph
        merged.insert(pos, ln)
    return merged, len(added)


MAX_RECOVER = 40


def _read_row(gray: np.ndarray, y0: int, y1: int, x0: int, x1: int, langs: str) -> Line | None:
    """Read one row of text as a single line, enlarged, skipping layout analysis."""
    crop = cv2.resize(gray[y0:y1, x0:x1], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    crop = cv2.copyMakeBorder(crop, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    for psm in (13, 7):
        found = [ln for ln in run_tsv(crop, langs=langs, psm=psm) if ln.words]
        words = [wd for ln in found for wd in ln.words]
        if not words:
            continue
        line = Line(block=0, par=0, words=words)
        if line.conf < 50 or not any(len(wd.text) >= 2 for wd in words):
            continue
        for wd in words:  # back to page coordinates
            wd.left = x0 + (wd.left - 20) // 2
            wd.top = y0 + (wd.top - 20) // 2
            wd.width //= 2
            wd.height //= 2
        return line
    return None


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
