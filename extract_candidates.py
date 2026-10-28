"""Step 1 - Gather prediction candidates from the Impresso newspaper archive.

Searches Impresso for strong predictive cue phrases, pulls the full text of each
matching article, keeps the sentence that contains the cue, and writes the
candidates to a CSV. Columns filled by later steps (LLM filtering, outcome
retrieval) are left empty.

Usage:
    pip install impresso
    python extract_candidates.py          # asks for an Impresso token on first run
"""

import csv
import re

from impresso import DateRange, connect

TARGET = 200                    # number of candidates to export
MAX_ARTICLES_PER_CUE = 20       # safety cap on articles scanned for one cue
DATE_RANGE = None                # e.g. DateRange("1900-01-01", "1999-12-31")
OUTPUT = "prediction_candidates.csv"

# Strong predictive cues only, per language (Impresso is mostly FR/DE).
CUES = {
    "fr": ["on s'attend à ce que", "il faut s'attendre à", "il est probable que",
           "il est vraisemblable que", "il est à prévoir que", "on prévoit que",
           "selon les prévisions", "selon toute probabilité", "selon toute vraisemblance",
           "sera vraisemblablement", "seront vraisemblablement", "sera probablement",
           "seront probablement", "devrait vraisemblablement", "devrait probablement",
           "devraient probablement", "est prévu pour", "sont prévus pour"],
    "en": ["is expected to", "are expected to", "is likely to", "are likely to",
           "is forecast to", "are forecast to", "is predicted to", "are predicted to",
           "is projected to", "are projected to", "is scheduled to", "are scheduled to",
           "is due to", "are due to", "is bound to", "is certain to", "will probably",
           "will almost certainly", "in all likelihood", "it is expected that"],
    "de": ["wird voraussichtlich", "werden voraussichtlich", "soll voraussichtlich",
           "sollen voraussichtlich", "aller Voraussicht nach", "wird erwartet",
           "ist zu erwarten", "ist damit zu rechnen", "man rechnet damit",
           "wird wahrscheinlich", "werden wahrscheinlich", "wird vermutlich",
           "werden vermutlich", "höchstwahrscheinlich", "mit Sicherheit wird",
           "Prognosen zufolge", "dürfte voraussichtlich"],
}

# Columns of the final dataset; later steps fill the empty ones.
COLUMNS = [
    "candidate_id", "impresso_id", "publication_date", "newspaper",   # step 1
    "statement_original", "context_original",                         # step 1
    "author", "topics", "category", "statement_en",                   # step 2
    "resolution_date", "horizon_days", "predicted_value",             # step 2
    "actual_value", "outcome_confidence", "outcome_source_url",       # step 3
    "accuracy",                                                       # step 3
]


def normalize(text):
    return re.sub(r"\s+", " ", text.replace("’", "'")).strip()


def sentences(text):
    return re.split(r"(?<=[.!?])\s+", normalize(text))


def full_text(impresso, item):
    text = (item.get("text") or {}).get("content")
    if text:
        return text
    raw = impresso.content_items.get(item["id"]).raw
    return (raw.get("text") or {}).get("content") or ""


def main():
    impresso = connect()
    cues = [(lang, cue) for lang, lst in CUES.items() for cue in lst]
    rows, seen = [], set()

    for i, (lang, cue) in enumerate(cues):
        quota = TARGET * (i + 1) // len(cues)   # cumulative: later cues fill earlier gaps
        pattern = re.compile(re.escape(cue), re.IGNORECASE)
        result = impresso.search.find(term=f'"{cue}"', language=lang,
                                      with_text_contents=True, date_range=DATE_RANGE)
        scanned = 0
        for page in result.pages():
            for item in page.raw["data"]:
                scanned += 1
                sents = sentences(full_text(impresso, item))
                for k, sent in enumerate(sents):
                    if len(rows) >= quota:
                        break
                    if not pattern.search(sent) or len(sent) > 600 or sent.lower() in seen:
                        continue
                    seen.add(sent.lower())
                    meta = item.get("meta") or {}
                    rows.append({
                        "candidate_id": f"C{len(rows) + 1:05d}",
                        "impresso_id": item["id"],
                        "publication_date": str(meta.get("date", ""))[:10],
                        "newspaper": meta.get("mediaTitle") or meta.get("mediaId", ""),
                        "statement_original": sent,
                        "context_original": " ".join(sents[max(k - 2, 0):k + 2]),
                    })
                if len(rows) >= quota or scanned >= MAX_ARTICLES_PER_CUE:
                    break
            if len(rows) >= quota or scanned >= MAX_ARTICLES_PER_CUE:
                break
        print(f"[{lang}] {cue!r}: {len(rows)} candidates so far ({scanned} articles scanned)")

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, restval="")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} candidates to {OUTPUT}")


if __name__ == "__main__":
    main()
