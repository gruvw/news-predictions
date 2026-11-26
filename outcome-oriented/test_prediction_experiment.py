"""Offline experiment tests. All LLM/Impresso calls are mocked."""
import copy
from contextlib import redirect_stdout
import csv
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import prediction_experiment as exp


def response(result):
    return dict(exp.envelope(result), usage=dict(input_tokens=100, output_tokens=50))


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sample = self.root / "sample"
        (self.sample / "articles").mkdir(parents=True)
        self.existing = self.root / "existing"
        self.existing.mkdir()
        self.output = self.root / "experiment"
        self.path = self.output / "state.json"
        # Keep tests independent of the user's now-approved active query revision.
        # Reuse vocabularies but give each test its own original four-slot layout.
        seed = self.root / "test-active-queries.py"
        prefix = exp.SEEDS.read_text(encoding="utf-8").split("\ndef iter_queries(", 1)[0]
        seed.write_text(prefix + '''
def iter_queries(language):
    groups = {
        "forecast_frame": OR(*FORECAST_FRAMES[language]),
        "likelihood": OR(*LIKELIHOOD[language]),
        "long_horizon": OR(*LONG_HORIZONS[language]),
        "modal_or_future_form_and_calendar": (
            OR(*MODALS_OR_FUTURE_FORMS[language]) & OR(*CALENDAR_CUES[language])
        ),
    }
    for family, term in groups.items():
        yield family, dict(term=term, language=language, with_text_contents=True)
''', encoding="utf-8")
        seed_patch = patch.object(exp, "SEEDS", seed)
        seed_patch.start()
        self.addCleanup(seed_patch.stop)
        self.flags = ["--sample", str(self.sample), "--existing", str(self.existing),
                      "--output", str(self.output)]
        self.article("a")
        self.args = SimpleNamespace(sample=self.sample, existing=self.existing, min_chars=200,
            reviewer="gpt-6-luna", review_input_rate=.1, review_output_rate=.5,
            per_query=1, search_limit=100, fetch_limit=10)
        self.negative = dict(predictions=[], no_prediction_reason="Only retrospective reporting.")
        self.review = dict(article_status="usable", reason="No future claims in the whole article.",
                           judgments=[], discoveries=[])
        self.env = patch.dict(os.environ, {"OPENAI_API_KEY": "test", "IMPRESSO_API_TOKEN": "test"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def article(self, cid, text=None, language="en"):
        raw = dict(id=cid, meta={"date": "1900-01-01T00:00:00Z"}, text=dict(
            langCode=language, itemType="ar", content=text or "Reports about yesterday's events. " * 10))
        (self.sample / "articles" / f"{cid}.json").write_text(json.dumps(raw), encoding="utf-8")
        return raw

    def state(self):
        return exp.initial(self.args)

    def saved_extraction(self, state, cid="a", result=None):
        state["extractions"][cid] = dict(article=state["baseline"][cid], status="completed",
            cost_usd=.001, input_tokens=100, output_tokens=20,
            response=response(self.negative if result is None else result),
            result=self.negative if result is None else result)

    def saved_review(self, state, cid="a", result=None):
        result = self.review if result is None else result
        state["reviews"][cid] = dict(status="completed", result=result,
            response=response(result), ledger_key=exp.ex.digest(exp.request_for(state["baseline"][cid],
                state["review_config"], state["extractions"][cid]["result"])))

    def prediction(self, quote="Reports about yesterday's events.", statement="A future event will occur."):
        return dict(quote=quote, statement=statement, predictor="", confidence="possible",
                    eligibility_reason="Observable uncertain future.", cues=[])

    def judgment(self, index=0, decision="accept", duplicate=-1):
        return dict(prediction_index=index, decision=decision, reason="Source supports claim.",
                    cues_useful=False, duplicate_of=duplicate)

    def query_state(self):
        self.article("a", "Analysts say it is expected that prices will fall next year. " * 6)
        state = self.state()
        self.saved_extraction(state, result=dict(predictions=[self.prediction(
            "it is expected that prices will fall next year.", "Prices will fall in 1901.")], no_prediction_reason=""))
        self.saved_review(state, result=dict(self.review, judgments=[dict(self.judgment(), cues_useful=True)]))
        return state

    def test_preview_no_files_no_network(self):
        with patch("urllib.request.urlopen") as api, redirect_stdout(io.StringIO()):
            exp.main(self.flags)
        api.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_newer_temporary_checkpoint_recovers_llm_and_retrieval_without_network(self):
        state = self.state()
        state["query_version"] = "v1"
        request = exp.request_for(state["baseline"]["a"], state["config"])
        llm_key = exp.ex.digest(request)
        state["llm"][llm_key] = dict(status="pending", cost_usd=.1, request=request)
        params = dict(language="en", limit=1, query_version="v1")
        retrieval_key = exp.ex.digest(["search_results", params])
        state["retrieval"][retrieval_key] = dict(status="pending", kind="search_results", params=params, reserved=1)
        exp.save(self.path, state)
        recovered = copy.deepcopy(state)
        recovered["llm"][llm_key].update(status="completed", response=response(self.negative))
        recovered["retrieval"][retrieval_key].update(status="completed", raw={"data": [{"id": "a"}]}, total=1)
        with patch.object(Path, "replace", side_effect=PermissionError("locked")), \
                patch.object(exp.ex.time, "sleep"):
            with self.assertRaises(PermissionError):
                exp.save(self.path, recovered)
        old_bytes = self.path.read_bytes()
        temporary_bytes = self.path.with_suffix(".tmp").read_bytes()
        loaded = exp.load_state(self.path)
        self.assertEqual(self.path.read_bytes(), old_bytes)  # Preview/recovery reads are free and read-only.
        self.assertEqual(self.path.with_suffix(".tmp").read_bytes(), temporary_bytes)
        sdk = Mock()
        with patch("urllib.request.urlopen") as api:
            exp.call(loaded, self.path, request, loaded["config"], 1, lambda raw: self.negative)
            result = exp.RetrievalCache(loaded, self.path, sdk).find(language="en", limit=1)
        api.assert_not_called()
        sdk.search.find.assert_not_called()
        self.assertEqual(result.raw["data"][0]["id"], "a")

    def test_incomplete_temporary_checkpoint_stops_without_overwriting_evidence(self):
        exp.save(self.path, self.state())
        old = self.path.read_bytes()
        self.path.with_suffix(".tmp").write_text('{"incomplete":')
        with self.assertRaisesRegex(ValueError, "Temporary checkpoint is incomplete"):
            exp.load_state(self.path)
        self.assertEqual(self.path.read_bytes(), old)
        self.assertTrue(self.path.with_suffix(".tmp").exists())

    def test_conflicting_temporary_checkpoint_cannot_lose_reservations(self):
        state = self.state()
        state["llm"]["reserved"] = dict(status="pending", cost_usd=.1)
        exp.save(self.path, state)
        candidate = copy.deepcopy(state)
        candidate["llm"].clear()
        self.path.with_suffix(".tmp").write_text(json.dumps(candidate))
        with self.assertRaisesRegex(ValueError, "lose request history"):
            exp.load_state(self.path)

    def test_stale_temporary_file_does_not_replace_newer_main_checkpoint(self):
        state = self.state()
        exp.save(self.path, state)
        self.path.with_suffix(".tmp").write_text('{"incomplete":')
        os.utime(self.path.with_suffix(".tmp"), ns=(1, 1))
        self.assertEqual(exp.load_state(self.path), state)

    def test_prepare_free_freezes_full_library_and_exclusions(self):
        self.article("short", "small")
        self.article("redacted", "[REDACTED]")
        self.article("b")
        with patch("urllib.request.urlopen") as api, redirect_stdout(io.StringIO()):
            exp.main(self.flags + ["--prepare"])
        api.assert_not_called()
        state = exp.read(self.path)
        self.assertEqual(set(state["baseline"]), {"a", "b"})
        self.assertEqual({e["reason"] for e in state["excluded"]}, {"unavailable", "undersized"})
        self.article("later")
        with redirect_stdout(io.StringIO()):
            exp.main(self.flags + ["--prepare"])
        self.assertEqual(set(exp.read(self.path)["baseline"]), {"a", "b"})

    def test_lock_prevents_second_runner(self):
        self.output.mkdir()
        (self.output / "run.lock").write_text("existing runner")
        with patch("urllib.request.urlopen") as api, redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "run.lock"):
                exp.main(self.flags + ["--run"])
        api.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_preview_counts_correction_reviews_as_remaining(self):
        state = self.state()
        self.saved_extraction(state)
        self.saved_review(state)
        state["review_config"]["instructions"] += "\nNew calibrated instruction"
        output = io.StringIO()
        with redirect_stdout(output):
            exp.preview(state)
        self.assertEqual(json.loads(output.getvalue())["remaining_reviews"], 1)

    def test_preview_includes_known_comparison_work(self):
        state = self.state()
        self.saved_extraction(state)
        self.saved_review(state)
        self.article("new")
        state["refined_articles"] = {"new": exp.inventory(self.sample, 200)[0]["new"]}
        output = io.StringIO()
        with redirect_stdout(output):
            exp.preview(state)
        preview = json.loads(output.getvalue())
        self.assertEqual(preview["remaining_extractions"], 1)
        self.assertEqual(preview["remaining_reviews"], 1)
        self.assertGreater(preview["known_refined_remaining_upper_usd"], 0)

    def test_preview_does_not_advertise_reviews_of_failed_extractions_as_remaining_work(self):
        state = self.state()
        self.saved_extraction(state)
        state["extractions"]["a"]["status"] = "error"
        output = io.StringIO()
        with redirect_stdout(output):
            exp.preview(state)
        preview = json.loads(output.getvalue())
        self.assertEqual(preview["remaining_reviews"], 0)
        self.assertEqual(preview["reviews_blocked_by_extraction"], 1)
        self.assertEqual(preview["attempted_extractions"], 1)
        self.assertEqual(preview["reusable_extractions"], 0)

    def test_incompatible_import_rejected(self):
        state = self.state()
        config = dict(state["config"], model="other")
        exp.save(self.existing / "checkpoint.json", dict(config=config, records={}))
        with self.assertRaisesRegex(ValueError, "differ"):
            self.state()

    def test_budget_includes_imports_and_both_stages_after_restart(self):
        state = self.state()
        self.saved_extraction(state)
        request = exp.request_for(state["baseline"]["a"], state["review_config"], self.negative)
        with patch("urllib.request.urlopen") as api:
            with self.assertRaisesRegex(ValueError, "budget"):
                exp.call(state, self.path, request, state["review_config"], .001, lambda r: self.review)
        api.assert_not_called()
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response(self.review)).encode())):
            exp.call(state, self.path, request, state["review_config"], 1, lambda r: self.review)
        resumed = exp.read(self.path)
        self.assertAlmostEqual(exp.costs(resumed)["charged_or_reserved_usd"], .001 + .000035)
        # Same response is reused even with a lower cap; no paid call is needed.
        with patch("urllib.request.urlopen") as api:
            exp.call(resumed, self.path, request, resumed["review_config"], .001, lambda r: self.review)
        api.assert_not_called()

    def test_uncertain_request_never_replayed(self):
        state = self.state()
        request = exp.request_for(state["baseline"]["a"], state["config"])
        with patch("urllib.request.urlopen", side_effect=TimeoutError):
            with self.assertRaisesRegex(ValueError, "failed"):
                exp.call(state, self.path, request, state["config"], 1, lambda r: self.negative)
        resumed = exp.read(self.path)
        with patch("urllib.request.urlopen") as api:
            with self.assertRaisesRegex(ValueError, "Uncertain"):
                exp.call(resumed, self.path, request, resumed["config"], 1, lambda r: self.negative)
        api.assert_not_called()
        self.assertGreater(exp.costs(resumed)["uncertain_reservations_usd"], 0)

    def test_saved_raw_pending_response_recovered_without_billing(self):
        state = self.state()
        request = exp.request_for(state["baseline"]["a"], state["config"])
        key = exp.ex.digest(request)
        state["llm"][key] = dict(status="pending", cost_usd=.1, request=request,
                                 response=response(self.negative))
        with patch("urllib.request.urlopen") as api:
            result = exp.call(state, self.path, request, state["config"], .001,
                lambda raw: exp.validate_extraction(raw, state["baseline"]["a"]))
        api.assert_not_called()
        self.assertEqual(result["status"], "completed")
        self.assertAlmostEqual(exp.costs(state)["charged_or_reserved_usd"], .000035)

    def test_missing_usage_retains_reservation_even_for_usable_response(self):
        state = self.state()
        request = exp.request_for(state["baseline"]["a"], state["config"])
        raw = exp.envelope(self.negative)
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(raw).encode())):
            exp.call(state, self.path, request, state["config"], 1, lambda r: self.negative)
        self.assertEqual(exp.costs(state)["uncertain_reservations_usd"], exp.reserve(request, state["config"]))

    def test_process_reuses_import_and_review_then_restarts_free(self):
        state = self.state()
        self.saved_extraction(state)
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response(self.review)).encode())) as api:
            exp.process(state, self.path, state["baseline"], 1)
        self.assertEqual(api.call_count, 1)
        with patch("urllib.request.urlopen") as api:
            exp.process(exp.read(self.path), self.path, state["baseline"], 1)
        api.assert_not_called()

    def test_failed_process_is_counted_and_not_retried(self):
        state = self.state()
        with patch("urllib.request.urlopen", side_effect=TimeoutError):
            with self.assertRaises(ValueError):
                exp.process(state, self.path, state["baseline"], 1)
        self.assertEqual(exp.metrics(state, ["a"], {})["failed"], 1)
        self.assertIsNone(exp.metrics(state, ["a"], {})["A_over_N"])
        with patch("urllib.request.urlopen") as api:
            with self.assertRaises(ValueError):
                exp.process(state, self.path, state["baseline"], 1)
        api.assert_not_called()

    def test_all_originals_and_evidence_required_in_review(self):
        article = self.state()["baseline"]["a"]
        extraction = dict(predictions=[self.prediction()], no_prediction_reason="")
        with self.assertRaisesRegex(ValueError, "ALL"):
            exp.validate_review(response(self.review), article, extraction)
        bad = dict(self.review, discoveries=[dict(prediction=self.prediction("Invented source quote"),
                   reason="Missed", cues_useful=False, duplicate_of=-1)])
        recovered = exp.validate_review(response(bad), article, self.negative)
        self.assertEqual(recovered["article_status"], "unresolved")
        self.assertIn("evidence_error", recovered["discoveries"][0])
        too_long = dict(self.review, discoveries=[dict(prediction=self.prediction("x"*601),
                   reason="Missed", cues_useful=False, duplicate_of=-1)])
        with self.assertRaises(ValueError):
            exp.validate_review(response(too_long), article, self.negative)

    def test_duplicate_validation_and_discoveries(self):
        article = self.state()["baseline"]["a"]
        extraction = dict(predictions=[self.prediction(), self.prediction()], no_prediction_reason="")
        review = dict(self.review, judgments=[self.judgment(0), self.judgment(1)])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            exp.validate_review(response(review), article, extraction)
        review["judgments"][1] = self.judgment(1, "reject", 0)
        exp.validate_review(response(review), article, extraction)
        review = dict(self.review, discoveries=[dict(prediction=self.prediction(), reason="Missed claim",
            cues_useful=False, duplicate_of=-1)])
        self.assertEqual(len(exp.validate_review(response(review), article, self.negative)["discoveries"]), 1)

    def test_denominators_exclude_unresolved_failed_and_unreviewed(self):
        for cid in ("b", "c", "d"):
            self.article(cid)
        state = self.state()
        for cid in ("a", "b", "c"):
            self.saved_extraction(state, cid)
        self.saved_review(state)
        self.saved_review(state, "b", dict(self.review, article_status="unresolved"))
        state["reviews"]["c"] = dict(status="error")
        m = exp.metrics(state, list(state["baseline"]), {})
        self.assertEqual((m["eligible"], m["N"], m["A"], m["P"], m["failed"], m["unresolved"]),
                         (4, 1, 0, 0, 1, 1))
        self.assertEqual(m["P_over_N"], 0)
        self.assertIsNone(m["P_over_A"])
        self.assertIsNone(exp.metrics(state, [], {})["P_over_N"])

    def test_human_precedence_and_flagged_article_not_negative(self):
        state = self.state()
        self.saved_extraction(state, result=dict(predictions=[self.prediction()], no_prediction_reason=""))
        self.saved_review(state, result=dict(self.review, judgments=[self.judgment(decision="flag")]))
        self.assertEqual(exp.metrics(state, ["a"], {})["N"], 0)
        self.assertEqual(exp.metrics(state, ["a"], {"a:p1": "accept"})["P"], 1)
        self.assertEqual(exp.metrics(state, ["a"], {"a": "checked_negative"})["A"], 0)
        self.assertEqual(exp.metrics(state, ["a"], {"a": "checked_negative"})["N"], 1)
        self.assertEqual(exp.metrics(state, ["a"], {"a:p1": "revise"})["N"], 0)

    def test_original_and_discovered_counts_separate(self):
        state = self.state()
        self.saved_extraction(state)
        self.saved_review(state, result=dict(self.review, discoveries=[dict(prediction=self.prediction(),
            reason="Missed", cues_useful=False, duplicate_of=-1)]))
        m = exp.metrics(state, ["a", "a"], {})
        self.assertEqual((m["N"], m["P"], m["original_accepted"], m["discovered_accepted"]), (1, 1, 0, 1))

    def test_human_csv_preserved_and_packet_combined(self):
        state = self.state()
        path = self.existing / "predictions.csv"
        path.write_text("prediction_id,review_decision,review_notes\na:p1,reject,existing\n")
        exp.save(self.output / "calibration.json", dict(cases=[dict(id="a:p2", human_decision="accept")]))
        self.assertEqual(exp.human_decisions(state, self.output), {"a:p1": "reject", "a:p2": "accept"})
        self.assertIn("existing", path.read_text())

    def test_query_versions_and_nonadditive_associations(self):
        rounds = self.sample / "rounds"
        for name, seed in (("one", "old"), ("two", "new")):
            directory = rounds / name
            directory.mkdir(parents=True)
            (directory / "seed_queries.py").write_text(seed)
            (directory / "references.csv").write_text("article_id,query_id\na,en.frame\n")
        refs = exp.associations(self.sample)["a"]
        self.assertEqual(len(refs), 2)
        self.assertNotEqual(refs[0].split("/")[1], refs[1].split("/")[1])

    def test_retrieval_budget_and_cache_no_replay_or_mutation(self):
        state = self.state()
        state["query_version"] = "v1"
        state["settings"]["search_limit"] = 2
        sdk = Mock()
        sdk.search.find.return_value = SimpleNamespace(raw={"data": [dict(id="a"), dict(id="b")]}, total=2)
        cache = exp.RetrievalCache(state, self.path, sdk)
        first = cache.find(language="en", limit=2)
        first.raw["data"].reverse()
        second = cache.find(language="en", limit=2)
        self.assertEqual(second.raw["data"][0]["id"], "a")
        self.assertEqual(sdk.search.find.call_count, 1)
        with self.assertRaises(exp.RetrievalLimitReached):
            cache.find(language="fr", limit=1)
        sdk.content_items.get.side_effect = TimeoutError
        with self.assertRaises(TimeoutError):
            cache.get("unknown")
        sdk.content_items.get.reset_mock()
        with self.assertRaisesRegex(ValueError, "Uncertain"):
            cache.get("unknown")
        sdk.content_items.get.assert_not_called()

    def test_retrieve_overlap_does_not_fill_new_quota(self):
        import download_articles as dl
        state = self.state()
        state["query_version"] = exp.ex.digest(exp.SEEDS.read_text(encoding="utf-8"))
        new = self.article("new")
        cached = self.article("a")
        self.output.mkdir()
        with patch("impresso.client.ImpressoClient"), patch.object(dl, "LANGUAGES", ("en",)), \
                patch("impresso_prediction_seed_queries.iter_queries", return_value=[("frame", {})]), \
                patch.object(dl, "sample_query", return_value=iter([cached, new])), patch.object(dl, "UsageCounter"):
            exp.retrieve(state, self.path, self.sample, self.output)
        self.assertEqual(state["refined"], ["new"])
        self.assertEqual(state["refined_all"], ["a", "new"])
        self.assertEqual(len(state["refined_references"]), 2)

    def test_saved_review_bad_discovery_is_recovered_locally_and_never_accepted(self):
        state = self.state()
        self.saved_extraction(state)
        bad = dict(self.review, discoveries=[dict(prediction=self.prediction("Invented source quotation"),
            reason="Suggested missed claim", cues_useful=False, duplicate_of=-1)])
        self.saved_review(state, result=bad)
        row = state["reviews"]["a"]
        row.update(status="error", error="Quotation invalid")
        state["llm"][row["ledger_key"]] = dict(row, cost_usd=.002, input_tokens=100, output_tokens=20)
        raw = copy.deepcopy(row["response"])
        before_cost = exp.costs(state)
        with patch("urllib.request.urlopen") as api:
            exp.recover_saved_reviews(state)
            exp.process(state, self.path, state["baseline"], 1)
        api.assert_not_called()
        self.assertEqual(raw, state["reviews"]["a"]["response"])
        self.assertEqual(before_cost, exp.costs(state))
        self.assertEqual(exp.metrics(state, ["a"], {})["unresolved"], 1)
        self.assertEqual(exp.claims(state, "a", {"a:d1": "accept"})[0]["effective_decision"], "flag")
        self.assertFalse(exp.usable(state, "a", {"a": "checked_positive", "a:d1": "accept"}))

    def test_invalid_saved_extraction_does_not_stop_other_cached_articles(self):
        self.article("b")
        state = self.state()
        self.saved_extraction(state, result=dict(predictions=[self.prediction("Invented source quote")],
                                                 no_prediction_reason=""))
        self.saved_extraction(state, "b")
        self.saved_review(state, "b")
        with patch("urllib.request.urlopen") as api:
            exp.process(state, self.path, state["baseline"], 1)
        api.assert_not_called()
        self.assertEqual(state["extractions"]["a"]["status"], "error")
        self.assertEqual(exp.metrics(state, state["baseline"], {})["N"], 1)

    def test_total_scope_cap_preserves_attempts_and_full_library(self):
        for i in range(120):
            self.article(f"p{i:03}", language=("fr", "de", "en")[i % 3])
        state = self.state()
        for cid in ("a", "p000", "p119"):
            self.saved_extraction(state, cid)
        costs = exp.costs(state)
        exp.extend_comparison(state, 76, 24)
        self.assertEqual(len(state["baseline"]), 76)
        self.assertEqual(len(exp.library_ids(state)), 121)
        self.assertTrue({"a", "p000", "p119"} <= set(state["baseline"]))
        self.assertEqual(state["settings"]["comparison_articles"], 24)
        self.assertEqual(costs, exp.costs(state))
        ids = list(state["baseline"])
        exp.extend_comparison(state, 76, 24)
        self.assertEqual(ids, list(state["baseline"]))
        self.assertEqual(len(state["scope_changes"]), 1)

    def test_deferred_library_article_cannot_fill_fresh_quota(self):
        import download_articles as dl
        state = self.state()
        old = self.article("deferred")
        new = self.article("new")
        state["library_baseline"] = {**state["baseline"], "deferred": exp.inventory(self.sample, 200)[0]["deferred"]}
        state["query_version"] = exp.ex.digest(exp.SEEDS.read_text(encoding="utf-8"))
        self.output.mkdir()
        with patch("impresso.client.ImpressoClient"), patch.object(dl, "LANGUAGES", ("en",)), \
                patch("impresso_prediction_seed_queries.iter_queries", return_value=[("frame", {})]), \
                patch.object(dl, "sample_query", return_value=iter([old, new])), patch.object(dl, "UsageCounter"):
            exp.retrieve(state, self.path, self.sample, self.output)
        self.assertEqual(state["refined"], ["new"])
        self.assertEqual(state["refined_all"], ["deferred", "new"])

    def test_calibration_correction_reuses_extractions_keeps_ledger(self):
        state = self.state()
        self.saved_extraction(state)
        self.saved_review(state)
        exp.save(self.output / "calibration.json", dict(general_directions="Check negation more strictly", cases=[]))
        self.assertFalse(exp.calibration_gate(state, self.output))
        correction = exp.read(self.output / "correction.json")
        correction["approve"] = True
        exp.save(self.output / "correction.json", correction)
        self.assertFalse(exp.calibration_gate(state, self.output))
        self.assertIn("Check negation", state["review_config"]["instructions"])
        self.assertEqual(len(state["extractions"]), 1)
        self.assertEqual(state["stage"], "baseline")
        self.assertFalse((self.output / "calibration.json").exists())

    def test_query_approval_snapshots_and_idempotence(self):
        state = self.query_state()
        state["human_snapshot"] = {}
        seed = self.root / "seed_queries.py"
        seed.write_text(state["original_seeds"], encoding="utf-8")
        with patch.object(exp, "SEEDS", seed):
            self.assertFalse(exp.query_gate(state, self.output))
            packet = exp.read(self.output / "query-approval.json")
            packet["approve"] = True
            exp.save(self.output / "query-approval.json", packet)
            self.assertTrue(exp.query_gate(state, self.output))
            self.assertTrue(exp.query_gate(state, self.output))
        snapshot = exp.read(self.output / "query-change.json")
        self.assertEqual(snapshot["before_source"], state["original_seeds"])
        self.assertNotEqual(snapshot["before_fingerprint"], snapshot["after_fingerprint"])
        # Execute proposed code with the real SDK offline. TermSet does not
        # implement boolean OR via |, which otherwise silently returns a bare set.
        namespace = {}
        exec(snapshot["after_source"], namespace)
        for language in ("fr", "de", "en"):
            queries = list(namespace["iter_queries"](language))
            self.assertEqual(len(queries), 4)
            self.assertEqual(queries[0][0], "forecast_frame_and_time")
            term = queries[0][1]["term"]
            self.assertEqual(len(term.chain), 1)
            self.assertEqual(term.chain[0].op, "OR")

    def test_query_approval_requires_boolean_true(self):
        state = self.query_state()
        state["human_snapshot"] = {}
        self.assertFalse(exp.query_gate(state, self.output))
        packet = exp.read(self.output / "query-approval.json")
        packet["approve"] = "false"
        exp.save(self.output / "query-approval.json", packet)
        with patch("urllib.request.urlopen") as api:
            self.assertFalse(exp.query_gate(state, self.output))
        api.assert_not_called()

    def test_no_query_revision_is_invented_without_supported_predictions(self):
        with self.assertRaisesRegex(ValueError, "No accepted predictions"):
            exp.propose_queries(self.state(), {})

    def likelihood_state(self):
        quotes = {"en": "Prices will probably fall.", "fr": "Le prix sera probablement stable.",
                  "de": "Der Preis wird wahrscheinlich fallen."}
        for lang, quote in quotes.items():
            self.article(lang, quote * 12, language=lang)
        state = self.state()
        for lang, quote in quotes.items():
            self.saved_extraction(state, lang, dict(predictions=[self.prediction(quote)], no_prediction_reason=""))
            self.saved_review(state, lang, dict(self.review, judgments=[dict(self.judgment(), cues_useful=True)]))
        return state

    def test_supported_likelihood_future_fallback_preserves_other_families(self):
        state = self.likelihood_state()
        packet = exp.propose_queries(state, {})
        self.assertEqual(packet["proposal_kind"], "likelihood_and_future")
        self.assertEqual([c["support_article_count"] for c in packet["changes"]], [1, 1, 1])
        namespace = {}
        exec(packet["after_source"], namespace)
        families = [family for family, kwargs in namespace["iter_queries"]("en")]
        self.assertEqual(families, packet["query_families"])
        self.assertIn("forecast_frame", families)
        self.assertNotIn("likelihood", families)
        for lang in ("en", "fr", "de"):
            self.assertTrue(namespace["FORECAST_FRAMES"][lang])
        # Rejected predictions cannot supply support, nor can a cue veto.
        humans = {lang + ":p1": "reject" for lang in ("en", "fr", "de")}
        with self.assertRaisesRegex(ValueError, "No accepted predictions"):
            exp.propose_queries(state, humans)

    def test_query_operand_does_not_match_inside_another_word(self):
        self.assertFalse(exp.term_occurs("may", "The mayor probably wins."))
        self.assertFalse(exp.term_occurs("will", "William is likely to leave."))
        self.assertTrue(exp.term_occurs("will", "Prices WILL probably fall."))

    def test_prepare_generates_pending_fallback_without_applying_or_paying(self):
        state = self.likelihood_state()
        state["human_snapshot"] = {}
        exp.extend_comparison(state, 76, 24)
        state["stage"] = "query_approval"
        exp.save(self.path, state)
        seeds_before = exp.SEEDS.read_text(encoding="utf-8")
        cost_before = exp.costs(state)
        with patch("urllib.request.urlopen") as api, redirect_stdout(io.StringIO()):
            exp.main(self.flags + ["--prepare"])
        api.assert_not_called()
        self.assertEqual(exp.SEEDS.read_text(encoding="utf-8"), seeds_before)
        self.assertEqual(exp.costs(exp.read(self.path)), cost_before)
        packet = exp.read(self.output / "query-approval.json")
        self.assertEqual(packet["proposal_kind"], "likelihood_and_future")
        self.assertIs(packet["approve"], False)
        # Even an already approved packet must not be applied by --prepare.
        packet["approve"] = True
        exp.save(self.output / "query-approval.json", packet)
        with patch("urllib.request.urlopen") as api, redirect_stdout(io.StringIO()):
            exp.main(self.flags + ["--prepare"])
        api.assert_not_called()
        self.assertEqual(exp.SEEDS.read_text(encoding="utf-8"), seeds_before)

    def test_fallback_report_shortfalls_use_the_actual_proposed_family(self):
        state = self.likelihood_state()
        state["human_snapshot"] = {}
        exp.prepare_query_packet(state, self.output)
        exp.report(state, self.output)
        shortfalls = exp.read(self.output / "report.json")["shortfalls"]
        self.assertIn("en.likelihood_and_future", shortfalls)
        self.assertIn("en.forecast_frame", shortfalls)
        self.assertNotIn("en.forecast_frame_and_time", shortfalls)

    def test_sdk_filter_cache_is_order_independent_but_preserves_boolean_logic(self):
        from impresso import OR
        self.assertEqual(exp.canonical_filter(OR("a", "b")), exp.canonical_filter(OR("b", "a")))
        self.assertNotEqual(exp.canonical_filter(OR("a") & OR("b")), exp.canonical_filter(OR("a", "b")))
        state = self.state()
        state["query_version"] = "version"
        sdk = Mock()
        sdk.search.find.return_value = SimpleNamespace(raw={"data": []}, total=0)
        cache = exp.RetrievalCache(state, self.path, sdk)
        cache.find(term=OR("a", "b"), limit=1)
        cache.find(term=OR("b", "a"), limit=1)
        self.assertEqual(sdk.search.find.call_count, 1)

    def test_changed_publication_date_does_not_reuse_extraction(self):
        state = self.state()
        self.saved_extraction(state)
        articles = copy.deepcopy(state["baseline"])
        articles["a"]["date"] = "1901-01-01"
        with patch("urllib.request.urlopen") as api:
            with self.assertRaisesRegex(ValueError, "date/language"):
                exp.process(state, self.path, articles, 1)
        api.assert_not_called()

    def test_extension_migration_retains_history_approvals_and_extra_work(self):
        for i in range(110):
            self.article(f"x{i:03}", language=("fr", "de", "en")[i % 3])
        state = self.state()
        state["library_baseline"] = copy.deepcopy(state["baseline"])
        state["baseline"] = {c: state["baseline"][c] for c in sorted(state["baseline"])[:76]}
        state["settings"].update(max_articles=100, comparison_articles=24)
        self.saved_extraction(state)
        state.update(stage="complete", method_fingerprint="frozen", query_version="approved", human_snapshot={"a:p1": "accept"})
        state["llm"]["uncertain"] = dict(status="pending", cost_usd=.1)
        old = copy.deepcopy(state)
        exp.extend_comparison(state, 100, 100)
        self.assertEqual(len(state["baseline"]), 100)
        self.assertEqual(state["stage"], "extension")
        self.assertEqual(state["llm"], old["llm"])
        self.assertEqual(state["human_snapshot"], old["human_snapshot"])
        self.assertEqual(state["settings"]["fetch_limit"], old["settings"]["fetch_limit"])
        self.assertEqual(state["settings"]["per_query"], 9)
        self.assertTrue(set(old["baseline"]) <= set(state["baseline"]))
        once = copy.deepcopy(state)
        exp.extend_comparison(state, 100, 100)
        self.assertEqual(state, once)
        exp.extend_comparison(state, 90, 90)
        self.assertEqual(len(state["baseline"]), 100)  # never discard compatible work

    def test_excluded_original_ids_remain_already_seen(self):
        state = self.state()
        state["excluded"] = [dict(article_id="redacted", reason="unavailable")]
        self.assertEqual(exp.already_seen_ids(state), {"a", "redacted"})

    def test_saved_detached_extraction_recovered_offline(self):
        state = self.state()
        key = exp.ex.digest(exp.request_for(state["baseline"]["a"], state["config"]))
        state["llm"][key] = dict(status="pending", response=response(self.negative), cost_usd=.01)
        before = copy.deepcopy(state["llm"])
        with patch("urllib.request.urlopen") as api:
            exp.recover_saved_extractions(state)
        api.assert_not_called()
        self.assertEqual(state["extractions"]["a"]["status"], "completed")
        self.assertEqual(state["llm"], before)

    def test_tables_match_denominators_and_keep_unresolved_separate(self):
        self.article("b")
        state = self.state()
        for cid in ("a", "b"):
            self.saved_extraction(state, cid, result=dict(predictions=[self.prediction()], no_prediction_reason=""))
            self.saved_review(state, cid, result=dict(self.review, judgments=[self.judgment()]))
        humans = {"b:p1": "flag"}
        self.output.mkdir()
        exp.export_tables(state, self.output, humans, state["baseline"])
        def rows(name):
            with (self.output / name).open(encoding="utf-8", newline="") as f:
                return list(csv.DictReader(f))
        self.assertEqual(len(rows("initial_predictions.csv")), exp.metrics(state, state["baseline"], humans)["P"])
        cases = rows("initial_review_cases.csv")
        self.assertEqual(len(cases), 2)
        flagged = next(r for r in cases if r["article_id"] == "b")
        self.assertEqual(flagged["human_override"], "flag")
        self.assertEqual(flagged["included_in_totals"], "False")
        self.assertFalse(any("path" in key or "context" in key for key in flagged))
        self.assertTrue(all(len(r["quote"]) <= 600 for r in cases))
        self.assertEqual(rows("initial_articles.csv")[1]["accepted_distinct_predictions"], "")

    def test_private_hits_skip_fetch_and_streams_alternate(self):
        import download_articles as dl
        state = self.state()
        state["settings"].update(comparison_articles=10, per_query=2)
        state["query_version"] = exp.ex.digest(exp.SEEDS.read_text(encoding="utf-8"))
        order = []
        def stream(client, usage, kwargs, rng, label):
            for n in range(2):
                order.append(label)
                yield dict(id=f"{label}{n}", access=dict(dataDomain="prt"))
        with patch("impresso.client.ImpressoClient"), patch.object(dl, "LANGUAGES", ("fr", "de", "en")), \
                patch("impresso_prediction_seed_queries.iter_queries", return_value=[("frame", {})]), \
                patch.object(dl, "sample_query", side_effect=stream), patch.object(dl, "save_article") as fetch, \
                patch.object(dl, "UsageCounter"):
            exp.retrieve(state, self.path, self.sample, self.output)
        fetch.assert_not_called()
        self.assertEqual(order, ["fr.frame", "de.frame", "en.frame"] * 2)
        self.assertEqual(len(state["retrieval_excluded"]), 6)

    def test_relocated_prepare_preserves_reservations_and_raw_evidence(self):
        state = self.state()
        state["paths"] = dict(sample="/old/computer/sample", existing="/old/computer/existing")
        state["retrieval"]["uncertain"] = dict(kind="item_fetches", params="lost", status="pending", reserved=1)
        exp.save(self.path, state)
        with patch("urllib.request.urlopen") as api, redirect_stdout(io.StringIO()):
            exp.main(self.flags + ["--prepare"])
        api.assert_not_called()
        saved = exp.read(self.path)
        self.assertEqual(saved["paths"]["sample"], str(self.sample.resolve()))
        self.assertEqual(saved["retrieval"], state["retrieval"])

    def test_explicit_fetch_limit_change_is_cumulative_and_persists(self):
        state = self.state()
        state["retrieval"]["spent"] = dict(kind="item_fetches", params="prior", status="completed", reserved=1, raw={}, total=None)
        exp.save(self.path, state)
        with patch("urllib.request.urlopen") as api, redirect_stdout(io.StringIO()):
            exp.main(self.flags + ["--prepare", "--fetch-limit", "15"])
            exp.main(self.flags + ["--prepare"])
        api.assert_not_called()
        saved = exp.read(self.path)
        self.assertEqual(saved["settings"]["fetch_limit"], 15)
        self.assertEqual(saved["retrieval"], state["retrieval"])
        self.assertEqual(len(saved["limit_changes"]), 1)

    def test_original_overlap_never_fetches_again_even_without_local_file(self):
        import download_articles as dl
        state = self.state()
        state["query_version"] = exp.ex.digest(exp.SEEDS.read_text(encoding="utf-8"))
        (self.sample / "articles/a.json").unlink()
        with patch("impresso.client.ImpressoClient"), patch.object(dl, "LANGUAGES", ("en",)), \
                patch("impresso_prediction_seed_queries.iter_queries", return_value=[("frame", {})]), \
                patch.object(dl, "sample_query", return_value=iter([dict(id="a")])), \
                patch.object(dl, "save_article") as fetch, patch.object(dl, "UsageCounter"):
            exp.retrieve(state, self.path, self.sample, self.output)
        fetch.assert_not_called()
        self.assertEqual(state["refined"], [])
        self.assertEqual(state["refined_all"], ["a"])

    def test_sparse_cells_redistribute_quota_without_new_query_or_pages(self):
        import download_articles as dl
        state = self.state()
        state["settings"].update(comparison_articles=4, per_query=1)
        state["query_version"] = exp.ex.digest(exp.SEEDS.read_text(encoding="utf-8"))
        hits = [self.article(f"fresh{i}") for i in range(4)]
        def stream(client, usage, kwargs, rng, label):
            return iter([] if label.startswith("fr.") else hits)
        with patch("impresso.client.ImpressoClient"), patch.object(dl, "LANGUAGES", ("fr", "en")), \
                patch("impresso_prediction_seed_queries.iter_queries", return_value=[("frame", {})]), \
                patch.object(dl, "sample_query", side_effect=stream) as samples, patch.object(dl, "UsageCounter"):
            exp.retrieve(state, self.path, self.sample, self.output)
        self.assertEqual(len(state["refined"]), 4)
        self.assertEqual(samples.call_count, 2)

    def test_sdk_internal_read_error_and_server_error_never_retry(self):
        import httpx
        from impresso.util import retry
        with patch.object(retry, "MAX_ATTEMPTS", retry.MAX_ATTEMPTS):
            exp.impresso_client("offline-test")
            for failure in (httpx.ReadError("lost response"), None):
                attempts = []
                def handler(request):
                    attempts.append(request)
                    if failure:
                        raise failure
                    return httpx.Response(503, request=request)
                with retry.RetryingClient(transport=httpx.MockTransport(handler)) as client:
                    with redirect_stdout(io.StringIO()):
                        if failure:
                            with self.assertRaises(httpx.ReadError):
                                client.get("https://offline.test/")
                        else:
                            self.assertEqual(client.get("https://offline.test/").status_code, 503)
                self.assertEqual(len(attempts), 1)

    def test_uncertain_query_is_skipped_without_replaying_or_blocking_other_cells(self):
        import download_articles as dl
        state = self.state()
        state["query_version"] = exp.ex.digest(exp.SEEDS.read_text(encoding="utf-8"))
        def stream(client, usage, kwargs, rng, label):
            if label == "en.frame":
                raise exp.UncertainRetrieval("Uncertain saved request")
            yield self.article("new")
        with patch("impresso.client.ImpressoClient"), patch.object(dl, "LANGUAGES", ("en", "fr")), \
                patch("impresso_prediction_seed_queries.iter_queries", return_value=[("frame", {})]), \
                patch.object(dl, "sample_query", side_effect=stream), patch.object(dl, "UsageCounter"):
            exp.retrieve(state, self.path, self.sample, self.output)
        self.assertIn("en.frame", state["unresolved_queries"])
        self.assertEqual(state["refined"], ["new"])

    def test_interrupted_retrieval_reports_saved_new_articles_without_downloading(self):
        state = self.state()
        self.article("new")
        state.update(refined=["new"], refined_all=["new"], stage="retrieval")
        self.output.mkdir()
        with patch("urllib.request.urlopen") as api:
            exp.report(state, self.output)
        api.assert_not_called()
        with (self.output / "refined_articles.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["extraction_status"], "unattempted")
        self.assertEqual(rows[0]["accepted_distinct_predictions"], "")

    def test_pending_review_survives_handoff_without_replay_and_other_work_continues(self):
        self.article("b")
        state = self.state()
        self.saved_extraction(state)
        self.saved_extraction(state, "b")
        self.saved_review(state, "b")
        key = exp.ex.digest(exp.request_for(state["baseline"]["a"], state["review_config"], self.negative))
        state["llm"][key] = dict(status="pending", cost_usd=.01)
        exp.recover_saved_extractions(state)
        before = copy.deepcopy(state["llm"])
        with patch("urllib.request.urlopen") as api, redirect_stdout(io.StringIO()):
            exp.process(state, self.path, state["baseline"], 1)
        api.assert_not_called()
        self.assertEqual(state["llm"], before)
        self.assertIn("a", state["unresolved_articles"])
        self.assertEqual(exp.metrics(state, state["baseline"], {})["N"], 1)
        self.assertEqual(exp.metrics(state, state["baseline"], {})["failed"], 1)

    def test_mocked_bounded_full_workflow_stops(self):
        # Exercise stage transitions and repeated --run after completion; use a
        # local seed file so this test cannot change the repository's active queries.
        state = self.query_state()
        exp.save(self.path, state)
        seed = self.root / "seed_queries.py"
        seed.write_text(state["original_seeds"], encoding="utf-8")
        with patch.object(exp, "SEEDS", seed), patch.object(exp.ex, "load_dotenv"), \
                patch("urllib.request.urlopen") as api, redirect_stdout(io.StringIO()):
            exp.main(self.flags + ["--run"])
            packet = exp.read(self.output / "calibration.json")
            packet["approve_method"] = True
            for case in packet["cases"]:
                case["human_decision"] = "checked_negative" if case["id"] in state["baseline"] else "accept"
            exp.save(self.output / "calibration.json", packet)
            exp.main(self.flags + ["--run"])
            query = exp.read(self.output / "query-approval.json")
            query["approve"] = True
            exp.save(self.output / "query-approval.json", query)
            def fake_retrieve(state, *args):
                state["refined_all"] = ["a"]  # overlap is cached, no new evidence
                state["refined"] = []
                state["retrieval_done"] = True
            with patch.object(exp, "retrieve", side_effect=fake_retrieve) as retrieval:
                exp.main(self.flags + ["--run"])
                exp.main(self.flags + ["--run"])
            self.assertEqual(retrieval.call_count, 1)
        api.assert_not_called()
        report = exp.read(self.output / "report.json")
        self.assertEqual(report["stage"], "shortfall")
        self.assertEqual(report["statistics"]["refined_unseen"]["N"], 0)
        self.assertEqual(report["overlap"], 1)
        self.assertIsNone(report["positive_article_rate_difference_pp"])


if __name__ == "__main__":
    unittest.main()
