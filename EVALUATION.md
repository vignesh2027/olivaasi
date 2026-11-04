# Evaluation

Status: first end-to-end slice, 4 Nov 2026. The numbers below come from `eval/results.md`, which `uv run python eval/run_eval.py` regenerates. Nothing here was measured with real students.

## What was tested, and what was not

* Four pages, two Tamil and two English, typeset for this project in the layout of a state-board lesson: a title, prose, verse, a ruled table and numbered questions. The Tamil verse is Thirukkural 1, 391 and 396 (public domain); the English verse is the first stanza of Wordsworth's "I Wandered Lonely as a Cloud" (public domain); all other text was written for the project. Ground truth is the source text, in `eval/pages/*.json`.
* Each page as three images: a clean scan, a simulated phone photo (page on a desk, perspective, tilt, uneven light, blur, noise, JPEG), and a hard photo (the same plus page curl, a strong corner shadow, about 60 percent of the resolution and heavier compression). See `eval/images/`.
* Real Tamil Nadu textbook pages were not used. Several textbook titles are described as Creative Commons licensed, but we could not confirm the licence for the whole series from an official copy: the official portal textbooksonline.tn.nic.in did not resolve from our network, tnschools.gov.in loads its books through a script, and the copies we found were third-party Google Drive uploads. We did not use them. Real printed pages photographed on a phone will be harder than these images: textbook fonts, colour panels, two columns, pictures and worn paper are not covered.
* Baseline: plain Tesseract with the same models and language setting, run directly on the image.

## Text accuracy

Character error rate, whole page in reading order (lost or misordered text counts as error):

| | Plain Tesseract | Olivaasi |
|---|---:|---:|
| Tamil, clean scans | 0.1% | 0.0% |
| Tamil, phone photos | 41.9% | 0.1% |
| Tamil, hard photos | 17.3% | 1.7% |
| English, clean scans | 0.5% | 0.2% |
| English, phone photos | 0.4% | 0.1% |
| English, hard photos | 21.4% | 0.6% |

How to read this:

* On clean digital typesetting Tesseract's Tamil model is already excellent. The value Olivaasi adds is not better letters but not losing text: on the Tamil phone photos plain Tesseract skipped whole paragraphs and scrambled tables, which is why its error is so high.
* The hard photos exposed a failure we did not expect. Tesseract's page-layout step silently drops entire lines on blurred, low-resolution images, and our first version made it worse by enlarging the image (hard-photo CER of 41 to 48 percent on the Tamil pages). For a blind reader a missing line is the worst kind of error, because nothing signals it. Fixes, each measured on all twelve images: no enlargement of photos above 1000 px wide, page outline from edges so shadowed corners are kept, skew estimated from letter-sized marks only, and a coverage check that finds any row of ink no recognised line accounts for and reads it again as a single line.
* These pages are short (677 to 736 characters). One wrong word moves the rate by about a percentage point.

## Structure

On scans and phone photos every heading, question, verse line and table was recovered with the right element type, except one table cell per page on three images (a stray full stop). On the hard photos structure is weaker: bold subheadings are missed on three of four pages (stroke width stops separating bold from regular text at that resolution), and on the Thirukkural page verse and two questions merged into neighbouring blocks. Text is still present and in order in those cases, but a screen reader user loses the heading and list navigation for that part. This is the main open problem.

## Speed (Apple M1, 8 GB RAM)

* Recognition: 0.7 to 1.8 seconds per page.
* Speech: 1.4 to 2.0 seconds per page for about a minute of audio. The first version spoke one sentence per call and took 13 seconds per page; the macOS speech service handles one request at a time, so sentences in the same language are now spoken in one call with a long silence marker between them, and the track is cut at those silences. If the cut does not produce one piece per sentence, it falls back to one call per sentence.
* The M1 is faster than the laptops in most rural school labs. We expect several times slower on an older Intel laptop but have not measured it.

## Accessibility of the app

* axe-core 4.10.2, WCAG 2.0, 2.1 and 2.2 A and AA rules plus best practices, on the home page, the error state, and a converted page in all three reading styles at 100 and 300 percent text size: 0 violations (`scripts/a11y_check.py`). We confirmed the checker works by planting four known violations, which it reported.
* Automated checks cover only part of WCAG. Still to do and to report here: a full keyboard-only walkthrough of the task, a VoiceOver pass on the Tamil page (does it switch to the Tamil voice on `lang="ta"`?), and a 320 px reflow check.

## Speech quality

The Tamil voice is the macOS system voice Vani. It is offline and clear, but we have not rated it with Tamil-speaking listeners. On Linux and Windows the fallback is eSpeak NG, which has Tamil but sounds robotic. We found no small, offline, openly licensed neural Tamil voice: Meta's MMS Tamil model is licensed CC BY-NC 4.0 and AI4Bharat's Indic Parler-TTS is too heavy for an 8 GB laptop at usable speed.
