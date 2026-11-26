# Step 3: prediction extraction pilot

For the bounded baseline → calibration → one query revision → fresh comparison
workflow, use [the experiment orchestrator](./experiment_README.md). It reuses
extraction v2, targets at least 100 eligible articles per cohort, independently reviews results,
and provides one preview command and one run/resume command with a common budget.

This script uses `gpt-6-luna` through the OpenAI Responses API. Install its only
dependency with `pip install python-dotenv`. Put `OPENAI_API_KEY=your-key` in the
repository root's `.env` file (already excluded from Git). This file loads
automatically regardless of your working directory; its values take precedence
over existing environment variables. Without that file, an existing environment
key still works. It reads the saved article
JSON files, not search snippets, and never downloads articles or verifies outcomes.

From the repository root:

```powershell
# Free preview: deterministic selection, one article per query/language first.
python outcome-oriented/extract_sample_predictions.py --output outcome-oriented/prediction_sample/extraction_v2

# Revised 12-article pilot, separate from the original translation-only pilot.
python outcome-oriented/extract_sample_predictions.py --run --output outcome-oriented/prediction_sample/extraction_v2

# AFTER reviewing the pilot: process the remaining unattempted articles.
python outcome-oriented/extract_sample_predictions.py --run --limit 208 --output outcome-oriented/prediction_sample/extraction_v2
```

The pilot selection covers the available query groups; it is not a representative
random sample of the archive. Articles shared by queries still receive one call.
The complete article, publication date, target definition and extraction prompt
are submitted together. Existing cue vocabularies are compared locally without
additional LLM calls. One response supplies all
predictions, self-contained English statements, eligibility reasons and linguistic
cues. A statement names subjects from the article and resolves relative dates when
the evidence permits; it is not a literal translation or an outcome verdict.
Attribution and uncertainty are kept in `predictor` and `confidence`. Negation,
conditions and thresholds stay in the statement. No deadline is invented.
Quotations are limited to 600 characters and are saved as exact OCR substrings,
as is cue evidence. A unique near-exact source span can restore a tiny copying
error (one character for 25–99-character quotes, at most two for longer quotes).
This restores the original OCR rather than correcting it. Ambiguous or larger
differences still fail validation, and the original model response is retained
in the checkpoint. Overlong quotes cause an error rather than being cut off.
Context and local file locations are not included in CSVs. Publication dates use
`YYYY-MM-DD`. Full source text remains in the checkpoint for reproducibility.

## Replace unavailable transcripts before scaling

In the original 208-article library, 87 transcripts are only `[REDACTED]`.
These are unavailable data, not evidence that a query found no predictions.
Both scripts now require at least 200 available transcript characters after
trimming whitespace, and always exclude the `[REDACTED]` marker. The downloader
checks cached files too; invalid cached files are retained for the historical
record but are not counted in the new round. The extractor also skips them, so
old files in the shared library cannot silently re-enter the LLM batch.

Run a fresh retrieval round before scaling extraction:

```powershell
python outcome-oriented/download_articles.py --min-chars 200 --seed 43
python outcome-oriented/extract_sample_predictions.py --min-chars 200 --output outcome-oriented/prediction_sample/extraction_v2
```

The different seed samples different pages; valid existing articles can still be
reused. Each round records the minimum and seed in `settings.json`, eligible
associations in `references.csv`, and short/redacted rejections in `skipped.csv`.
The downloader continues searching after a rejection within its existing five-page
limit, so it may still return fewer than 20 valid articles per query. Size is a
pragmatic availability filter, not a guarantee of readable or unrestricted text;
it also excludes genuinely short articles. Change `--min-chars` in both scripts
if you need a different cutoff. Extraction scans the eligible shared library across
all saved rounds, not exclusively the most recent round.

## Review files

Outputs live in the selected `--output` directory (`prediction_sample/extraction/`
by default; use `extraction_v2` for the revised prompt):

- `predictions.csv`: one row per prediction, with short exact quotation, normalized
  English `statement`, predictor, confidence, publication date, article ID and
  retrieving query IDs.
- `articles.csv`: every attempted article, including explicit negative reasons,
  query IDs, completion/error status, token usage and cost. An error or pending
  request is **not** a negative; its prediction count is blank.
- `cue_candidates.csv`: generalized operands, AND/OR operator, observed evidence,
  source language, existing/new operands and distinct supporting article counts.
  Support counts are model suggestions until the linked predictions are reviewed.
- `checkpoint.json`: full source text, fixed configuration, raw API responses,
  usage and results. This is the resumable source of truth; keep it private along
  with your article data. It contains no API key.

Review the three CSVs, using `review_decision` and `review_notes`:

| File | Suggested decisions | What to check |
| --- | --- | --- |
| `predictions.csv` | `accept`, `reject`, `revise` | Eligibility, exact quote, statement meaning, dates and conditions. Describe needed corrections in notes. |
| `articles.csv` | `checked_positive`, `checked_negative`, `missed_prediction`, `unavailable` | Read the article, especially model negatives; note missed quotes and redacted/unusable text. |
| `cue_candidates.csv` | `accept`, `reject`, `revise` | Topic-neutral wording, linked accepted predictions, useful search combination, duplication of seeds. |

Decisions are annotations, not executable instructions. On a resumed run, the script
preserves these two columns for matching IDs, but it does **not** change the prompt,
retry rejected results, train the model, recalculate cue support from accepted-only
claims, or edit queries. Cue support counts remain raw model counts. Other manual
CSV edits do not survive export; use review notes for proposed corrections and a
separate corrected copy if you add missing predictions. Quotation checks establish
textual fidelity, not that the model's interpretation is correct.

Once review is complete, request application of the reviewed cues (for example,
"Apply the accepted cues from extraction_v2 and summarize query quality"). That is
a separate step: inspect linked prediction decisions and article notes, exclude
unavailable articles from precision denominators, and edit the active
[seed-query file](./impresso_prediction_seed_queries.py) with approved changes.
Keep the original round snapshots unchanged. Then download a new small round with
those queries and evaluate its additional yield. If the extraction prompt needs
fixing, make those changes and validate another pilot before continuing at scale.

## Cost and resuming

Requests run sequentially, with low reasoning effort, a 6,000-token output limit,
no tools and no automatic retries. All attempted IDs are skipped on subsequent
runs, including negative, error and pending results. Each paid response is saved
before proceeding, including incomplete or invalid responses. Errors stop the run.

The default $0.25 budget is cumulative for the output directory, not per invocation.
Before each call the script reserves a pessimistic input bound (serialized request
UTF-8 bytes plus framing allowance) and the full output allowance. Afterward it
settles using reported input/output tokens. Unknown outcomes retain the reservation
and are skipped so a restart cannot silently pay again. Do not run two instances
against the same output directory. Do not delete checkpoints to resume.

Estimates use standard prices of $0.10 input / $0.50 output per million tokens,
checked 2026-11-21 against the [official model page](https://developers.openai.com/api/docs/models/gpt-6-luna).
No cached-input discount is assumed. These are local guardrails at those rates,
not an account billing limit; taxes, other applications and future price changes
are outside their scope. The free preview shows the selected batch's upper estimate.
Increase `--budget-usd` explicitly if needed. The output limit can truncate a dense
article: this is recorded as an error, never silently treated as no predictions.

If a request fails, inspect the raw response and reservation first. There is no
retry switch: avoid unintentionally rebilling uncertain requests. To deliberately
rerun a pilot after refining the prompt, use a new `--output` directory and budget.
An HTTP 401 means the configured key was rejected; fix the key in `.env` and use
a fresh output directory for the pilot (for example `--output
outcome-oriented/prediction_sample/extraction_pilot`). A failed request does not
establish any negative extraction result. Unknown billing still retains a local
reservation; `charged_or_reserved_usd` is deliberately not a billing receipt.
Changes to the definition, prompt, minimum-size filter or model configuration are
detected and require a new directory so results are not mixed. The configuration
is saved in each checkpoint; keep it fixed for comparable retrieval rounds.
Changing only the search vocabulary does not invalidate extractions. Reuse the
same revised output directory after future retrieval rounds: existing article IDs
are skipped, their query associations are refreshed, and only unseen eligible
articles need paid calls. Existing/new cue operands are compared against the
current seed vocabulary when CSVs are exported.

## Turning cue findings into query updates

1. Accept/reject the linked predictions first. Reject cues based on rejected claims,
   topical content or OCR accidents. Review the original-language evidence.
2. Prioritize cues supported by multiple distinct accepted articles. Check
   `new_operands` against the current seed file; an existing operand may still
   suggest a useful new combination. Case-insensitive string comparison is only
   a convenience, not a semantic novelty check.
3. Add approved operands to the appropriate vocabulary in
   [impresso_prediction_seed_queries.py](./impresso_prediction_seed_queries.py).
   Test novel AND/OR combinations as separate, uniquely named query families.
   Start broad cues such as modals in combination with temporal/forecast frames.
   Keep the previous retrieval round's `seed_queries.py` snapshot unchanged.
4. Retrieve another small batch. Compare manually confirmed article-level precision
   (accepted positive articles / reviewed articles), prediction yield, overlap and
   additional unique positive articles per query. Use `articles.csv` for negatives
   and query attribution; exclude unchecked/error/pending records from denominators.
   Associations record retrieval, not every query that could match an article.
5. Retain cues that add useful predictions across topics. Do not remove a rare cue
   solely for low pilot frequency or call retrieval yield recall. Independent
   randomly sampled articles are needed to evaluate recall (roadmap step 4).

No seed queries are changed automatically. Cue proposal and review require no
extra LLM calls. Offline guardrail checks:

```powershell
python -m unittest discover -s outcome-oriented -p test_extract_sample_predictions.py
```
