"""
Question-quality checker — pure, importable, testable.

Was a closure inside `process_pdf.py` until Phase C; extracted here so the
flag set can be exercised by unit tests without standing up the full HTTP
endpoint. Behavior is unchanged from the prior closure form, with two
additions called out explicitly:

    checkbox_not_yes_no            — Phase C, NEW
    multiselect_missing_select_all — Phase C, NEW

Both new flags are quality-reporting only. They do not change extraction,
template matching, AI calls, or PDF filling — they only annotate
`AnalysisReport.question_quality.weak_reasons_by_field`.

Public API:
    quality_flags(fd, entry, user_language, extraction_source) -> list[str]
"""
from __future__ import annotations

import re

# Bare nouns / single-word answers that are clearly NOT a question.
# Lower-case, full-string match (no substring check).
NOUN_PHRASES = {
    "number / count", "number", "count", "amount", "day", "month", "year",
    "time", "starting location", "destination", "route / distance",
    "transportation", "description", "notes / remarks", "reason", "purpose",
    "we", "ja", "nein", "yes", "no",
}

# Both ASCII "?" and the Arabic question mark count as "ends with question mark".
_QUESTION_TERMINATORS = ("?", "؟")

# Substrings that indicate a checkbox is using imperative "check this" form
# instead of an interrogative form. Tolerated as alternative valid phrasing.
_CHECKBOX_INSTRUCTION_HINTS = (
    "check this", "mark this", "tick this", "select this",
    "ankreuzen", "ankreuzen wenn", "markieren",
    "cocher", "marquez",
    "ضع علامة", "حدد",
    "işaretle", "tikle",
    "shëno", "shënoni",
    "marque", "marcar",
    "отметьте", "отметить",
    "позначте", "відмітьте",
)

# Substrings that indicate a multiselect question is telling the user
# they may pick more than one option.
_MULTISELECT_HINTS = (
    "select all", "choose all", "tick all", "check all",
    "all that apply", "alle zutreffenden", "zutreffende",
    "tout ce qui s'applique", "tous ceux qui",
    "كل ما ينطبق", "جميع ما ينطبق",
    "tümünü seçin", "uygun olanları",
    "të gjitha që",
    "todo lo que aplique", "todos los que",
    "все подходящие", "выберите все",
    "всі, що", "виберіть усі",
)


def _ends_with_question_mark(q: str) -> bool:
    return bool(q) and q.strip().endswith(_QUESTION_TERMINATORS)


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lo = text.lower()
    return any(n in lo for n in needles)


def quality_flags(
    fd,
    entry,
    user_language: str,
    extraction_source: str = "auto",
) -> list[str]:
    """
    Return a list of quality flags for one rendered question.

    Inputs:
      fd                 — FieldDefinition (Pydantic model)
      entry              — FieldMapEntry (dataclass) for the same field_id, or None
      user_language      — locale string ("en", "de", ...) used to read fd.question
      extraction_source  — "verified_template" enables Level 1 strict checks

    Returns: list of flag identifiers (empty when the question is strong).
    """
    q = (fd.question or {}).get(user_language, "") or ""
    reasons: list[str] = []
    q_words = q.split()
    ftype = fd.input_type
    orig = getattr(entry, "original_label", "") if entry is not None else ""
    has_guidance = fd.guidance is not None
    has_example = (
        has_guidance
        and bool((fd.guidance.example or {}) if fd.guidance else {})
    )
    has_format_hint = (
        has_guidance
        and bool((fd.guidance.format_hint or {}) if fd.guidance else {})
    )

    # 5-word minimum is an English-centric heuristic for catching AI noise
    # and raw labels. Verified questions are human-reviewed in 9 locales,
    # several of which (Arabic, Turkish) hit the same meaning in 3-4 words —
    # so we exempt verified-source questions from this single check.
    if (
        len(q_words) < 5
        and ftype not in ("checkbox", "signature")
        and fd.question_source != "verified"
    ):
        reasons.append("too_short")
    if q.lower() == orig.lower() and len(orig) < 30:
        reasons.append("same_as_label")
    if re.search(r"\s+\d+$", q):
        reasons.append("trailing_number")
    if "=" in q:
        reasons.append("contains_equals")
    if q.lower().strip() in NOUN_PHRASES:
        reasons.append("noun_not_question")
    if q.startswith("⚠") or "translation unavailable" in q.lower():
        reasons.append("explicit_failure")
    if ftype == "date" and not has_example:
        reasons.append("date_missing_example")
    if (
        ftype == "number"
        and not (has_example or has_format_hint)
        and fd.question_source not in ("verified", "semantic")
    ):
        reasons.append("number_missing_example")

    # Phase C — NEW
    if ftype == "checkbox" and q:
        # A checkbox is "yes/no" if it ends with a question mark OR contains
        # one anywhere (covers two-sentence forms like
        # "Do you receive other benefits? If yes, please specify."), OR
        # uses an explicit instructional opener ("Check this if...").
        is_question = _ends_with_question_mark(q) or any(qm in q for qm in _QUESTION_TERMINATORS)
        is_instruction = _contains_any(q, _CHECKBOX_INSTRUCTION_HINTS)
        if not (is_question or is_instruction):
            reasons.append("checkbox_not_yes_no")

    # Phase C — NEW
    if ftype == "multiselect" and q:
        looks_like_multiselect = _contains_any(q, _MULTISELECT_HINTS)
        if not looks_like_multiselect:
            reasons.append("multiselect_missing_select_all")

    # Level 1 invariants (CRITICAL — should never fire for a verified template):
    if fd.question_source == "verified" and reasons:
        reasons.append("verified_question_weak")
    if (
        extraction_source == "verified_template"
        and fd.question_source not in ("verified", "")
    ):
        reasons.append("template_field_not_verified")

    return reasons
