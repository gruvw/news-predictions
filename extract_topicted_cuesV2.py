"""Extraction v3 : thème d'abord, marqueur ensuite.

1. Cherche dans Impresso des articles par THÈME (votation, élection, sport, infrastructure).
2. Garde les phrases contenant un marqueur de FUTUR + un verbe de RÉSULTAT vérifiable.
3. Exclut le passé, les questions et le "favori" statique.
4. Écrit les candidats retenus ET les rejetés (avec la raison) pour ajuster les règles.

Usage :
    python extract_candidates_v3.py              # extraction
    python extract_candidates_v3.py --diagnostic # compte seulement les articles par terme/langue
"""

import argparse
import csv
import re
import time

from impresso import DateRange, connect

TARGET = 350                  # ~58 % de précision -> ~200 vraies prédictions
MAX_ARTICLES_PER_TERM = 60    # plafond d'articles parcourus par terme de recherche
MAX_SENTENCES_PER_ARTICLE = 2 # évite qu'un seul article monopolise les résultats
DATE_RANGE = None             # ex. DateRange("1880-01-01", "1990-12-31")
OUTPUT = "prediction_candidates_v3.csv"
REJECTED = "rejected_candidates_v3.csv"
PAUSE = 0.5                   # secondes entre requêtes (politesse envers l'API)

# ---------------------------------------------------------------------------
# THÈMES : termes de recherche Impresso + quota (part du TARGET)
# ---------------------------------------------------------------------------
THEMES = {
    "votation": {
        "share": 0.30, "hint": "admin.ch / OFS (résultats des votations)",
        "terms": {"fr": ["votation", "initiative populaire", "référendum"],
                  "de": ["Abstimmung", "Volksabstimmung", "Volksinitiative"],
                  "en": ["referendum"]},
    },
    "conseil_federal": {
        "share": 0.15, "hint": "admin.ch (liste des conseillers fédéraux) / Wikipedia",
        "terms": {"fr": ["élection au Conseil fédéral", "Conseil fédéral élection"],
                  "de": ["Bundesratswahl", "Bundesratsersatzwahl"],
                  "en": []},
    },
    "election": {
        "share": 0.20, "hint": "sites électoraux officiels / Wikipedia",
        "terms": {"fr": ["élections", "scrutin"],
                  "de": ["Wahlen", "Nationalratswahlen"],
                  "en": ["election", "general election"]},
    },
    "sport": {
        "share": 0.15, "hint": "archives sportives / Wikipedia",
        "terms": {"fr": ["championnat", "finale", "Tour de France"],
                  "de": ["Meisterschaft", "Endspiel", "Tour de Suisse"],
                  "en": ["championship", "final"]},
    },
    "infrastructure": {
        "share": 0.20, "hint": "dates d'inauguration (Wikipedia, CFF, archives)",
        "terms": {"fr": ["tunnel", "inauguration", "ligne de chemin de fer", "Exposition nationale"],
                  "de": ["Tunnel", "Eröffnung", "Bahnlinie", "Landesausstellung"],
                  "en": ["tunnel", "opening of the"]},
    },
}

# ---------------------------------------------------------------------------
# MARQUEURS (regex) — à ajuster en lisant rejected_candidates_v3.csv
# ---------------------------------------------------------------------------
FUTURE = {
    "fr": r"\b(sera|seront|serait|seraient|devrait|devraient|probablement|vraisemblablement|"
          r"sans doute|certainement|selon toute (probabilité|vraisemblance)|"
          r"on (s'attend|prévoit|pense|croit|estime) que|il est (probable|certain|à prévoir|à craindre) que|"
          r"il faut s'attendre|ne fait (aucun|pas de) doute|"
          r"\w+(era|eront|ira|iront)\b)",          # futur simple : l'emportera, gagneront...
    "de": r"\b(wird|werden|dürfte|dürften|voraussichtlich|wahrscheinlich|vermutlich|"
          r"zweifellos|sicherlich|kaum|erwartet|rechnet man|ist zu erwarten|Prognose)\b",
    "en": r"\b(will|shall|is (likely|expected|certain|bound|sure) to|are (likely|expected|certain|bound|sure) to|"
          r"probably|in all likelihood|expected to)\b",
}
OUTCOME = {
    "fr": r"(accept|rejet|repouss|adopt|élu|réélu|l'emport|gagn|remport|vainc|battr|battu|"
          r"majorité|inaugur|mis en service|ouvert|achev|termin|qualifi|champion|victoire|défaite)",
    "de": r"(angenommen|verworfen|abgelehnt|gewählt|wiedergewählt|sieg|gewinn|gewonnen|unterlieg|"
          r"Mehrheit|eröffnet|vollendet|fertiggestellt|in Betrieb|Meister|qualifizier|Niederlage)",
    "en": r"(elected|re-elected|\bwin\b|\bwins\b|defeat|\bbeat\b|carried|rejected|majority|"
          r"opened|completed|champion|victory|qualif)",
}
# Constructions fortes : seules capables de "sauver" une phrase avec "favori"
STRONG = {
    "fr": r"(l'emportera|gagnera|remportera|sera (élu|réélu|accepté|rejeté|adopté|battu)|"
          r"seront (élus|acceptés|rejetés)|devrait (gagner|l'emporter|être élu))",
    "de": r"(wird (siegen|gewinnen|gewählt|angenommen|verworfen)|dürfte (siegen|gewinnen|gewählt))",
    "en": r"(will (win|be elected|be defeated|be carried|be rejected))",
}
FAVORI = r"\b(favori|favorite|favoris|Favorit|Favoriten|favourite|favorite)\b"
PAST = {
    "fr": r"\b(a|ont|avait|avaient) été (accept|rejet|repouss|adopt|élu|battu|inaugur)|\bfut (élu|accept|rejet)",
    "de": r"\b(wurde|wurden) (angenommen|verworfen|abgelehnt|gewählt|eröffnet)|\bist (angenommen|gewählt) worden",
    "en": r"\b(was|were|has been|have been) (elected|rejected|carried|defeated|opened)",
}

COLUMNS = ["candidate_id", "impresso_id", "publication_date", "newspaper", "language",
           "theme", "search_term", "cue", "statement_original", "context_original", "source_hint"]


# ---------------------------------------------------------------------------
# OUTILS (si vos fonctions full_text / sentences de la v2 marchent, gardez-les)
# ---------------------------------------------------------------------------
def full_text(impresso, item):
    for key in ("transcript", "content", "text"):
        if item.get(key):
            return item[key]
    try:  # repli : récupérer l'article complet
        return impresso.content_items.get(item["id"]).raw.get("transcript", "")
    except Exception:
        return ""


def sentences(text):
    text = re.sub(r"\s+", " ", text or "")
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ«\"])", text) if s.strip()]


def classify(sent, lang):
    """Retourne (garder?, raison_ou_cue)."""
    if len(sent) < 40 or len(sent) > 600:
        return False, "longueur"
    if sent.rstrip().endswith("?"):
        return False, "question"
    if re.search(PAST[lang], sent, re.I):
        return False, "passé"
    fut = re.search(FUTURE[lang], sent, re.I)
    out = re.search(OUTCOME[lang], sent, re.I)
    strong = re.search(STRONG[lang], sent, re.I)
    if re.search(FAVORI, sent, re.I) and not strong:
        return False, "favori_statique"
    if strong:
        return True, strong.group(0)
    if fut and out:
        return True, f"{fut.group(0)} + {out.group(0)}"
    return False, "pas_futur" if not fut else "pas_resultat"


def total_hits(result):
    for getter in (lambda r: r.total, lambda r: r.raw["pagination"]["total"]):
        try:
            return getter(result)
        except Exception:
            pass
    return "?"


# ---------------------------------------------------------------------------
def diagnostic(impresso):
    print(f"{'thème':16} {'langue':6} {'terme':32} articles")
    for theme, cfg in THEMES.items():
        for lang, terms in cfg["terms"].items():
            for term in terms:
                res = impresso.search.find(term=f'"{term}"', language=lang, date_range=DATE_RANGE)
                print(f"{theme:16} {lang:6} {term:32} {total_hits(res)}")
                time.sleep(PAUSE)


def extract(impresso):
    rows, rejected, seen = [], [], set()
    for theme, cfg in THEMES.items():
        quota = int(TARGET * cfg["share"])
        start = len(rows)
        for lang, terms in cfg["terms"].items():
            for term in terms:
                if len(rows) - start >= quota:
                    break
                res = impresso.search.find(term=f'"{term}"', language=lang,
                                           with_text_contents=True, date_range=DATE_RANGE)
                scanned = 0
                for page in res.pages():
                    for item in page.raw["data"]:
                        scanned += 1
                        meta = item.get("meta") or {}
                        sents = sentences(full_text(impresso, item))
                        kept_here = 0
                        for k, sent in enumerate(sents):
                            if sent.lower() in seen:
                                continue
                            keep, info = classify(sent, lang)
                            base = {
                                "impresso_id": item["id"],
                                "publication_date": str(meta.get("date", ""))[:10],
                                "newspaper": meta.get("mediaTitle") or meta.get("mediaId", ""),
                                "language": lang, "theme": theme, "search_term": term,
                                "statement_original": sent,
                            }
                            if not keep:
                                # on ne garde que les rejets "intéressants" pour l'ajustement
                                if info in ("favori_statique", "passé", "pas_resultat"):
                                    rejected.append({**base, "reason": info})
                                continue
                            seen.add(sent.lower())
                            rows.append({**base,
                                         "candidate_id": f"C{len(rows) + 1:05d}",
                                         "cue": info,
                                         "context_original": " ".join(sents[max(k - 2, 0):k + 2]),
                                         "source_hint": cfg["hint"]})
                            kept_here += 1
                            if kept_here >= MAX_SENTENCES_PER_ARTICLE:
                                break
                        if len(rows) - start >= quota or scanned >= MAX_ARTICLES_PER_TERM:
                            break
                    if len(rows) - start >= quota or scanned >= MAX_ARTICLES_PER_TERM:
                        break
                print(f"[{theme}/{lang}] {term!r}: {len(rows) - start}/{quota} ({scanned} articles)")
                time.sleep(PAUSE)
    return rows, rejected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    impresso = connect()

    if args.diagnostic:
        diagnostic(impresso)
        return

    rows, rejected = extract(impresso)
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, restval="")
        w.writeheader()
        w.writerows(rows)
    with open(REJECTED, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS + ["reason"], restval="", extrasaction="ignore")
        w.writeheader()
        w.writerows(rejected)
    print(f"\n{len(rows)} candidats -> {OUTPUT} | {len(rejected)} rejets -> {REJECTED}")


if __name__ == "__main__":
    main()
