"""Download the step-2 pilot using the prediction seed queries.

Install: pip install impresso
Run from the repository root: python outcome-oriented/download_articles.py
On first connection, Impresso requests an API token.

Defaults: all years, 20 articles per family/language, up to 240 unique articles.
Edit the constants below to change the sample. Each run creates a retrieval round
under prediction_sample/rounds; unique articles live in prediction_sample/articles.
Article JSON files retain metadata and OCR text. A round's references.csv records
sampled query/article associations, including overlaps. It does not enumerate
every query that could match each article. Re-running creates a new round and
reuses article files already downloaded.

Sampling: randomly ordered pages within the first 5,000 results sorted by ID,
then shuffled hits within each page. This is a cheap, approximate sample, NOT
a uniform sample of the full archive. At most five pages are tried per query;
queries with few accessible articles may fall short. Transcripts must contain at
least 200 characters after trimming whitespace; [REDACTED] is always excluded.
This uses available transcript text, not the source article's reported length.
Use --min-chars to change the minimum and --seed to draw a different sample.

UsageCounter persists successful search-result and article-fetch counts in the
repository's impresso_usage.json, including discarded/repeated results. These
are approximate local usage counts, not the account's remaining quota. Do not
run this alongside another downloader using the same counter file.
"""

import argparse
import csv
import datetime as dt
import json
import random
import shutil
import sys
from pathlib import Path

from impresso import connect

from impresso_prediction_seed_queries import iter_queries

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from impresso_quota import UsageCounter


LANGUAGES = ("fr", "de", "en")
ARTICLES_PER_QUERY = 20
PAGE_SIZE = 20
RESULT_WINDOW = 5_000
MAX_PAGES_PER_QUERY = 5
RANDOM_SEED = 42  # Change to draw another sample; unchanged settings repeat it.
MIN_ARTICLE_CHARS = 200
OUTPUT = Path(__file__).resolve().parent / "prediction_sample"


def search(client, usage, kwargs, offset, limit):
    result = client.search.find(**kwargs, order_by="id", offset=offset, limit=limit)
    usage.record("search_results", len(result.raw.get("data", [])))
    return result


def sample_query(client, usage, kwargs, rng, label):
    """Yield shuffled candidates from a few random pages, counting every hit."""
    print(f"{label}: counting matches...", flush=True)
    total = search(client, usage, kwargs, offset=0, limit=1).total
    reachable = min(total, RESULT_WINDOW)
    print(f"  {total:,} matches; sampling within the first {reachable:,}.", flush=True)
    offsets = list(range(0, reachable, PAGE_SIZE))
    rng.shuffle(offsets)
    for page, offset in enumerate(offsets[:MAX_PAGES_PER_QUERY], 1):
        print(f"  Searching page {page}/{min(len(offsets), MAX_PAGES_PER_QUERY)} "
              f"(offset {offset:,})...", flush=True)
        result = search(client, usage, kwargs, offset, min(PAGE_SIZE, reachable - offset))
        hits = result.raw.get("data", [])
        rng.shuffle(hits)
        yield from hits


def save_article(client, usage, hit, articles, min_chars=MIN_ARTICLE_CHARS):
    """Validate cached AND new transcripts before counting an article in a round."""
    path = articles / f"{hit['id']}.json"
    cached = path.exists()
    if cached:
        hit = json.loads(path.read_text(encoding="utf-8"))
    info = hit.get("text") or {}
    if info.get("itemType") and info["itemType"] not in ("ar", "article"):
        return None
    if not cached and (not info.get("content") or not info.get("itemType")):
        print(f"    Fetching article {hit['id']}...", flush=True)
        item = client.content_items.get(hit["id"])
        usage.record("item_fetches", 1)
        hit = {**hit, **item.raw}
        info = hit.get("text") or {}
    if info.get("itemType") not in ("ar", "article") or not info.get("content"):
        return None
    transcript = info["content"].strip()
    if len(transcript) < min_chars or "[REDACTED]" in transcript:
        return "too_short_or_redacted"
    if cached:
        return "reused"
    path.write_text(json.dumps(hit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "saved"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-chars", type=int, default=MIN_ARTICLE_CHARS)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()
    if args.min_chars < 1:
        parser.error("min-chars must be positive")
    client = connect(public_api_url="https://dev.impresso-project.ch/public-api/v1")
    usage = UsageCounter()
    print(usage.summary(), flush=True)
    articles = OUTPUT / "articles"
    articles.mkdir(parents=True, exist_ok=True)
    round_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    round_dir = OUTPUT / "rounds" / round_id
    round_dir.mkdir(parents=True)
    # Keep the exact seed definitions used, even if they change in a later round.
    shutil.copyfile(Path(__file__).with_name("impresso_prediction_seed_queries.py"),
                    round_dir / "seed_queries.py")
    settings = dict(languages=LANGUAGES, articles_per_query=ARTICLES_PER_QUERY,
                    page_size=PAGE_SIZE, result_window=RESULT_WINDOW,
                    max_pages_per_query=MAX_PAGES_PER_QUERY, random_seed=args.seed,
                    min_article_chars=args.min_chars,
                    years="all", order_by="id")
    (round_dir / "settings.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    queries = [(language, family, kwargs)
               for language in LANGUAGES for family, kwargs in iter_queries(language)]
    unique = set()
    downloaded = 0
    print(f"Round {round_id}: {len(queries)} queries, up to "
          f"{len(queries) * ARTICLES_PER_QUERY} articles.\nOutput: {round_dir}", flush=True)
    try:
        with (round_dir / "references.csv").open("w", newline="", encoding="utf-8") as file, \
                (round_dir / "skipped.csv").open("w", newline="", encoding="utf-8") as skip_file:
            writer = csv.writer(file)
            writer.writerow(["round", "query_id", "language", "family", "article_id"])
            skip_writer = csv.writer(skip_file)
            skip_writer.writerow(["round", "query_id", "article_id", "reason"])
            for index, (language, family, kwargs) in enumerate(queries, 1):
                query_id = f"{language}.{family}"
                rng = random.Random(f"{args.seed}:{query_id}")
                selected = set()
                seen = set()
                label = f"[{index}/{len(queries)}] {query_id}"
                for hit in sample_query(client, usage, kwargs, rng, label):
                    cid = hit["id"]
                    if cid in seen:
                        continue
                    seen.add(cid)
                    status = save_article(client, usage, hit, articles, args.min_chars)
                    if status == "too_short_or_redacted":
                        skip_writer.writerow([round_id, query_id, cid, status])
                        skip_file.flush()
                        print(f"  Skipping {cid}: short/redacted transcript", flush=True)
                        continue
                    if status is None:
                        continue
                    writer.writerow([round_id, query_id, language, family, cid])
                    file.flush()
                    selected.add(cid)
                    unique.add(cid)
                    downloaded += status == "saved"
                    print(f"  {len(selected)}/{ARTICLES_PER_QUERY}: {cid} ({status}); "
                          f"{len(unique)} unique this round", flush=True)
                    if len(selected) == ARTICLES_PER_QUERY:
                        break
                print(f"  Query complete: {len(selected)}/{ARTICLES_PER_QUERY} articles. "
                      f"{usage.summary()}", flush=True)
    finally:
        print(f"Round saved: {len(unique)} unique articles, {downloaded} newly downloaded.", flush=True)
        print(usage.summary(), flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nInterrupted. Saved articles and references remain available.")
