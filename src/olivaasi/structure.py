"""Rebuild headings, paragraphs, verse, numbered questions and tables from OCR lines."""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from .ocr import Line, clean_text

TAMIL = re.compile(r"[஀-௿]")
LATIN = re.compile(r"[A-Za-z]")
LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z'’\-]*(?:[ ,]+[A-Za-z][A-Za-z'’\-]*)*")
TAMIL_RUN = re.compile(r"[஀-௿]+(?:[ ,]+[஀-௿]+)*")

# "1.", "2)", "(3)", "௧.", "(அ)", "அ)", "a)", "(b)"
LABEL = re.compile(
    r"^(?:\(\s*(?P<p>\d{1,2}|[௧-௯௰]{1,2}|[a-hA-H]|[அஆஇஈஉஊஎஏ])\s*\)"
    r"|(?P<n>\d{1,2}|[௧-௯௰]{1,2})\s*[.)]"
    r"|(?P<l>[a-hA-H]|[அஆஇஈஉஊஎஏ])\s*\))\s*(?P<rest>\S.*)$"
)
ABBREV = re.compile(r"(?:\b(?:Mr|Mrs|Ms|Dr|St|Prof|etc|e\.g|i\.e|No|Fig)\.)$")


@dataclass
class Sentence:
    text: str
    lang: str
    id: int = 0

    def segments(self) -> list[tuple[str, str | None]]:
        """Split into runs whose language differs from the sentence (for lang="..." spans)."""
        return lang_segments(self.text, self.lang)


@dataclass
class ListItem:
    label: str
    sentences: list[Sentence]


@dataclass
class Block:
    kind: str  # heading, paragraph, verse, list, table, pagenum
    top: int = 0
    level: int = 0
    lang: str = "ta"
    sentences: list[Sentence] = field(default_factory=list)
    items: list[ListItem] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    row_sentences: list[Sentence] = field(default_factory=list)
    conf: float = 100.0
    height: int = 0  # text line height in pixels, used to rank headings
    lines: list[Line] = field(default_factory=list, repr=False)
    simple: list[Sentence] = field(default_factory=list)  # optional simplified reading of a paragraph

    def all_sentences(self) -> list[Sentence]:
        if self.kind == "list":
            return [s for it in self.items for s in it.sentences]
        if self.kind == "table":
            return list(self.row_sentences)
        return list(self.sentences)


@dataclass
class Document:
    blocks: list[Block]
    lang: str

    @property
    def title(self) -> str:
        for b in self.blocks:
            if b.kind == "heading":
                return " ".join(s.text for s in b.sentences)
        return "Converted page"

    def sentences(self) -> list[Sentence]:
        return [s for b in self.blocks for s in b.all_sentences()]

    def plain_text(self) -> str:
        """Reading-order text, used for accuracy measurement and the text download."""
        out: list[str] = []
        for b in self.blocks:
            if b.kind == "list":
                for it in b.items:
                    out.append(f"{it.label}. " + " ".join(s.text for s in it.sentences))
            elif b.kind == "table":
                for r in b.rows:
                    out.append(" ".join(c for c in r if c))
            else:
                out.append(" ".join(s.text for s in b.sentences))
        return "\n".join(out)


def detect_lang(text: str) -> str:
    ta = len(TAMIL.findall(text))
    en = len(LATIN.findall(text))
    return "en" if en > ta else "ta"


def lang_segments(text: str, base: str) -> list[tuple[str, str | None]]:
    pattern = LATIN_RUN if base == "ta" else TAMIL_RUN
    other = "en" if base == "ta" else "ta"
    out: list[tuple[str, str | None]] = []
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            out.append((text[pos : m.start()], None))
        out.append((m.group(0), other))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], None))
    return out or [(text, None)]


def split_sentences(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    parts: list[str] = []
    start = 0
    for m in re.finditer(r"[.?!](?=[\"'’”)]*\s+)", text):
        chunk = text[start : m.end()]
        if ABBREV.search(chunk) or re.search(r"(?:^|\s)\d{1,2}\.$", chunk):
            continue
        parts.append(chunk.strip())
        start = m.end()
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


def make_sentences(text: str, lang: str | None = None) -> list[Sentence]:
    return [Sentence(t, lang or detect_lang(t)) for t in split_sentences(text)]


def join_lines(texts: list[str]) -> str:
    out = ""
    for t in texts:
        if out.endswith("-") and t[:1].islower():
            out = out[:-1] + t  # rejoin an English word split across lines
        else:
            out = (out + " " + t).strip()
    return out


def _is_noise(line: Line) -> bool:
    t = line.text
    if not re.search(r"[\w஀-௿]", t):
        return True
    return line.conf < 30 and len(t) < 4


@dataclass
class _Page:
    body_h: float
    body_stroke: float
    col_left: int
    col_w: int

    def indented(self, ln: Line) -> bool:
        return ln.left - self.col_left > 0.03 * self.col_w

    def short(self, ln: Line) -> bool:
        return (ln.right - ln.left) < 0.75 * self.col_w

    def same_left(self, a: Line, b: Line) -> bool:
        return abs(a.left - b.left) <= 0.03 * self.col_w

    def is_heading(self, ln: Line) -> bool:
        t = ln.text
        if len(ln.words) > 10 or t.endswith((".", "?", ",", ";", ":")) or LABEL.match(t):
            return False
        # Thresholds from measured lines on 20 images (eval/): on degraded photos
        # bold headings are only 1.15 to 1.35 times the body stroke, while
        # short body lines stay below 1.07.
        tall = ln.height >= 1.2 * self.body_h
        bold = self.body_stroke > 0 and ln.stroke >= 1.12 * self.body_stroke
        return tall or bold


def build(lines: list[Line], tables: list[tuple[int, list[list[str]]]] | None = None, page_height: int = 0) -> Document:
    """Rebuild a document from OCR lines (in reading order) and already-read tables."""
    lines = [ln for ln in lines if not _is_noise(ln)]
    blocks: list[Block] = []
    if lines:
        body = [ln for ln in lines if len(ln.words) >= 4] or lines
        strokes = [ln.stroke for ln in body if ln.stroke > 0]
        page = _Page(
            body_h=statistics.median(ln.height for ln in body),
            body_stroke=statistics.median(strokes) if strokes else 0.0,
            col_left=min(ln.left for ln in lines),
            col_w=max(1, max(ln.right for ln in lines) - min(ln.left for ln in lines)),
        )
        groups: list[list[Line]] = []
        for ln in lines:
            if groups and (groups[-1][0].block, groups[-1][0].par) == (ln.block, ln.par):
                groups[-1].append(ln)
            else:
                groups.append([ln])
        for g in groups:
            run: list[Line] = []
            for ln in g:
                if page.is_heading(ln):
                    if run:
                        blocks.extend(_body_blocks(run, page))
                        run = []
                    lang = detect_lang(ln.text)
                    blocks.append(Block(kind="heading", top=ln.top, lang=lang, sentences=[Sentence(ln.text, lang)], conf=ln.conf, height=ln.height, lines=[ln]))
                else:
                    run.append(ln)
            if run:
                blocks.extend(_body_blocks(run, page))
        _merge_verse(blocks, page)
        _merge_paragraphs(blocks, page)
        _absorb_bare_numbers(blocks)
        _merge_lists(blocks)
        _page_number(blocks, page_height)
    for top, rows in tables or []:
        blocks.append(_table_block(top, rows))
    blocks.sort(key=lambda b: b.top)
    _assign_heading_levels(blocks)
    doc_lang = detect_lang(" ".join(s.text for b in blocks for s in b.all_sentences()))
    doc = Document(blocks=blocks, lang=doc_lang)
    for i, s in enumerate(doc.sentences(), 1):
        s.id = i
    return doc


def _paragraph(run: list[Line]) -> Block:
    text = join_lines([ln.text for ln in run])
    return Block(kind="paragraph", top=run[0].top, lang=detect_lang(text), sentences=make_sentences(text), conf=_conf(run), lines=list(run))


def _verse(run: list[Line]) -> Block:
    texts = [ln.text for ln in run]
    return Block(kind="verse", top=run[0].top, lang=detect_lang(" ".join(texts)), sentences=[Sentence(t, detect_lang(t)) for t in texts], conf=_conf(run), lines=list(run))


def _conf(run: list[Line]) -> float:
    return sum(ln.conf for ln in run) / len(run)


def _body_blocks(run: list[Line], page: _Page) -> list[Block]:
    """Turn consecutive non-heading lines of one Tesseract paragraph into blocks."""
    if any(LABEL.match(ln.text) for ln in run):
        out: list[Block] = []
        items: list[tuple[str, list[str], int]] = []
        lead: list[Line] = []
        for ln in run:
            m = LABEL.match(ln.text)
            if m:
                label = m.group("p") or m.group("n") or m.group("l")
                items.append((label, [m.group("rest")], ln.top))
            elif items:
                items[-1][1].append(ln.text)  # a question that wraps onto a second line
            else:
                lead.append(ln)
        if lead:
            out.extend(_body_blocks(lead, page))
        b = Block(kind="list", top=items[0][2], conf=_conf(run), lines=list(run))
        for label, texts, _ in items:
            b.items.append(ListItem(label=label, sentences=make_sentences(join_lines(texts))))
        b.lang = detect_lang(" ".join(s.text for s in b.all_sentences()))
        out.append(b)
        return out
    if len(run) >= 2 and all(page.short(ln) for ln in run):
        return [_verse(run)]
    return [_paragraph(run)]


def _verse_like(b: Block, page: _Page) -> bool:
    if b.kind == "verse":
        return True
    return b.kind == "paragraph" and len(b.lines) == 1 and page.short(b.lines[0]) and page.indented(b.lines[0])


def _merge_verse(blocks: list[Block], page: _Page) -> None:
    """Join verse lines that Tesseract split apart, then re-split into stanzas by vertical gaps."""
    i = 0
    while i < len(blocks):
        if not _verse_like(blocks[i], page):
            i += 1
            continue
        j = i + 1
        while j < len(blocks) and _verse_like(blocks[j], page) and page.same_left(blocks[j].lines[0], blocks[i].lines[0]):
            j += 1
        lines = sorted((ln for b in blocks[i:j] for ln in b.lines), key=lambda ln: ln.top)
        if len(lines) < 2:
            i = j
            continue
        gaps = [b.top - a.top for a, b in zip(lines, lines[1:])]
        pitch = statistics.median(gaps)
        stanzas: list[list[Line]] = [[lines[0]]]
        for gap, ln in zip(gaps, lines[1:]):
            if gap > 1.3 * pitch:
                stanzas.append([ln])
            else:
                stanzas[-1].append(ln)
        blocks[i:j] = [_verse(s) for s in stanzas]
        i += len(stanzas)


def _merge_paragraphs(blocks: list[Block], page: _Page) -> None:
    """Join a paragraph that Tesseract cut in two mid-sentence."""
    i = 0
    while i < len(blocks) - 1:
        a, b = blocks[i], blocks[i + 1]
        if (
            a.kind == "paragraph" and b.kind == "paragraph"
            and a.sentences and not a.sentences[-1].text.endswith((".", "?", "!", ":", ";", "”", '"'))
            and page.same_left(a.lines[0], b.lines[0])
            and b.lines[0].top - a.lines[-1].top < 2.2 * page.body_h
        ):
            blocks[i] = _paragraph(a.lines + b.lines)
            del blocks[i + 1]
        else:
            i += 1


BARE_NUMBER = re.compile(r"^(\d{1,2})\s+(\S.*)$")


def _absorb_bare_numbers(blocks: list[Block]) -> None:
    """A question whose full stop was lost ("2 What ...") joins the list it continues."""
    for i, b in enumerate(blocks):
        if b.kind != "paragraph":
            continue
        m = BARE_NUMBER.match(" ".join(s.text for s in b.sentences))
        if not m:
            continue
        n = int(m.group(1))
        prev = blocks[i - 1] if i > 0 else None
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        fits_prev = prev is not None and prev.kind == "list" and prev.items[-1].label == str(n - 1)
        fits_next = nxt is not None and nxt.kind == "list" and nxt.items[0].label == str(n + 1)
        if fits_prev or fits_next:
            b.kind = "list"
            b.items = [ListItem(label=str(n), sentences=make_sentences(m.group(2)))]
            b.sentences = []


def _merge_lists(blocks: list[Block]) -> None:
    i = 0
    while i < len(blocks) - 1:
        a, b = blocks[i], blocks[i + 1]
        if a.kind == "list" and b.kind == "list":
            a.items.extend(b.items)
            a.lines.extend(b.lines)
            del blocks[i + 1]
        else:
            i += 1
    for b in blocks:
        if b.kind == "list":
            _renumber(b)


TAMIL_DIGITS = set("\u0BE6\u0BE7\u0BE8\u0BE9\u0BEA\u0BEB\u0BEC\u0BED\u0BEE\u0BEF\u0BF0")


def _renumber(b: Block) -> None:
    """Fix question numbers misread as look-alike Tamil digits (a printed 2. read as ௨).

    Only when the numbers that were read as ordinary digits all agree with a
    simple 1, 2, 3 sequence; otherwise the labels are left exactly as read.
    """
    labels = [it.label for it in b.items]
    arabic = [(k, int(x)) for k, x in enumerate(labels) if x.isascii() and x.isdigit()]
    if not arabic or len(arabic) == len(labels):
        return
    start = arabic[0][1] - arabic[0][0]
    if any(n != start + k for k, n in arabic):
        return
    if not all(x.isascii() and x.isdigit() or set(x) <= TAMIL_DIGITS for x in labels):
        return
    for k, it in enumerate(b.items):
        it.label = str(start + k)


def _assign_heading_levels(blocks: list[Block]) -> None:
    """One h1 per page: the title if the page opens with a heading, else the tallest heading."""
    heads = [b for b in blocks if b.kind == "heading"]
    for h in heads:
        h.level = 2
    if not heads:
        return
    if blocks[0].kind == "heading":
        blocks[0].level = 1
    else:
        tallest = max(heads, key=lambda h: h.height)
        if all(tallest.height >= 1.15 * h.height for h in heads if h is not tallest):
            tallest.level = 1


def _page_number(blocks: list[Block], page_height: int) -> None:
    if not blocks or not page_height:
        return
    last = blocks[-1]
    if last.kind == "paragraph" and len(last.sentences) == 1 and re.fullmatch(r"\d{1,3}", last.sentences[0].text):
        if last.top > 0.85 * page_height:
            last.kind = "pagenum"


def _table_block(top: int, rows: list[list[str]]) -> Block:
    """A table, plus one spoken sentence per row ("Stage: Evaporation, What happens: ...")."""
    b = Block(kind="table", top=top, rows=rows)
    b.lang = detect_lang(" ".join(c for r in rows for c in r))
    if not rows:
        return b
    header = rows[0]
    if len(rows) > 1:
        b.row_sentences.append(Sentence(", ".join(c for c in header if c) + ".", detect_lang(" ".join(header))))
        for r in rows[1:]:
            spoken = ", ".join(f"{h}: {c}" if h else c for h, c in zip(header, r) if c)
            b.row_sentences.append(Sentence(spoken + ".", detect_lang(spoken)))
    else:
        spoken = ", ".join(c for c in header if c)
        b.row_sentences.append(Sentence(spoken + ".", detect_lang(spoken)))
    return b
