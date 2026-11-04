# Olivaasi: design

Olivaasi (ஒலிவாசி, from ஒலி "sound, voice" and வாசி "read") turns a photo of a printed textbook page into an accessible page a student can read with a screen reader, at a large font, in a dyslexia-friendly layout, or by listening, on a laptop with no internet.

## Name

The working name was Padi (படி, "read"). It was dropped on 4 Nov 2026 after a search showed real collisions, and Olivaasi was chosen after checking each candidate on GitHub (repositories, users and organisations, code), the Apple App Store (iTunes Search API), Google Play (store search page), PyPI, the web, and DNS for the .com, .org, .in and .app domains.

| Candidate | Result | Decision |
|---|---|---|
| Padi | PADI, the Professional Association of Diving Instructors, a large trademarked brand that fills both app stores; Google Play also lists "Padi App : TN Samacheer Kalvi", a Tamil Nadu textbook app in the same space, plus "My Padi", "Padi Business" and "Padiku" | Rejected |
| Vaasi | App Store "Vaasi Tamil & English Phonics"; Google Play "Vaasi - Books for kids" | Rejected |
| Thiravu (திறவு, "open") | GitHub "openassistiveaiapps/thiravugal-app", an assistive app with a near-identical name | Rejected |
| Kanoli | 18 GitHub repositories and 35 users, including a Kanban app | Rejected |
| Olipakkam (ஒலிப்பக்கம், "sound page") | No product or company, but it is the name of a village in Ranipet district (Tamil Nadu gazette, pincode and map data), so searches would lead there | Not chosen |
| **Olivaasi** | No App Store or Google Play app, no GitHub repository, user, organisation or code mention, no PyPI package, no web result, and none of olivaasi.com, .org, .in or .app resolves | **Chosen** |

Limits of this check: it is a search for notable existing use, not a legal trademark clearance. The Indian trademark register (IP India public search) needs an interactive captcha and was not searched. The spelling with one "a" (Olivasi) appears as an unrelated word in other languages and in expired-domain lists; the project always uses the double "aa".

A note on meaning: வாசி is the verb "read". As a suffix it can also mean "one who lives in" (as in நகரவாசி, city dweller), so the name can be heard as "one who reads aloud" or, loosely, "one who lives in sound". Both fit a tool for listening to a page.

## The learner

Kayal is a made-up student. She is 15 and in Class 10 at a government high school in a village outside Tiruvannamalai. She has low vision: she reads print only at very large sizes, slowly, with a handheld magnifier, and her eyes tire within a few minutes. Her medium of instruction is Tamil, and her English paper is a separate subject.

Her school has one shared computer lab with old laptops. Internet comes from a teacher's phone hotspot when it comes at all. A resource teacher for children with disabilities, Selvam (also made up), visits twice a week.

## The obstacle

> Kayal wants to read tonight's lesson page and answer its five numbered questions, but the only copy is printed Tamil text she cannot read at that size, and the accessible version, if one exists, is not on the laptop in front of her.

Why the existing routes fail her on the night:

* Accessible editions of some Tamil Nadu textbooks exist (Bookshare lists several), but they need an account, a download, and a reading app. Worksheets, model question papers, notes the teacher photocopies and the newest editions are usually not available at all.
* Phone OCR apps that handle Tamil mostly need the internet, and they return a flat block of text: headings, question numbers and tables are lost, so a screen reader reads everything as one paragraph.
* Large-print copies are made by hand and arrive late.

## What Olivaasi does

1. Selvam or Kayal photographs the page with any phone or webcam and copies the image to the laptop, or opens it directly on the laptop.
2. Olivaasi finds the page in the photo, straightens it, evens out the light and the tilt, and straightens text lines that curve into a book's spine. It runs Tesseract OCR with the Tamil and English models, keeps the layout Tesseract reports (block and line positions, text heights, stroke width), and reads again any row of print that the first pass skipped.
3. It rebuilds structure: headings from larger, short lines; numbered questions (1. 2. 3., (அ) (ஆ) and Tamil numerals) as an ordered list; paragraphs from blocks; tables from ruled grids.
4. It writes a single self-contained HTML page with real `h1`/`h2`, `ol`, `p` and `table` elements, a `lang` attribute on every block (`ta` or `en`, so a screen reader switches voice), a font size control, a dyslexia-friendly mode (wider spacing, left aligned, no italics, cream background option) and a high-visibility mode.
5. It records audio offline and joins it into one track with sentence timings, so the page highlights the sentence being spoken. Labelled buttons play and pause, step back, repeat, step forward, and jump to the next heading, at three speeds.
6. Optional: a simplified reading of English prose paragraphs from a local model, labelled "Simplified by computer", with its own audio and the original one tap away. Tamil is not simplified: the model we could run offline changed the meaning or grammar of Tamil paragraphs too often (see `eval/simplification.md`).

The output page works by opening the file in any browser, with no server and no network, so it can be copied to a pen drive or another laptop.

## Before and after (the concrete example)

Measured on the Tamil water-cycle page, photographed on a desk (`eval/images/ta_water_photo.jpg`):

* Before: the only copy is print. A screen reader has nothing to read in a photo. Plain Tesseract on the same photo skips the whole first paragraph and scrambles the table: 51 percent of the characters are wrong or missing, and the result is one flat block of text with no headings or list.
* After: in about 4 seconds on the laptop, Olivaasi produces a page with the lesson title as heading level 1, two subheadings, both paragraphs, the table with its column headers, and the four questions as a numbered list, with 0.1 percent of characters wrong. Kayal can raise the text to 300 percent, switch to wide spacing or dark high contrast, or press Play and follow the highlighted sentence. To hear question 3 with the keyboard alone takes 15 key presses (Tab to Next heading, jump to the questions, step to question 3).

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
* Optional simplification: gemma3:4b through a local Ollama server (Gemma terms of use), English only. Olivaasi works fully without it.
* Server and UI: Python, FastAPI, Jinja templates, plain CSS, a small inline script only for audio, highlighting and settings. No frontend toolchain. Without scripts the page still reads, with the browser's own audio player.

## Accessibility of Olivaasi itself (target WCAG 2.2 AA)

* All controls are native HTML elements (buttons, select, radio groups, details) with visible labels; no custom widgets.
* Visible focus ring, skip link, logical heading order, `lang` on every block.
* Colour contrast at least 4.5:1 for text against the light-blue theme (#F4F9FF background, #FFFFFF surface, #0B1B33 text, #2563EB primary, #4C1D95 accent, #9F1239 danger); state is never shown by colour alone.
* Status messages use a live region; errors are announced and tied to the field.
* Text resizes to 300 percent without loss; layout reflows at 320 px width.
* Target size at least 24 by 24 px.

## Out of scope for the hackathon

Handwriting; maths notation (read as plain text, no warning yet); pictures and diagrams (not detected or described, and labels inside them may appear as stray lines); two-column pages; braille output; multi-page books.
