# Short experiment checklist

The experiment now covers **at most 100 articles total: 76 baseline + 24 fresh**.
Existing paid work is reused. Unsupported quotations stay unresolved; no paid retry.

- [x] From the repository root, preview the remaining work for free:
  `python outcome-oriented/prediction_experiment.py`
- [x] Run/resume with a cumulative $2 LLM cap:
  `python outcome-oriented/prediction_experiment.py --run --budget-usd 2`
- [x] When it pauses, open [calibration.json](./prediction_sample/experiment/calibration.json).
  Rate the six to eight cases in `human_decision` (`accept` / `reject` / `flag`;
  negative articles: `checked_negative` / `missed_prediction` / `flag`).
  Set `approve_method` to `true`. Repeat the same run command.
- [x] At the next pause, open [query-approval.json](./prediction_sample/experiment/query-approval.json).
  Read the single bundle and reasons. Set `approve` to `true` if agreed.
  Repeat the same run command; it retrieves the fresh sample and stops after comparison.
- [ ] Read [report.md](./prediction_sample/experiment/report.md).
  Check usable review counts, unresolved cases, fresh-sample shortfalls and the recommendation.

The approval files appear when their evidence is ready. For general corrections,
leave approval false and use `general_directions`; see the
[detailed instructions](./experiment_README.md). Budget stops retain all work;
increase the explicit cap only if you want to spend more. Do not delete state or
start another experiment directory to work around a stop.

Optional free local recovery/preparation:
`python outcome-oriented/prediction_experiment.py --prepare`.

If Windows reports `WinError 5`, close programs holding the checkpoint open and
repeat the same run command. Local file operations now retry brief locks. Keep
both checkpoint files: **do not delete `state.json` or `state.tmp`**. Saved retrieval
responses are reused on resume.
