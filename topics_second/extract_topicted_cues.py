"""Extraction de candidats de prédictions depuis Impresso (v3 corrigée).

Stratégie : THÈME d'abord (recherche Impresso), MARQUEUR ensuite (filtre local).
Une phrase est retenue si elle contient :
  - un marqueur de futur / probabilité (FUTURE)
  - ET un verbe de résultat vérifiable (OUTCOME)
Elle est rejetée si elle est au passé, une question, ou un "favori" statique.

Usage :
    python extract_candidates_v3.py --diagnostic   # compte les articles par terme (léger)
    python extract_candidates_v3.py                # extraction complète
"""

import csv
import re
import sys

from impresso import DateRange, connect

# ----------------------------------------------------------------- CONFIG
TARGET = 300                  # nombre de candidats visé
MAX_ARTICLES_PER_TERM = 40    # articles scannés par (thème, langue, terme)
PAGE_SIZE = 20                # petit = évite les 504
MAX_SENT_LEN = 500
DATE_RANGE = None             # ex. DateRange("1900-01-01", "1980-12-31") pour alléger
OUTPUT = "prediction_candidates_v3.csv"
REJECTED = "rejected_candidates_v3.csv"

COLUMNS = ["candidate_id", "impresso_id", "publication_date", "newspaper",
           "language", "theme", "search_term", "statement_original",
           "context_original"]

# Termes de recherche Impresso, par thème et par langue.
# Les termes anglais sont gardés : le --diagnostic dira s'ils renvoient quelque chose.
THEMES = {
    "votation": {
        "fr": ["votation", "initiative populaire", "référendum", "scrutin fédéral"],
        "de": ["Abstimmung", "Volksinitiative", "Referendum", "Volksabstimmung"],
        "en": ["referendum", "plebiscite"],
    },
    "election": {
        "fr": ["élection du Conseil fédéral", "élections fédérales", "candidat à l'élection"],
        "de": ["Bundesratswahl", "Nationalratswahlen", "Wahlen"],
        "en": ["election", "presidential election", "general election"],
    },
    "sport": {
        "fr": ["finale", "championnat", "Coupe du monde", "Jeux olympiques"],
        "de": ["Meisterschaft", "Weltmeisterschaft", "Olympische Spiele", "Endspiel"],
        "en": ["world cup", "olympic games", "championship final"],
    },
    "infrastructure": {
        "fr": ["inauguration", "mise en service", "tunnel", "exposition nationale"],
        "de": ["Einweihung", "Eröffnung", "Tunnel", "Landesausstellung"],
        "en": ["inauguration", "opening ceremony", "tunnel"],
    },
}

# ----------------------------------------------------------------- MARQUEURS
# Futur / probabilité (la phrase doit en contenir au moins un)
FUTURE = [
    # français
    r"\bsera\b", r"\bseront\b", r"\bdevrait\b", r"\bdevraient\b",
    r"\bprobablement\b", r"\bvraisemblablement\b", r"\bselon toute probabilité\b",
    r"\bil est probable que\b", r"\bil faut s'attendre\b", r"\bon s'attend à\b",
    r"\bon prévoit\b", r"\best prévu\b", r"\bsont prévus?\b", r"\bà prévoir\b",
    r"\b\w+(?:era|eront)\b",
    # allemand
    r"\bwird\b", r"\bwerden\b", r"\bdürfte\b", r"\bdürften\b", r"\bvoraussichtlich\b",
    r"\bwahrscheinlich\b", r"\bvermutlich\b", r"\bzu erwarten\b", r"\baller Voraussicht\b",
    r"\bman rechnet\b", r"\bsoll\b", r"\bsollen\b",
    # anglais
    r"\bwill\b", r"\bis expected\b", r"\bare expected\b", r"\bis likely\b",
    r"\bare likely\b", r"\bis forecast\b", r"\bis predicted\b", r"\bis projected\b",
    r"\bis scheduled\b", r"\bis due\b", r"\bis certain to\b", r"\bin all likelihood\b",
]

# Verbes / noms de résultat vérifiable (la phrase doit en contenir au moins un)
OUTCOME = [
    # français
    r"\baccept", r"\brejet", r"\bélu", r"\bélue", r"\bélect", r"\bgagn", r"\bl'emporter",
    r"\bremport", r"\bbattr", r"\bvaincr", r"\bvainqueur", r"\bchampion", r"\btriomph",
    r"\bapprouv", r"\bpassera", r"\bterminé", r"\bachevé", r"\binaugur", r"\bouvert",
    r"\bmis en service", r"\bterminera", r"\bse tiendra", r"\bauront lieu",
    r"\bscore", r"\bmajorité", r"\bnon l'emportera", r"\boui l'emportera",
    # allemand
    r"\bangenommen", r"\bverworfen", r"\babgelehnt", r"\bgewählt", r"\bgewinn",
    r"\bsiegen", r"\bsieg", r"\bMehrheit", r"\bMeister", r"\beröffnet", r"\beingeweiht",
    r"\bfertiggestellt", r"\bstattfinden", r"\bdurchfallen", r"\bbesiegen",
    # anglais
    r"\bwin\b", r"\bwon\b", r"\bwinner", r"\belected", r"\bdefeat", r"\bpass\b",
    r"\breject", r"\bapprove", r"\bcompleted\b", r"\bopen(?:ed)?\b", r"\bmajority",
    r"\bchampion", r"\btake place", r"\bbe held",
]

# Rejets : passé, question, "favori" statique
PAST = [
    r"\ba été\b", r"\bont été\b", r"\bétait\b", r"\bétaient\b", r"\bavait été\b",
    r"\bwurde\b", r"\bwurden\b", r"\bwar\b", r"\bwaren\b", r"\bhat gewonnen\b",
    r"\bwas\b", r"\bwere\b", r"\bhas been\b", r"\bhave been\b", r"\bhad been\b",
]
STATIC_FAVORITE = [r"\bfavori\b", r"\bfavorite\b", r"\bfavoris\b", r"\bFavorit\b"]
STRONG = [  # un favori + un de ceux-ci = vraie prédiction, on garde
    r"\bl'emportera\b", r"\bsera élu\b", r"\bgagnera\b", r"\bsiegen wird\b",
    r"\bwird gewinnen\b", r"\bwill win\b", r"\bwill be elected\b",
]

FUTURE_RE = re.compile("|".join(FUTURE), re.IGNORECASE)
OUTCOME_RE = re.compile("|".join(OUTCOME), re.IGNORECASE)
PAST_RE = re.compile("|".join(PAST), re.IGNORECASE)
FAV_RE = re.compile("|".join(STATIC_FAVORITE), re.IGNORECASE)
STRONG_RE = re.compile("|".join(STRONG), re.IGNORECASE)


# ----------------------------------------------------------------- OUTILS TEXTE
def _as_text(value):
    """Impresso renvoie parfois une chaîne, parfois {"content": "..."}."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("content", "transcript", "text"):
            if isinstance(value.get(key), str):
                return value[key]
    return ""


def full_text(impresso, item):
    for key in ("text", "transcript", "content"):
        txt = _as_text(item.get(key))
        if txt:
            return txt
    try:  # repli : récupérer l'article complet (requête supplémentaire)
        raw = impresso.content_items.get(item["id"]).raw
        for key in ("text", "transcript", "content"):
            txt = _as_text(raw.get(key))
            if txt:
                return txt
    except Exception as e:
        print(f"   [texte indisponible] {item.get('id')}: {e}")
    return ""


def sentences(text):
    text = re.sub(r"\s+", " ", text if isinstance(text, str) else "")
    text = text.replace("’", "'").strip()
    return [s.strip() for s in
            re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ«\"])", text) if s.strip()]


def classify(sentence):
    """Renvoie (garder: bool, raison_du_rejet: str)."""
    if len(sentence) > MAX_SENT_LEN:
        return False, "trop_long"
    if len(sentence) < 25:
        return False, "trop_court"
    if sentence.rstrip().endswith("?"):
        return False, "question"
    if not FUTURE_RE.search(sentence):
        return False, "pas_futur"
    if not OUTCOME_RE.search(sentence):
        return False, "pas_resultat"
    if PAST_RE.search(sentence) and not re.search(r"\b(sera|wird|will|devrait|dürfte)\b",
                                                  sentence, re.IGNORECASE):
        return False, "passe"
    if FAV_RE.search(sentence) and not STRONG_RE.search(sentence):
        return False, "favori_statique"
    return True, ""


# ----------------------------------------------------------------- API
def safe_search(impresso, term, lang):
    """Lance la recherche ; renvoie None si l'API échoue (le terme est ignoré)."""
    kwargs = dict(term=f'"{term}"', language=lang,
                  with_text_contents=True, date_range=DATE_RANGE)
    try:
        return impresso.search.find(**kwargs, limit=PAGE_SIZE)
    except TypeError:
        # version de la librairie sans paramètre "limit"
        try:
            return impresso.search.find(**kwargs)
        except Exception as e:
            print(f"   [échec API, terme ignoré] {term!r} ({lang}): {e}")
            return None
    except Exception as e:
        print(f"   [échec API, terme ignoré] {term!r} ({lang}): {e}")
        return None


def save(rows, rejected):
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, restval="", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(REJECTED, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS + ["reason"], restval="",
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(rejected)


# ----------------------------------------------------------------- DIAGNOSTIC
def diagnostic(impresso):
    """Compte les articles disponibles par terme, sans télécharger les textes."""
    print(f"{'thème':<15}{'langue':<8}{'terme':<35}articles")
    print("-" * 70)
    for theme, langs in THEMES.items():
        for lang, terms in langs.items():
            for term in terms:
                try:
                    res = impresso.search.find(term=f'"{term}"', language=lang,
                                               date_range=DATE_RANGE)
                    total = getattr(res, "total", None)
                    print(f"{theme:<15}{lang:<8}{term:<35}{total if total is not None else '?'}")
                except Exception as e:
                    print(f"{theme:<15}{lang:<8}{term:<35}ERREUR ({e})")


# ----------------------------------------------------------------- EXTRACTION
def extract(impresso):
    rows, rejected, seen = [], [], set()
    jobs = [(theme, lang, term)
            for theme, langs in THEMES.items()
            for lang, terms in langs.items()
            for term in terms]

    for j, (theme, lang, term) in enumerate(jobs):
        quota = TARGET * (j + 1) // len(jobs)   # quota cumulatif : les termes pauvres cèdent leur place
        res = safe_search(impresso, term, lang)
        if res is None:
            continue
        scanned = 0
        kept_here = 0
        try:
            for page in res.pages():
                for item in page.raw["data"]:
                    scanned += 1
                    meta = item.get("meta") or {}
                    sents = sentences(full_text(impresso, item))
                    for k, sent in enumerate(sents):
                        if len(rows) >= quota:
                            break
                        key = sent.lower()
                        if key in seen:
                            continue
                        ok, reason = classify(sent)
                        record = {
                            "impresso_id": item.get("id", ""),
                            "publication_date": str(meta.get("date", ""))[:10],
                            "newspaper": meta.get("mediaTitle") or meta.get("mediaId", ""),
                            "language": lang,
                            "theme": theme,
                            "search_term": term,
                            "statement_original": sent,
                            "context_original": " ".join(sents[max(k - 2, 0):k + 2]),
                        }
                        if ok:
                            seen.add(key)
                            record["candidate_id"] = f"C{len(rows) + 1:05d}"
                            rows.append(record)
                            kept_here += 1
                        elif reason in ("pas_resultat", "passe", "favori_statique"):
                            # on ne garde dans les rejets que ceux qui ont un marqueur futur
                            # (utile pour repérer les faux négatifs)
                            if FUTURE_RE.search(sent) and len(rejected) < 2000:
                                record["reason"] = reason
                                record["candidate_id"] = f"R{len(rejected) + 1:05d}"
                                rejected.append(record)
                    if len(rows) >= quota or scanned >= MAX_ARTICLES_PER_TERM:
                        break
                if len(rows) >= quota or scanned >= MAX_ARTICLES_PER_TERM:
                    break
        except Exception as e:
            print(f"   [échec API en cours de pagination] {term!r}: {e} "
                  f"-> on garde les {scanned} articles déjà lus")
        print(f"[{theme}/{lang}] {term!r}: +{kept_here} "
              f"(total {len(rows)}/{quota}, {scanned} articles lus)")
        save(rows, rejected)   # sauvegarde progressive
    return rows, rejected


def main():
    impresso = connect()
    if "--diagnostic" in sys.argv:
        diagnostic(impresso)
        return
    rows, rejected = extract(impresso)
    save(rows, rejected)
    print(f"\n{len(rows)} candidats -> {OUTPUT} | {len(rejected)} rejets -> {REJECTED}")


if __name__ == "__main__":
    main()