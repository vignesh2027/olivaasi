"""Turn a phone photo of a page into a flat, upright, evenly lit greyscale image."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class Prepared:
    gray: np.ndarray
    notes: list[str] = field(default_factory=list)


def load(path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)  # applies EXIF rotation
    if img is None:
        raise ValueError("The file could not be read as an image.")
    return img


def _order(pts: np.ndarray) -> np.ndarray:
    pts = pts.reshape(4, 2).astype(np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.float32([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]])


def find_page(img: np.ndarray) -> np.ndarray | None:
    """Corners of the paper if the photo shows a page on a darker surface."""
    h, w = img.shape[:2]
    scale = 1000 / max(h, w)
    small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (7, 7), 0)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(c)
    frac = area / (small.shape[0] * small.shape[1])
    if frac < 0.25 or frac > 0.97:
        return None  # no clear page edge, or the page already fills the frame
    peri = cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, 0.02 * peri, True)
    if len(approx) != 4:
        approx = cv2.boxPoints(cv2.minAreaRect(c))
    return _order(np.asarray(approx) / scale)


def warp(img: np.ndarray, quad: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = quad
    width = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    dst = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    m = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(img, m, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def flatten_light(gray: np.ndarray) -> np.ndarray:
    """Divide out uneven lighting so the paper becomes uniformly white."""
    k = max(31, (min(gray.shape) // 25) | 1)
    bg = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    bg = cv2.GaussianBlur(bg, (0, 0), k / 4)
    out = cv2.divide(gray, bg, scale=255)
    return out


def skew_angle(gray: np.ndarray) -> float:
    """Small rotation (degrees) that makes text rows horizontal, by projection profile."""
    scale = 800 / max(gray.shape)
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    _, ink = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    h, w = ink.shape
    centre = (w / 2, h / 2)
    best, best_score = 0.0, -1.0
    for a in np.arange(-6, 6.01, 0.25):
        m = cv2.getRotationMatrix2D(centre, a, 1.0)
        rot = cv2.warpAffine(ink, m, (w, h), flags=cv2.INTER_NEAREST)
        score = float(np.var(rot.sum(axis=1, dtype=np.float64)))
        if score > best_score:
            best, best_score = float(a), score
    return best


def rotate(gray: np.ndarray, angle: float) -> np.ndarray:
    h, w = gray.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(gray, m, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)


def prepare(img: np.ndarray) -> Prepared:
    notes: list[str] = []
    quad = find_page(img)
    if quad is not None:
        img = warp(img, quad)
        notes.append("Found the page edges and straightened the perspective.")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = flatten_light(gray)
    angle = skew_angle(gray)
    if abs(angle) >= 0.25:
        gray = rotate(gray, angle)
        notes.append(f"Rotated the text by {angle:.2f} degrees.")
    w = gray.shape[1]
    if w < 1800:
        f = 1800 / w
        gray = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
        notes.append("Enlarged a small image for better recognition.")
    elif w > 3200:
        f = 3200 / w
        gray = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    return Prepared(gray=gray, notes=notes)
