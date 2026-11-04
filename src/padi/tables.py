"""Find ruled tables (printed grid lines) and read them cell by cell."""

from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np

from . import ocr


@dataclass
class Grid:
    x0: int
    y0: int
    x1: int
    y1: int
    xs: list[int]  # column boundaries, left to right
    ys: list[int]  # row boundaries, top to bottom

    @property
    def n_rows(self) -> int:
        return len(self.ys) - 1

    @property
    def n_cols(self) -> int:
        return len(self.xs) - 1


def _peaks(profile: np.ndarray, min_value: float, min_gap: int) -> list[int]:
    idx = np.where(profile >= min_value)[0]
    groups: list[list[int]] = []
    for i in idx:
        if groups and i - groups[-1][-1] <= min_gap:
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    return [int(np.mean(g)) for g in groups]


def find_grids(gray: np.ndarray) -> list[Grid]:
    h, w = gray.shape
    ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 15)
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(40, w // 25), 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(30, h // 50)))
    horiz = cv2.morphologyEx(ink, cv2.MORPH_OPEN, hk)
    vert = cv2.morphologyEx(ink, cv2.MORPH_OPEN, vk)
    mesh = cv2.dilate(cv2.bitwise_or(horiz, vert), np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mesh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    grids: list[Grid] = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if cw < w * 0.15 or ch < h * 0.03:
            continue
        hs = horiz[y : y + ch, x : x + cw]
        vs = vert[y : y + ch, x : x + cw]
        ys = _peaks(hs.sum(axis=1) / 255, cw * 0.5, 6)
        xs = _peaks(vs.sum(axis=0) / 255, ch * 0.5, 6)
        if len(ys) < 3 or len(xs) < 2:
            continue  # need at least two rows and one column of cells
        grids.append(Grid(x, y, x + cw, y + ch, [x + v for v in xs], [y + v for v in ys]))
    grids.sort(key=lambda g: g.y0)
    return grids


def read_grid(gray: np.ndarray, grid: Grid, langs: str, psm: int = 6) -> list[list[str]]:
    """OCR the table area once and drop each word into the cell holding its centre."""
    pad = 6
    crop = gray[grid.y0 : grid.y1, grid.x0 : grid.x1].copy()
    # Paint the rules white so Tesseract does not read them as | or _.
    for x in grid.xs:
        cv2.rectangle(crop, (x - grid.x0 - pad, 0), (x - grid.x0 + pad, crop.shape[0]), 255, -1)
    for y in grid.ys:
        cv2.rectangle(crop, (0, y - grid.y0 - pad), (crop.shape[1], y - grid.y0 + pad), 255, -1)
    lines = ocr.run_tsv(crop, langs=langs, psm=psm)
    cells: list[list[list[ocr.Word]]] = [[[] for _ in range(grid.n_cols)] for _ in range(grid.n_rows)]
    for line in lines:
        for wd in line.words:
            cx = grid.x0 + wd.left + wd.width / 2
            cy = grid.y0 + wd.top + wd.height / 2
            r = next((i for i in range(grid.n_rows) if grid.ys[i] <= cy < grid.ys[i + 1]), None)
            c = next((j for j in range(grid.n_cols) if grid.xs[j] <= cx < grid.xs[j + 1]), None)
            if r is None or c is None:
                continue
            if not re.search(r"[\w஀-௿]", wd.text):
                continue  # leftover bits of a ruled line read as ~ or |
            cells[r][c].append(wd)
    rows = []
    for r in cells:
        row = []
        for words in r:
            ordered = [w.text for ln in ocr.group_words_into_lines(words) for w in ln]
            row.append(ocr.clean_text(" ".join(ordered)))
        rows.append(row)
    return rows


def blank_out(gray: np.ndarray, grids: list[Grid]) -> np.ndarray:
    out = gray.copy()
    for g in grids:
        cv2.rectangle(out, (g.x0 - 6, g.y0 - 6), (g.x1 + 6, g.y1 + 6), 255, -1)
    return out
