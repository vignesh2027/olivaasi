# Olivaasi (ஒலிவாசி)

Olivaasi turns a photo of a printed Tamil or English textbook page into a page a student can read with a screen reader, at a large size, with wide spacing, or by listening while each sentence is highlighted. It runs on a laptop with no internet connection.

It is built for students who are blind, have low vision or find dense print hard to read, in schools where the accessible edition of a page is not on the computer in front of them. See [DESIGN.md](DESIGN.md) for the learner and the problem, and [EVALUATION.md](EVALUATION.md) for measured accuracy, speed and accessibility results and their limits.

![A Tamil science page in Olivaasi, with the sentence being read highlighted](docs/screenshots/02-page-tamil-reading-along.png)

## What it does

1. Finds the page in the photo, straightens it and evens out the light.
2. Reads the text with Tesseract (Tamil and English models), including text that Tesseract's first pass skips.
3. Rebuilds the structure: headings, paragraphs, verse, numbered questions and ruled tables.
4. Writes one self-contained HTML page with real headings, lists and tables, a language tag on every block and every English phrase inside Tamil text, text size and reading style controls, and the original photo one click away.
5. Records the page with the computer's offline voices and highlights each sentence as it is read; previous, repeat and next sentence buttons and three speeds.

The output folder can be copied to a pen drive and opened in any browser.

## Setup (macOS, tested)

You need [Homebrew](https://brew.sh) and [uv](https://docs.astral.sh/uv/). Internet is needed only for these steps.

```sh
brew install tesseract
git clone <this repository> olivaasi
cd olivaasi
uv sync
sh scripts/get_models.sh
uv run olivaasi doctor
```

`doctor` should report Tesseract, the `tam` and `eng` models, and a Tamil voice. On macOS the Tamil voice is "Vani". If it is missing, add it in System Settings, Accessibility, Spoken Content, System voice, Manage Voices, Tamil.

On Debian or Ubuntu, install `tesseract-ocr` and `espeak-ng` with apt instead of the brew step. This path has not been tested yet.

## Use

Start the app and open http://127.0.0.1:8765/ in a browser:

```sh
uv run olivaasi serve
```

Choose a photo, or press one of the sample buttons. Converted pages are kept in `work/` and listed on the home page.

Or convert one photo from the command line:

```sh
uv run olivaasi convert eval/images/ta_water_photo.jpg -o out/ta_water
open out/ta_water/index.html
```

## Tests and evaluation

```sh
uv run pytest
uv run python eval/run_eval.py
```

The evaluation writes `eval/results.md`. The accessibility check and the screenshots need the app running in another terminal and Google Chrome installed:

```sh
uv run python scripts/a11y_check.py
uv run python scripts/screenshots.py
```

## Limitations

* Tested on typeset pages and simulated photos, not yet on real textbook photos (see EVALUATION.md for why).
* One text column. Two-column pages are read across both columns.
* Pictures, diagrams and handwriting are not described. Mathematical notation is read as plain text.
* On poor photos, bold subheadings can be missed and become ordinary paragraphs.
* Speech quality depends on the voices installed on the computer.

## Credits

Built during AccessED Hacks (17 October to 20 November 2026); all project code is new work started on 4 November 2026.

* [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) and the [tessdata_best](https://github.com/tesseract-ocr/tessdata_best) Tamil and English models, Apache 2.0.
* [OpenCV](https://opencv.org), Apache 2.0. [NumPy](https://numpy.org), BSD. [FastAPI](https://fastapi.tiangolo.com), [Starlette](https://www.starlette.io) and [Uvicorn](https://www.uvicorn.org), BSD and MIT. [Jinja](https://jinja.palletsprojects.com), BSD.
* Speech: the macOS system voices, or [eSpeak NG](https://github.com/espeak-ng/espeak-ng) (GPL 3.0, run as a separate program).
* Development only: [axe-core](https://github.com/dequelabs/axe-core) 4.10.2 (MPL 2.0) for accessibility checks, Google Chrome for screenshots, pytest.
* Evaluation text: Thirukkural (public domain) and William Wordsworth, "I Wandered Lonely as a Cloud" (1807, public domain). All other sample text and the logo were made for this project.
