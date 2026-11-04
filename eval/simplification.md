# Simplification review

Model: gemma3:4b through Ollama on the same laptop, temperature 0, the prompts in `src/olivaasi/simplify.py`. Input: the prose paragraphs Olivaasi recognised from the phone-photo image of each page. Reviewed by the project author on 4 Nov 2026, reading every output against its original. The author reads Tamil, but no teacher has reviewed these, so this is a check of meaning and grammar, not of reading level.

## First prompt (loose: "rewrite for a ten-year-old")

| Page | What came back | Verdict |
|---|---|---|
| Thirukkural note (Tamil) | Spoken, colloquial Tamil (சொல்றாங்க, இருக்கு), and "more than 3300 kurals" for the book's 1330. Also an added claim that each kural teaches something good. | Wrong fact, wrong register. Unsafe. |
| Water cycle 2 (Tamil) | "Vapour that comes from the sky cools..." The vapour rises from below. | Wrong fact. Unsafe. |
| Water cycle 2 (English) | Short sentences, facts kept. | Acceptable. |

## Strict prompt (the one Olivaasi uses)

| Page | What came back | Verdict |
|---|---|---|
| Water cycle 1 (English) | One long sentence split in two. Nothing changed. | Good. |
| Water cycle 2 (English) | Three sentences split into six. Nothing changed. | Good. |
| Water cycle 1 (Tamil) | "Water on Earth is not stable" for "does not stay in one place", the fact that the vapour rises was dropped, and the last sentence is ungrammatical (இந்த ஆவியாதல் என்று அழைக்கப்படுகிறது). | Meaning changed. Unsafe. |
| Water cycle 2 (Tamil) | Nearly identical; drops "(Condensation)" and makes the last verb singular with a plural subject. | No gain, small grammar error. |
| Thirukkural note (Tamil) | Nearly identical, with one longer phrase. | No gain. |
| Plant box (Tamil) | "Leaves use sunlight. They make food. This is called photosynthesis." | Good. |

## Decision

Simplification is offered for English paragraphs only. Tamil paragraphs are left as printed, with a note on the page saying why: in this small test the model changed the meaning or grammar of three of four Tamil paragraphs, and a blind or low-vision student cannot easily spot such a change. Setting `OLIVAASI_SIMPLIFY_TAMIL=1` turns Tamil on for experiments.

Safeguards that stay on in all cases: only prose paragraphs are simplified (never questions, verse, tables or headings), a result with any number not in the original is dropped, a result much longer or shorter than the original is dropped, a near-copy is dropped, and every shown version is labelled "Simplified by computer" with the original one tap away.

Time on the M1 with 8 GB: 13 seconds to load the model the first time, then about 3 to 7 seconds per paragraph. While the model is loaded, speech for the same page took about twice as long (memory pressure), so the whole conversion took 15 seconds instead of 4.
