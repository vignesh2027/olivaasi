from padi.ocr import Line, Word, clean_text, group_words_into_lines, parse_tsv
from padi.structure import build, detect_lang, lang_segments, split_sentences


def line(text, top, left=100, height=30, block=1, par=1, stroke=3.0, width=None):
    words = text.split()
    w = width or 18 * len(text)
    step = w // max(1, len(words))
    ln = Line(block=block, par=par, stroke=stroke)
    for i, t in enumerate(words):
        ln.words.append(Word(t, left + i * step, top, step - 6, height, 95.0))
    return ln


BODY = 1600  # a full-width body line


def test_clean_text_removes_zero_width_non_joiner():
    assert clean_text("பாடம்‌ 3  திருக்குறள்‌") == "பாடம் 3 திருக்குறள்"


def test_detect_lang_and_segments():
    assert detect_lang("இதற்கு ஆவியாதல் (Evaporation) என்று பெயர்.") == "ta"
    assert detect_lang("What is evaporation?") == "en"
    segs = lang_segments("இதற்கு ஆவியாதல் (Evaporation) என்று பெயர்.", "ta")
    assert ("Evaporation", "en") in segs
    assert "".join(t for t, _ in segs) == "இதற்கு ஆவியாதல் (Evaporation) என்று பெயர்."


def test_split_sentences_keeps_numbers_and_abbreviations():
    assert split_sentences("This is one. Mr. Raman came. Is it two?") == ["This is one.", "Mr. Raman came.", "Is it two?"]
    assert split_sentences("பாடம் 3 திருக்குறள்") == ["பாடம் 3 திருக்குறள்"]


def test_headings_by_size_and_by_boldness():
    lines = [
        line("அலகு 5 நீர்ச் சுழற்சி", 50, height=60, block=1, stroke=5),
        line("பூமியில் உள்ள நீர் ஓர் இடத்தில் நிலையாக இருப்பதில்லை. கடல் ஆறு ஏரி", 150, block=2, width=BODY),
        line("ஆகியவற்றில் உள்ள நீர் மேலே செல்கிறது.", 190, block=2, width=900),
        line("மேகங்கள் உருவாதல்", 260, height=32, block=3, stroke=5.2),  # bold, same size
        line("மேலே சென்ற நீராவி குளிர்ந்து சிறு நீர்த்துளிகளாக மாறுகிறது. பல நீர்த்துளிகள்", 320, block=4, width=BODY),
        line("சேர்ந்து மேகங்கள் உருவாகின்றன.", 360, block=4, width=700),
    ]
    doc = build(lines)
    kinds = [(b.kind, b.level) for b in doc.blocks]
    assert kinds == [("heading", 1), ("paragraph", 0), ("heading", 2), ("paragraph", 0)]
    assert doc.title == "அலகு 5 நீர்ச் சுழற்சி"


def test_numbered_questions_become_one_list_with_wrapped_lines():
    lines = [
        line("Read the lesson carefully and answer every question in full sentences please.", 50, width=BODY, block=1),
        line("1. What is evaporation?", 120, block=2, par=1),
        line("2. How are clouds formed in the sky above the sea when", 160, block=2, par=2, width=1100),
        line("the air is cold?", 200, block=2, par=2),
        line("(அ) ஆவியாதல் என்றால் என்ன?", 240, block=2, par=3),
    ]
    doc = build(lines)
    lists = [b for b in doc.blocks if b.kind == "list"]
    assert len(lists) == 1
    items = lists[0].items
    assert [i.label for i in items] == ["1", "2", "அ"]
    assert items[1].sentences[0].text == "How are clouds formed in the sky above the sea when the air is cold?"


def test_verse_fragments_are_merged_then_split_into_stanzas():
    lines = [
        line("Body text runs across the full width of the page so the column is known.", 20, left=100, width=BODY, block=1),
        line("I wandered lonely as a cloud", 100, left=200, block=2, par=1),
        line("That floats on high o'er vales and hills,", 150, left=200, block=2, par=2),
        line("When all at once I saw a crowd,", 200, left=200, block=2, par=2),
        line("A host, of golden daffodils;", 300, left=200, block=2, par=3),  # bigger gap: new stanza
        line("Beside the lake, beneath the trees,", 350, left=200, block=2, par=3),
    ]
    doc = build(lines)
    verses = [b for b in doc.blocks if b.kind == "verse"]
    assert [len(v.sentences) for v in verses] == [3, 2]


def test_paragraph_cut_mid_sentence_is_rejoined():
    lines = [
        line("Water on the Earth does not stay in one place. The heat of the Sun turns water", 100, width=BODY, block=1),
        line("in seas into vapour.", 140, block=2),
    ]
    doc = build(lines)
    assert [b.kind for b in doc.blocks] == ["paragraph"]
    assert doc.blocks[0].sentences[-1].text == "The heat of the Sun turns water in seas into vapour."


def test_table_rows_are_spoken_with_headers():
    doc = build([], tables=[(10, [["Stage", "What happens"], ["Evaporation", "Water turns into vapour"]])])
    t = doc.blocks[0]
    assert t.kind == "table"
    assert [s.text for s in t.row_sentences] == ["Stage, What happens.", "Stage: Evaporation, What happens: Water turns into vapour."]
    assert [s.id for s in doc.sentences()] == [1, 2]


def test_group_words_into_lines_orders_by_row_then_x():
    words = [Word("number", 60, 2, 50, 20, 90), Word("a", 0, 6, 10, 14, 90), Word("large", 15, 0, 40, 22, 90), Word("next", 0, 40, 30, 20, 90)]
    assert [[w.text for w in ln] for ln in group_words_into_lines(words)] == [["a", "large", "number"], ["next"]]


def test_parse_tsv_skips_empty_words():
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t10\t10\t50\t20\t96.0\tபாடம்‌\n"
        "5\t1\t1\t1\t1\t2\t70\t10\t20\t20\t95.0\t3\n"
        "5\t1\t1\t1\t1\t3\t95\t10\t20\t20\t-1\t \n"
    )
    lines = parse_tsv(tsv)
    assert len(lines) == 1 and lines[0].text == "பாடம் 3"
