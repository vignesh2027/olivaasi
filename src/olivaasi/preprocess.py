"""Turn a phone photo of a page into a flat, upright, evenly lit greyscale image."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


DEWARP_GAIN = 1.01  # keep a dewarp only if text rows get at least this much sharper
MIN_WIDTH = 1000  # enlarge only very small pages; enlarging blurred photos made Tesseract drop lines (see EVALUATION.md)


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
    pts = pts.reshape(-1, 2).astype(np.float32)  # any number of points; picks the four extremes
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.float32([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]])


def _quad_from_contour(c: np.ndarray) -> np.ndarray | None:
    """Four corners from a page outline, via its convex hull."""
    hull = cv2.convexHull(c)
    peri = cv2.arcLength(hull, True)
    for eps in (0.02, 0.03, 0.04, 0.05):
        approx = cv2.approxPolyDP(hull, eps * peri, True)
        if len(approx) == 4:
            return _order(approx)
    return None


def find_page(img: np.ndarray) -> np.ndarray | None:
    """Corners of the paper if the photo shows a page on a different-looking surface.

    First from edges: the border between paper and desk stays sharp even where
    a shadow darkens the paper. If that gives no clean outline, fall back to a
    brightness threshold. Returns None when the page already fills the frame
    or no page outline is found, and the photo is then used as it is.
    """
    h, w = img.shape[:2]
    scale = 1000 / max(h, w)
    small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (7, 7), 0)
    area_all = small.shape[0] * small.shape[1]

    edges = cv2.Canny(gray, 20, 60)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8))
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    for mask in (edges, bw):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        c = max(contours, key=lambda c: cv2.contourArea(cv2.convexHull(c)))
        frac = cv2.contourArea(cv2.convexHull(c)) / area_all
        if frac < 0.25 or frac > 0.97:
            continue
        quad = _quad_from_contour(c)
        if quad is not None and cv2.contourArea(quad) / area_all > 0.25:
            return quad / scale
    return None


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


def letter_mask(gray: np.ndarray) -> np.ndarray:
    """Ink that looks like letters: drops page edges, shadows, rules and big blobs."""
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    h, w = ink.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    x, y, cw, ch = stats[:, 0], stats[:, 1], stats[:, 2], stats[:, 3]
    keep = (x > 0) & (y > 0) & (x + cw < w) & (y + ch < h) & (cw < 0.1 * w) & (ch < 0.06 * h)
    keep[0] = False
    return np.where(keep[labels], 255, 0).astype(np.uint8)


def skew_angle(gray: np.ndarray) -> float:
    """Small rotation (degrees) that makes text rows horizontal, by projection profile.

    Only letter-sized marks are used, so page edges and table rules cannot
    pull the estimate. The rotation is kept only if it clearly beats leaving
    the page as it is.
    """
    scale = min(1.0, 1000 / max(gray.shape))
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ink = letter_mask(small)
    h, w = ink.shape
    centre = (w / 2, h / 2)

    def score(a: float) -> float:
        m = cv2.getRotationMatrix2D(centre, a, 1.0)
        rot = cv2.warpAffine(ink, m, (w, h), flags=cv2.INTER_NEAREST)
        return float(np.var(rot.sum(axis=1, dtype=np.float64)))

    base = score(0.0)
    best, best_score = 0.0, base
    for a in np.arange(-6, 6.01, 0.25):
        s = score(float(a))
        if s > best_score:
            best, best_score = float(a), s
    return best if best_score > 1.10 * base else 0.0


def _row_sharpness(ink: np.ndarray) -> float:
    return float(np.var(ink.sum(axis=1, dtype=np.float64)))


def dewarp(gray: np.ndarray) -> tuple[np.ndarray, float]:
    """Straighten text lines that bend, as on a page curving into a book's spine.

    The page is cut into vertical strips and horizontal bands. In each band,
    each strip's row profile is matched against its neighbour's to find how
    far its text lines are shifted up or down; the shifts become a smooth
    vertical displacement field that is undone with a remap. The result is
    kept only if the text rows get clearly sharper. Returns the image and the
    largest correction in pixels (0 when nothing was changed).
    """
    h, w = gray.shape
    scale = min(1.0, 1000 / max(h, w))
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ink = (letter_mask(small) > 0).astype(np.float32)
    sh, sw = ink.shape
    nx, ny, reach = 12, 6, 8
    xs = np.linspace(0, sw, nx + 1).astype(int)
    ys = np.linspace(0, sh, ny + 1).astype(int)
    dy = np.full((ny, nx), np.nan, np.float32)
    for j in range(ny):
        y0, y1 = max(0, ys[j] - reach), min(sh, ys[j + 1] + reach)
        profs = [cv2.GaussianBlur(ink[y0:y1, xs[i] : xs[i + 1]].sum(axis=1).reshape(-1, 1), (1, 5), 1.5).ravel() for i in range(nx)]
        has = [p.sum() > 0.02 * (y1 - y0) * (xs[1] - xs[0]) for p in profs]
        filled = [i for i in range(nx) if has[i]]
        if len(filled) < 3:
            continue
        c = filled[len(filled) // 2]
        dy[j, c] = 0.0
        for order in (range(c + 1, nx), range(c - 1, -1, -1)):
            prev = c
            for i in order:
                if not has[i]:
                    continue
                a, b = profs[prev], profs[i]
                best, best_s = -1.0, 0
                for sft in range(-reach, reach + 1):
                    if sft >= 0:
                        v = float(np.dot(a[: len(a) - sft], b[sft:]))
                    else:
                        v = float(np.dot(a[-sft:], b[: len(b) + sft]))
                    if v > best:
                        best, best_s = v, sft
                dy[j, i] = dy[j, prev] + best_s
                prev = i
    if np.isnan(dy).all():
        return gray, 0.0
    for j in range(ny):  # fill strips without text from their neighbours
        row = dy[j]
        known = np.nonzero(~np.isnan(row))[0]
        if len(known):
            dy[j] = np.interp(np.arange(nx), known, row[known])
    for i in range(nx):
        col = dy[:, i]
        known = np.nonzero(~np.isnan(col))[0]
        dy[:, i] = np.interp(np.arange(ny), known, col[known]) if len(known) else 0
    dy -= np.median(dy)
    if np.abs(dy).max() < 1.0:
        return gray, 0.0
    field_small = cv2.resize(cv2.GaussianBlur(dy, (3, 3), 0.8), (sw, sh), interpolation=cv2.INTER_CUBIC)
    gx, gy = np.meshgrid(np.arange(sw, dtype=np.float32), np.arange(sh, dtype=np.float32))
    test = cv2.remap(ink, gx, gy + field_small, cv2.INTER_LINEAR, borderValue=0)
    if _row_sharpness(test) < DEWARP_GAIN * _row_sharpness(ink):
        return gray, 0.0
    field = cv2.resize(field_small, (w, h), interpolation=cv2.INTER_CUBIC) / scale
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    out = cv2.remap(gray, gx, gy + field, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return out, float(np.abs(field).max())


def rotate(gray: np.ndarray, angle: float) -> np.ndarray:
    h, w = gray.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(gray, m, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)


def prepare(img: np.ndarray) -> Prepared:
    notes: list[str] = []
    quad = find_page(img)
    if quad is not None:
        img = warp(img, quad)
        # The outline sits on the paper's edge; trim a thin strip so no desk
        # remains along the borders to be mistaken for ruled lines.
        h, w = img.shape[:2]
        dy, dx = int(0.012 * h), int(0.012 * w)
        img = img[dy : h - dy, dx : w - dx]
        notes.append("Found the page edges and straightened the perspective.")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = flatten_light(gray)
    angle = skew_angle(gray)
    if abs(angle) >= 0.25:
        gray = rotate(gray, angle)
        notes.append(f"Rotated the text by {angle:.2f} degrees.")
    w = gray.shape[1]
    if w < MIN_WIDTH:
        f = MIN_WIDTH / w
        gray = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
        notes.append("Enlarged a small image for better recognition.")
    elif w > 3200:
        f = 3200 / w
        gray = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    return Prepared(gray=gray, notes=notes)
