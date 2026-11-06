#!/usr/bin/env python3
"""
Download Impresso newspaper articles likely to contain predictive statements.

The target number of articles (TOTAL_ARTICLES) is spread evenly over a grid of
(topic x year) cells. Each cell is queried with a multilingual (fr/de/en) keyword
query for its topic, optionally ANDed with "future cue" words (forecast, expected,
voraussichtlich, prévoit...) to bias results towards forward-looking articles.

Cells that cannot fill their quota (e.g. "space exploration" in 1850) hand their
deficit to other cells in follow-up rounds, so the total is reached whenever the
archive allows it.

Output
------
articles/<content-item-id>.txt
    line 1 : the Impresso content item id (e.g. GDL-1910-03-14-a-i0012);
             the article is at https://impresso-project.ch/app/article/<id>
    line 2+: the article's OCR text
manifest.csv  (next to the script)
    one row per article: id, topic, year, date, language, media, title, url.
    It is also what makes the script resumable: re-running it skips everything
    already downloaded and only fetches what is missing.

Requirements
------------
    pip install impresso
On first run `impresso.connect()` asks for an API token
(get one at https://impresso-project.ch/datalab/token); it is then cached in
~/.impresso_py.yml.

Note: Impresso users have a monthly quota of content items (200,000 at the time of
writing). Search result pages count towards it, so keep SEARCH_PAGE_SIZE modest.
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
import math
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import impresso.util.retry as impresso_retry
from impresso import OR, DateRange, connect
from impresso.util.error import ImpressoError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TOTAL_ARTICLES = 10_000          # total number of articles to download
YEAR_START = 1930               # first year (inclusive); runs up to the current year.
# Years with no matching articles simply hand their share to the other years.

# Restrict languages (ISO 2-letter codes), or None for all languages in Impresso.
LANGUAGES: list[str] | None = ["fr", "de", "en"]

# AND the topic query with future-cue words to favour predictive articles.
REQUIRE_FUTURE_CUES = True

# Quality filters applied to search hits before downloading their text.
MIN_TOKENS = 100                # minimum article length (space-separated tokens)
MIN_OCR_QUALITY = 0.7           # skipped when the item has no OCR score
ALLOWED_ITEM_TYPES = {None, "ar", "article"}   # None = item type unknown

# Every search hit counts towards your monthly Impresso quota, rejected or not, so
# search pages are sized to what a cell still needs and a cell is given up quickly
# when its results don't pass the filters above.
SEARCH_PAGE_SIZE = 50           # maximum hits per search request
MIN_SEARCH_PAGE_SIZE = 10       # minimum hits per search request
HITS_PER_NEEDED_ARTICLE = 5     # page size = articles still needed x this (within the bounds)
MAX_FRUITLESS_PAGES = 2         # give up a cell after this many pages in a row with no usable hit
MAX_SEARCH_OFFSET = 5_000       # don't page deeper than this within a cell
MAX_RETRIES = 5
# Impresso searches take ~10 s each server-side, so several cells are processed in
# parallel. All workers share one request rate that adapts to the API: it is halved
# whenever Impresso answers "429 Too Many Requests" and slowly raised again while
# requests go through.
PARALLEL_WORKERS = 8
MAX_REQUESTS_PER_SECOND = 4.0   # starting (and highest) request rate, all workers together
MIN_REQUESTS_PER_SECOND = 0.2   # never slow down below this
RANDOM_SEED = 42

SCRIPT_DIR = Path(__file__).resolve().parent
ARTICLES_DIR = SCRIPT_DIR / "articles"
MANIFEST_PATH = SCRIPT_DIR / "manifest.csv"
WEB_APP_URL = "https://impresso-project.ch/app/article/{id}"

# ---------------------------------------------------------------------------
# Query vocabulary (French / German / English). Multi-word entries are phrases.
# ---------------------------------------------------------------------------

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "political": [
        # fr
        "élections", "élection", "votation", "référendum", "scrutin", "gouvernement",
        "ministère", "traité", "législation", "projet de loi", "parlement", "candidat",
        # de
        "Wahlen", "Wahl", "Abstimmung", "Volksabstimmung", "Referendum", "Regierung",
        "Vertrag", "Gesetz", "Gesetzesentwurf", "Parlament", "Kandidat",
        # en
        "election", "referendum", "government", "treaty", "legislation", "parliament",
    ],
    "economical": [
        "économie", "prix", "salaires", "chômage", "taux de change", "taux hypothécaire",
        "loyers", "inflation", "conjoncture", "renchérissement", "crise économique",
        "Wirtschaft", "Preise", "Löhne", "Arbeitslosigkeit", "Wechselkurs", "Hypothekarzins",
        "Mieten", "Teuerung", "Konjunktur", "Wirtschaftskrise",
        "economy", "prices", "wages", "unemployment", "exchange rate", "inflation", "rents",
    ],
    "environmental": [
        "météo", "prévisions météorologiques", "inondations", "inondation", "tremblement de terre",
        "éruption", "volcan", "canicule", "chaleur", "neige", "récolte", "vendanges", "sécheresse",
        "Wetter", "Wettervorhersage", "Hochwasser", "Überschwemmung", "Erdbeben", "Vulkan",
        "Hitzewelle", "Schnee", "Ernte", "Weinlese", "Trockenheit",
        "weather", "flood", "earthquake", "eruption", "heatwave", "snow", "harvest", "drought",
    ],
    "science_technology": [
        "découverte", "savants", "invention", "expérience", "aviation", "télégraphe",
        "électricité", "automobile", "astronomie", "fusée", "satellite", "comète", "ordinateur",
        "Entdeckung", "Wissenschaft", "Erfindung", "Forscher", "Flugzeug", "Telegraph",
        "Astronomie", "Rakete", "Satellit", "Komet", "Computer",
        "discovery", "scientists", "invention", "aviation", "rocket", "satellite", "comet",
    ],
    "infrastructure": [
        "chemin de fer", "tunnel", "ligne", "construction", "inauguration", "achèvement",
        "travaux", "retard", "grève", "trafic", "aéroport", "autoroute", "pont",
        "Eisenbahn", "Bahn", "Tunnel", "Bau", "Eröffnung", "Fertigstellung", "Bauarbeiten",
        "Verspätung", "Streik", "Verkehr", "Flughafen", "Autobahn", "Brücke",
        "railway", "tunnel", "construction", "strike", "airport", "bridge", "traffic",
    ],
    "health": [
        "épidémie", "choléra", "grippe", "typhus", "variole", "tuberculose", "mortalité",
        "population", "recensement", "vaccin", "maladie", "hôpital",
        "Epidemie", "Seuche", "Cholera", "Grippe", "Pocken", "Tuberkulose", "Sterblichkeit",
        "Bevölkerung", "Volkszählung", "Impfung", "Krankheit", "Spital",
        "epidemic", "cholera", "influenza", "mortality", "census", "vaccine", "disease",
    ],
    "sport_events": [
        "course", "championnat", "match", "coupe", "tour de France", "jeux olympiques",
        "exposition", "fête fédérale", "tir fédéral", "visiteurs", "spectateurs", "régates",
        "Rennen", "Meisterschaft", "Spiel", "Wettkampf", "Olympische Spiele", "Ausstellung",
        "Schützenfest", "Turnfest", "Besucher", "Zuschauer",
        "race", "championship", "olympic", "exhibition", "tournament", "spectators",
    ],
    "justice": [
        "procès", "verdict", "tribunal", "jugement", "condamné", "acquitté", "cour d'assises",
        "extradition", "accusé", "jury", "peine",
        "Prozess", "Urteil", "Gericht", "verurteilt", "freigesprochen", "Schwurgericht",
        "Auslieferung", "Angeklagte", "Geschworenen", "Strafe",
        "trial", "verdict", "court", "sentenced", "acquitted", "extradition", "jury",
    ],
    "security": [
        "guerre", "armistice", "cessez-le-feu", "paix", "sanctions", "blocus", "armée",
        "troupes", "mobilisation", "coup d'état", "attentat", "criminalité", "arrestation",
        "Krieg", "Waffenstillstand", "Frieden", "Sanktionen", "Blockade", "Armee", "Truppen",
        "Mobilmachung", "Staatsstreich", "Putsch", "Attentat", "Verhaftung",
        "war", "armistice", "ceasefire", "sanctions", "troops", "coup", "arrest",
    ],
    "energy": [
        "électricité", "usine électrique", "centrale", "nucléaire", "charbon", "pétrole",
        "essence", "gaz", "pénurie", "barrage", "énergie",
        "Elektrizität", "Kraftwerk", "Atomkraftwerk", "Kernkraftwerk", "Kohle", "Erdöl",
        "Benzin", "Gas", "Mangel", "Stausee", "Energie",
        "electricity", "power plant", "nuclear", "coal", "oil", "petrol", "shortage", "energy",
    ],
    "education": [
        "examens", "baccalauréat", "maturité", "université", "école", "étudiants",
        "enseignement", "diplôme", "faculté", "écoliers",
        "Prüfungen", "Matura", "Abitur", "Universität", "Hochschule", "Schule", "Studenten",
        "Unterricht", "Diplom", "Schüler",
        "examination", "university", "school", "students", "education",
    ],
    "business": [
        "société anonyme", "dividende", "bénéfice", "chiffre d'affaires", "fusion", "bourse",
        "actions", "faillite", "assemblée générale", "entreprise", "commerce",
        "Aktiengesellschaft", "Dividende", "Gewinn", "Umsatz", "Fusion", "Börse", "Aktien",
        "Konkurs", "Generalversammlung", "Unternehmen", "Handel",
        "company", "dividend", "profits", "merger", "stock exchange", "shares", "bankruptcy",
    ],
    "entertainment_leisure": [
        "théâtre", "cinéma", "film", "concert", "opéra", "prix littéraire", "festival",
        "vacances", "tourisme", "touristes", "saison", "hôtels",
        "Theater", "Kino", "Film", "Konzert", "Oper", "Festspiele", "Ferien", "Fremdenverkehr",
        "Touristen", "Saison", "Hotels",
        "theatre", "cinema", "concert", "festival", "holidays", "tourism", "tourists",
    ],
    "celebrity": [
        "mariage", "fiançailles", "divorce", "couronnement", "prince", "princesse", "reine",
        "roi", "retraite", "abdication", "célèbre",
        "Hochzeit", "Verlobung", "Scheidung", "Krönung", "Prinz", "Prinzessin", "Königin",
        "König", "Rücktritt", "Abdankung",
        "wedding", "engagement", "divorce", "coronation", "prince", "princess", "queen",
    ],
}

FUTURE_CUES: list[str] = [
    # fr
    "prévoit", "prévoir", "prévisions", "pronostic", "pronostics", "probablement",
    "devrait", "devraient", "prochainement", "perspectives", "on prévoit", "on s'attend",
    # de
    "voraussichtlich", "Prognose", "Prognosen", "Vorhersage", "erwartet", "dürfte",
    "dürften", "vermutlich", "Aussichten", "demnächst", "wahrscheinlich",
    # en
    "forecast", "expected", "predict", "predicted", "likely", "prospects", "outlook",
    "anticipated",
]

# ---------------------------------------------------------------------------

log = logging.getLogger("impresso-dl")


@dataclass
class Cell:
    topic: str
    year: int
    target: int = 0                 # articles this cell should provide in total
    have: int = 0                   # articles already downloaded for this cell
    total_hits: int | None = None   # size of the search result set (once known)
    exhausted: bool = False         # no more usable hits
    _hits: Iterator[dict] | None = field(default=None, repr=False)

    @property
    def missing(self) -> int:
        return max(0, self.target - self.have)


class AdaptiveRateLimiter:
    """Request rate shared by all worker threads.

    Every HTTP request (including the impresso library's own retries) waits for a slot.
    On a 429 the rate is halved and everyone pauses; after a run of successful
    requests the rate creeps back up towards MAX_REQUESTS_PER_SECOND.
    """

    SUCCESSES_BEFORE_SPEEDUP = 25
    SPEEDUP_FACTOR = 1.25
    MIN_SECONDS_BETWEEN_SLOWDOWNS = 5.0   # several workers often get a 429 at once

    def __init__(self) -> None:
        self.rate = MAX_REQUESTS_PER_SECOND
        self._lock = threading.Lock()
        self._next_slot = time.monotonic()
        self._successes = 0
        self._last_slowdown = -math.inf

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next_slot)
            self._next_slot = slot + 1.0 / self.rate
        if slot > now:
            time.sleep(slot - now)

    def success(self) -> None:
        with self._lock:
            self._successes += 1
            if (self._successes >= self.SUCCESSES_BEFORE_SPEEDUP
                    and self.rate < MAX_REQUESTS_PER_SECOND):
                self.rate = min(MAX_REQUESTS_PER_SECOND, self.rate * self.SPEEDUP_FACTOR)
                self._successes = 0

    def throttled(self, retry_after: float | None) -> None:
        with self._lock:
            self._successes = 0
            now = time.monotonic()
            pause = retry_after if retry_after is not None else 2.0
            self._next_slot = max(self._next_slot, now + pause)
            if now - self._last_slowdown < self.MIN_SECONDS_BETWEEN_SLOWDOWNS:
                return
            self._last_slowdown = now
            self.rate = max(MIN_REQUESTS_PER_SECOND, self.rate / 2)
            rate = self.rate
        log.warning("Impresso asked us to slow down: now %.2f requests/s for all workers.",
                    rate)


class Downloader:
    def __init__(self) -> None:
        self.client = connect()
        self.lock = threading.Lock()   # guards seen_ids, counters and the manifest
        self.seen_ids: set[str] = set()
        self.api_calls = 0
        self.downloaded = 0
        self.limiter = AdaptiveRateLimiter()
        self._install_rate_limiter()

    def _install_rate_limiter(self) -> None:
        """Route every HTTP request of the impresso client through the shared limiter."""
        api_client = getattr(self.client, "_api_client", None)
        if api_client is None:
            log.warning("Could not attach the rate limiter (unexpected impresso version).")
            return
        http = api_client.get_httpx_client()
        hooks = http.event_hooks
        hooks.setdefault("request", []).append(lambda request: self.limiter.acquire())
        hooks.setdefault("response", []).append(self._on_response)
        http.event_hooks = hooks
        # The library prints one long line per retried request; the limiter logs a
        # short summary instead. Messages about retries running out are kept.
        if hasattr(impresso_retry, "_print_retry_message"):
            impresso_retry._print_retry_message = lambda **kwargs: None

    def _on_response(self, response) -> None:
        if response.status_code == 429:
            retry_after = None
            try:
                retry_after = float(response.headers.get("retry-after", ""))
            except ValueError:
                pass
            self.limiter.throttled(retry_after)
        elif response.status_code < 400:
            self.limiter.success()

    # -- API helpers -------------------------------------------------------

    def _call(self, fn, *args, **kwargs):
        """Call the API with retries and exponential backoff."""
        for attempt in range(1, MAX_RETRIES + 1):
            with self.lock:
                self.api_calls += 1
            try:
                return fn(*args, **kwargs)
            except ImpressoError as e:
                status = getattr(e.error, "status", None)
                if status in (401, 403):
                    raise SystemExit(f"Access refused by Impresso ({e}). "
                                     "Check your token or your monthly quota.")
                if status == 404:
                    return None
                err = e
            except Exception as e:  # network errors, timeouts...
                err = e
            wait = min(60, 2 ** attempt)
            log.warning("API error (attempt %d/%d): %s - retrying in %ds",
                        attempt, MAX_RETRIES, err, wait)
            time.sleep(wait)
        log.error("Giving up after %d attempts", MAX_RETRIES)
        return None

    def _search(self, cell: Cell, offset: int, limit: int):
        term = OR(TOPIC_KEYWORDS[cell.topic])
        if REQUIRE_FUTURE_CUES:
            term = term & OR(FUTURE_CUES)
        kwargs = dict(
            term=term,
            date_range=DateRange(dt.date(cell.year, 1, 1), dt.date(cell.year, 12, 31)),
            with_text_contents=True,
            order_by="relevance",
            limit=limit,
            offset=offset,
        )
        if LANGUAGES:
            kwargs["language"] = OR(LANGUAGES)
        return self._call(self.client.search.find, **kwargs)

    # -- hit iteration -----------------------------------------------------

    def _iter_hits(self, cell: Cell) -> Iterator[dict]:
        """Yield usable search hits for a cell, visiting result pages in random order
        so we sample across the whole result set instead of only the top hits.
        Stops after MAX_FRUITLESS_PAGES consecutive pages without a usable hit."""
        rng = random.Random(f"{RANDOM_SEED}-{cell.topic}-{cell.year}")  # per cell: thread-safe
        size = max(MIN_SEARCH_PAGE_SIZE,
                   min(SEARCH_PAGE_SIZE, cell.missing * HITS_PER_NEEDED_ARTICLE))
        first = self._search(cell, 0, size)
        if first is None:
            return
        cell.total_hits = first.total
        reachable = min(cell.total_hits, MAX_SEARCH_OFFSET)
        n_pages = math.ceil(reachable / size)

        page_offsets = list(range(size, n_pages * size, size))
        rng.shuffle(page_offsets)
        page_offsets.insert(0, 0)  # the page we already have comes first

        fruitless = 0
        for off in page_offsets:
            page = first if off == 0 else self._search(cell, off, size)
            if page is None:
                continue
            hits = [h for h in page.raw.get("data", []) if self._hit_ok(h)]
            if not hits:
                fruitless += 1
                if fruitless >= MAX_FRUITLESS_PAGES:
                    log.info("  %s %d: no usable hits among %d results, moving on",
                             cell.topic, cell.year, cell.total_hits)
                    return
                continue
            fruitless = 0
            rng.shuffle(hits)
            yield from hits

    def _hit_ok(self, hit: dict) -> bool:
        cid = hit.get("id")
        if not cid or cid in self.seen_ids:
            return False
        text = hit.get("text") or {}
        if text.get("itemType") not in ALLOWED_ITEM_TYPES:
            return False
        length = text.get("contentLength")
        if length is not None and length < MIN_TOKENS:
            return False
        ocr = (hit.get("semanticEnrichments") or {}).get("ocrQuality")
        if ocr is not None and ocr < MIN_OCR_QUALITY:
            return False
        return True

    # -- downloading -------------------------------------------------------

    def fill(self, cell: Cell) -> None:
        """Download articles for a cell until it reaches its target or runs dry."""
        if cell.exhausted or cell.missing == 0:
            return
        if cell._hits is None:
            cell._hits = self._iter_hits(cell)
        while cell.missing > 0:
            hit = next(cell._hits, None)
            if hit is None:
                cell.exhausted = True
                return
            with self.lock:  # another worker may have claimed it in the meantime
                if hit["id"] in self.seen_ids:
                    continue
                self.seen_ids.add(hit["id"])
            if self._download(hit, cell):
                cell.have += 1
                with self.lock:
                    self.downloaded += 1
                    log.info("[%d/%d] %-22s %d  %s", self.downloaded, TOTAL_ARTICLES,
                             cell.topic, cell.year, hit["id"])

    def _download(self, hit: dict, cell: Cell) -> bool:
        cid = hit["id"]
        text = (hit.get("text") or {}).get("content")
        meta = hit.get("meta") or {}
        info = hit.get("text") or {}
        if not text:  # transcripts are usually not part of search results
            item = self._call(self.client.content_items.get, cid)
            if item is None:
                return False
            raw = item.raw
            text = (raw.get("text") or {}).get("content")
            meta = {**meta, **(raw.get("meta") or {})}
            info = {**info, **(raw.get("text") or {})}
        if not text or len(text.split()) < MIN_TOKENS:
            return False

        path = ARTICLES_DIR / f"{cid}.txt"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(f"{cid}\n{text.strip()}\n", encoding="utf-8")
        tmp.replace(path)

        with self.lock, MANIFEST_PATH.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                cid, cell.topic, cell.year, str(meta.get("date", ""))[:10],
                info.get("langCode") or "", meta.get("mediaTitle") or meta.get("mediaId") or "",
                (info.get("title") or "").replace("\n", " "), WEB_APP_URL.format(id=cid),
            ])
        return True


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------

def balanced_order(cells: list[list[Cell]]) -> list[Cell]:
    """Order cells (indexed [year][topic]) so that any prefix is spread as evenly
    as possible over both years and topics (a 'diagonal' walk through the grid)."""
    n_years, n_topics = len(cells), len(cells[0])
    out = []
    for k in range(n_years * n_topics):
        y = k % n_years
        t = (y + k // n_years) % n_topics
        out.append(cells[y][t])
    return out


def allocate(order: list[Cell], amount: int) -> None:
    """Add `amount` to the targets of the cells in `order`, as evenly as possible."""
    if not order or amount <= 0:
        return
    base, rest = divmod(amount, len(order))
    for i, cell in enumerate(order):
        cell.target += base + (1 if i < rest else 0)


def load_manifest(grid: dict[tuple[str, int], Cell], dl: Downloader) -> int:
    """Register articles from previous runs (resume support)."""
    if not MANIFEST_PATH.exists():
        with MANIFEST_PATH.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                ["id", "topic", "year", "date", "language", "media", "title", "url"])
        return 0
    n = 0
    with MANIFEST_PATH.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not (ARTICLES_DIR / f"{row['id']}.txt").exists():
                continue
            dl.seen_ids.add(row["id"])
            cell = grid.get((row["topic"], int(row["year"])))
            if cell:
                cell.have += 1
            n += 1
    return n


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # hide per-request log lines
    ARTICLES_DIR.mkdir(exist_ok=True)

    topics = list(TOPIC_KEYWORDS)
    years = list(range(YEAR_START, dt.date.today().year + 1))
    rows = [[Cell(t, y) for t in topics] for y in years]
    order = balanced_order(rows)
    grid = {(c.topic, c.year): c for c in order}

    dl = Downloader()
    already = load_manifest(grid, dl)
    dl.downloaded = already
    log.info("Target: %d articles over %d years x %d topics (%d cells); %d already on disk.",
             TOTAL_ARTICLES, len(years), len(topics), len(order), already)

    # Round 1: even split over all cells (cells already holding articles from a previous
    # run keep counting them towards their share).
    allocate(order, TOTAL_ARTICLES)

    rnd = 1
    while True:
        todo = [c for c in order if c.missing > 0 and not c.exhausted]
        ex = ThreadPoolExecutor(max_workers=PARALLEL_WORKERS)
        try:
            futures = [ex.submit(dl.fill, c) for c in todo]
            for i, fut in enumerate(as_completed(futures), 1):
                fut.result()  # re-raise worker errors (e.g. token refused)
                if i % 50 == 0 or i == len(todo):
                    log.info("round %d: %d/%d cells | %d/%d articles | %d API calls",
                             rnd, i, len(todo), dl.downloaded, TOTAL_ARTICLES, dl.api_calls)
        finally:
            # On error or Ctrl+C, drop queued cells instead of waiting for all of them.
            ex.shutdown(wait=True, cancel_futures=True)

        done = sum(c.have for c in order)
        deficit = TOTAL_ARTICLES - done
        open_cells = [c for c in order if not c.exhausted]
        if deficit <= 0 or not open_cells:
            break
        # Cells that ran dry give up their unmet share; redistribute it over the cells
        # that still have hits, keeping the year/topic balance.
        for c in order:
            if c.exhausted:
                c.target = c.have
        log.info("Redistributing %d missing articles over %d open cells.",
                 deficit, len(open_cells))
        allocate(open_cells, deficit)
        rnd += 1

    total = sum(c.have for c in order)
    log.info("Finished: %d articles in %s (%d API calls).", total, ARTICLES_DIR, dl.api_calls)
    if total < TOTAL_ARTICLES:
        log.warning("Only %d/%d articles available with the current filters.",
                    total, TOTAL_ARTICLES)

    # Short summary per topic
    by_topic: dict[str, int] = {}
    for c in order:
        by_topic[c.topic] = by_topic.get(c.topic, 0) + c.have
    for t, n in by_topic.items():
        log.info("  %-22s %d", t, n)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nInterrupted - re-run the script to resume.")
