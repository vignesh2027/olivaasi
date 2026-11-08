"""Public demo of Olivaasi on Modal.

Deploy: modal deploy modal_app.py
URL:    https://applemacbook6sep2004--olivaasi.us-east.modal.run

One small container (half a CPU, 1 GB) that scales to zero when idle, so the first
visit after a quiet spell takes a few seconds longer. OLIVAASI_HOSTED=1 converts each
photo in a temporary folder under /dev/shm (RAM), returns one self-contained page and
deletes the folder before replying. Nothing is stored or logged. Speech uses eSpeak NG,
because the macOS voices do not exist on Linux.
"""

from pathlib import Path

import modal

HERE = Path(__file__).resolve().parent

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("tesseract-ocr", "espeak-ng", "ffmpeg", "libglib2.0-0")
    .pip_install("fastapi>=0.162.0", "jinja2>=3.1.6", "numpy>=2.5.4", "opencv-python-headless>=5.0.0.93",
                 "pillow>=13.0.0", "python-multipart>=0.0.33")
    .env({"OLIVAASI_HOSTED": "1", "OLIVAASI_TESSDATA": "/root/tessdata", "TMPDIR": "/dev/shm",
          "OLIVAASI_WORK": "/dev/shm/unused", "OMP_THREAD_LIMIT": "1"})
    .add_local_dir(str(HERE / "models" / "tessdata"), "/root/tessdata")
    .add_local_dir(str(HERE / "eval" / "images"), "/root/olivaasi/eval/images")
    .add_local_dir(str(HERE / "src" / "olivaasi"), "/root/olivaasi/src/olivaasi", ignore=["**/__pycache__"])
)

app = modal.App("olivaasi")


@app.function(image=image, cpu=0.5, memory=1024, min_containers=0, max_containers=1, scaledown_window=900, timeout=300)
@modal.concurrent(max_inputs=4)
@modal.asgi_app(label="olivaasi")
def web():
    import sys

    sys.path.insert(0, "/root/olivaasi/src")
    from olivaasi.server import app as fastapi_app

    return fastapi_app
