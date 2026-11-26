# One prediction comparison

Use **prediction_experiment.py** as the entry point. It defaults to a free,
read-only preview. It reuses saved articles and paid responses, independently
reviews extraction with the frozen method, applies the single approved query
change and stops after the comparison. It never resolves historical outcomes.

The corrected scope is **at least 100 eligible articles per cohort**. All compatible
attempted/processed work is retained even if a cohort exceeds its target. Eligible
selection is separate from successful extraction and completed usable review.
Failed, pending and unresolved articles never become negative observations.

## Install and configure

Python 3.10+; standard library plus the two pinned direct dependencies:

```sh
python -m pip install -r outcome-oriented/requirements.txt
```

Copy the entries in [.env.example](./.env.example) to the repository root `.env`.
Use `OPENAI_API_KEY` and `IMPRESSO_API_TOKEN` (a bearer token). No interactive login
is used. Root `.env` values override environment variables. Never commit credentials.
Commands below work from the repository root; defaults resolve from the script,
so another working directory is also supported using the script's full path.

```sh
# Free preview: no writes, credentials or network.
python outcome-oriented/prediction_experiment.py

# Local recovery, additive scope migration, manifests, CSVs and report; no network.
python outcome-oriented/prediction_experiment.py --prepare

# Run/resume within the saved Impresso caps and a cumulative $2 LLM cap.
python outcome-oriented/prediction_experiment.py --run --budget-usd 2
```

Do not run the last command until the offline preparation is reviewed. The saved
300-fetch cap is exhausted, so it cannot complete fresh retrieval. Limits never
increase implicitly. After explicitly approving a larger cap, pass `--fetch-limit`
and/or `--search-limit`; these are **cumulative**, including the original attempt,
and their changes are recorded. A preview with those flags only previews a change.
`--budget-usd` is cumulative across imported extraction and all LLM stages. It
controls pessimistic per-request reservations, not account billing. Frozen token
prices remain $0.10 input / $0.50 output per million tokens, with no cache discount.
Unknown transcript sizes prevent a guaranteed advance estimate of final cost.

Run paid work in **Terminal -> New Terminal** in VS Code to see its output. For
unbuffered progress on Windows, use:

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -u outcome-oriented/prediction_experiment.py --run --budget-usd 3 --fetch-limit 450
```

These are the approved cumulative limits for the current comparison. The report
updates at preparation, completion or a stop; it is not a live activity indicator.
Do not assume an agent tool session will survive the end of a chat turn. Do not
start a second runner. After an interrupted process is confirmed absent, remove
only its stale lock and resume. A saved pending article request without a response
is skipped with its reservation retained, stays outside usable-review totals, and
is never replayed automatically; remaining articles can continue. Failed requests
without saved responses still require inspection.

## Existing approval and migration

The saved calibration and query approval remain valid; **do not repeat calibration**.
The approved change is only `LIKELIHOOD AND MODALS_OR_FUTURE_FORMS`, replacing the
broad likelihood family. All other families and the extraction/review method stay
frozen. The approval was supported by four accepted articles across fr/de/en.

The additive `per-cohort-v1` migration keeps checkpoint format version 1. It records
the previous settings and cohort IDs, keeps every attempted article, fills the
initial cohort deterministically from the frozen library, and reopens only the
comparison extension. The original bounded attempt is copied to
`experiment/history/bounded-attempt/` before promotion. No ledger, raw response,
human decision or approved before/after source is removed. A separate extension
retrieval directory preserves the original round snapshots. Repeating prepare or
resume does not repeat migration or launch another query-optimization round.

All 341 originally eligible IDs **and the 87 original exclusions** remain already
seen. Deferred eligible library articles cannot fill the fresh quota. Initial
selection retains the previous 76 and balances additional selections by language;
the retained historical query associations remain inspectable. Fresh retrieval
alternates across language/query streams with nine accepted unseen associations
per cell by default (12 cells), stopping once 100 unique eligible articles exist.
Overlapping associations do not count as new articles. If cells exhaust their pages,
unused quota is shared among remaining cells one article per cell at a time,
without changing seeds, queries, page limits or the result window. Original
per-cell shortfalls and actual composition remain visible; the target can still
fall short when availability or cumulative limits prevent completion.

The local audit found **292/300 fetched responses redacted**: all 292 were marked
private (`access.dataDomain=prt`); eight were public and readable. The extension
skips private search hits before a fetch, retaining exclusion reasons. Public
metadata is not proof of eligibility; full transcript validation still applies.
This availability screen changes sampling composition and is disclosed in reports.
Search remains within five shuffled pages, 20 hits/page, the first 5,000 ID-sorted
results and minimum 200 transcript characters. Cached search/fetch results are
reused; search snippets never substitute for OCR transcripts.

For a *new* experiment, the same CLI pauses for two packets: `calibration.json`
(at least six cases, then `approve_method: true`) and `query-approval.json`
(`approve: true`). See packet reasons and source evidence before approving.
Existing claim overrides use accept/reject/flag; article overrides use
checked_positive/checked_negative/missed_prediction/flag. Explicit saved human
choices take precedence; conflicts and unsupported evidence remain unresolved.

## Read the results

The short [checklist](./experiment_CHECKLIST.md) links outputs. Under
`prediction_sample/experiment/`:

- `initial_predictions.csv`, `refined_predictions.csv`: **accepted distinct claims
  in usable-reviewed articles only**; their row counts equal P.
- `initial_review_cases.csv`, `refined_review_cases.csv`: every original/discovered
  candidate, including rejected, failed and unresolved cases. Columns include
  article ID, day-only date, language, exact OCR quote, English statement, origin,
  automated judgment, explicit claim override, effective decision, evidence error
  and inclusion in totals. `evidence_status` separates validated candidates from
  unsupported raw responses (including the additional 27 initial / 10 fresh raw
  original candidates that failed extraction validation). Unsupported quotation cells are blank; raw candidates
  remain in JSON. The 600-character limit remains. No context/path columns.
- `initial_articles.csv`, `refined_articles.csv`: coverage of every eligible article,
  including negatives and failures. Unusable reviews have a blank accepted count.
  Article human overrides are separate from automated review status.
- `seed_queries_original.py`, `seed_queries_revised.py`, `query-comparison.diff`:
  inspect sources side by side and the exact change. `query-change.json` retains
  the immutable human approval, rationale, fingerprints and original sources.
- `report.md`, `report.json`: descriptive comparison, language/query-version
  breakdowns, source/decade composition, overlap, exclusions, shortfalls and costs.
- `state.json`, manifests and `review-results.json`: machine-readable provenance
  and evidence, separate from the readable tables. Raw responses stay in state.

Python computes N = eligible articles with completed usable review; A = those
with accepted distinct claims; P = accepted distinct claims in N. A/N, P/A and P/N
are null for zero denominators. Counts of original accepted/rejected claims and
reviewer discoveries are separate. Overall article totals deduplicate IDs; query
subtotals overlap and **are not additive**. Coverage categories can overlap.

Results are **LLM-reviewed with limited human validation**, descriptive, not causal
and not recall. The old 68.5% versus 80% rates cannot establish improvement: the
fresh cohort had eight eligible articles, none English and none contributed by
the revised family. Extending sample size alone does not isolate a query effect.

## Copying to another machine and recovery

Copy reusable code/configuration separately from the entire private
`prediction_sample/` tree. In particular preserve:

- `experiment/` including `state.json`, any `state.tmp`, decision packets,
  manifests, raw evidence, history and exports;
- `articles/` and **all** `rounds/` including seed snapshots and references;
- `extraction_v2/` including checkpoint and annotated CSVs (human overrides).

These private data are partly ignored by Git: a clone alone is insufficient.
Also copy the repository usage counter `impresso_usage.json` for informational
accounting; experiment ledgers enforce limits independently. Configure credentials
on the destination. Default paths rebind to the new checkout; article content,
dates, languages, prompts, schemas and models must still match frozen evidence.
Free preview/prepare can recover saved responses without paying again. Invalid
quotes are never accepted; only the existing unique, tiny OCR-copy restoration is
allowed. Unsupported discoveries remain flagged, even with an accept override.

Only one runner may use the experiment. After a crash, confirm none is alive and
remove **only** `run.lock`. Never delete checkpoints or reservations to resume.
Atomic writes retry local file locks up to eight times; these retries never retry
an API. Preserve `state.json` and `state.tmp`: a newer consistent temporary state
can recover reservations/responses. Conflicting/incomplete recovery stops rather
than losing request history. Uncertain API attempts are never automatically
replayed. Retrieval skips a query when it reaches an existing uncertain request,
retains its reservation, and records it in `unresolved_queries`; other query
groups can continue. The pinned SDK's internal retry loop is explicitly limited
to one attempt. Reconcile a missing response with trusted saved evidence before
any deliberate new request. No retry switch bypasses that protection.

`extract_sample_predictions.py` supplies frozen extraction/validation and atomic
write helpers; `download_articles.py` supplies SDK sampling/transcript validation;
`impresso_prediction_seed_queries.py` holds reusable active definitions. Their old
pilot CLIs are historical utilities; use the experiment entry point to resume.

## A completely fresh experiment with only copied article JSONs

This is a new experiment, not a way to resume the approved comparison. It pays for
new extraction/review and requires new calibration and query approval. Keep the
existing experiment intact. Resetting local ledgers does not reset account quotas.

The simplest installation is a fresh repository checkout. If copying only a
minimal code bundle, preserve this structure:

```text
project/
  impresso_quota.py
  outcome-oriented/
    prediction_experiment.py
    extract_sample_predictions.py
    download_articles.py
    impresso_prediction_seed_queries.py
    target_predictions_def.md
    requirements.txt
    .env.example
    experiment_README.md
```

The code dependencies above are required; the README and example are setup aids.
The three `test_*.py` files are also useful for offline verification. No old private
checkpoint, manifest, calibration, approval, report or usage-counter file is needed
for a new experiment. Set new credentials in the root `.env`; do not copy secrets.

Copy each source JSON unchanged to
`outcome-oriented/prediction_sample/fresh/articles/<article-id>.json`. Each must
retain its Impresso `id`, `meta.date`, `text.langCode` (or original language),
`text.itemType`, and complete OCR `text.content`. Missing/redacted/short text is
excluded. The whole `fresh/` directory is ignored by Git. Without old retrieval
rounds, historical query attribution is unavailable; it is not reconstructed from
snippets or invented. All copied IDs become already seen for this new experiment.

Before preparing the new experiment, choose/edit its starting seed definitions in
`impresso_prediction_seed_queries.py` **in the new checkout**. The current active
file already contains the approved likelihood conjunction. To begin with the
original broad likelihood family, use the original source exported by the existing
experiment as the reusable seed configuration, then edit that copy as desired.
Changing starting seeds does not change what the already copied articles contain.
Once prepared, settings and methodology are frozen; do not edit seeds mid-run.

From the new project's root (repeat these explicit paths on every command):

```sh
python -m pip install -r outcome-oriented/requirements.txt

# Free preview. no_import must be absent or empty, including annotation CSVs.
python outcome-oriented/prediction_experiment.py --sample outcome-oriented/prediction_sample/fresh --existing outcome-oriented/prediction_sample/fresh/no_import --output outcome-oriented/prediction_sample/fresh/experiment

# Optional free freezing/export; run only after choosing starting seeds/method.
python outcome-oriented/prediction_experiment.py --prepare --sample outcome-oriented/prediction_sample/fresh --existing outcome-oriented/prediction_sample/fresh/no_import --output outcome-oriented/prediction_sample/fresh/experiment

# Paid extraction/review; choose the cumulative cap after reading the preview.
python outcome-oriented/prediction_experiment.py --run --budget-usd 3 --sample outcome-oriented/prediction_sample/fresh --existing outcome-oriented/prediction_sample/fresh/no_import --output outcome-oriented/prediction_sample/fresh/experiment
```

The last command is an example cap, not an estimate or authorization for a separate
experiment. It pauses at the new calibration packet and then the query approval
packet in `fresh/experiment/`. Fill each when prompted and repeat the same command.
Fresh retrieval uses the saved Impresso caps; explicit increases require a separate
budget decision. Fresh defaults select up to 100 eligible copied articles for the
initial cohort, retaining compatible attempts; use e.g. `--initial-articles 200`
on **every** command if you want 200 initial articles reviewed. Inspect the preview
first; requesting more than the copied eligible library leaves a visible shortfall.

The automated reviewer reads every successfully extracted selected article,
including extractor negatives. It does not review only the six-to-eight human
calibration examples. More selected articles can provide more evidence; simply
starting over with the same sample size does not. Queries are proposed using
accepted distinct claims in usable reviews, with a cue-usefulness check.

**Current limitation:** `propose_queries()` only chooses between two preset
conjunctions. It does not freely discover/promote new terms or make drastic query
changes, however large the sample. A broader revision workflow must be implemented
in the new copy before starting it, or its single proposal must be deliberately
prepared from the accepted evidence before approval. The current bounded
comparison must retain its already approved query change. Arbitrary starting
query layouts may not contain the slots the preset proposer expects and can stop
at proposal generation; a fresh ledger does not remove that code restriction.

## Offline checks

```sh
python -m unittest discover -s outcome-oriented -p "test_*.py"
```

All APIs are mocked. Tests cover budgets, cache/recovery, scope migration,
relocation, cohort isolation, fair retrieval, private-hit screening, human
overrides, quotation validation, distinct claims and denominator exclusions.
