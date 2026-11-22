"""Offline transcript-filter checks; no Impresso requests or quota writes."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import download_articles as download


class TranscriptFilterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.articles = Path(self.temp.name)
        self.client, self.usage = Mock(), Mock()

    def hit(self, text):
        return dict(id="article-1", text=dict(itemType="ar", content=text,
                                            contentLength=99999))

    def save(self, hit, **kwargs):
        return download.save_article(self.client, self.usage, hit, self.articles, **kwargs)

    def test_redacted_hit_is_not_saved_or_fetched(self):
        self.assertEqual(self.save(self.hit("[REDACTED]")), "too_short_or_redacted")
        self.assertFalse((self.articles / "article-1.json").exists())
        self.client.content_items.get.assert_not_called()

    def test_cached_redacted_article_is_neither_reused_nor_deleted(self):
        path = self.articles / "article-1.json"
        original = json.dumps(self.hit("[REDACTED]"))
        path.write_text(original)
        self.assertEqual(self.save(self.hit("x" * 500)), "too_short_or_redacted")
        self.assertEqual(path.read_text(), original)
        self.client.content_items.get.assert_not_called()

    def test_available_transcript_length_not_reported_length(self):
        self.assertEqual(self.save(self.hit(" " * 1000 + "x" * 199)), "too_short_or_redacted")
        self.assertEqual(self.save(self.hit("x" * 200)), "saved")
        self.assertEqual(self.save(self.hit("unused")), "reused")

    def test_fetched_redacted_article_is_also_rejected(self):
        self.client.content_items.get.return_value.raw = self.hit("[REDACTED]")
        self.assertEqual(self.save(dict(id="article-1", text={})), "too_short_or_redacted")
        self.usage.record.assert_called_once_with("item_fetches", 1)
        self.assertFalse((self.articles / "article-1.json").exists())

    def test_custom_minimum_cannot_admit_redacted_marker(self):
        self.assertEqual(self.save(self.hit("[REDACTED]"), min_chars=1), "too_short_or_redacted")


if __name__ == "__main__":
    unittest.main()
