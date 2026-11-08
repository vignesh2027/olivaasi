# Olivaasi: submission material for AccessED Hacks

Text for the Devpost form, ready to paste. Figures come from EVALUATION.md and `eval/results.md`; check them again if the code changes. The AI-assistance credit line is added at submission time (placeholder at the end of Credits).

## Name

Olivaasi (ஒலிவாசி)

## Short pitch

Olivaasi turns a phone photo of a Tamil or English textbook page into a page a blind or low-vision student can read with a screen reader, in large print, or by listening along, entirely offline on a school laptop.

## The learning story

### The problem

A student wants to read tonight's lesson and answer its questions, but the only copy is printed. For a blind student a printed page is silent. For a low-vision student it means a magnifier and minutes per paragraph. Accessible editions exist for some state-board textbooks, but worksheets, photocopied notes, question banks and new editions usually have no accessible copy, and the school lab's internet comes and goes.

### Who it is for

Students in Tamil-medium and English-medium schools who are blind, have low vision, or find dense print hard to read, and the resource teachers who support them. Our example learner is Kayal, a made-up Class 10 student with low vision at a government school outside Tiruvannamalai, with one shared lab of old laptops and patchy internet.

### What it does

A teacher or student photographs the page, or opens a photo on the laptop. Olivaasi finds the page in the photo, straightens it, evens out the light, straightens text lines that curve into a book's spine, and reads it with Tesseract's Tamil and English models. It then rebuilds the page's structure: the title and subheadings as real headings, paragraphs, poems line by line, ruled tables with column headers, and the numbered questions as a list. Every block, and every English word inside Tamil text, is tagged with its language so a screen reader can switch voice.

The result is one HTML file that opens in any browser with no internet: text size up to 300 percent, a wide-spacing style, a dark high-contrast style, and an audio track made with the laptop's own Tamil and English voices that highlights each sentence as it is read. Labelled buttons play, step back, repeat, step forward and jump to the next heading. The original photo is one click away so a teacher can check the text. For English pages there is an optional simplified version of each paragraph from a local model, always labelled, with the original one tap away.

### One concrete before and after

The Tamil water-cycle lesson, photographed on a desk:

* Before: a screen reader has nothing to read in a photo. Plain Tesseract on that photo skips the whole first paragraph and scrambles the table: 51 percent of the characters are wrong or missing, with no headings or list.
* After: about 4 seconds later on the laptop, the page has a level 1 heading, two subheadings, both paragraphs, the table with headers and the four questions as a numbered list, with 0.1 percent of characters wrong, plus a one-minute read-along audio track. Hearing question 3 with the keyboard alone takes 15 key presses.

### How we built it

Python with FastAPI and Jinja for a local web app, OpenCV for image clean-up and table detection, Tesseract 5 with the tessdata_best Tamil and English models, the operating system's offline voices for speech (Vani for Tamil on macOS, eSpeak NG elsewhere), plain HTML and CSS with a small inline script, and optionally a local Gemma 3 4B model through Ollama for English simplification. No account, no cloud service, no tracking.

### Challenges

* Tesseract silently drops whole lines on blurred photos. For a blind reader that is the worst error, because nothing signals it. We added a check that finds every row of print no recognised line covers and reads it again.
* Our first speech version took 13 seconds a page because the system voice handles one request at a time. Speaking each language's sentences in one call, with long silences between them that we then cut at, brought it to about 2 seconds.
* Pages curving into a book's spine bend the text lines. Straightening them helped some pages and hurt others, so Olivaasi reads both versions and keeps the one Tesseract is more confident in.
* The simplification model changed facts in Tamil (it turned the Thirukkural's 1330 couplets into "more than 3300"). We switched Tamil simplification off rather than ship it.

### What we learned

Measuring against plain Tesseract on every change kept us honest: two ideas that looked sensible (binarising the image ourselves, erasing box borders) made results worse and were removed. Not losing text matters more than perfect letters. And for learners who cannot check the output, a missing feature is safer than a feature that is sometimes wrong.

## Built during the event

All of Olivaasi's code, documents, evaluation pages, evaluation images and the logo were made between 4 and 20 November 2026, inside the event window, starting from an empty repository. There is no pre-existing project code. The third-party components listed under credits existed before the event and are used unmodified.

## Try it

* Try it live: https://applemacbook6sep2004--olivaasi.us-east.modal.run (press a sample button, or upload a photo; the first conversion after a quiet spell takes about 15 seconds). Photos are converted in memory and deleted before the page is sent; nothing is stored or logged. The demo runs on Linux, so its speech is the robotic eSpeak NG fallback rather than the macOS Tamil voice.
* Source code: [GITHUB REPO LINK]. Setup on macOS takes a few commands; the app then runs at http://127.0.0.1:8765/ with no internet.
* Sample pages are built in, so no photo and no personal information are needed to try it.
* Recorded walkthrough: [YOUTUBE LINK] (script below; the script is also the transcript).

## Limitations

* Tested on pages we typeset ourselves and on simulated photos and camera captures, not on real textbook pages, because we could not confirm that reuse of the state textbooks is permitted. Real pages will be harder.
* On the harshest simulated captures, 3.6 percent of Tamil characters and 1.6 percent of English characters are still wrong, and some coloured headings and a few question numbers are not recognised as such. The text stays in order, but those headings and questions lose their navigation.
* One text column only. Pictures and diagrams are not described. Maths is read as plain text. Handwriting is not supported.
* Speech uses the voices installed on the computer. The macOS Tamil voice is clear; the eSpeak NG fallback on Linux and Windows is robotic. The hosted demo uses eSpeak NG, which is how we checked that the Linux path works; it has not been tested on Windows.
* Simplification is English only, optional, and needs a local model that uses about 3.4 GB of memory.
* Accessibility was checked with automated tools and a scripted keyboard walkthrough, not yet with blind or low-vision students or with a person using VoiceOver or NVDA.

## Credits

* Tesseract OCR and the tessdata_best Tamil and English models (Apache 2.0).
* OpenCV (Apache 2.0), NumPy (BSD), FastAPI, Starlette, Uvicorn and Jinja (MIT and BSD).
* Speech: macOS system voices, or eSpeak NG (GPL 3.0, run as a separate program).
* Optional simplification: Gemma 3 4B (Gemma terms of use) through Ollama (MIT).
* Development only: axe-core 4.10.2 (MPL 2.0), Google Chrome, pytest.
* Hosting for the public demo: Modal.
* Evaluation text: Thirukkural (public domain) and William Wordsworth, "I Wandered Lonely as a Cloud" (1807, public domain). All other sample text, the made-up learner and the logo were created for this project.
* [AI-ASSISTANCE CREDITS LINE]

## Screenshots and their alt text

| File | Alt text |
|---|---|
| docs/screenshots/01-home.png | Olivaasi home page with a photo upload form, sample pages and pages already converted on this computer. |
| docs/screenshots/02-page-tamil-reading-along.png | A Tamil science lesson converted by Olivaasi, with the sentence being read aloud highlighted in yellow and underlined. |
| docs/screenshots/03-page-wide-spacing-200.png | The same lesson at 200 percent text size in the wide-spacing reading style. |
| docs/screenshots/04-page-dark-high-contrast.png | The lesson in the dark high-contrast style with a table of the water cycle stages. |
| docs/screenshots/05-page-phone-width.png | The lesson on a phone-sized screen with the settings folded away and the audio buttons at the top. |
| docs/screenshots/06-page-english-simplified.png | An English lesson showing paragraphs labelled "Simplified by computer", with a switch back to the original. |

## Demo video script (2 minutes 30 seconds)

Also the caption transcript. Use the made-up learner only. Screen recording of the laptop, with the audio of the app audible where noted.

| Time | On screen | Narration |
|---|---|---|
| 0:00 | A printed Tamil lesson page on a desk, then the same page as a photo. | This is a Tamil science lesson. For Kayal, a Class 10 student with low vision, and for blind classmates, a printed page like this is the barrier. A screen reader cannot read a photo, and accessible copies of worksheets and new editions are rarely on the school laptop. |
| 0:20 | Plain Tesseract output of the photo in a text editor, first paragraph missing, table scrambled. | Ordinary text recognition on this photo loses the whole first paragraph and mixes up the table. Half the page is wrong, and nothing tells the student. |
| 0:35 | Olivaasi home page. Wi-Fi turned off in the menu bar. | This is Olivaasi, running on a laptop with Wi-Fi switched off. I choose the photo and press Convert page. |
| 0:45 | The converted page appears. | About four seconds later the page is back, with its title as a heading, both paragraphs, the table with column headers, and the four questions as a numbered list. |
| 0:58 | Press Play. The sentence highlight moves; Tamil speech audible. | Press Play and the laptop's own Tamil voice reads the lesson, highlighting each sentence. |
| 1:10 | Press Next heading, then Next twice; question 3 highlighted and read. | With only the keyboard, Next heading jumps to the questions and Next steps to question 3. |
| 1:22 | Text size to 300 percent, then Wide spacing, then Dark high contrast. | Kayal can make the text three times larger, add spacing between letters and lines, or switch to dark, high contrast. |
| 1:35 | Open "Show the original photo". | The original photo is always one click away, so a teacher can check any word. |
| 1:42 | Convert the open-book sample; the curved page is straightened. | It also handles a page photographed in an open book, curving into the spine, by straightening the lines. |
| 1:55 | English sample with Simplified by computer selected. | For English pages there is an optional simplified version, clearly labelled, with the original one tap away. We switched it off for Tamil because the small offline model changed facts. |
| 2:08 | EVALUATION.md table. | We measured every change against plain Tesseract. On our simulated phone photos of Tamil pages, characters wrong fell from 30 percent to under 1 percent. |
| 2:18 | README credits and limitations. | Everything here was built during AccessED Hacks on open-source tools. It has not yet been tested on real textbook pages or with students, and that is our next step. |
| 2:28 | Logo. | Olivaasi. Read any page, aloud, offline. |
