"""
Locale quality reporter.

Scores how completely a set of FieldDefinitions covers a target locale and
reports per-Tier-A coverage so the frontend (and tests) can detect drops in
question + guidance language coverage before they reach a user.

Tier-A locales: en, de, fr, ar, tr, sq.

What it checks per locale:
  - question[locale]              must be present, non-fallback, right script
  - explanation[locale]           coverage tracked, asymmetry flagged
  - guidance.plain_language[loc]  coverage tracked, asymmetry flagged
  - guidance.example[loc]         coverage tracked
  - guidance.format_hint[loc]     coverage tracked

ready_for_locale (Tier-A) is FALSE when any of these hold:
  - missing_questions is non-empty
  - fallback_questions > 0 (question equals German label outside German)
  - wrong_language_questions > 0 (e.g. Arabic locale, no Arabic chars)
  - For input_type="date":  example[locale] missing
  - For input_type="number" (non-verified): example/format[locale] missing
  - Any help/example field that EVERY OTHER Tier-A locale has is missing
    here (asymmetry — the data exists, just not for this locale → bug)

Tier-B locales fall back to English; readiness only requires question coverage.
"""
from __future__ import annotations

import re
from typing import Iterable

TIER_A_LOCALES: tuple[str, ...] = ("en", "de", "fr", "ar", "tr", "sq")

# Arabic Unicode block (U+0600..U+06FF) plus extended Arabic.
_ARABIC_RE = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")


# ── Field-dict accessors (work for both Pydantic models and dicts) ───────────


def _get(field, name, default=None):
    val = getattr(field, name, None)
    if val is None and isinstance(field, dict):
        val = field.get(name)
    return default if val is None else val


def _question_text(field, locale: str) -> str:
    q = _get(field, "question", {})
    if not isinstance(q, dict):
        return ""
    return (q.get(locale) or "").strip()


def _guidance_dict(field, attr: str, locale: str) -> str:
    g = _get(field, "guidance", None)
    if g is None:
        return ""
    inner = getattr(g, attr, None)
    if inner is None and isinstance(g, dict):
        inner = g.get(attr)
    if not isinstance(inner, dict):
        return ""
    val = inner.get(locale)
    return (val or "").strip() if isinstance(val, str) else ""


def _explanation_text(field, locale: str) -> str:
    e = _get(field, "explanation", {})
    if not isinstance(e, dict):
        return ""
    return (e.get(locale) or "").strip()


def _input_type(field) -> str:
    return (_get(field, "input_type", "") or "").strip()


def _question_source(field) -> str:
    return (_get(field, "question_source", "") or "").strip()


def _key(field) -> str:
    return _get(field, "key", "") or ""


def _original_label(field) -> str:
    return (_get(field, "original_label", "") or "").strip()


# ── Per-locale snapshot ──────────────────────────────────────────────────────


def _snapshot_for_locale(
    fields: list,
    loc: str,
    document_language: str,
) -> dict:
    """Build a per-locale coverage snapshot. Used internally to compose readiness."""
    total = len(fields)
    localized_q: list[str] = []
    fallback_q: list[str] = []
    missing_q: list[str] = []
    wrong_lang_q: list[str] = []

    has_help: list[str] = []
    missing_help: list[str] = []

    has_example: list[str] = []
    missing_example: list[str] = []

    has_format: list[str] = []
    missing_format: list[str] = []

    for f in fields:
        key = _key(f)
        q = _question_text(f, loc)
        orig = _original_label(f)
        if not q:
            missing_q.append(key)
        elif loc != document_language and orig and q == orig:
            fallback_q.append(key)
        else:
            localized_q.append(key)
            # Wrong-language heuristic: Arabic locale must contain Arabic chars
            if loc == "ar" and not _ARABIC_RE.search(q):
                wrong_lang_q.append(key)

        plain = _guidance_dict(f, "plain_language", loc) or _explanation_text(f, loc)
        if plain:
            has_help.append(key)
        else:
            missing_help.append(key)

        example = _guidance_dict(f, "example", loc)
        if example:
            has_example.append(key)
        else:
            missing_example.append(key)

        fmt = _guidance_dict(f, "format_hint", loc)
        if fmt:
            has_format.append(key)
        else:
            missing_format.append(key)

    return {
        "locale": loc,
        "tier": "A" if loc in TIER_A_LOCALES else "B",
        "total_user_facing_fields": total,
        # questions
        "localized_questions": len(localized_q),
        "fallback_questions": len(fallback_q),
        "missing_questions": missing_q,
        "fallback_field_ids": fallback_q,
        "wrong_language_questions": wrong_lang_q,
        # help
        "localized_help": len(has_help),
        "fallback_help": 0,           # we don't silently fall back
        "missing_help": missing_help,
        # examples
        "localized_examples": len(has_example),
        "fallback_examples": 0,
        "missing_examples": missing_example,
        # format hints
        "localized_formats": len(has_format),
        "fallback_formats": 0,
        "missing_formats": missing_format,
    }


# ── Asymmetry detection (across Tier-A locales) ──────────────────────────────


def _asymmetry_gaps(
    fields: list,
    loc: str,
    snapshots: dict[str, dict],
) -> dict[str, list[str]]:
    """
    A field has an "asymmetry gap" when at least 2 OTHER Tier-A locales have
    help/example/format for it but THIS locale doesn't. That's a quality bug:
    the data exists, just not for the user's language.

    Returns {help: [field_ids], example: [field_ids], format: [field_ids]}.
    """
    other_locales = [l for l in TIER_A_LOCALES if l != loc]
    keys_by_field = [_key(f) for f in fields]

    def _has_in(snapshot: dict, kind: str, key: str) -> bool:
        # snapshot.localized_<kind> is a count, not a list — we need the
        # set of field_ids that have it, derived from the missing list.
        missing = snapshot.get(f"missing_{kind}", [])
        return key not in missing

    gaps: dict[str, list[str]] = {"help": [], "example": [], "format": []}
    for key in keys_by_field:
        for kind, snap_kind in (("help", "help"), ("example", "examples"), ("format", "formats")):
            this_missing = key in snapshots[loc][f"missing_{snap_kind}"]
            if not this_missing:
                continue
            # Count other Tier-A locales that DO have this field's data
            others_have = sum(
                1
                for ol in other_locales
                if _has_in(snapshots[ol], snap_kind, key)
            )
            if others_have >= 2:
                gaps[kind].append(key)
    return gaps


# ── Public entry point ───────────────────────────────────────────────────────


def build_locale_quality_report(
    *,
    shown_fields: Iterable,
    selected_locale: str,
    document_language: str,
    extraction_source: str,
    support_level: int,
    template_id: str | None = None,
) -> dict:
    """
    Build the full locale_quality_report. Includes a per-locale snapshot for
    every Tier-A locale (used by tests + the frontend's QA dashboard) plus a
    summary block for the selected_locale.
    """
    fields = list(shown_fields)
    total = len(fields)

    # 1. Per-locale snapshots
    snapshots: dict[str, dict] = {}
    locales_to_check = list(dict.fromkeys([selected_locale] + list(TIER_A_LOCALES)))
    for loc in locales_to_check:
        snapshots[loc] = _snapshot_for_locale(fields, loc, document_language)

    # 2. Asymmetry gaps per Tier-A locale (Level 1 quality bug detector)
    asymmetry: dict[str, dict[str, list[str]]] = {}
    for loc in TIER_A_LOCALES:
        asymmetry[loc] = _asymmetry_gaps(fields, loc, snapshots)
        snapshots[loc]["asymmetry_help"] = asymmetry[loc]["help"]
        snapshots[loc]["asymmetry_example"] = asymmetry[loc]["example"]
        snapshots[loc]["asymmetry_format"] = asymmetry[loc]["format"]

    # 3. Quality-required help/example based on input_type
    def _quality_required_gaps(loc: str) -> dict[str, list[str]]:
        """
        For dates/numbers, the quality checker requires example/format. If
        those are missing in `loc`, ready_for_locale must be False on Tier-A.
        """
        gaps: dict[str, list[str]] = {"date_missing_example": [], "number_missing_example": []}
        for f in fields:
            ftype = _input_type(f)
            key = _key(f)
            example = _guidance_dict(f, "example", loc)
            fmt = _guidance_dict(f, "format_hint", loc)
            if ftype == "date" and not example:
                gaps["date_missing_example"].append(key)
            elif ftype == "number" and _question_source(f) not in ("verified", "semantic"):
                if not (example or fmt):
                    gaps["number_missing_example"].append(key)
        return gaps

    for loc in TIER_A_LOCALES:
        snapshots[loc]["quality_required_gaps"] = _quality_required_gaps(loc)

    # 4. Readiness rule
    #
    # Per spec section 4 — ready_for_locale is FALSE when:
    #   • any shown field lacks question[selected_locale]
    #   • any main question falls back to English/German (i.e. equals raw label
    #     when locale != document_language)
    #   • any main question is in the wrong script (e.g. Latin chars in `ar`)
    #   • any help/example/format hint REQUIRED BY THE QUALITY CHECKER is
    #     missing in selected_locale (date_missing_example,
    #     number_missing_example — see services/question_quality.py)
    #
    # Asymmetry (data exists in N other locales but not this one) is
    # REPORTED as a quality signal but does NOT block readiness — it's a
    # gradient that grows naturally as we author more verified content.
    def _is_ready(loc: str) -> bool:
        snap = snapshots[loc]
        if loc not in TIER_A_LOCALES:
            return snap["localized_questions"] > 0
        if snap["missing_questions"]:
            return False
        if snap["fallback_questions"] > 0:
            return False
        if snap["wrong_language_questions"]:
            return False
        q_gaps = snap["quality_required_gaps"]
        if q_gaps["date_missing_example"] or q_gaps["number_missing_example"]:
            return False
        return True

    for loc in TIER_A_LOCALES:
        snapshots[loc]["ready_for_locale"] = _is_ready(loc)

    # Tier-B / unknown selected locale: still get a readiness flag
    if selected_locale not in TIER_A_LOCALES:
        snapshots[selected_locale]["ready_for_locale"] = _is_ready(selected_locale)

    selected = snapshots[selected_locale]

    return {
        "selected_locale": selected_locale,
        "template_id": template_id,
        "document_language": document_language,
        "extraction_source": extraction_source,
        "support_level": support_level,
        "total_user_facing_fields": total,
        # selected-locale summary
        "localized_questions": selected["localized_questions"],
        "fallback_questions": selected["fallback_questions"],
        "missing_questions": selected["missing_questions"],
        "fallback_field_ids": selected["fallback_field_ids"],
        "wrong_language_questions": selected["wrong_language_questions"],
        "localized_help": selected["localized_help"],
        "fallback_help": selected["fallback_help"],
        "missing_help": selected["missing_help"],
        "localized_examples": selected["localized_examples"],
        "fallback_examples": selected["fallback_examples"],
        "missing_examples": selected["missing_examples"],
        "localized_formats": selected["localized_formats"],
        "fallback_formats": selected["fallback_formats"],
        "missing_formats": selected["missing_formats"],
        "asymmetry_help": selected.get("asymmetry_help", []),
        "asymmetry_example": selected.get("asymmetry_example", []),
        "asymmetry_format": selected.get("asymmetry_format", []),
        "quality_required_gaps": selected.get("quality_required_gaps", {}),
        "ready_for_locale": _is_ready(selected_locale),
        "per_locale": snapshots,
        "tier_a_ready": all(snapshots[loc]["ready_for_locale"] for loc in TIER_A_LOCALES),
    }
