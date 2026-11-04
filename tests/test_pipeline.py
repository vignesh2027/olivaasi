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


def test_simplify_checks_reject_changed_numbers_and_copies():
    from olivaasi import simplify

    orig = "It has 133 chapters and 1330 couplets in all, which are read in every school in the state."
    assert "numbers" in simplify.check(orig, "It has 133 chapters and more than 3300 couplets.")
    assert simplify.check(orig, orig) == "almost the same as the original"
    assert simplify.check(orig, "It has 133 chapters. It has 1330 couplets. Every school reads them.") == ""


@needs_ocr
def test_simplified_paragraphs_are_labelled_and_original_kept(work, monkeypatch):
    from olivaasi import simplify

    monkeypatch.setattr(simplify, "available", lambda model=simplify.MODEL: None)
    monkeypatch.setattr(simplify, "simplify", lambda text, lang, model=simplify.MODEL: simplify.Simplified("Water moves. The Sun heats it. This is called evaporation."))
    from conftest import ROOT

    out = work / "s"
    pipeline.convert(ROOT / "eval" / "images" / "en_water_photo.jpg", out, audio=False, simplified=True)
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'class="simple" hidden' in html and "Simplified by computer:" in html
    assert 'class="orig"' in html and "Water on the Earth does not stay in one place." in html
    assert 'value="original" checked' in html


@needs_ocr
def test_tamil_paragraphs_are_not_simplified_by_default(work, sample_image, monkeypatch):
    from olivaasi import simplify

    monkeypatch.setattr(simplify, "available", lambda model=simplify.MODEL: None)
    monkeypatch.setattr(simplify, "simplify", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not be called")))
    r = pipeline.convert(sample_image, work / "t", audio=False, simplified=True)
    assert any("Tamil paragraph" in n for n in r.notes)
