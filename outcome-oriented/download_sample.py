"""Sample up to 100 German, French and English articles from Impresso.

Install: pip install impresso   (Python 3.10+)
Run:     python outcome-oriented/download_sample.py
The first run requests an API token: https://impresso-project.ch/datalab/token

Each run creates a new directory in sample_articles, with text files and a manifest.
Sampling uses search-result counts and rejects non-articles, missing text, and
duplicates. It is approximate: it depends on Impresso's dates, language and type
labels, stable search ordering, access permissions, and available transcripts.
Search requests also consume Impresso quota and may take a while.
"""

import csv
import datetime as dt
import random
import sys
from pathlib import Path

from impresso import DateRange, connect
from impresso.util.error import ImpressoError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from impresso_quota import UsageCounter

TOTAL = 100
LANGUAGES = ("de", "fr", "en")
MAX_OFFSET = 5000
MAX_ATTEMPTS = 2000  # Avoid looping forever if few results have usable text.
OUTPUT = Path(__file__).resolve().parent / "sample_articles"


def main():
    rng = random.Random(42)
    client = connect()
    counts = {}
    usage = UsageCounter()
    print(usage.summary(), flush=True)

    def find(**kwargs):
        result = client.search.find(**kwargs)
        usage.record("search_results", len(result.raw.get("data", [])))
        return result

    def search(language, start, end, offset=0):
        return find(
            language=language, date_range=DateRange(start, end),
            with_text_contents=True, order_by="id", limit=1, offset=offset,
        )

    def count(language, start, end):
        key = (language, start, end)
        if key not in counts:
            counts[key] = search(language, start, end).total
        return counts[key]

    # Find the actual date range rather than imposing a historical cutoff.
    groups = []
    for language in LANGUAGES:
        print(f"Finding available dates for {language}...", flush=True)
        dates = []
        for order in ("date", "-date"):
            result = find(language=language, with_text_contents=True,
                          order_by=order, limit=1)
            hits = result.raw.get("data", [])
            if not hits:
                break
            dates.append(dt.date.fromisoformat(hits[0]["meta"]["date"][:10]))
        if len(dates) == 2:
            start, end = dates
            size = count(language, start, end)
            if size:
                groups.append((language, start, end, size))
            print(f"  {language}: {size:,} text items, {start} to {end}", flush=True)

    if not groups:
        raise SystemExit("No searchable text items found for the selected languages.")

    # A separate directory prevents earlier runs from being mistaken for this sample.
    OUTPUT.mkdir(exist_ok=True)
    run_dir = OUTPUT / dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    run_dir.mkdir()
    seen = set()
    print(f"Saving sample to {run_dir}", flush=True)
    with (run_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["id", "language", "date", "media", "title", "url"])
        file.flush()
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if len(seen) == TOTAL:
                break
            print(f"Selecting candidate {attempt} ({len(seen)}/{TOTAL} saved)...", flush=True)
            language, start, end, size = rng.choices(groups, weights=[g[3] for g in groups])[0]

            # Split dense periods until all offsets are reachable, choosing each
            # half in proportion to its count. Cached counts reduce repeat searches.
            while size > MAX_OFFSET + 1:
                if start == end:
                    raise SystemExit(f"Too many results on {start} for {language}; cannot sample without bias.")
                middle = start + (end - start) // 2
                right_start = middle + dt.timedelta(days=1)
                left_size = count(language, start, middle)
                right_size = count(language, right_start, end)
                if left_size + right_size != size:
                    raise SystemExit("Search counts changed or date ranges overlap; please retry.")
                if rng.randrange(size) < left_size:
                    end, size = middle, left_size
                else:
                    start, size = right_start, right_size

            hits = search(language, start, end, rng.randrange(size)).raw.get("data", [])
            if not hits:
                raise SystemExit("A selected search result disappeared; please retry.")
            hit = hits[0]
            cid = hit.get("id")
            if not cid or cid in seen:
                continue
            info = hit.get("text") or {}
            meta = hit.get("meta") or {}
            if not info.get("content") or not info.get("itemType"):
                item = client.content_items.get(cid)
                usage.record("item_fetches", 1)
                raw = item.raw
                info = {**info, **(raw.get("text") or {})}
                meta = {**meta, **(raw.get("meta") or {})}
            # Only save confirmed articles; an unknown type is not enough.
            text = info.get("content")
            if info.get("itemType") not in ("ar", "article") or not text:
                continue
            if info.get("langCode") and info["langCode"] != language:
                continue
            (run_dir / f"{cid}.txt").write_text(f"{cid}\n{text.strip()}\n", encoding="utf-8")
            writer.writerow([cid, language, str(meta.get("date", ""))[:10],
                             meta.get("mediaTitle") or meta.get("mediaId") or "",
                             (info.get("title") or "").replace("\n", " "),
                             f"https://impresso-project.ch/app/article/{cid}"])
            file.flush()  # Keep the manifest usable if the run is interrupted.
            seen.add(cid)
            print(f"  [{len(seen)}/{TOTAL}] {cid} | {usage.summary()}", flush=True)

    print(f"Finished: {len(seen)}/{TOTAL} articles in {run_dir}", flush=True)
    print(usage.summary(), flush=True)
    if len(seen) < TOTAL:
        print("Stopped after the attempt limit; the sample is incomplete.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except ImpressoError as exc:
        if getattr(exc.error, "status", None) == 500:
            raise SystemExit(
                "Impresso returned an internal server error after retrying. "
                "Wait a few minutes and try again; if it persists, send Impresso "
                "the failing request shown above. The local quota counter may "
                "not include requests that failed or were retried."
            ) from None
        raise
