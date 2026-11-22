"""Topic-neutral seed queries for the Impresso Python SDK.

Use with an authenticated client in a notebook:

    from impresso_prediction_seed_queries import iter_queries

    for family, kwargs in iter_queries("fr"):
        results = client.search.find(**kwargs, limit=25)
        print(family, results.total)
        # Save the matched content-item IDs with the language and family.

Use "de" and "en" for German and English. Run each family independently.
For a pilot, repeat over publication periods using the SDK's DateRange.
"""

from impresso import OR


# Each string is one search operand. Multiword strings are phrase cues.
FORECAST_FRAMES = {
    "fr": (
        "on prévoit que", "prévoit que", "prédisait que", "prédit que",
        "on peut prévoir", "il faut s’attendre à", "il faut s'attendre à",
        "on s’attend à", "on s'attend à", "laisse prévoir", "tout porte à croire",
        "selon les prévisions", "il y a lieu de croire", "il est à craindre que",
    ),
    "de": (
        "es ist zu erwarten", "es steht zu erwarten", "ist damit zu rechnen",
        "man rechnet damit", "man erwartet", "es ist vorauszusehen",
        "sagt voraus", "sagte voraus", "nach den Prognosen",
        "es ist zu befürchten", "alles deutet darauf hin",
    ),
    "en": (
        "predicts that", "predicted that", "forecast that", "forecasts that",
        "is expected to", "are expected to", "it is expected that",
        "it is to be expected", "is projected to", "is unlikely to",
        "there is reason to expect", "it is feared that", "is likely to",
    ),
}

LIKELIHOOD = {
    "fr": (
        "probablement", "vraisemblablement", "selon toute vraisemblance",
        "selon toute probabilité", "il est probable que", "il est peu probable que",
        "il est fort probable que", "il n'est pas impossible que",
    ),
    "de": (
        "wahrscheinlich", "voraussichtlich", "vermutlich",
        "aller Wahrscheinlichkeit nach", "aller Voraussicht nach",
        "mit großer Wahrscheinlichkeit", "mit grosser Wahrscheinlichkeit",
        "es ist unwahrscheinlich", "es ist wahrscheinlich daß",
        "es ist wahrscheinlich dass",
    ),
    "en": (
        "probably", "in all probability", "in all likelihood",
        "it is likely that", "it is unlikely that", "it seems likely that",
        "will likely", "will almost certainly",
    ),
}

LONG_HORIZONS = {
    "fr": (
        "dans les années à venir", "dans les prochaines décennies",
        "au cours des prochaines années", "d'ici dix ans", "dans vingt ans",
        "dans cinquante ans", "d'ici la fin du siècle",
        "avant la fin du siècle", "d'ici la fin de ce siècle", "au siècle prochain",
    ),
    "de": (
        "in den kommenden Jahren", "in den nächsten Jahrzehnten",
        "in zehn Jahren", "in zwanzig Jahren", "in fünfzig Jahren",
        "bis Ende des Jahrhunderts", "bis zum Ende dieses Jahrhunderts",
        "bis zum Ende des Jahrhunderts", "im nächsten Jahrhundert",
    ),
    "en": (
        "in the years to come", "over the coming decades", "in the next decade",
        "in ten years", "in twenty years", "in fifty years",
        "by the end of the century", "by the end of this century",
        "before the end of the century", "by the turn of the century",
        "in the next century",
    ),
}

MODALS_OR_FUTURE_FORMS = {
    "fr": (
        "devrait", "devraient", "pourrait", "pourraient",
        "sera", "seront", "aura", "auront",
    ),
    "de": (
        "wird", "werden", "werde", "dürfte", "dürften",
        "könnte", "könnten", "würde", "würden",
    ),
    "en": (
        "will", "shall", "would", "should", "may", "might", "could", "won't",
    ),
}

CALENDAR_CUES = {
    "fr": (
        "demain", "la semaine prochaine", "le mois prochain",
        "l'année prochaine", "l'an prochain", "avant la fin de l'année",
        "d'ici la fin de l'année", "dans quelques mois", "au printemps prochain",
    ),
    "de": (
        "morgen", "nächste Woche", "kommende Woche", "nächsten Monat",
        "nächstes Jahr", "im kommenden Jahr", "bis Ende des Jahres",
        "in wenigen Monaten", "im kommenden Frühjahr",
    ),
    "en": (
        "tomorrow", "next week", "next month", "next year",
        "by the end of the year", "before the end of the year",
        "in a few months", "next spring",
    ),
}


def iter_queries(language):
    """Yield (family, search.find kwargs) for one language."""
    term_groups = {
        "forecast_frame": OR(*FORECAST_FRAMES[language]),
        "likelihood_and_future": (OR(*LIKELIHOOD[language]) &
            OR(*MODALS_OR_FUTURE_FORMS[language])),
        "long_horizon": OR(*LONG_HORIZONS[language]),
        "modal_or_future_form_and_calendar": (
            OR(*MODALS_OR_FUTURE_FORMS[language]) & OR(*CALENDAR_CUES[language])
        ),
    }
    for family, term in term_groups.items():
        yield family, {
            "term": term,
            "language": language,
            "with_text_contents": True,
        }
