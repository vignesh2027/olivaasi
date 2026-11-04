"""Measure Padi on the evaluation pages.

For every page in eval/pages/*.json and both images of it (a clean scan and a
simulated phone photo) this reports:

  * character error rate (CER) and word error rate (WER) of plain Tesseract
    (the baseline: the same engine and models with no clean-up or structure)
    and of Padi, both against the typeset ground truth, in reading order;
  * structure recovered: headings (text and level), numbered questions,
    table cells, verse lines, and the block sequence;
  * time per stage, median of several runs, and the speech time per page.

    uv run python eval/run_eval.py [--runs 3] [--no-audio]

Writes eval/results.md and eval/results.json.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from padi import config, ocr, pipeline, preprocess, structure, tts  # noqa: E402


def norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("‌", "").replace("‍", "")
    return " ".join(text.split())


def lev(a, b) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(ref: str, hyp: str) -> float:
    ref, hyp = norm(ref), norm(hyp)
    return lev(ref, hyp) / max(1, len(ref))


def wer(ref: str, hyp: str) -> float:
    r, h = norm(ref).split(), norm(hyp).split()
    return lev(r, h) / max(1, len(r))


def truth_text(spec: dict) -> str:
    out = []
    for b in spec["blocks"]:
        t = b["type"]
        if t in ("h1", "h2", "p"):
            out.append(b["text"])
        elif t == "verse":
            out.append(" ".join(b["lines"]))
        elif t == "table":
            out += [" ".join(r) for r in b["rows"]]
        elif t == "ol":
            out += [f"{i}. {x}" for i, x in enumerate(b["items"], 1)]
    return "\n".join(out)


def kinds_truth(spec: dict) -> list[str]:
    m = {"h1": "h1", "h2": "h2", "p": "paragraph", "verse": "verse", "table": "table", "ol": "list"}
    return [m[b["type"]] for b in spec["blocks"]]


def kinds_doc(doc: structure.Document) -> list[str]:
    return [f"h{b.level}" if b.kind == "heading" else b.kind for b in doc.blocks]


def structure_scores(spec: dict, doc: structure.Document) -> dict:
    gt_heads = [(b["type"], b["text"]) for b in spec["blocks"] if b["type"] in ("h1", "h2")]
    got_heads = [(f"h{b.level}", " ".join(s.text for s in b.sentences)) for b in doc.blocks if b.kind == "heading"]
    heads_ok = sum(1 for lvl, txt in gt_heads if any(l2 == lvl and cer(txt, t2) < 0.15 for l2, t2 in got_heads))

    gt_items = [x for b in spec["blocks"] if b["type"] == "ol" for x in b["items"]]
    got_items = [(it.label, " ".join(s.text for s in it.sentences)) for b in doc.blocks if b.kind == "list" for it in b.items]
    items_ok = sum(1 for i, x in enumerate(gt_items, 1) if any(lbl == str(i) and cer(x, t) < 0.15 for lbl, t in got_items))

    gt_cells = [c for b in spec["blocks"] if b["type"] == "table" for r in b["rows"] for c in r]
    got_tables = [b.rows for b in doc.blocks if b.kind == "table"]
    gt_tables = [b["rows"] for b in spec["blocks"] if b["type"] == "table"]
    cells_ok = 0
    for gt, got in zip(gt_tables, got_tables):
        for r, row in enumerate(gt):
            for c, cell in enumerate(row):
                if r < len(got) and c < len(got[r]) and norm(got[r][c]) == norm(cell):
                    cells_ok += 1

    gt_verse = [ln for b in spec["blocks"] if b["type"] == "verse" for ln in b["lines"]]
    got_verse = [s.text for b in doc.blocks if b.kind == "verse" for s in b.sentences]
    verse_ok = sum(1 for ln in gt_verse if any(cer(ln, g) < 0.15 for g in got_verse))

    kt, kd = kinds_truth(spec), kinds_doc(doc)
    seq = 1 - lev(kt, kd) / max(1, len(kt))
    return {
        "headings": [heads_ok, len(gt_heads)],
        "questions": [items_ok, len(gt_items)],
        "table_cells": [cells_ok, len(gt_cells)],
        "verse_lines": [verse_ok, len(gt_verse)],
        "block_sequence": round(seq, 3),
        "kinds_truth": kt,
        "kinds_found": kd,
    }


def raw_tesseract(path: Path, langs: str) -> tuple[str, float]:
    cmd = [config.tesseract_bin(), str(path), "stdout", "-l", langs, "--psm", "3"]
    td = config.tessdata_dir()
    if td:
        cmd += ["--tessdata-dir", str(td)]
    t = time.perf_counter()
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8").stdout
    return ocr.clean_text(out), time.perf_counter() - t


def machine() -> str:
    try:
        chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
        mem = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) // 2**30
        return f"{chip}, {mem} GB RAM, macOS {platform.mac_ver()[0]}"
    except (OSError, ValueError):
        return platform.platform()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--langs", default="tam+eng")
    args = ap.parse_args()

    tess = subprocess.run([config.tesseract_bin(), "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    rows = []
    for spec_path in sorted((ROOT / "eval" / "pages").glob("*.json")):
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        truth = truth_text(spec)
        for variant, ext in (("scan", ".png"), ("photo", ".jpg")):
            img_path = ROOT / "eval" / "images" / f"{spec['id']}_{variant}{ext}"
            raw, raw_secs = raw_tesseract(img_path, args.langs)
            image = preprocess.load(img_path)
            stage_runs = []
            for _ in range(args.runs):
                doc, _notes, stages, conf = pipeline.recognise(image, args.langs)
                stage_runs.append(stages)
            stages = {k: statistics.median(r[k] for r in stage_runs) for k in stage_runs[0]}
            row = {
                "page": spec["id"],
                "lang": spec["lang"],
                "variant": variant,
                "chars": len(norm(truth)),
                "raw_cer": round(cer(truth, raw), 4),
                "raw_wer": round(wer(truth, raw), 4),
                "padi_cer": round(cer(truth, doc.plain_text()), 4),
                "padi_wer": round(wer(truth, doc.plain_text()), 4),
                "confidence": round(conf, 1),
                "raw_seconds": round(raw_secs, 2),
                "seconds": {k: round(v, 2) for k, v in stages.items()},
                "recognise_seconds": round(sum(stages.values()), 2),
                "structure": structure_scores(spec, doc),
                "sentences": len(doc.sentences()),
            }
            if not args.no_audio and variant == "photo":
                backend = tts.pick_backend()
                if backend:
                    clips = [c for _, c in pipeline.speech_clips(doc)]
                    with tempfile.TemporaryDirectory() as d:
                        t = time.perf_counter()
                        _, timings = tts.build_track(clips, Path(d), backend)
                        row["audio_seconds"] = round(time.perf_counter() - t, 2)
                        row["audio_length"] = round(timings[-1].end, 1) if timings else 0
                        row["voice"] = backend.name
            rows.append(row)
            print(f"{spec['id']:13s} {variant:5s} raw CER {row['raw_cer']:.3f}  Padi CER {row['padi_cer']:.3f}  "
                  f"recognise {row['recognise_seconds']:.1f}s  audio {row.get('audio_seconds', '-')}s  {row['structure']['kinds_found']}")
    result = {"machine": machine(), "tesseract": tess, "tessdata": str(config.tessdata_dir() or "system"), "langs": args.langs, "runs": args.runs, "rows": rows}
    (ROOT / "eval" / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "eval" / "results.md").write_text(to_markdown(result), encoding="utf-8")
    print("wrote eval/results.md")
    return 0


def frac(p: list[int]) -> str:
    return f"{p[0]}/{p[1]}" if p[1] else "n/a"


def to_markdown(r: dict) -> str:
    lines = [
        "# Evaluation results",
        "",
        "Generated by `uv run python eval/run_eval.py`. Do not edit by hand.",
        "",
        f"* Machine: {r['machine']}",
        f"* OCR: {r['tesseract']}, models from `{Path(r['tessdata']).name}` (tessdata_best), languages `{r['langs']}`",
        f"* Timings are the median of {r['runs']} runs.",
        "",
        "## Text accuracy (lower is better)",
        "",
        "CER is character error rate (edits per ground-truth character, in Unicode code points); WER is word error rate. "
        "Both compare the whole page in reading order, so text that is lost or put in the wrong order counts as error.",
        "",
        "| Page | Image | Characters | Plain Tesseract CER | Padi CER | Plain Tesseract WER | Padi WER |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for x in r["rows"]:
        lines.append(f"| {x['page']} | {x['variant']} | {x['chars']} | {x['raw_cer']:.1%} | {x['padi_cer']:.1%} | {x['raw_wer']:.1%} | {x['padi_wer']:.1%} |")
    for lang, name in (("ta", "Tamil"), ("en", "English")):
        for v in ("scan", "photo"):
            sel = [x for x in r["rows"] if x["lang"] == lang and x["variant"] == v]
            if sel:
                tot = sum(x["chars"] for x in sel)
                raw = sum(x["raw_cer"] * x["chars"] for x in sel) / tot
                padi = sum(x["padi_cer"] * x["chars"] for x in sel) / tot
                lines.append(f"| **{name}, all {v}s** | {v} | {tot} | **{raw:.1%}** | **{padi:.1%}** | | |")
    lines += [
        "",
        "## Structure recovered",
        "",
        "| Page | Image | Headings (text and level) | Questions | Table cells exact | Verse lines | Block sequence |",
        "|---|---|---|---|---|---|---:|",
    ]
    for x in r["rows"]:
        s = x["structure"]
        lines.append(f"| {x['page']} | {x['variant']} | {frac(s['headings'])} | {frac(s['questions'])} | {frac(s['table_cells'])} | {frac(s['verse_lines'])} | {s['block_sequence']:.0%} |")
    lines += [
        "",
        "## Time per page",
        "",
        "| Page | Image | Clean-up | Tables | OCR | Structure | Recognition total | Speech (sentences, audio length) |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for x in r["rows"]:
        s = x["seconds"]
        speech = f"{x['audio_seconds']:.1f} s ({x['sentences']} sentences, {x['audio_length']:.0f} s of audio)" if "audio_seconds" in x else ""
        lines.append(f"| {x['page']} | {x['variant']} | {s['clean_up']:.2f} s | {s['tables']:.2f} s | {s['ocr']:.2f} s | {s['structure']:.2f} s | {x['recognise_seconds']:.1f} s | {speech} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
