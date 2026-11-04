"""Local web app. Binds to 127.0.0.1 by default and makes no outside requests."""

from __future__ import annotations

import io
import json
import secrets
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from . import __version__, config, ocr, pipeline

MAX_BYTES = 15 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/tiff": ".tif", "image/bmp": ".bmp"}
SAMPLES = {
    "ta_water_photo": ("Tamil science lesson, phone photo", "ta"),
    "ta_kural_photo": ("Tamil Thirukkural lesson, phone photo", "ta"),
    "en_water_photo": ("English science lesson, phone photo", "en"),
    "en_daffodils_photo": ("English poem lesson, phone photo", "en"),
}

app = FastAPI(title="Padi", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=config.PACKAGE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=config.PACKAGE_DIR / "templates")


def sample_path(key: str) -> Path | None:
    for ext in (".jpg", ".png"):
        p = config.REPO_DIR / "eval" / "images" / f"{key}{ext}"
        if p.exists():
            return p
    return None


def recent(limit: int = 8) -> list[dict]:
    out = []
    for d in config.work_dir().iterdir():
        meta = d / "doc.json"
        if d.is_dir() and meta.exists():
            m = json.loads(meta.read_text(encoding="utf-8"))
            out.append({"id": d.name, "title": m["title"], "lang": m["lang"], "made": m["made"], "mtime": meta.stat().st_mtime})
    out.sort(key=lambda r: r["mtime"], reverse=True)
    return out[:limit]


def page(request: Request, *, error: str | None = None, status: int = 200, lang: str = "tam+eng"):
    samples = [{"key": k, "label": v[0], "lang": v[1]} for k, v in SAMPLES.items() if sample_path(k)]
    return templates.TemplateResponse(
        request,
        "index.html",
        {"error": error, "langs": ocr.LANG_CHOICES, "lang": lang, "samples": samples, "recent": recent(), "version": __version__},
        status_code=status,
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return page(request)


async def _convert(src: Path, doc_dir: Path, lang: str, audio: bool) -> RedirectResponse:
    await run_in_threadpool(pipeline.convert, src, doc_dir, lang, audio)
    return RedirectResponse(f"/doc/{doc_dir.name}/", status_code=303)


@app.post("/convert")
async def convert(request: Request, photo: UploadFile = File(None), lang: str = Form("tam+eng"), audio: str | None = Form(None)):
    if lang not in ocr.LANG_CHOICES:
        lang = "tam+eng"
    if photo is None or not photo.filename:
        return page(request, error="Choose a photo of the page first.", status=400, lang=lang)
    data = await photo.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        return page(request, error="That photo is larger than 15 MB. Take it again at a lower resolution, or crop it.", status=413, lang=lang)
    ext = IMAGE_TYPES.get(photo.content_type or "")
    if ext is None:
        return page(request, error="That file is not a photo Padi can read. Use a JPG or PNG image.", status=415, lang=lang)
    doc_dir = config.work_dir() / secrets.token_hex(6)
    doc_dir.mkdir()
    src = doc_dir / f"input{ext}"
    src.write_bytes(data)
    try:
        return await _convert(src, doc_dir, lang, audio is not None)
    except ValueError:
        return page(request, error="That file could not be opened as an image. Try another photo.", status=400, lang=lang)


@app.post("/sample")
async def sample(request: Request, key: str = Form(...), audio: str | None = Form(None)):
    src = sample_path(key) if key in SAMPLES else None
    if src is None:
        return page(request, error="That sample page is missing.", status=404)
    lang = "tam+eng"
    doc_dir = config.work_dir() / secrets.token_hex(6)
    return await _convert(src, doc_dir, lang, audio is not None)


def _doc_dir(doc_id: str) -> Path:
    if not (len(doc_id) == 12 and all(c in "0123456789abcdef" for c in doc_id)):
        raise HTTPException(404)
    d = config.work_dir() / doc_id
    if not (d / "view.html").exists():
        raise HTTPException(404)
    return d


@app.get("/doc/{doc_id}")
def doc_no_slash(doc_id: str):
    _doc_dir(doc_id)
    return RedirectResponse(f"/doc/{doc_id}/", status_code=307)


@app.get("/doc/{doc_id}/", response_class=HTMLResponse)
def doc_view(doc_id: str):
    return FileResponse(_doc_dir(doc_id) / "view.html", media_type="text/html; charset=utf-8")


@app.get("/doc/{doc_id}/download")
def doc_download(doc_id: str):
    d = _doc_dir(doc_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ("index.html", "audio.m4a", "audio.wav", "original.jpg", "text.txt"):
            if (d / name).exists():
                z.write(d / name, f"padi-{doc_id}/{name}")
    buf.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="padi-{doc_id}.zip"'}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)


@app.get("/doc/{doc_id}/{name}")
def doc_file(doc_id: str, name: str):
    d = _doc_dir(doc_id)
    if name not in {"audio.m4a", "audio.wav", "original.jpg", "text.txt", "index.html"}:
        raise HTTPException(404)
    path = d / name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)
