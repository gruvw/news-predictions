# Comparison checklist

- [x] Inspect and reuse the previous bounded attempt; retain human approvals.
- [x] Offline tests and [free preview/preparation](./experiment_README.md).
- [x] Extend initial selection to 100; preserve all frozen IDs as already seen.
- [ ] Approve any increased cumulative API limits before further retrieval.
- [ ] Finish extraction/review with the frozen method; reach 100 eligible fresh articles.
- [ ] Read the two accepted tables: [initial](./prediction_sample/experiment/initial_predictions.csv)
  and [refined](./prediction_sample/experiment/refined_predictions.csv).
- [ ] Inspect [initial coverage](./prediction_sample/experiment/initial_articles.csv),
  [refined coverage](./prediction_sample/experiment/refined_articles.csv), and the
  separate [initial](./prediction_sample/experiment/initial_review_cases.csv) /
  [refined](./prediction_sample/experiment/refined_review_cases.csv) candidate tables.
- [x] Preserve [calibration](./prediction_sample/experiment/calibration.json) and
  [query approval](./prediction_sample/experiment/query-change.json).
- [x] Export [original seeds](./prediction_sample/experiment/seed_queries_original.py),
  [revised seeds](./prediction_sample/experiment/seed_queries_revised.py) and
  [diff](./prediction_sample/experiment/query-comparison.diff).
- [ ] Read the [comparison report](./prediction_sample/experiment/report.md) and
  [machine statistics](./prediction_sample/experiment/report.json). Confirm cohort
  sizes, N/A/P, coverage shortfalls, composition differences and descriptive limits.

The old 76 + 8 comparison is insufficient. The 68.5% versus 80% positive-article
rates do not establish improvement. Failed/unresolved articles are not negatives.
No further query optimization or historical outcome resolution follows this run.
