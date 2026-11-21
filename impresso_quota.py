"""Persistent, approximate Impresso usage counts for this repository.

Counts successful search-result items and successful content-item fetches, including
repeated items. They are not Impresso's account-wide quota balance: other clients,
server-side accounting, retries and failed requests are not captured. Do not run
multiple downloader processes concurrently against the same counter file.
"""

import datetime as dt
import json
import threading
import time
from pathlib import Path


COUNTER = Path(__file__).resolve().parent / "impresso_usage.json"


class UsageCounter:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = json.loads(COUNTER.read_text(encoding="utf-8")) if COUNTER.exists() else {}

    def record(self, kind, amount):
        if not amount:
            return
        with self.lock:
            # UTC months make the local accounting period explicit; Impresso's
            # actual quota reset time and account-wide usage may differ.
            month = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
            totals = self.data.setdefault(month, {"search_results": 0, "item_fetches": 0})
            totals[kind] += amount
            temp = COUNTER.with_suffix(".tmp")
            temp.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
            # Windows may briefly block replacement while another program reads
            # the file (for example, an editor or antivirus scanner).
            for attempt in range(5):
                try:
                    temp.replace(COUNTER)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.2 * (attempt + 1))

    def summary(self):
        with self.lock:
            month = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
            totals = self.data.get(month, {})
            search = totals.get("search_results", 0)
            fetches = totals.get("item_fetches", 0)
            return (f"Local usage for {month} UTC: {search + fetches:,} item responses "
                    f"({search:,} search results, {fetches:,} item fetches)")
