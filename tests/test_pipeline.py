import io
import re
import zipfile

from fastapi.testclient import TestClient

from conftest import needs_ocr
from olivaasi import pipeline


@needs_ocr
def test_convert_tamil_photo_to_accessible_page(work, sample_image):
    out = work / "out"
    r = pipeline.convert(sample_image, out, audio=False)
    html = (out / "index.html").read_text(encoding="utf-8")
    assert html.count("<h1") == 1
    assert '<article lang="ta">' in html
    assert '<span lang="en">Evaporation</span>' in html
    questions = re.search(r'<ol class="questions".*?</ol>', html, re.S).group(0)
    assert len(re.findall(r"<li>", questions)) == 4
    assert '<th scope="col">நிலை</th>' in html
    assert "<audio" not in html  # audio was switched off
    assert r.doc.title == "அலகு 5 நீர்ச் சுழற்சி"
    # The output must work offline: nothing is loaded from another host.
    assert not re.search(r'(src|href)="(https?:)?//', html)
    assert (out / "text.txt").read_text(encoding="utf-8").startswith("அலகு 5")


@needs_ocr
def test_server_flow(work, sample_image):
    from olivaasi.server import app

    c = TestClient(app)
    assert c.get("/").status_code == 200

    r = c.post("/convert", data={"lang": "tam"})
    assert r.status_code == 400 and 'role="alert"' in r.text and 'aria-invalid="true"' in r.text

    r = c.post("/convert", files={"photo": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 415

    r = c.post("/convert", files={"photo": ("broken.jpg", b"not really a jpeg", "image/jpeg")})
    assert r.status_code == 400

    with open(sample_image, "rb") as f:
        r = c.post("/convert", files={"photo": ("page.jpg", f, "image/jpeg")}, data={"lang": "tam+eng"}, follow_redirects=False)
    assert r.status_code == 303
    url = r.headers["location"]
    page = c.get(url)
    assert page.status_code == 200 and "நீர்ச் சுழற்சி" in page.text and "Convert another page" in page.text

    z = zipfile.ZipFile(io.BytesIO(c.get(url + "download").content))
    names = z.namelist()
    assert any(n.endswith("/index.html") for n in names) and any(n.endswith("/original.jpg") for n in names)
    assert "Convert another page" not in z.read([n for n in names if n.endswith("index.html")][0]).decode()

    assert c.get("/doc/../../etc/passwd").status_code == 404
    assert c.get("/doc/zzzzzzzzzzzz/").status_code == 404
    assert c.get(url + "doc.json").status_code == 404
