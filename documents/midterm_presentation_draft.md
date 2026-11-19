# Predictive statements in the historical press

## Presentation draft and speaker notes

This first draft turns the midterm outline into a nine-slide talk. Its central message is that the project can extract structured candidates at useful scale, while deciding which claims qualify and verifying their outcomes remain the main work ahead. The historical question is what people expected and where those expectations proved wrong. The resulting dataset could also support evaluation of language models with a historical knowledge cutoff.

The planned delivery is **9 minutes 30 seconds**, leaving 30 seconds for pauses and speaker transitions within a 10-minute speaking slot. Questions are assumed to follow the talk. The script contains the essential spoken content; optional material appears separately after the Copilot section. Presenter names, speaking assignments, and any completed manual outcome checks remain unconfirmed.

**How to use this document:** paste the section between BEGIN COPILOT INPUT and END COPILOT INPUT into PowerPoint Copilot. It contains the slide text, layout instructions, and spoken notes. Everything after that section is preparation material and should stay outside the deck. If Copilot does not retain the speaker notes, copy each notes paragraph into the corresponding PowerPoint Notes pane.

## Timing plan

| Slide | Subject | Duration | Cumulative time |
| --- | --- | --- | --- |
| 1 | Motivation and research goal | 1:10 | 1:10 |
| 2 | What makes a useful prediction | 1:05 | 2:15 |
| 3 | Search experiments | 1:15 | 3:30 |
| 4 | Article selection and LLM extraction | 1:20 | 4:50 |
| 5 | An extracted candidate | 1:05 | 5:55 |
| 6 | Current extraction scale | 0:55 | 6:50 |
| 7 | A suspected false positive | 1:05 | 7:55 |
| 8 | Verification and next steps | 1:05 | 9:00 |
| 9 | Conclusion | 0:30 | 9:30 |

---

## BEGIN COPILOT INPUT

Create a nine-slide presentation in English for a university digital humanities midterm project presentation. Follow the slide order and exact factual content below. The presentation has a 10-minute speaking limit; the supplied delivery plan totals 9 minutes 30 seconds.

Use the text under ON SLIDE as visible slide content. Treat LAYOUT as instructions for arranging the content, not as text to display. Put SPEAKER NOTES in the Notes pane, not on the slides. Do not add slides for the timing plan, references, or preparation tasks. Use restrained academic formatting, readable text, and generous spacing. Keep quotations legible and use editable PowerPoint text. No stock imagery or invented charts are needed.

Use only the supplied numbers and examples. Empty cells on slide 3 are intentional: leave them empty. Do not invent experimental results, outcome labels, costs, accuracy percentages, sources, or presenter names. Preserve the distinction between extracted candidates, human-validated predictions, and verified outcomes. A model's verifiability label is not evidence that an outcome has been checked.

### Slide 1 Predictive statements in the historical press

**Time:** 1 minute 10 seconds.

**Purpose:** introduce the historical motivation and connect it to the proposed language-model benchmark without spending a separate slide on a title or agenda.

**ON SLIDE**

Title: Predictive statements in the historical press

Subtitle: Extracting past expectations for historical analysis and AI evaluation

- What did newspapers expect to happen?
- Which predictions came true?
- Can these dated questions test models with historical knowledge cutoffs?

Bottom line: Dated claim → later evidence → verified outcome

**LAYOUT**

Combine the title and introduction on one slide. Give the three questions most of the space. Place the short sequence along the bottom as editable text. Avoid a separate decorative title slide.

**SPEAKER NOTES**

Our project starts with a historical question: what did people expect their future to look like, and how often were those expectations right? Newspapers preserve forecasts about elections, prices, public works, and many other subjects. Those statements record expectations that can disappear when we tell history only through what eventually happened.

We want to turn them into dated claims with outcomes supported by later evidence. That would let us study where expectations were accurate, including differences between topics and prediction horizons.

It could also produce questions for language models whose knowledge stops at a historical date. Starting with contemporary predictions helps us avoid choosing only events that became famous afterward. Our midterm work focuses on the first stage: finding and structuring usable prediction candidates.

### Slide 2 What makes a useful prediction

**Time:** 1 minute 5 seconds.

**Purpose:** establish the selection criteria that explain both the extraction difficulties and the remaining verification work.

**ON SLIDE**

Title: What makes a useful prediction

Selection criteria:

- An outcome still unsettled at publication
- Enough context and timing to interpret the claim
- An outcome that can realistically be checked

Illustrative examples, not newspaper quotations:

- Predictable event: “There will be a full moon next month.”
- Uncertain and testable: “Party A will win Sunday's election.”
- Uncertain but vague: “The winter will be harsh.”

Small note: Conditional claims need an explicit condition

**LAYOUT**

Use two simple text columns: criteria on the left and the three short examples on the right. Keep the illustrative-example label visible. The contrast between uncertainty and verifiability should be clear without requiring a chart.

**SPEAKER NOTES**

A future-tense sentence is only a starting point. For our purpose, the strongest candidates concern an outcome that was still unsettled when the article appeared, and that we can later check.

These examples show why selection is difficult. A full moon is predictable, so it contributes little to a benchmark of uncertain events. An election result is uncertain and usually has a clear outcome. A harsh winter may be interesting, but we need a location, a period, and a definition of harsh before we can judge it.

Conditional claims add another difficulty: if a party wins, it will introduce reforms. We must preserve that condition and decide how to handle cases where it never occurs. These criteria guide our filtering; the current extractor still accepts a broader range of announcements and scheduled events.

### Slide 3 What we learned from search cues

**Time:** 1 minute 15 seconds.

**Purpose:** explain the progression of methods while leaving the unavailable comparison data blank.

**ON SLIDE**

Title: What we learned from search cues

Introductory line: Preliminary observations from exploratory trials

| Search strategy | Observation | Reviewed yield |
| --- | --- | --- |
| Topic + strong future cues | Few candidates; mixed usefulness | |
| Strong future cues alone | Many irrelevant matches | |
| Weak future cues alone | Large volume; much noise | |
| Topic + weak future cues | More promising candidates; filtering still needed | |

Examples of cue vocabulary: strong “is expected to”; weak “will”; topic “election”

Takeaway: Search narrows the corpus; context helps decide whether a claim qualifies

**LAYOUT**

Use a compact table with four strategy rows. Keep the Reviewed yield cells empty. Put the vocabulary examples and takeaway below the table. Do not create a ranking chart, assign scores, or show a numerical winner.

**SPEAKER NOTES**

We first tried finding predictions through Impresso searches using topic words and expressions that suggest the future. Strong cues explicitly express expectation, such as “is expected to.” Weaker cues include general future markers such as “will.”

Our exploratory trials revealed a tradeoff. Combining topics with strong cues gave us few candidates, and their usefulness was mixed. Strong cues alone still returned irrelevant material. Weak cues alone widened the search substantially but introduced too much noise.

Combining topics with weaker cues looked more promising, although useful predictions still needed filtering. These are preliminary observations; the comparable reviewed yields are still missing, so we cannot claim a measured improvement.

This led to two promising directions: refine topic-based sentence filtering, and separate broad article selection from a second stage that reads the article's context. That second approach is the pipeline I will show next.

### Slide 4 Article selection and LLM extraction

**Time:** 1 minute 20 seconds.

**Purpose:** explain the two-stage method and the most consequential prompt requirements without displaying code or the full prompt.

**ON SLIDE**

Title: Article selection and LLM extraction

1. Select articles in Impresso using topic words and future cues
2. Give article text and publication metadata to an LLM
3. Extract structured candidates and validate the output schema

Prompt requirements:

- Retain a source quotation
- Make the English claim understandable on its own
- Resolve references and relative dates using article context
- Exclude irrelevant material; do not add later knowledge

Output fields: quote · statement · category · resolution date · predictor · confidence · verifiable

**LAYOUT**

Put the three numbered stages across the upper half. Below them, list the four prompt requirements. Place the output fields in a small, readable line at the bottom. Avoid a screenshot of code or a wide dataset table.

**SPEAKER NOTES**

The main change is to give search and extraction different jobs. Search collects potentially relevant articles. The language model then reads their text in context and identifies individual claims.

We provide publication metadata so that expressions such as “next year” can be interpreted relative to the article's date. The prompt asks for a source quotation and a standalone English statement, along with a category, a resolution date where possible, the predictor, expressed confidence, and a verifiability flag.

It also asks the model to exclude material such as fiction and advertisements and to avoid adding knowledge of what happened later. Long texts are split into parts. Output is requested as JSON and checked against a schema, which makes it easier to process consistently.

That check validates structure, however. It does not establish that a claim was extracted faithfully, that its date is justified, or that its outcome is true. Those require further review.

### Slide 5 An extracted candidate

**Time:** 1 minute 5 seconds.

**Purpose:** make the output concrete using an actual saved extraction, while distinguishing enrichment from outcome verification.

**ON SLIDE**

Title: An extracted candidate

Source: La Liberté · 20 February 1995

Original quote:
“Selon toute vraisemblance Kent Ruhnke sera à la bande mardi à Coire.”

Extracted English statement:
“Kent Ruhnke, coach of HC Olten, will be behind the bench on Tuesday 21 February 1995 in Chur.”

Metadata:

- Category: sport_events
- Resolution date: 1995-02-21
- Expressed confidence: likely
- Model verifiability flag: true

Status: Extracted candidate; outcome verification pending

**LAYOUT**

Put the original quote above the English statement so the audience can compare them. Place metadata below in a short list. Make the pending-verification status visible. Do not add an outcome or a success mark.

**SPEAKER NOTES**

Here is one candidate in the saved output, from La Liberté in February 1995. The French sentence says that Kent Ruhnke will, in all likelihood, be behind the bench on Tuesday in Chur.

The English version makes the claim more explicit: it names his club and gives an absolute date. This is what enrichment is meant to achieve: a statement that someone can understand without reading the whole article.

The metadata records “likely” as the confidence expressed in the source. That is different from confidence that the extraction is correct. Similarly, the verifiability flag means the model thinks the outcome could be checked; it has not checked it.

We still need to confirm the added context against the article and find later evidence of whether he was actually there.

### Slide 6 Current extraction scale

**Time:** 55 seconds.

**Purpose:** demonstrate concrete progress without presenting raw candidate volume as dataset quality.

**ON SLIDE**

Title: Current extraction scale

- 819 articles processed
- 3,473 prediction candidates extracted
- 415 articles produced at least one candidate

Scope of this saved batch: 1950–2018 · French and German

Status: Candidate extraction completed for this batch; human validation and outcome verification remain to be established

**LAYOUT**

Use three large, vertically arranged numbers with their labels. Put batch scope and status below them. No accuracy chart or quality percentage should appear.

**SPEAKER NOTES**

The saved batch contains 819 processed articles and 3,473 extracted candidates. Of those articles, 415 produced at least one candidate. These exact counts correspond to the roughly eight hundred articles and thirty-four hundred predictions in our working outline.

They demonstrate that the pipeline can generate structured material at useful scale. They do not tell us how many candidates satisfy our final definition or how many predictions came true.

The batch covers French and German material from 1950 to 2018. It is an extraction pilot. For a historical-model benchmark, we will need to choose dates that match the model's knowledge cutoff and ensure the outcomes being tested were still unknown to it.

### Slide 7 A suspected false positive

**Time:** 1 minute 5 seconds.

**Purpose:** show a specific semantic failure and explain why contextual review matters.

**ON SLIDE**

Title: A suspected false positive

Source: Le Peuple, La Sentinelle · 27 March 1958 · Le Locle

Extracted quote:
“la semaine de cinq jours ne sera pas introduite dans les classes primaires”

English reading: “The five-day school week will not be introduced in primary schools.”

- Future wording can report a decision already taken
- The team's reading: a decision report rather than an unsettled forecast
- Check the surrounding article before assigning the final label

**LAYOUT**

Make the quote the main element and place its English reading immediately below it. Use the three bullets to explain the classification issue. Do not label the statement historically true or false.

**SPEAKER NOTES**

This example exposes a limit of the current extraction. The sentence says that the five-day school week will not be introduced in primary schools in Le Locle. It uses future wording and was marked verifiable by the model.

Our working interpretation is that it reports a decision already taken, rather than predicting an unsettled outcome. The distinction depends on what the article actually says: reporting a decision and forecasting its implementation are different claims.

We should therefore confirm the surrounding passage before treating this as a definitive false positive. But it illustrates the central problem: plausible wording and well-formed metadata do not guarantee a useful prediction.

The next evaluation needs explicit acceptance rules and a manually reviewed sample. That will tell us which errors are common enough to guide changes to the prompt and filters.

### Slide 8 Verification and next steps

**Time:** 1 minute 5 seconds.

**Purpose:** identify a concrete route from candidates to the intended historical dataset and benchmark.

**ON SLIDE**

Title: Verification and next steps

1. Review candidates against an agreed prediction definition
2. Find later evidence and record sourced outcomes
3. Analyse prediction accuracy by topic and horizon
4. Generate questions for a model with a suitable historical cutoff

Start with a small, verifiable subset

Brief's midterm target: 200 extracted statements; 50 outcomes checked by hand

**LAYOUT**

Use a numbered list in the main area. Place the suggested starting point and the brief's milestone below it. Label the milestone as a target, not as an achieved result. Do not add a completed-check count.

**SPEAKER NOTES**

The main missing component is evidence for outcomes. First, we need to review candidates against a consistent definition. Then we can search later newspapers or other suitable records and store the evidence behind each outcome label. Cases without enough evidence should remain unresolved.

A practical next step is a small subset with clear events and dates, such as election results or infrastructure openings. That would let us test the verification process before expanding it.

The project brief asks for two hundred extracted statements and fifty outcomes checked by hand at the midterm milestone. Candidate volume alone does not establish that milestone.

Once verified, the data can support accuracy analysis by topic and horizon. We can then turn suitable claims into questions for historical models, keeping later evidence out of their inputs.

### Slide 9 Conclusion

**Time:** 30 seconds.

**Purpose:** leave the audience with the current contribution and the next decisive task.

**ON SLIDE**

Title: Conclusion

- Historical predictions preserve expectations before outcomes were known
- Article selection plus LLM extraction produced 3,473 candidates in this batch
- The next milestone is a reviewed subset with sourced outcomes

Closing line: A benchmark needs verified outcomes as well as dated questions

**LAYOUT**

Use a plain summary slide with three bullets and one closing line. Keep it on screen for questions. Do not introduce new results or another example.

**SPEAKER NOTES**

Historical newspapers give us access to expectations before their outcomes were known. We now have a pipeline that selects articles and extracts structured candidates, with more than three thousand in the saved batch.

The next milestone is a carefully reviewed subset with sourced outcomes. That is what will turn this extraction work into evidence for historical analysis and a credible benchmark for language models.

## END COPILOT INPUT

---

## Preparation notes outside the Copilot input

### Missing information and next steps

The blank entries below are deliberate. The spoken draft works without filling them; the next iteration should replace preliminary descriptions with evidence where available. Do not interpret a blank count as zero.

| Priority | Task | Information still needed | Value or result | Affected slides |
| --- | --- | --- | --- | --- |
| Before presenting | Confirm audience and speaking format | Instructors and classmates or another audience; one presenter or shared delivery; whether questions occupy the 10 minutes | | All |
| Before presenting | Establish manual validation status | Number of candidates reviewed; number of outcomes checked; acceptance criteria; sources; true, false, and unresolved counts | | 6, 8 |
| Before presenting | Recover comparable cue experiments | Search settings, code version, dates and languages, number of articles inspected, candidates retrieved, number reviewed and accepted for each strategy | | 3 |
| Before presenting | Expand Samuel's method description | Exact retrieval and local filtering steps used in the run being presented; relation between saved script and result version; one representative accepted example | | 3 |
| Before presenting | Verify the positive candidate in context | Original article for the Kent Ruhnke example; support for club and date; whether later evidence is available | | 5 |
| Before presenting | Verify the suspected false positive in context | Original Le Locle passage showing whether it reports a settled decision or forecasts future implementation | | 7 |
| Before presenting | Agree the final prediction definition | Treatment of scheduled events, announcements, uncertainty, conditional claims, missing dates, and vague claims | | 2, 4, 7 |
| Before presenting | Confirm the reported extraction run | Whether the current saved batch is the intended midterm snapshot; model and prompt version used; agreement on counting units | | 4, 6 |
| Before presenting | Rehearse aloud | Actual delivery time, slide 3 readability, pronunciation, and speaker handoffs | | All |
| Next iteration | Select the benchmark's historical setting | Target model, training cutoff, prediction publication window, and outcome window | | 1, 6, 8 |
| Next iteration | Design a manual audit | Sampling procedure, sample size, annotation rules, disagreement resolution, and error categories | | 7, 8 |
| Next iteration | Build outcome verification | Evidence sources, search procedure, outcome labels, unresolved status, and handling of conditions | | 8 |
| Next iteration | Create benchmark questions | Atomic claims, faithful question wording, answer labels, preserved conditions, and prevention of later-information leakage | | 8 |
| Optional for this talk | Confirm cost estimates | Billing or run logs supporting approximately $1 exploration and $4 extraction; scope, model, tokens, and whether retries are included | | Optional material |

**What to bring for the next iteration:** the cue-experiment counts and examples; the number and results of any manual outcome checks; the original context for slides 5 and 7; the agreed inclusion policy; and the target model or historical period. Even a small reviewed sample is more useful than an unsupported overall quality estimate.

### Recovering the experiment comparison

For each of the four strategies on slide 3, record these fields together:

| Strategy | Code or run version | Articles inspected | Candidates retrieved | Candidates reviewed | Candidates accepted | Acceptance rate among reviewed |
| --- | --- | --- | --- | --- | --- | --- |
| Topic + strong cues | | | | | | |
| Strong cues alone | | | | | | |
| Weak cues alone | | | | | | |
| Topic + weak cues | | | | | | |

Compute acceptance rate only as accepted candidates divided by reviewed candidates under the same definition. Report retrieval volume separately. These figures do not establish recall unless a suitable reference set of predictions exists. Differences in period, language, topic mix, or filtering should be stated before comparing runs.

The older experiments are intentionally left for the next iteration. The repository history was inspected only to identify that earlier trials exist; no historical performance figure has been promoted into this draft. The current topic-filter script describes itself as version 3 and names a version 3 output, while the checked-in result is named version 6. Match the actual run before describing its results as if they came from the present script.

### Content choices for the ten minute limit

The talk gives roughly two minutes to motivation and definitions, then spends most of its time on methods, a concrete output, and evaluation. The introduction shares the first slide with the title. There is no agenda slide, separate taxonomy slide, full prompt screenshot, or exhaustive schema table.

The current batch counts replace the rounded counts in the outline. Historical accuracy, extraction precision, and number of verified outcomes remain unreported because the inspected files do not establish them. The qualitative cue comparison remains explicitly preliminary.

The fact-based alternative is kept for discussion. It is a useful methodological comparison, but explaining both dataset-building routes fully would crowd out the current extraction work. Costs are also kept outside the main talk until their scope is confirmed. No claim that this project has improved modern forecasting ability is made; that remains a downstream motivation, not a demonstrated result.

The illustrative England–Spain 1954 World Cup example from the source outline is omitted because its specific historical setup is unsuitable as a factual example. The generic election sentence on slide 2 is explicitly illustrative. Slide 5 uses a saved extraction and is labelled as a candidate rather than a validated success.

### Optional speaking material

Use these only in questions or by replacing existing material, rather than adding them to the timed script.

**Prediction-based versus fact-based construction — about 25 seconds**

“We could also start with reports of completed events and construct earlier questions from them. That might make outcome collection easier, especially when an article explicitly says the result was unexpected. But it risks selecting questions through hindsight. Extracting contemporary forecasts gives us direct evidence that someone expressed an expectation at the time, although it makes outcome verification harder.”

**Cost and scaling — about 20 seconds, after confirming the figures**

“Our working estimates are about one dollar for exploration and four dollars for extraction, although the scope still needs checking. Outcome retrieval may cost more because each claim needs supporting evidence. We plan to begin with clearly verifiable events and measure cost per verified item before scaling.”

Do not present the estimates as audited costs, or claim verification cost scales linearly. That is a design goal requiring measurement.

**Conditional predictions — about 20 seconds**

“For a conditional forecast, we need to check whether the condition occurred as well as whether the predicted consequence followed. If the condition never happened, we should not count the case as an ordinary correct or incorrect forecast. We can keep those claims separately until we agree on an evaluation policy.”

**Language-model cutoff — about 25 seconds**

“A modern model may already know historical outcomes, so asking it old questions is not automatically a forecasting test. The model's training cutoff, the date of the question, and the outcome date must be compatible. Later evidence belongs in the answer key, not in the information the model receives.”

**Scope and representativeness — about 20 seconds**

“The data records expectations expressed in the selected press. Those are evidence of what particular newspapers and quoted people expected; they do not represent every member of society. Search cues, languages, topics, and archive coverage also shape the sample.”

### If questions are included in the ten minutes

Use a shorter speaking target of approximately eight minutes. Retain the nine-slide sequence but reduce the timing to 55, 55, 55, 65, 50, 45, 55, 65, and 30 seconds respectively, totalling 7 minutes 55 seconds. Shorten slide 3 to the search tradeoff and emerging methods; describe only the main prompt requirements on slide 4; trim the conditional discussion on slide 2 and the metadata explanation on slide 5. Rehearse the shortened script before using that schedule.

## Source and evidence notes

These references are for preparation and speaker-note traceability. They are not an extra slide. Source state checked on 11 November 2026. The primary outline was already modified in the working tree and has been left untouched.

| Source | Use in the draft | Limits |
| --- | --- | --- |
| [midterm_pres.md](./midterm_pres.md) | Primary narrative; motivation; qualitative cue findings; two promising methods; suspected false positive; outcome and question-generation gaps; reported cost estimates | Outline, not a controlled experiment report; missing comparison figures intentionally remain blank |
| [Project description PDF](C:/Users/mo2fr/OneDrive/Desktop/EPFL/Semester_1/DH-405_Foundations_of_Digital_Humanities/Predictive_statements_project_description.pdf) | Historical expectations; verified outcomes; accuracy by category and horizon; midterm target of 200 extracted statements and 50 checked by hand; link to vintage models | General reference; the brief's talkie-1930 example concerns predictions before 1931, while the saved extraction batch here covers 1950–2018 |
| [prediction_definition.md](./prediction_definition.md) | Uncertainty, context, atomic claims, and conditional predictions | Working conceptual notes; the current extraction prompt includes a broader set of scheduled events |
| [roadmap.md](./roadmap.md) and [structure.md](./structure.md) | Verifiable categories; candidate metadata; outcome collection | Plans and proposed structure, not proof of completed verification |
| [download_articles.py](./llm/download_articles.py) | Topic and future-cue article selection; multilingual configuration; sampling across topics and years | Current code configuration does not prove the exact settings used for every saved article |
| [extract_predictions.py](./llm/extract_predictions.py) | Prompt requirements; JSON output; schema checks; seven extraction fields; chunking of long texts | Current prompt is not necessarily the precise prompt used for every saved record; `statement` is an enriched claim, not a verified outcome |
| [extractions.jsonl](./llm/extractions.jsonl) | 819 records with 819 unique article IDs; 3,473 nested prediction candidates; model recorded as deepseek-flash; batch scope | Counts of saved output; no manual acceptance rate or historical accuracy is established |
| [predictions.csv](./llm/predictions.csv) | 3,473 rows from 415 distinct article IDs; exact quoted examples and metadata | Flat export of candidates; 1,498 rows have no resolution date; verifiability is a model-assigned flag |
| [extract_candidates.py](./topics_first/extract_candidates.py) | Examples of strong future cues and sentence extraction | No comparable reviewed yield inferred from this file |
| [extract_topicted_cues.py](./topics_second/extract_topicted_cues.py) | Topic-first retrieval and local future/outcome filters | Version/run alignment with [prediction_candidates_v6.csv](./topics_second/prediction_candidates_v6.csv) needs confirmation |

### Counting and interpretation details

- The 819 records include 404 articles with no extracted candidate. The 415 articles with candidates are therefore a subset of the 819 processed articles. Neither count is a precision measure.
- The batch contains 714 French and 105 German article records. Its earliest publication date is 16 February 1950 and its latest is 20 January 2018. The broader downloader supports other languages and years; those settings should not be substituted for the actual batch scope.
- The 3,473 count is a count of exported candidates. It has not been established as the number of unique events or human-accepted predictions. Multiple claims can come from one article, and related claims can recur across articles.
- The current prompt permits correction of obvious OCR errors in quotations. Describe them as source quotations, not guaranteed character-for-character transcriptions. Confirm context against the original article before using a record as a validated example.
- A `resolution_date` is when an outcome should be knowable. A `statement` is the contextualised predicted claim. Neither field records what actually happened.
- The original articles themselves are not present in this checkout. The quotation examples were checked against the saved extraction export, not against the complete original newspaper text.
