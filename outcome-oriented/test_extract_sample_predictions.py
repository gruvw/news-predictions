"""Offline checks for the paid-call guardrails and review exports."""

from contextlib import redirect_stdout
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import extract_sample_predictions as extract


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sample = self.root / "sample"
        (self.sample / "articles").mkdir(parents=True)
        self.output = self.root / "output"
        for cid in ("a", "b"):
            article = dict(id=cid, meta={"date": "1900-01-01T00:00:00+00:00"}, text={
                "langCode": "en", "content": "Analysts predict prices will fall next year." * 6})
            (self.sample / "articles" / f"{cid}.json").write_text(json.dumps(article))
        self.result = dict(predictions=[], no_prediction_reason="Only a routine announcement.")

    def response(self, result=None, status="completed"):
        raw = dict(status=status, usage=dict(input_tokens=100, output_tokens=50),
                   output=[dict(content=[dict(type="output_text", text=json.dumps(
                       self.result if result is None else result))])])
        return io.BytesIO(json.dumps(raw).encode())

    def run_main(self, *flags, response=None):
        argv = ["extract", "--sample", str(self.sample), "--output", str(self.output), *flags]
        with patch("sys.argv", argv), patch.dict("os.environ", {"OPENAI_API_KEY": "test"}), \
                patch.object(extract, "load_dotenv") as env_loader, \
                patch("urllib.request.urlopen", return_value=response or self.response()) as api, \
                redirect_stdout(io.StringIO()):
            extract.main()
            env_loader.assert_called_once_with(extract.HERE.parent / ".env", override=True)
        return api.call_count

    def read_csv(self, name):
        with (self.output / name).open(encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))

    def test_preview_is_free_and_writes_nothing(self):
        self.assertEqual(self.run_main(), 0)
        self.assertFalse(self.output.exists())

    def test_negative_and_resume_skip_paid_call(self):
        self.assertEqual(self.run_main("--run", "--limit", "1"), 1)
        negative = self.read_csv("articles.csv")[0]
        self.assertEqual(negative["status"], "completed")
        self.assertEqual(negative["prediction_count"], "0")
        self.assertTrue(negative["no_prediction_reason"])
        self.assertEqual(self.run_main("--run", "--limit", "1"), 1)
        self.assertEqual(self.run_main("--run"), 0)

    def test_budget_prevents_call_including_after_resume(self):
        self.assertEqual(self.run_main("--run", "--budget-usd", "0.000001"), 0)
        self.run_main("--run", "--limit", "1")
        self.assertEqual(self.run_main("--run", "--budget-usd", "0.000001"), 0)

    def test_incomplete_is_error_never_negative_or_automatically_retried(self):
        self.assertEqual(self.run_main("--run", "--limit", "1",
                                      response=self.response(status="incomplete")), 1)
        self.assertEqual(self.read_csv("articles.csv")[0]["status"], "error")
        self.assertEqual(self.read_csv("articles.csv")[0]["prediction_count"], "")
        self.run_main("--run", "--limit", "1")
        self.assertEqual(self.run_main("--run"), 0)

    def test_exact_quotes_statement_columns_and_review_preservation(self):
        quote = "Analysts predict prices will fall next year."
        self.result = dict(no_prediction_reason="", predictions=[dict(quote=quote,
            statement="Prices will fall in 1901.", predictor="Analysts", confidence="likely",
            eligibility_reason="Prices may rise instead.",
            cues=[dict(evidence="predict", terms=["predict"], operator="OR",
                       family="forecast_frame", rationale="A forecasting verb.")])])
        self.run_main("--run", "--limit", "1")
        row = self.read_csv("predictions.csv")[0]
        self.assertEqual(row["quote"], quote)
        self.assertEqual(row["date"], "1900-01-01")
        self.assertEqual(row["statement"], "Prices will fall in 1901.")
        self.assertNotIn("context", row)
        self.assertNotIn("source_file", row)
        self.assertNotIn("english_translation", row)
        self.assertNotIn("source_file", self.read_csv("articles.csv")[0])
        path = self.output / "predictions.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(row))
            writer.writeheader()
            writer.writerow({**row, "review_decision": "accept", "review_notes": "checked"})
        self.run_main("--run", "--limit", "1")
        self.assertEqual(self.read_csv("predictions.csv")[0]["review_decision"], "accept")
        self.assertEqual(self.read_csv("cue_candidates.csv")[0]["support_articles"], "2")
        self.result["predictions"][0]["quote"] = "An invented quotation"
        with self.assertRaisesRegex(ValueError, "exact source"):
            extract.validate(json.loads(self.response().read()), quote)

    def test_long_quote_is_rejected_without_truncation(self):
        quote = "x" * (extract.MAX_QUOTE_CHARS + 1)
        self.result = dict(no_prediction_reason="", predictions=[dict(quote=quote,
            statement="A future event will occur.", predictor="", confidence="likely",
            eligibility_reason="Observable alternative.", cues=[])])
        with self.assertRaisesRegex(ValueError, "exceeds"):
            extract.validate(json.loads(self.response().read()), quote)

    def test_small_copying_error_restores_original_ocr(self):
        source = "unb die Lage verwickeln könnte."
        copied = "und die Lage verwickeln könnte."
        self.result = dict(no_prediction_reason="", predictions=[dict(quote=copied,
            statement="The situation could become more complicated.", predictor="",
            confidence="possible", eligibility_reason="An uncertain future state.",
            cues=[dict(evidence="könnte", terms=["könnte"], operator="OR",
                       family="likelihood", rationale="Modal verb.")])])
        raw = json.loads(self.response().read())
        result = extract.validate(raw, source)
        self.assertEqual(result["predictions"][0]["quote"], source)
        original = json.loads(raw["output"][0]["content"][0]["text"])
        self.assertEqual(original["predictions"][0]["quote"], copied)

    def test_ambiguous_or_large_copying_errors_remain_errors(self):
        quote = "und die Lage verwickeln könnte."
        with self.assertRaisesRegex(ValueError, "unique"):
            extract.source_quote(quote, "unb die Lage verwickeln könnte. unf die Lage verwickeln könnte.")
        with self.assertRaises(ValueError):
            extract.source_quote("This invented claim will never happen.", "Completely unrelated source text.")
        with self.assertRaises(ValueError):
            extract.source_quote("und", "unb")

    def test_old_short_and_redacted_library_files_are_excluded(self):
        for cid, content in (("short", "A short notice"), ("redacted", "[REDACTED]")):
            article = dict(id=cid, meta={"date": "1900-01-01"}, text={
                "langCode": "en", "content": content})
            (self.sample / "articles" / f"{cid}.json").write_text(json.dumps(article))
        self.assertEqual(set(extract.load_articles(self.sample)), {"a", "b"})
        self.assertNotIn("redacted", extract.load_articles(self.sample, min_chars=1))

    def test_pending_request_is_skipped_and_reservation_counts(self):
        self.run_main("--run", "--limit", "1")
        state_path = self.output / "checkpoint.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        record = next(iter(state["records"].values()))
        record.update(status="pending", cost_usd=0.25)
        record.pop("result")
        extract.checkpoint(state_path, state)
        self.assertEqual(self.run_main("--run"), 0)

    def test_prompt_change_refuses_mixed_results(self):
        self.run_main("--run", "--limit", "1")
        with patch.object(extract, "PROMPT", "changed prompt"):
            with self.assertRaisesRegex(ValueError, "new --output"):
                self.run_main("--run")

    def test_query_changes_reuse_results_and_refresh_provenance(self):
        self.run_main("--run")
        round_dir = self.sample / "rounds" / "new_round"
        round_dir.mkdir(parents=True)
        (round_dir / "references.csv").write_text("article_id,query_id\na,en.new_frame\n")
        with patch.object(extract, "seed_groups", return_value={"NEW": {"en": ["predict"]}}):
            self.assertEqual(self.run_main("--run"), 0)
        rows = {row["article_id"]: row for row in self.read_csv("articles.csv")}
        self.assertEqual(json.loads(rows["a"]["query_ids"]), ["en.new_frame"])


if __name__ == "__main__":
    unittest.main()
