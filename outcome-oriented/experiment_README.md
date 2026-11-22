# One bounded prediction experiment

Start with the short [run checklist](./experiment_CHECKLIST.md).

Use the existing article library and extraction v2 checkpoint. The orchestrator
now caps the experiment at **100 distinct articles total: 76 baseline plus up to
24 fresh comparison articles**. This replaces the original full-library scope at
the user's request. It independently reviews the baseline, pauses for a
small human calibration, proposes **one** query revision, retrieves an unseen
comparison sample after approval, evaluates it with the same method, and stops.
It never checks historical outcomes or repeats optimization rounds.

From the repository root, these are the two commands you need:

```powershell
# Free, read-only preview; no credentials, downloads, writes, or API calls.
python outcome-oriented/prediction_experiment.py

# Run/resume the same experiment. $10 is a cumulative maximum, not a charge.
python outcome-oriented/prediction_experiment.py --run --budget-usd 10
```

Install dependencies with `python -m pip install python-dotenv impresso`. Put
`OPENAI_API_KEY` and `IMPRESSO_API_TOKEN` in the repository root's `.env`. Values
there override the environment. The latter is the Impresso bearer token; this
workflow does not prompt interactively or write credentials into SDK config.
Credentials are never included in checkpoints. No live calls were used to test
this implementation.

The default budget without an explicit flag is \$2. Increase it deliberately if a
budget stop occurs, then repeat your run command. Imported extraction v2 charges
count toward this cap. Prices follow the existing extractor: $0.10 input and
$0.50 output per million tokens for gpt-6-luna, without cache discounts. They are
estimates at those configured prices, not an account billing limit. The preview
estimates baseline work conservatively; future article sizes are unknown. Every
actual request needs its own pessimistic reservation under the common cap.

Optional **free local preparation** freezes the baseline and writes an initial
coverage report without starting any paid work:

```powershell
python outcome-oriented/prediction_experiment.py --prepare
```

The original inventory contained 341 eligible unique articles and 87 unavailable
transcripts. The baseline sample retains all already attempted eligible articles,
then deterministically fills to 76 across source languages and query groups.
The other 265 eligible articles are **deferred**, not negative or unavailable.
Their IDs remain frozen as already seen, so they cannot fill the fresh quota.
Changing the scope preserves prior paid extractions/reviews, their costs and raw
responses. The previous manifest is archived; `scope-changes.json` records the
change, and `library-manifest.json` lists the full original library and deferred IDs.
This remains an inventory, **not** an evaluated full-library baseline.
The older translation-only extraction directory is not imported. No historical
CSV decisions are overwritten.

## The two decisions

Files live in `outcome-oriented/prediction_sample/experiment/`, alongside a
report updated at each stop. This local directory contains private source text
and is ignored by Git. Keep a backup; never delete state to resume.

1. **Calibration:** after baseline extraction/review, open `calibration.json`.
   It has about eight cases: accepted claims, disputes/rejections, and at least
   two negative articles when available. Each case includes the exact quotation,
   normalized English statement, model recommendation, reason and full source
   text, so you need only this one file. Read the source for negatives, too.
   Fill `human_decision` with `accept`, `reject` or `flag` for claims, or
   `checked_negative`, `missed_prediction` or `flag` for negative articles.
   Rate at least six cases (all if fewer are available), then set
   `approve_method` to `true` and rerun. Unavailable case categories are explicitly
   reported rather than invented. You may add a case with an article ID and
   `human_decision` of `checked_positive`/`checked_negative` to resolve an article
   judgment after inspecting the full source. A checked positive still needs a
   supported accepted claim; conflicting human decisions stay unresolved.

   For a systematic problem, leave approval false and enter one set of
   `general_directions`. Rerunning creates `correction.json` containing the
   consolidated reviewer-rubric correction and its consequence. Review/edit the
   correction, set `approve: true`, and rerun twice: once to apply the correction,
   then to re-review. Raw extractions are reused, earlier review responses and
   charges stay in the ledger, and a replacement calibration packet is generated.
   Only one consolidated correction is allowed; after calibration the method
   stays frozen. A claim needing edited normalization is flagged, not silently
   rewritten or accepted under a different method.

2. **Query bundle:** open `query-approval.json`, inspect its rationale, per-language
   supporting article IDs/counts, unique positive contributions, and complete
   before/after fingerprints. Set `approve` to `true` and rerun. This updates the
   active seed definitions and proceeds with retrieval and comparison. The modest
   first tries replacing just the broad forecasting-frame slot with forecasting
   frames AND calendar/long-horizon cues. If that combination has no accepted
   support, it instead tries likelihood AND future/modal forms, replacing only the
   broad likelihood slot. Both likelihood and future/modal operands must occur as
   complete words/phrases in the same accepted quotation with reviewer-approved
   useful cues. Other slots and language allocations stay fixed. Only **one**
   supported bundle is presented; this is local proposal selection, not an extra
   retrieval round or optimization loop.
   It uses established topic-neutral operands, never automatically promotes new
   names, topical words, OCR accidents or generic verbs. Supported co-occurrence
   is a hypothesis for better yield; it does not establish recall. Zero or rare
   support is visible and does not silently remove a language or cue. If no
   accepted prediction supports either combination in any language, the workflow
   stops with an explicit unresolved refinement rather than inventing support.
   At the query-approval stage, `--prepare` can generate the packet for free; it
   never applies approved queries or starts retrieval.

   If you disagree, leave approval false and enter general directions in the
   packet; the workflow stays paused so the bundle can be revised with those
   directions. It does not invent an interpretation of a free-text direction.
   The `after_source` and its fingerprint must agree. A revised bundle can be
   prepared with your coding agent before approving it. Historical retrieval
   snapshots remain untouched. `query-change.json` preserves immutable before/
   after source and the approved rationale.

These are spot-checks, not proof that all automated judgments are correct. Results
are labeled **LLM-reviewed, with limited human validation**.

## Outputs and methodology

- `state.json`: atomic checkpoint, frozen baseline source text, prompt/schema/
  model settings, raw extraction and review responses, separate review judgments,
  input/output token usage, estimated charges, uncertain reservations, retrieval
  cache and stage. Requests are keyed by content and the complete model/prompt/
  schema/version configuration. Old v2 responses are validated and reused locally.
- `baseline-manifest.json`: explicit eligible article IDs, content fingerprints,
  dates, languages, retrieval-round/query-version associations and exclusions.
- `calibration.json`, optionally `correction.json`, and `query-approval.json`:
  the compact human decision packets, generated when their evidence is ready.
- `query-change.json`: immutable approved query source before/after and change log.
- `prediction_sample/rounds/experiment-<timestamp>/`: query snapshot, settings and
  references, using the existing retrieval-round layout so other scripts retain
  this provenance. Its path is saved in state. Refined provenance is also in
  `refined-manifest.json`, including primary unseen IDs, overlaps and hashes.
- `review-results.json`: machine-readable automated judgments, validated
  discoveries, effective decisions and their **human/automated** provenance.
  Existing explicit human CSV decisions and calibration overrides take precedence;
  revise/flag/missed/unavailable cases remain unresolved. Raw extractions are kept
  separate and are never rewritten as human-reviewed CSVs. Existing CSVs retain
  their day-only dates and absence of context/path columns.
- `report.md` and `report.json`: side-by-side baseline, unseen comparison and all
  retrieved statistics; query/language breakdowns; newspaper/decade composition;
  percentage-point yield change; costs, token counts, exclusions, overlap,
  shortfalls and recommendation. Empty/unavailable denominators are null.

The reviewer receives the **whole article and all original predictions together**,
independently checks eligibility, faithful normalization, dates, conditions,
negation and semantic duplicates, checks cues, and searches for omissions even in
extractor negatives. Review is a separate Responses API call, default gpt-6-luna.
Quotes and discoveries pass strict local schema, ID coverage, exact OCR substring,
600-character maximum and cue-evidence checks. The extractor's conservative
unique tiny-copying-difference restoration is reused; OCR is never edited.
Exact normalized-statement duplicates are checked locally as well as by the
reviewer. Separate distinct outcomes may share a quote.

For every cohort, **N** is articles with completed, usable reviews and no unresolved
claim flags/human conflicts; **A** is those with accepted distinct predictions;
**P** is their accepted distinct prediction count, including validated reviewer
discoveries. Python computes A/N, P/A and P/N. Original accepted/rejected and
additional discovered counts in these statistics refer to articles in N. All
judgments, including provisional claims outside N, remain available as evidence.
Failed, pending, unreviewed and unresolved articles never enter N as negatives.
`reviewed` means usable review, while `review_completed` includes unresolved
completed reviews. `failed`, `unresolved` and `unreviewed` describe coverage and
can overlap: they must not be summed as exclusive partitions.

Overall totals deduplicate article IDs. Query breakdown keys contain retrieval
round, immutable seed fingerprint and query ID; overlapping subtotals are **not
additive**. Source language, source/newspaper (ID prefix) and publication-decade
composition are retained. Small strata are descriptive, not reliable estimates.
No recall or causal effect is claimed.

## Limits and recovery

Defaults retain the existing downloader's fr/de/en allocation and search bounds,
but reduce the quota to **two unseen articles per query, at most 24 total**.
There are at most five pages per query, 20 hits/page within the first 5,000
ID-sorted matches, minimum 200 available transcript characters. A deterministic
new seed (44) is frozen. `--max-articles` defaults to 100 and
`--comparison-articles` to 24; their difference is the baseline allowance.
All previously attempted eligible articles must fit that allowance. A scope
change is allowed only before calibration; it cannot discard paid attempts.
Use `--per-query`, `--min-chars`, `--search-limit` and
`--fetch-limit` when first creating an experiment to change these. Retrieval limits
default to 1,500 reserved search-result items and 300 article fetches, cumulative
across restarts; count requests also consume limits. These limits are local
guardrails, not Impresso's account quota. Known cap exhaustion ends sampling with
explicit shortfalls; the comparison still runs on available evidence.

Overlap is recorded and cached extractions/reviews are reused, but **all original
library IDs**, including deferred articles, never fill the new-article quota.
Deferred overlaps are recorded without starting paid reviews on them. Queries
may overlap each other, so 24 is an upper bound, not a guaranteed unique cohort
size. The sampled baseline combines eligible articles from saved rounds, whereas the comparison is a fresh,
bounded retrieval: sample sizes/composition are inherently different. Shortfall
and incomplete-review results remain provisional.

Every LLM call and SDK search/fetch is durably reserved **before** sending.
Successful raw responses are saved before parsing and recovered locally on
resume. No automatic retries, model upgrades or uncertain-call replays occur.
Actual LLM usage settles reservations when returned; missing usage retains the
reservation even if evidence can be validated. Retrieval reserves requested
result capacity conservatively (even if fewer hits return); reports show actual
successful counts separately. The existing repository Impresso usage counter is
informational; experiment reservations enforce its own limits.

An uncertain request still stops for inspection, not another paid attempt.
An invalid quotation in a reviewer-discovered prediction now **flags that
discovery and article as unresolved**, preserving the review's other judgments and
the unchanged raw response. It never relaxes quotation checks, silently counts a
negative, or pays to retry. Other malformed saved evidence is retained as a failed
article while the batch continues; failures remain outside metric denominators.
`--prepare` recovers saved review responses locally, without paid calls, and
applies the smaller scope to the existing experiment. Rerun after fixing a purely
local validation/recovery issue; do not
delete a ledger entry to bypass billing uncertainty. If the provider response is
lost, this CLI intentionally has no retry switch. API outcomes need reconciliation
before any deliberate new attempt. Completed raw responses can be restored into
their existing ledger entry from a trusted saved copy without another request.

Only one runner may use an experiment directory. If the process is killed,
confirm no runner is alive and remove **only** `run.lock`; then repeat the run
command. Do not concurrently run the old extractor or downloader. Stop changing
prompts, prices and source data during an experiment. Frozen incompatible
configuration causes an explicit error. To use another reviewer, specify its
model and **both** prices initially and on resume, e.g. `--reviewer MODEL
--review-input-rate PRICE --review-output-rate PRICE` (USD per million tokens).
No automatic upgrades or price lookup occurs.

On Windows, another program may briefly lock a checkpoint during atomic file
replacement (`WinError 5`). Writes and replacements now retry locally up to eight
times, with bounded delays; API calls are never retried by this mechanism. If the
lock persists, close programs holding the checkpoint open and repeat the same
command. Keep both `state.json` and `state.tmp`. On restart, a newer valid temporary
checkpoint can recover cached responses and reservations before proceeding; an
incomplete or conflicting temporary file stops for inspection rather than losing
request history. A free preview reads recovery candidates without modifying them;
`--prepare` can save recovered state without network activity.

After the comparison completes, further `--run` invocations only regenerate the
report. They cannot retrieve another round or start a new optimization loop.

## Offline verification

```powershell
python -m unittest discover -s outcome-oriented -p "test_*.py"
```

Tests mock all paid APIs and cover cumulative budgets, uncertain reservations,
saved-response recovery, locking/state stages, full-baseline freezing, exclusions,
query versions, unseen quotas, overlaps, human overrides, discovery validation,
duplicate claims, zero/unresolved denominators and the bounded stopping rule.
