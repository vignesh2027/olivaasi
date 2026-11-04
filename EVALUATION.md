# Evaluation

Updated 4 Nov 2026. Numbers come from `eval/results.md`, which `uv run python eval/run_eval.py` regenerates, and from the scripts named below. Nothing here was measured with real students, and no real textbook page was tested.

## What was tested

* Five pages, three Tamil and two English, typeset for this project in the layout of a state-board lesson: titles, prose, verse, ruled tables, numbered questions, and on one page a tinted "Did you know" box, coloured headings and a page number. The Tamil verse is Thirukkural 1, 391 and 396 (public domain); the English verse is the first stanza of Wordsworth's "I Wandered Lonely as a Cloud" (public domain); all other text was written for the project. Ground truth is the source text in `eval/pages/*.json`.
* Each page as four images (`eval/images/`):
  * **scan**: a clean 150 dpi rendering;
  * **photo**: the page on a desk, mild perspective and tilt, uneven light, blur, noise, JPEG;
  * **hard**: the same plus page curl, a strong corner shadow, about 60 percent of the resolution, heavier compression;
  * **camera**: a 300 dpi print-quality rendering photographed in simulation as an open book: the half near the spine bends and darkens, strong perspective and tilt, warm indoor light, hand shake, soft focus, sensor noise and JPEG quality 50, in a 3000 by 4000 frame.
* Baseline: plain Tesseract 5.5.4 with the same `tam+eng` models, run directly on the image.

## No real textbook page was tested

We wanted to measure real Tamil Nadu state-board pages and checked the official sources on 4 Nov 2026 with a browser:

* textbooksonline.tn.nic.in, the old free download portal, no longer resolves (DNS: no such domain).
* tnschools.gov.in/textbooks returns "Page Not Found"; the site footer says "Copyright All Rights Reserved. Department of School Education".
* textbookcorp.in, the Tamil Nadu Textbook and Educational Services Corporation, sells printed books and offers no free download; its footer says "All Rights Reserved" and its Terms of Use cover linking, not reuse.
* Some titles on Bookshare are described as carrying a Creative Commons licence inside the book, and the copies we could find online were third-party uploads, so we could not read the licence page from an official copy.

Reuse is not clearly permitted, so we did not use any real page. Real printed pages will be harder than our images in ways the simulation does not cover: real textbook fonts and ligatures, two columns, pictures with captions, coloured panels with white text, glossy paper glare and worn pages.

## Text accuracy

Character error rate (CER), whole page in reading order, so text that is lost or put in the wrong order counts as error:

| | Plain Tesseract | Olivaasi |
|---|---:|---:|
| Tamil, scans | 0.5% | 0.0% |
| Tamil, phone photos | 30.4% | 0.2% |
| Tamil, hard photos | 15.5% | 1.7% |
| Tamil, camera captures | 84.7% | 3.6% |
| English, scans | 0.5% | 0.2% |
| English, phone photos | 0.4% | 0.1% |
| English, hard photos | 21.4% | 0.6% |
| English, camera captures | 65.2% | 1.6% |

Per page, the worst result is the textbook-style Tamil page as a camera capture: 9.0% CER and 23% word error rate. Its note box sits in the darkest part of the spine shadow.

How to read this:

* On clean typesetting Tesseract's Tamil model is already excellent. What Olivaasi adds is not losing text. On photos plain Tesseract skips whole paragraphs and scrambles tables without warning, and for a blind reader a missing line is the worst kind of error because nothing signals it.
* What made the difference, each change measured on all images before it was kept:
  * finding the page from its edges, so a shadowed corner is not cut off;
  * not enlarging blurred photos (enlarging made Tesseract drop lines: 41 to 48% CER on the hard Tamil pages in our first version);
  * estimating skew from letter-sized marks only;
  * a coverage check that finds any row of ink no recognised line accounts for and reads it again on its own;
  * straightening curved lines near a book's spine, then keeping whichever of the two readings Tesseract is more confident in (straightening blindly helped some pages and hurt others; for example the textbook-style camera page went from 12.5% to 18.2%);
  * restoring a table border lost in shadow from the rules that cross it.
* Two things we tried made results worse and were removed: binarising the image ourselves, and erasing long rules such as box borders before reading.
* Pages are short (about 600 to 740 characters), so one wrong word moves a page's rate by about a percentage point.

## Structure

Elements recovered with the right type, all pages added up:

| Image | Headings (text and level) | Questions | Table cells | Verse lines |
|---|---|---|---|---|
| scan | 17/17 | 20/20 | 38/40 | 12/12 |
| photo | 15/17 | 20/20 | 38/40 | 12/12 |
| hard | 12/17 | 18/20 | 33/40 | 12/12 |
| camera | 12/17 | 13/20 | 34/40 | 9/12 |

* Headings are found by size and by stroke width (bold). Thresholds were set from measured lines on all images: on degraded photos bold headings are only 1.15 to 1.35 times as thick as body text, while short body lines stay below 1.07. Coloured headings are the main miss: once converted to grey, blue bold text measures like ordinary text. All four misses on the textbook-style camera page are of this kind.
* On camera captures some question numbers merge with or split from their text, so a few questions become plain paragraphs. The words are still there and in order, but the list navigation is lost for those items.
* Question numbers misread as look-alike Tamil digits (a printed "2." read as ௨) are corrected when the other numbers in the list show the sequence. Genuine Tamil-numeral lists are left alone.

## Speed (Apple M1, 8 GB RAM)

* Recognition: 0.7 to 1.4 seconds for scans and photos, 1.8 to 3.1 seconds for hard photos, 4.0 to 7.2 seconds for camera captures (these are read twice when their lines look curved, and are 3000 by 4000 pixels).
* Speech: 1.6 to 2.4 seconds per page for about a minute of audio. Our first version took 13 seconds per page, because the macOS speech service handles one request at a time and each call costs about 0.8 seconds. Sentences in the same language are now spoken in one call with a long silence between them, and the track is cut at those silences, with a fallback to one call per sentence if the cut does not match.
* The M1 is faster than most school lab laptops. We have not measured an older Intel laptop.

## Simplified reading

Optional, off by default, and only for English paragraphs. Full review in `eval/simplification.md`. With gemma3:4b running locally, English paragraphs were split into shorter sentences without changing facts. In Tamil the model changed meaning or grammar in three of four paragraphs; with a looser prompt it also turned "1330 kurals" into "more than 3300". So Olivaasi does not simplify Tamil, and says so on the page. Every simplified paragraph is labelled "Simplified by computer", has its own audio, and the original is one tap away.

## Accessibility of the app

Automated (axe-core 4.10.2, WCAG 2.0, 2.1 and 2.2 A and AA rules plus best practices, `scripts/a11y_check.py`): 0 violations on the home page, the error state, a converted page in each of the three reading styles at 100 and 300 percent text size, an English page with the simplified version shown, and a converted page at 360 px phone width. The checker was confirmed working by planting four known violations, all of which it reported.

Keyboard only (`scripts/keyboard_walk.py`, log in `docs/keyboard-walkthrough.txt`):

* 15 tab stops on a converted page, in visual order, each with a visible focus outline of at least 2 px, starting with a skip link.
* The browser's own audio player added six tab stops, some without a focus outline we could verify, so it is replaced by labelled Play, Previous, Repeat, Next and Next heading buttons; the native player returns if scripts are off.
* The task "reach question 3 and hear it read" takes 15 key presses: 8 Tab to reach Next heading, 3 Space to reach the questions, 1 Shift+Tab, 3 Space on Next. Before Next heading was added it took 29.

Screen reader: not tested with a person using VoiceOver, NVDA or TalkBack. We did not run VoiceOver on this machine because it takes over the keyboard and speech of a shared computer. Instead we read the accessibility tree that Chrome gives screen readers: one level 1 heading, level 2 headings, a list with one item per question, a table with column headers, labelled buttons and radio groups, and a `lang` attribute on every block (7 Tamil and 2 English on the Tamil science page) so a screen reader can switch voices. Whether VoiceOver actually switches to its Tamil voice on `lang="ta"` is untested.

Layout: at 320, 360 and 390 px width with text at 100, 200 and 300 percent the page never scrolls sideways (checked by `scripts/a11y_check.py` on three pages; tables scroll inside their own region). This check first failed at 300 percent, because single long Tamil words were wider than the screen; long words may now break at the edge of the lesson. On phones the settings start folded so the lesson is visible at once.

## Speech quality

The Tamil voice is the macOS system voice Vani. It is offline and clear to the author, but has not been rated by other Tamil listeners. On Linux and Windows the fallback is eSpeak NG, which has Tamil but sounds robotic; that path is untested. We found no small, offline, openly licensed neural Tamil voice: Meta's MMS Tamil model is licensed CC BY-NC 4.0, and AI4Bharat's Indic Parler-TTS is too heavy for an 8 GB laptop at usable speed.
