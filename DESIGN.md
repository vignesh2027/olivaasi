# Padi: design

Padi (படி, "read") turns a photo of a printed textbook page into an accessible page a student can read with a screen reader, at a large font, in a dyslexia-friendly layout, or by listening, on a laptop with no internet.

## The learner

Kayal is a made-up student. She is 15 and in Class 10 at a government high school in a village outside Tiruvannamalai. She has low vision: she reads print only at very large sizes, slowly, with a handheld magnifier, and her eyes tire within a few minutes. Her medium of instruction is Tamil, and her English paper is a separate subject.

Her school has one shared computer lab with old laptops. Internet comes from a teacher's phone hotspot when it comes at all. A resource teacher for children with disabilities, Selvam (also made up), visits twice a week.

## The obstacle

> Kayal wants to read tonight's lesson page and answer its five numbered questions, but the only copy is printed Tamil text she cannot read at that size, and the accessible version, if one exists, is not on the laptop in front of her.

Why the existing routes fail her on the night:

* Accessible editions of some Tamil Nadu textbooks exist (Bookshare lists several), but they need an account, a download, and a reading app. Worksheets, model question papers, notes the teacher photocopies and the newest editions are usually not available at all.
* Phone OCR apps that handle Tamil mostly need the internet, and they return a flat block of text: headings, question numbers and tables are lost, so a screen reader reads everything as one paragraph.
* Large-print copies are made by hand and arrive late.

## What Padi does

1. Selvam or Kayal photographs the page with any phone or webcam and copies the image to the laptop, or opens it directly on the laptop.
2. Padi cleans the image (greyscale, deskew, contrast), runs Tesseract OCR with the Tamil and English models, and keeps the layout signals Tesseract reports: block and line positions and text heights.
3. It rebuilds structure: headings from larger, short lines; numbered questions (1. 2. 3., (அ) (ஆ) and Tamil numerals) as an ordered list; paragraphs from blocks; tables from ruled grids.
4. It writes a single self-contained HTML page with real `h1`/`h2`, `ol`, `p` and `table` elements, a `lang` attribute on every block (`ta` or `en`, so a screen reader switches voice), a font size control, a dyslexia-friendly mode (wider spacing, left aligned, no italics, cream background option) and a high-visibility mode.
5. It records audio offline, one sentence at a time, and joins it into one track with sentence timings, so the page highlights the sentence being spoken and any sentence can be replayed by clicking it or pressing a key.
6. Optional: a simplified reading of a paragraph, always labelled "Simplified", with the original one keypress away. Only if an offline model does this acceptably in Tamil; otherwise it stays out (see Evaluation).

The output page works by opening the file in any browser, with no server and no network, so it can be copied to a pen drive or another laptop.

## Before and after (the concrete example)

* Before: a printed Class 9 style Tamil lesson page, a heading, two paragraphs, a small table and five questions. With VoiceOver or NVDA there is nothing to read; at the size Kayal can see, she reads a line every 20 to 30 seconds.
* After: the same page as HTML. The screen reader announces "heading level 1", the lesson title, then the paragraphs, then "list, 5 items" for the questions; she jumps by heading or list item, raises the font to 200 percent, or presses Play and follows the highlighted sentence.

## How success is measured

| Question | Measure | Where |
|---|---|---|
| Is the text right? | Character error rate (CER) and word error rate per page, Tamil and English, against hand-checked ground truth | `eval/` and EVALUATION.md |
| Is the structure right? | Headings, question items and table cells recovered versus ground truth | `eval/` |
| Is it fast enough on an old laptop? | Seconds per page for each stage on an M1 MacBook Air with 8 GB RAM, a modest proxy we state as such | `eval/` |
| Is the app usable without a mouse or sight? | Keyboard-only walkthrough of the full task, automated accessibility checker run on the app pages and the output page, VoiceOver spot check | EVALUATION.md |
| Can the learner do the task? | Scripted task: find question 3 and hear it read, using only the keyboard. Measured by us, not by real students; we do not claim learning outcomes | EVALUATION.md |

## What is offline

Everything at runtime. Installing needs the internet once (Python packages, Tesseract, the language models). After that the server, OCR, structure rebuild, audio and the output page all work with networking switched off. No accounts, no analytics, no external fonts or scripts in either the app or the output page.

## Components and why

* OCR: Tesseract 5 with `tam` and `eng` from `tessdata_best` (Apache 2.0). Tamil support is mature, it runs on CPU, and its TSV output carries the positions needed for structure. Alternatives (EasyOCR, PaddleOCR) need PyTorch or Paddle and several hundred MB; they may be compared later if Tesseract accuracy is weak.
* Image clean-up and table grid detection: OpenCV (Apache 2.0).
* Speech: the operating system voice. On macOS, `say` with the Tamil voice "Vani" and an Indian English voice, both offline once installed. On Linux and Windows, `espeak-ng` (GPL 3.0, run as a separate program) which has Tamil, robotic but intelligible. There is no high-quality, permissively licensed, small offline Tamil neural voice we could find: Meta's MMS Tamil model is CC BY-NC 4.0 and AI4Bharat's Indic Parler-TTS is too large for an 8 GB laptop at usable speed. This is a known limitation.
* Server and UI: Python, FastAPI, Jinja templates, plain CSS, a few lines of inline JavaScript only for audio highlighting and settings. No frontend toolchain.

## Accessibility of Padi itself (target WCAG 2.2 AA)

* All controls are native HTML elements with visible labels; no custom widgets.
* Visible focus ring, skip link, logical heading order, `lang` on every block.
* Colour contrast at least 4.5:1 for text against the light-blue theme (#F4F9FF background, #FFFFFF surface, #0B1B33 text, #2563EB primary, #4C1D95 accent, #9F1239 danger); state is never shown by colour alone.
* Status messages use a live region; errors are announced and tied to the field.
* Text resizes to 200 percent without loss; layout reflows at 320 px width.
* Target size at least 24 by 24 px.

## Out of scope for the hackathon

Handwriting, maths equations (read as plain text, with a warning), images and diagrams (marked as "Figure: no description" rather than ignored), braille output, multi-page books.
