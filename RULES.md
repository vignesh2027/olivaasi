# AccessED Hacks: rules as recorded

Source pages fetched on 4 Nov 2026:

* Overview: https://accessed-hacks.devpost.com/
* Rules: https://accessed-hacks.devpost.com/rules
* Resources: https://accessed-hacks.devpost.com/resources

Quotes below are copied from those pages. Where the page text is garbled or silent, that is stated rather than guessed.

## Dates

* Build window: "Build from October 17, 2026 at 12:00 AM until November 20 at 5:00 PM Eastern Time."
* Deadline: Nov 20, 2026, 5:00 PM EST. That is Sat 21 Nov 2026, 03:30 IST.
* Judging: Nov 21, 9:00 AM ET to Nov 22, 5:00 PM ET. Results Nov 23, 9:00 AM ET.
* "Keep judging links available through Nov 22."
* Note: the overview prose says "For four days, they are your brief", which conflicts with the five week window above. The rules page dates are the ones we follow.
* Our own target: feature complete with README, evaluation and demo script by 18 Nov.

## Eligibility

* Students at a recognized educational institution, above the legal age of majority, eligible under the geographic rules (all countries except standard exceptions).
* Solo entries are allowed. Companies are excluded.

## What counts as an entry

Rules page, verbatim:

> Submit one Devpost entry per project addressing a specific barrier to learning. Include a project story, screenshots, and an accessible demo, build, or recorded walkthrough. A demo video is optional. Identify work created during the event and distinguish it from pre-existing work. Any stack, including low-code and AI-assisted tools, is allowed when its terms permit use.

Overview "Requirements", verbatim:

> Create a working education-related prototype that improves access to learning. Explain the intended learner, the task they need to complete, and the barrier your project addresses. Build your event contribution during October 17–November 20, 2026; clearly identify any pre-existing foundation.

## Submission package (overview page)

1. Project page: name, short pitch, every contributing team member.
2. The learning story: problem, intended users, solution, tools, challenges, what we learned. Must include one concrete before-and-after example.
3. Something to evaluate: a working demo link, downloadable build, or recorded walkthrough of core functionality, plus simple setup instructions and a description of limitations.
4. Visual evidence: screenshots. "A short 2–3 minute demo video is encouraged, but optional; if used, provide captions or a transcript where possible."
5. Transparent credits: link source code or project files where possible, and disclose libraries, datasets, assets, AI assistance, and pre-existing work.

Video length: optional, 2 to 3 minutes if provided, with captions or a transcript. Our demo script targets 2 minutes 30 seconds so it sits inside that band.

Repo: "link source code or project files where possible". Not strictly mandatory, but the rules reward verifiable claims, so the repo will be linked at submission time.

Description fields: Devpost's standard story fields; the rules ask that the story cover problem, users, solution, tools, challenges, learnings and a before-and-after.

## New work during the event

* "Identify work created during the event and distinguish it from pre-existing work."
* "Build your event contribution during October 17–November 20, 2026; clearly identify any pre-existing foundation."

Padi was started from an empty repository on 4 Nov 2026, inside the window. Every line of project code is event work. Pre-existing foundations are third-party open source components only (Tesseract and its trained models, the operating system voices, Python libraries), and they are listed in the README credits.

## Entering the same project elsewhere

The overview, rules and resources pages say nothing about submitting the same project to another hackathon. The only related rule is "Submit one final entry per project", which limits entries within this event. We will not assume permission: if Padi is ever entered elsewhere, check that event's rules first, and do not enter it in any other event before the AccessED results are published.

## Data and content rules

* "Use synthetic or permission-cleared examples; do not upload private educational records or identifiable learner data."
* "Credit third-party work and AI assistance. Only use material you have permission to use."
* "Do not require judges to provide private personal information to test a demo."
* Overview adds: "Do not submit private student records, real grades," and then the sentence is cut off on the live page ("real grades, November 22."). We read it as also excluding identifiable learner data.
* Resources page: "Use made-up learner data."

Consequences for Padi: the learner in DESIGN.md is a made-up person; the evaluation pages are typeset by us from public-domain Tamil and English text unless a textbook licence clearly permits reuse; no login, no personal data, no network calls.

## Judging criteria

Four criteria, equal weight, each scored 1 to 5, ranked by total. Ties broken by Barrier Removed, then Learning Value, then judges' comparison. "Unverifiable claims and nonfunctional core features may reduce scores."

| Criterion | What the page asks | How Padi answers it |
|---|---|---|
| Barrier Removed | "Does the project identify a specific obstacle to learning and show a credible improvement for the intended learner? Reward a clear before-and-after and thoughtful understanding of real constraints." | One named learner, one obstacle (a printed Tamil textbook page she cannot read), before and after shown on the same page. Real constraints: no internet, shared old laptop, Tamil script. |
| Learning Value | "Does the prototype help someone understand, practice, teach, or reach useful learning material? Assess educational relevance, clarity, and a concrete learning task rather than unsupported claims of better outcomes." | Concrete task: read a lesson page and answer its numbered questions. No claims about grades. |
| Inclusive Experience | "Does the design meet the intended learner's needs through readable content, clear language, keyboard access, alternative formats, or low-bandwidth use? Assess relevant choices and honest testing evidence." | Semantic HTML, lang tags per line, font size and dyslexia-friendly controls, audio with sentence highlighting, fully keyboard operable, offline. Automated accessibility check results and manual keyboard and VoiceOver notes are published with their limits. |
| Working Prototype and Explanation | "Does the core learning task work? Assess functionality, thoughtful implementation, and a clear demo that explains event contributions, credits, and limitations. Technical complexity alone earns no bonus." | README that runs as written, pytest suite, measured OCR accuracy and timing, limitations section, credits section. |

## Resources page guidance we follow

* Finish the sentence "A learner wants to ___, but ___ gets in the way." (done in DESIGN.md)
* Make the task demonstrable in two minutes.
* Test: keyboard completion, information not relying on colour or audio alone, understandable labels, behaviour on a slow connection or small screen or shared device, evidence the learner can do something useful.
* "Do not claim universal accessibility from a single test."
* Demo outline: introduce learner and barrier, show the original difficulty, demonstrate the core task, explain what was built during the event, credit dependencies, name one limitation or next step.

## Prize

1st place: $225 cash. 2nd, 3rd and three runners-up: honorary recognition only.
