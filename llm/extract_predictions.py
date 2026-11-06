#!/usr/bin/env python3
"""
Extract predictive statements from the downloaded Impresso articles with DeepSeek.

Input
-----
articles/<id>.txt   (line 1: Impresso content item id, line 2+: article text)
manifest.csv        (optional, written by download_articles.py: date, media, language)

Output (next to the script)
------
extractions.jsonl   one line per processed article, with all its predictions.
                    This file makes the script resumable: re-running it only
                    processes articles that are not in it yet.
predictions.csv     flat list of every predictive statement found (rebuilt at the end
                    of each run from extractions.jsonl).

Requirements
------------
    pip install openai pydantic        # DeepSeek's API is OpenAI-compatible
    export DEEPSEEK_API_KEY=...        # https://platform.deepseek.com/api_keys
"""

from __future__ import annotations

import csv
import json
import logging
import os
import random
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal, Optional

import openai
from pydantic import BaseModel, Field, ValidationError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = "deepseek-flash"        # or "deepseek-v4-pro" (more capable, ~4x the price)
THINKING = True                # let the model reason before answering (slower, more output tokens)
REASONING_EFFORT = "low"        # with THINKING: "low", "high" (DeepSeek's default) or "max"
MAX_ARTICLES: int | None = None # process only the first N articles (handy for a test run)
PARALLEL_REQUESTS = 8
# The output limit covers the model's reasoning as well as the JSON answer, so thinking
# needs a much larger budget or the answer gets cut off.
MAX_OUTPUT_TOKENS = 8_000
MAX_OUTPUT_TOKENS_THINKING = 32_000
CHUNK_CHARS = 30_000            # longer texts (~5,000+ words) are sent in several parts
ATTEMPTS_PER_ARTICLE = 2        # ask again if the answer is not valid JSON
FIX_MISSING_YEARS = True        # send statements without a year back to the model once
RANDOM_SEED = 42                # articles are processed in a random (but repeatable) order

API_BASE_URL = "https://api.deepseek.com"

SCRIPT_DIR = Path(__file__).resolve().parent
ARTICLES_DIR = SCRIPT_DIR / "articles"
MANIFEST_PATH = SCRIPT_DIR / "manifest.csv"
EXTRACTIONS_PATH = SCRIPT_DIR / "extractions.jsonl"
PREDICTIONS_CSV = SCRIPT_DIR / "predictions.csv"

CATEGORIES = Literal[
    "political", "economical", "environmental", "science_technology", "infrastructure",
    "health", "sport_events", "justice", "security", "energy", "education", "business",
    "entertainment_leisure", "celebrity", "other",
]

# ---------------------------------------------------------------------------
# Output schema (validated after each answer)
# ---------------------------------------------------------------------------


class Prediction(BaseModel):
    quote: str
    statement: str
    category: CATEGORIES
    resolution_date: Optional[str] = None
    predictor: Optional[str] = None
    confidence: Literal["certain", "likely", "possible", "unlikely"]
    verifiable: bool


SYSTEM_PROMPT = """\
You are helping build a dataset of predictions made in historical newspapers, used to test \
whether language models can forecast events after their training cut-off.

You will receive a newspaper text (French, German, English or Luxembourgish), digitised \
with OCR, so expect recognition errors and broken hyphenation. It may be a single article, \
or a whole page or long document containing several unrelated articles: find every predictive \
statement in all of it, and make sure each one is attributed to the right story. Long texts \
may be sent in several parts; treat the part you receive on its own.

A predictive statement makes a claim about something that has not yet happened (or is not yet \
known) at the publication date, and whose outcome could later be judged clearly true or false. \
Include:
- forecasts and expectations (election outcomes, prices, harvests, weather, epidemics, \
  war outcomes, trial verdicts, sports results, attendance...);
- announced plans whose realisation is uncertain (a tunnel to open in 1960, a treaty to be \
  signed next month, a strike planned for Monday);
- newsworthy scheduled events: sports fixtures, elections and votes, parliamentary sessions, \
  trials, summits and conferences, the opening of roads, bridges, buildings or lines;
- implicit predictions ("the bill has no chance in the Senate", "prices will keep rising");
- conditional predictions ("if the permit is granted, the centre will open in 1973").

Exclude:
- statements about the past or present, including counterfactuals ("this jump would have \
  won bronze");
- opinions, value judgements, hopes, stated aims and advice whose outcome could not be judged \
  clearly true or false ("the police will keep the prestige it deserves", "the president aims \
  to speed up parliamentary work", "the sprinters will have to watch out");
- fiction (serialised novels, short stories, plays, film or book plots), horoscopes and \
  advertisements, including classified ads;
- agenda and listing items: concerts, shows, screenings, exhibitions and vernissages, lectures, \
  markets and local festivities, opening hours and closures of museums, pools or shops, \
  TV and radio programme schedules, timetables and practical notices (a new phone number);
- predictions about the private lives of people who are not public figures;
- open questions and requirements that do not say which outcome is expected ("the retrial will \
  decide whether he is guilty", "Nantes must beat Panathinaikos to qualify"). Include them only \
  if the article leans one way, and then state the outcome it expects;
- sentences too fragmentary (cut off by the page layout or OCR) to tell what is predicted.

List each prediction once, even if it is repeated or restated by several people in the text. \
Choose each prediction's category from what it predicts, not from the rest of the text.

THE ENGLISH STATEMENT MUST STAND ON ITS OWN. It will be shown, without the article, to \
someone asked whether it came true. Using the article's context and publication date:
- give an explicit date or period: turn "next year", "on Sunday", "this season", "soon" into \
  absolute dates ("in 1955", "on 12 June 1966", "in the 1965-66 season", "by the end of \
  1972"); if the article gives no time frame, anchor it to the publication date ("as of \
  February 1966, ...");
- name places precisely, with the country when useful ("Boudry, canton of Neuchâtel, \
  Switzerland"), and name competitions, leagues, institutions, projects and laws fully;
- write it as a plain claim about what will happen, without saying who predicted it (that goes \
  in "predictor") and without hedging (that goes in "confidence"): not "According to the chief \
  engineer, the tunnel could open in 1962" but "The tunnel will open in 1962". For predictions \
  that something will not happen, state the negative claim ("Parakou will not be chosen");
- keep the exact meaning of what is predicted: removing the attribution and hedging must not \
  change the claim. "Work will not start before 1969" stays "Work on ... will not start before \
  1969", never "Work will start in 1969". Never choose a direction the article does not give;
- one threshold per claim: if the article gives several values or alternatives ("subsidies \
  of 40%, or at least 35%"), make one separate prediction per value ("... will reach 40% of \
  the cost" and "... will reach at least 35% of the cost"), each with its own confidence;
- people and organisations that are part of the predicted event stay in the statement, named \
  with their role at the time ("Gilbert Facchinetti, president of Neuchâtel Xamax"), never \
  "the minister" or "the club" alone;
- spell out the condition of conditional predictions;
- use only what the article says: never add what you may know about what actually happened \
  afterwards, and do not invent details the text does not give.

Answer with a JSON object only, in exactly this format:
{
  "predictions": [
    {
      "quote": "the statement as written in the article, original language (obvious OCR errors may be fixed)",
      "statement": "standalone English statement following the rules above",
      "category": "one of: political, economical, environmental, science_technology, infrastructure, health, sport_events, justice, security, energy, education, business, entertainment_leisure, celebrity, other",
      "resolution_date": "when the outcome should be known, as YYYY, YYYY-MM or YYYY-MM-DD; null if no time frame",
      "predictor": "who makes the prediction ('the newspaper', 'Swiss Federal Council', a named person...); null if unclear",
      "confidence": "certain (scheduled/announced) | likely ('probably', 'expected') | possible ('may', 'could') | unlikely",
      "verifiable": true if the outcome could realistically be checked later against historical records, else false
    }
  ]
}

Example: an article published on 1959-06-12 about the Great St Bernard road tunnel between \
Switzerland and Italy says, in its last paragraph, "Selon l'ingénieur en chef, le tunnel \
pourrait être ouvert à la circulation dans trois ans."
{"predictions": [{"quote": "le tunnel pourrait être ouvert à la circulation dans trois ans", \
"statement": "The Great St Bernard road tunnel between Switzerland and Italy will open to \
traffic in 1962.", \
"category": "infrastructure", "resolution_date": "1962", "predictor": "chief engineer of the \
Great St Bernard road tunnel", "confidence": "possible", "verifiable": true}]}

If there is no predictive statement, answer {"predictions": []}.
"""

# ---------------------------------------------------------------------------

log = logging.getLogger("extract")
write_lock = threading.Lock()


def load_articles() -> list[dict]:
    meta: dict[str, dict] = {}
    if MANIFEST_PATH.exists():
        with MANIFEST_PATH.open(newline="", encoding="utf-8") as f:
            meta = {row["id"]: row for row in csv.DictReader(f)}

    articles = []
    for path in sorted(ARTICLES_DIR.glob("*.txt")):
        ref, _, text = path.read_text(encoding="utf-8").partition("\n")
        ref = ref.strip()
        m = meta.get(ref, {})
        # Impresso ids contain the issue date: JDG-1954-05-17-a-i0116
        date = m.get("date") or (re.search(r"\d{4}-\d{2}-\d{2}", ref) or [""])[0]
        articles.append({
            "article_id": ref,
            "publication_date": date,
            "media": m.get("media", ""),
            "language": m.get("language", ""),
            "topic_query": m.get("topic", ""),   # topic of the search that found the article
            "article_words": len(text.split()),
            "text": text.strip(),
        })
    return articles


def already_done() -> set[str]:
    if not EXTRACTIONS_PATH.exists():
        return set()
    with EXTRACTIONS_PATH.open(encoding="utf-8") as f:
        return {json.loads(line)["article_id"] for line in f if line.strip()}


def parse_predictions(content: str, article_id: str) -> list[Prediction]:
    """Validate the model's JSON. Raises ValueError if it is not usable at all;
    individual malformed predictions are dropped with a warning."""
    data = json.loads(content)  # raises json.JSONDecodeError (a ValueError)
    items = data.get("predictions") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("no 'predictions' list in the answer")
    predictions = []
    for item in items:
        try:
            predictions.append(Prediction.model_validate(item))
        except ValidationError as e:
            log.warning("%s: dropped a malformed prediction (%s)", article_id,
                        e.errors()[0].get("msg"))
    return predictions


def split_text(text: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    """Split a long text into parts of at most max_chars, cutting at line breaks
    (or spaces) so sentences are cut as rarely as possible."""
    parts = []
    while len(text) > max_chars:
        cut = text.rfind("\n", max_chars // 2, max_chars)
        if cut == -1:
            cut = text.rfind(" ", max_chars // 2, max_chars)
        if cut == -1:
            cut = max_chars
        parts.append(text[:cut].strip())
        text = text[cut:].strip()
    parts.append(text)
    return [p for p in parts if p]


def extract(client: openai.OpenAI, article: dict) -> list[Prediction] | None:
    """Extract predictions from an article, part by part for long texts.
    Returns None if any part fails (the whole article is retried on the next run)."""
    parts = split_text(article["text"])
    predictions: list[Prediction] = []
    for i, part in enumerate(parts, 1):
        found = extract_part(client, article, part, i, len(parts))
        if found is None:
            return None
        predictions.extend(found)
    return predictions


def extract_part(client: openai.OpenAI, article: dict, text: str, part: int,
                 n_parts: int) -> list[Prediction] | None:
    header = f"Publication date: {article['publication_date'] or 'unknown'}"
    if article["media"]:
        header += f"\nNewspaper: {article['media']}"
    if n_parts > 1:
        header += f"\nPart {part} of {n_parts} of a long text"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{header}\n\n<article>\n{text}\n</article>"},
    ]

    for attempt in range(1, ATTEMPTS_PER_ARTICLE + 1):
        content = ask(client, messages, article["article_id"])
        try:
            predictions = parse_predictions(content, article["article_id"])
        except ValueError as e:
            log.warning("%s: invalid JSON answer (attempt %d/%d): %s", article["article_id"],
                        attempt, ATTEMPTS_PER_ARTICLE, e)
            continue
        if FIX_MISSING_YEARS:
            fix_missing_years(client, messages, content, predictions, article)
        return predictions
    return None


def ask(client: openai.OpenAI, messages: list[dict], article_id: str) -> str:
    max_tokens = MAX_OUTPUT_TOKENS_THINKING if THINKING else MAX_OUTPUT_TOKENS
    kwargs = {}
    if THINKING:
        kwargs["reasoning_effort"] = REASONING_EFFORT
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        extra_body={"thinking": {"type": "enabled" if THINKING else "disabled"}},
        **kwargs,
    )
    choice = response.choices[0]
    if choice.finish_reason == "length":
        details = getattr(response.usage, "completion_tokens_details", None)
        reasoning = getattr(details, "reasoning_tokens", None)
        log.warning("%s: answer cut off at %d tokens%s", article_id, max_tokens,
                    f" ({reasoning} of them spent reasoning)" if reasoning else "")
    return choice.message.content or ""


# A four-digit year between 1600 and 2099 (also matches "1965-66" or "the 1950s").
YEAR_RE = re.compile(r"(?<!\d)(1[6-9]\d\d|20\d\d)(?!\d)")

FIX_YEARS_PROMPT = """\
These statements from your answer contain no explicit year, so they cannot be judged without \
the article. Rewrite each one to include an explicit date or year, taken from the article or \
worked out from the publication date ({date}); if the article gives no time frame, anchor it \
with "as of <Month YYYY>". Change nothing else and keep the exact meaning.

{statements}

Answer with a JSON object only: {{"statements": ["...", "..."]}}, with the rewritten \
statements in the same order."""


def fix_missing_years(client: openai.OpenAI, messages: list[dict], previous_answer: str,
                      predictions: list[Prediction], article: dict) -> None:
    """Ask the model once to add a year to the statements lacking one (edited in place).
    Statements that still have no year afterwards are kept as they are."""
    missing = [p for p in predictions if not YEAR_RE.search(p.statement)]
    if not missing:
        return
    listing = "\n".join(f"{i}. {p.statement}" for i, p in enumerate(missing, 1))
    follow_up = messages + [
        {"role": "assistant", "content": previous_answer},
        {"role": "user", "content": FIX_YEARS_PROMPT.format(
            date=article["publication_date"] or "unknown", statements=listing)},
    ]
    content = ask(client, follow_up, article["article_id"])
    try:
        rewritten = json.loads(content)["statements"]
        if not isinstance(rewritten, list) or len(rewritten) != len(missing):
            raise ValueError("wrong number of statements")
    except (ValueError, KeyError, TypeError) as e:
        log.warning("%s: could not add missing years (%s)", article["article_id"], e)
        return
    fixed = 0
    for p, new in zip(missing, rewritten):
        if isinstance(new, str) and YEAR_RE.search(new):
            p.statement = " ".join(new.split())
            fixed += 1
    log.info("  %s: added a year to %d of %d statements", article["article_id"], fixed,
             len(missing))


class StopRun(Exception):
    """An error that will hit every request (no credit left, invalid key): stop the run."""


STOP_ERRORS = {
    401: "DeepSeek rejected the API key (401). Check DEEPSEEK_API_KEY",
    402: "DeepSeek balance exhausted (402). Top up at platform.deepseek.com",
}
stop_event = threading.Event()


def process(client: openai.OpenAI, article: dict) -> int | None:
    if stop_event.is_set():  # the run is stopping: don't start new articles
        return None
    try:
        predictions = extract(client, article)
    except openai.APIStatusError as e:
        if e.status_code in STOP_ERRORS:
            stop_event.set()
            raise StopRun(STOP_ERRORS[e.status_code]) from e
        log.warning("%s: API error, will be retried on the next run: %s", article["article_id"], e)
        return None
    except openai.APIError as e:
        log.warning("%s: API error, will be retried on the next run: %s", article["article_id"], e)
        return None
    if predictions is None:
        return None
    record = {k: v for k, v in article.items() if k != "text"}
    record["model"] = MODEL
    record["predictions"] = [p.model_dump() for p in predictions]
    with write_lock, EXTRACTIONS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(predictions)


def write_csv() -> int:
    fields = ["article_id", "publication_date", "media", "language", "article_words",
              "topic_query", "quote", "statement", "category", "resolution_date",
              "predictor", "confidence", "verifiable"]
    n = 0
    with EXTRACTIONS_PATH.open(encoding="utf-8") as src, \
            PREDICTIONS_CSV.open("w", newline="", encoding="utf-8") as dst:
        writer = csv.DictWriter(dst, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for line in src:
            if not line.strip():
                continue
            rec = json.loads(line)
            for p in rec["predictions"]:
                writer.writerow({**rec, **p})
                n += 1
    return n


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        sys.exit("Set the DEEPSEEK_API_KEY environment variable first.")

    articles = load_articles()
    # Random order, so that a test run (MAX_ARTICLES) or a run cut short is a fair sample
    # of the whole set rather than the first newspapers in alphabetical order.
    random.Random(RANDOM_SEED).shuffle(articles)
    if MAX_ARTICLES:
        articles = articles[:MAX_ARTICLES]
    done = already_done()
    todo = [a for a in articles if a["article_id"] not in done]
    log.info("%d articles, %d already processed, %d to go (model: %s).",
             len(articles), len(articles) - len(todo), len(todo), MODEL)

    # The SDK retries rate limits (429), server errors and timeouts with backoff.
    client = openai.OpenAI(api_key=api_key, base_url=API_BASE_URL, max_retries=6,
                           timeout=900 if THINKING else 300)  # thinking answers take longer
    failed = 0
    stopped: StopRun | None = None
    with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as pool:
        futures = {pool.submit(process, client, a): a for a in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                n = fut.result()
            except StopRun as e:
                stopped = e
                # Drop the articles not started yet; the few already running finish (and
                # are saved if they got their answer in time).
                pool.shutdown(wait=False, cancel_futures=True)
                break
            if n is None:
                failed += 1
            log.info("[%d/%d] %s: %s", i, len(todo), futures[fut]["article_id"],
                     "failed" if n is None else f"{n} predictions")

    if EXTRACTIONS_PATH.exists():
        total = write_csv()
        done_now = len(already_done() & {a["article_id"] for a in articles})
        log.info("This run: %d articles processed, %d failed. Total: %d of %d articles done, "
                 "%d predictions in %s.", done_now - (len(articles) - len(todo)), failed,
                 done_now, len(articles), total, PREDICTIONS_CSV.name)
    if stopped:
        sys.exit(f"\nStopped: {stopped}, then re-run the script to continue where it left off.")
    if failed:
        log.info("Re-run the script to retry the failed articles.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nInterrupted - re-run the script to resume.")
