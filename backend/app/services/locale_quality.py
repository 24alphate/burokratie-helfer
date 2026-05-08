"""
Locale quality reporter.

Scores how completely a set of FieldDefinitions covers a target locale and
reports per-Tier-A coverage so the frontend (and tests) can detect drops in
question-language coverage before they reach a user.

Tier-A locales are the ones the product guarantees: en, de, fr, ar, tr, sq.
For Tier-A, "ready_for_locale" means every shown field's primary question
text is non-empty in the target locale and is not just the raw German label
(unless the target IS German). For Tier-B locales we report metrics but do
not fail readiness.
"""
from __future__ import annotations

from typing import Iterable, Optional

TIER_A_LOCALES: tuple[str, ...] = ("en", "de", "fr", "ar", "tr", "sq")


def _question_text(field_dict: dict, locale: str) -> str:
    """Read field.question[locale] safely from a FieldDefinition or its dict form."""
    q = getattr(field_dict, "question", None)
    if q is None and isinstance(field_dict, dict):
        q = field_dict.get("question")
    if not isinstance(q, dict):
        return ""
    return (q.get(locale) or "").strip()


def _original_label(field_dict) -> str:
    lbl = getattr(field_dict, "original_label", None)
    if lbl is None and isinstance(field_dict, dict):
        lbl = field_dict.get("original_label")
    return (lbl or "").strip()


def _question_source(field_dict) -> str:
    src = getattr(field_dict, "question_source", None)
    if src is None and isinstance(field_dict, dict):
        src = field_dict.get("question_source")
    return (src or "").strip()


def build_locale_quality_report(
    *,
    shown_fields: Iterable,
    selected_locale: str,
    document_language: str,
    extraction_source: str,
    support_level: int,
) -> dict:
    """
    Build the locale_quality_report for the *selected_locale* AND every Tier-A
    locale, so the frontend can see at a glance which languages a Level 1
    template is ready for.
    """
    fields = list(shown_fields)
    total = len(fields)

    def _per_locale(loc: str) -> dict:
        localized: list[str] = []
        fallback: list[str] = []
        missing: list[str] = []
        for f in fields:
            text = _question_text(f, loc)
            key = getattr(f, "key", None) or (f.get("key") if isinstance(f, dict) else "")
            if not text:
                missing.append(key)
                continue
            # A "fallback" is when the primary text is just the original German
            # label and the requested locale is NOT the document language.
            orig = _original_label(f)
            if loc != document_language and orig and text == orig:
                fallback.append(key)
                continue
            localized.append(key)

        # Tier-A readiness: no fallbacks, no missing.
        # Tier-B readiness: at least one localized question.
        is_tier_a = loc in TIER_A_LOCALES
        ready = (len(missing) == 0 and len(fallback) == 0) if is_tier_a else (len(localized) > 0)

        return {
            "locale": loc,
            "tier": "A" if is_tier_a else "B",
            "total_user_facing_fields": total,
            "localized_questions": len(localized),
            "fallback_questions": len(fallback),
            "missing_questions": missing,
            "fallback_field_ids": fallback,
            "ready_for_locale": ready,
        }

    per_locale: dict[str, dict] = {}
    locales_to_check = list(dict.fromkeys([selected_locale] + list(TIER_A_LOCALES)))
    for loc in locales_to_check:
        per_locale[loc] = _per_locale(loc)

    selected = per_locale[selected_locale]

    return {
        "selected_locale": selected_locale,
        "document_language": document_language,
        "extraction_source": extraction_source,
        "support_level": support_level,
        "total_user_facing_fields": total,
        "localized_questions": selected["localized_questions"],
        "fallback_questions": selected["fallback_questions"],
        "missing_questions": selected["missing_questions"],
        "fallback_field_ids": selected["fallback_field_ids"],
        "ready_for_locale": selected["ready_for_locale"],
        "per_locale": per_locale,
        "tier_a_ready": all(per_locale[loc]["ready_for_locale"] for loc in TIER_A_LOCALES),
    }
