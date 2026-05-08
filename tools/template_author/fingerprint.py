"""
Fingerprint phrase suggestion for new templates.

Strategy: extract n-grams (3-5 words) from the PDF text, score each by:
  - length (longer = more specific)
  - presence of section-marker words (Antrag, Persönliche, etc.)
  - rarity (avoid common phrases like "Datum", "Name")

Returns top-N candidates ranked by score. The author picks 3 from the list
that together uniquely identify the form.
"""
from __future__ import annotations

import re
from collections import Counter

# Common German words that appear in almost every form — exclude as fingerprint candidates
_STOPWORDS = {
    "der", "die", "das", "und", "oder", "wenn", "ist", "sind", "wird",
    "ein", "eine", "einen", "einer", "des", "den", "dem", "im", "in",
    "von", "vom", "zur", "zum", "für", "mit", "auf", "bei", "nach", "über",
    "ja", "nein", "bitte", "weitere", "siehe", "anlage", "seite",
    "datum", "name", "vorname", "ort", "unterschrift",
}

# High-value section-marker words common in German government forms
_SECTION_MARKERS = {
    "antrag", "anlage", "leistung", "beantragte", "persönliche", "angaben",
    "berechnung", "einkommen", "vermögen", "bedarfsgemeinschaft",
    "schülerbeförderung", "lernförderung", "mittagessen", "klassenfahrt",
    "wohngeld", "kindergeld", "elterngeld", "bürgergeld", "sozialhilfe",
    "aufenthalt", "einbürgerung", "asyl",
}


def _tokenize(text: str) -> list[str]:
    """Lowercase + word tokens. Keeps German letters."""
    text = text.lower()
    return re.findall(r"[a-zäöüß]+", text)


def _score_phrase(words: tuple[str, ...]) -> float:
    score = 0.0
    score += len(words) * 1.5  # longer phrases preferred
    if any(w in _SECTION_MARKERS for w in words):
        score += 5.0
    if all(w in _STOPWORDS for w in words):
        score -= 10.0  # all stopwords = bad
    avg_len = sum(len(w) for w in words) / len(words)
    if avg_len >= 6:
        score += 2.0  # longer words = more specific
    return score


def suggest_fingerprint_phrases(pdf_bytes: bytes, top_n: int = 10) -> list[str]:
    from app.services.pdf_pipeline import _extract_full_text

    text = _extract_full_text(pdf_bytes)
    if not text or len(text) < 50:
        return []

    tokens = _tokenize(text)
    candidates: Counter[tuple[str, ...]] = Counter()

    # Generate 3-, 4-, and 5-grams
    for n in (3, 4, 5):
        for i in range(len(tokens) - n + 1):
            ngram = tuple(tokens[i:i + n])
            candidates[ngram] += 1

    # Keep only phrases that appear once (more specific) or twice
    rare = [(p, c) for p, c in candidates.items() if c <= 2]
    scored = sorted(rare, key=lambda x: _score_phrase(x[0]), reverse=True)

    return [" ".join(p) for p, _ in scored[:top_n]]
