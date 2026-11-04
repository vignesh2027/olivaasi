"""Photo in, accessible HTML page and audio track out."""

from __future__ import annotations

import base64
import datetime as dt
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import __version__, config, ocr, preprocess, structure, tables, tts

_env = Environment(
    loader=FileSystemLoader(config.PACKAGE_DIR / "templates"),
    autoescape=select_autoescape(["html"]),
    trim_blocks=False,
)


@dataclass
class Result:
    doc: structure.Document
    out_dir: Path
    timings: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    audio_file: str | None = None
    confidence: float = 0.0


@dataclass
class _Reading:
    gray: object
    table_rows: list
    lines: list
    recovered: int
    tables_s: float
    ocr_s: float

    @property
    def score(self) -> float:
        """Confidently read characters: favours the version that recovers more text, more surely."""
        return sum(len(w.text) * max(w.conf, 0) / 100 for ln in self.lines for w in ln.words)


def _read(gray, langs: str) -> _Reading:
    t = time.perf_counter()
    grids = tables.find_grids(gray)
    table_rows = [(g.y0, tables.read_grid(gray, g, langs)) for g in grids]
    t2 = time.perf_counter()
    body = tables.blank_out(gray, grids)
    lines = ocr.run_tsv(body, langs=langs, psm=3)
    lines, recovered = ocr.recover_missed(body, lines, langs)
    ocr.add_strokes(gray, lines)
    return _Reading(gray, table_rows, lines, recovered, t2 - t, time.perf_counter() - t2)


def recognise(image, langs: str = "tam+eng") -> tuple[structure.Document, list[str], dict[str, float], float]:
    """Image (BGR array) to Document. Returns the document, notes, stage timings and mean confidence.

    If the text lines look curved, the page is read twice, as photographed and
    with the lines straightened, and the reading with more confidently
    recognised text is kept. Straightening helps a page bending into a book's
    spine but can hurt a flat one, and OCR confidence tells them apart better
    than any image measure we tried (see EVALUATION.md).
    """
    t0 = time.perf_counter()
    prepared = preprocess.prepare(image)
    t1 = time.perf_counter()
    reading = _read(prepared.gray, langs)
    straight, bend = preprocess.dewarp(prepared.gray)
    t_dewarp = 0.0
    if bend:
        td = time.perf_counter()
        other = _read(straight, langs)
        t_dewarp = time.perf_counter() - td
        if other.score > reading.score:
            reading = other
            prepared.notes.append(f"Straightened curved text lines (up to {bend:.0f} pixels).")
    if reading.recovered:
        prepared.notes.append(f"Read {reading.recovered} line(s) again that the first pass skipped.")
    t3 = time.perf_counter()
    doc = structure.build(reading.lines, reading.table_rows, page_height=reading.gray.shape[0])
    t4 = time.perf_counter()
    words = [w for ln in reading.lines for w in ln.words]
    conf = sum(w.conf for w in words) / len(words) if words else 0.0
    timings = {"clean_up": t1 - t0, "tables": reading.tables_s, "ocr": reading.ocr_s, "second_reading": t_dewarp, "structure": t4 - t3}
    return doc, prepared.notes, timings, conf


def speech_clips(doc: structure.Document) -> list[tuple[int, tts.Clip]]:
    """What to say for each sentence, in order. List items are read with their number."""
    out: list[tuple[int, tts.Clip]] = []
    for b in doc.blocks:
        end_pause = 700
        if b.kind == "list":
            for it in b.items:
                for k, s in enumerate(it.sentences):
                    text = f"{it.label}. {s.text}" if k == 0 else s.text
                    out.append((s.id, tts.Clip(text, s.lang, 500)))
        else:
            for s in b.all_sentences():
                out.append((s.id, tts.Clip(s.text, s.lang, 350)))
        if out:
            out[-1][1].pause_ms = end_pause
    return out


def render(doc: structure.Document, *, app_nav: bool, audio_file: str | None, timings: dict[int, tts.Timing],
           original_file: str | None, confidence: float, langs: str, notes: list[str], voice_note: str) -> str:
    static = config.PACKAGE_DIR / "static"
    return _env.get_template("document.html").render(
        doc=doc,
        has_h1=any(b.kind == "heading" and b.level == 1 for b in doc.blocks),
        app_nav=app_nav,
        audio_file=audio_file,
        timings=timings,
        original_file=original_file,
        confidence=confidence,
        langs_label=ocr.LANG_CHOICES.get(langs, langs),
        notes=notes,
        voice_note=voice_note,
        made_on=dt.date.today().isoformat(),
        version=__version__,
        css=(static / "doc.css").read_text(encoding="utf-8"),
        js=(static / "doc.js").read_text(encoding="utf-8"),
        logo_uri="data:image/svg+xml;base64," + base64.b64encode((static / "logo.svg").read_bytes()).decode(),
    )


def convert(image_path: Path, out_dir: Path, langs: str = "tam+eng", audio: bool = True) -> Result:
    """Run the whole pipeline and write index.html (standalone), view.html (with app links),
    audio.m4a or audio.wav, original.jpg, text.txt and doc.json into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    image = preprocess.load(image_path)
    doc, notes, stage, conf = recognise(image, langs)

    original = out_dir / "original.jpg"
    h, w = image.shape[:2]
    scale = min(1.0, 1600 / max(h, w))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else image
    cv2.imwrite(str(original), small, [cv2.IMWRITE_JPEG_QUALITY, 80])

    audio_file = None
    sent_timings: dict[int, tts.Timing] = {}
    voice_note = ""
    t = time.perf_counter()
    backend = tts.pick_backend() if audio else None
    if backend is not None and doc.sentences():
        clips = speech_clips(doc)
        path, times = tts.build_track([c for _, c in clips], out_dir, backend)
        sent_timings = {sid: tm for (sid, _), tm in zip(clips, times)}
        audio_file = path.name
        voices = sorted({backend.voice_for(c.lang) or "default" for _, c in clips})
        voice_note = f"{backend.name}, voice {', '.join(voices)}"
    elif audio:
        notes.append("No offline voice was found on this computer, so there is no audio track.")
    stage["audio"] = time.perf_counter() - t

    t = time.perf_counter()
    common = dict(audio_file=audio_file, timings=sent_timings, original_file=original.name,
                  confidence=conf, langs=langs, notes=notes, voice_note=voice_note)
    (out_dir / "index.html").write_text(render(doc, app_nav=False, **common), encoding="utf-8")
    (out_dir / "view.html").write_text(render(doc, app_nav=True, **common), encoding="utf-8")
    (out_dir / "text.txt").write_text(doc.plain_text() + "\n", encoding="utf-8")
    stage["render"] = time.perf_counter() - t
    stage["total"] = time.perf_counter() - start
    meta = {
        "title": doc.title,
        "lang": doc.lang,
        "langs": langs,
        "made": dt.datetime.now().isoformat(timespec="seconds"),
        "confidence": round(conf, 1),
        "seconds": {k: round(v, 3) for k, v in stage.items()},
        "notes": notes,
        "audio": audio_file,
        "blocks": [_block_json(b) for b in doc.blocks],
    }
    (out_dir / "doc.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return Result(doc=doc, out_dir=out_dir, timings=stage, notes=notes, audio_file=audio_file, confidence=conf)


def _block_json(b: structure.Block) -> dict:
    d = {"kind": b.kind, "lang": b.lang}
    if b.kind == "heading":
        d["level"] = b.level
    if b.kind == "list":
        d["items"] = [{"label": it.label, "text": " ".join(s.text for s in it.sentences)} for it in b.items]
    elif b.kind == "table":
        d["rows"] = b.rows
    else:
        d["sentences"] = [s.text for s in b.sentences]
    return d


def copy_input(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"input{src.suffix.lower() or '.jpg'}"
    shutil.copyfile(src, dst)
    return dst

