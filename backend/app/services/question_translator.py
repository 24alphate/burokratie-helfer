"""
Translates PDF field labels and their options into the user's preferred language.

Called once per upload — generates question text + option labels for every
field in the PDF, in whatever language the user selected. Supports any language
Groq's model can handle (French, Fula, Arabic, Turkish, etc.).

Falls back to the static dynamic_form_service lookup table for EN/DE/AR/TR
when Groq is unavailable.
"""
from __future__ import annotations

import json
import os
from typing import Optional

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English", "de": "German", "fr": "French", "ar": "Arabic",
    "tr": "Turkish", "es": "Spanish", "ru": "Russian", "zh": "Chinese",
    "it": "Italian", "pl": "Polish", "pt": "Portuguese", "nl": "Dutch",
    "fa": "Persian/Farsi", "ur": "Urdu", "hi": "Hindi", "bn": "Bengali",
    "sw": "Swahili", "ha": "Hausa", "fula": "Fula/Fulfulde",
    "so": "Somali", "am": "Amharic", "uk": "Ukrainian", "ro": "Romanian",
}


def _groq_client():
    from openai import OpenAI
    key = os.environ.get("GROQ_API_KEY", "")
    if not key or key.startswith("REPLACE"):
        return None
    return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=key)


def translate_fields(
    fields: list[dict],
    user_language: str,
    document_language: str = "de",
) -> dict[str, dict]:
    """
    Translate field labels + options into user_language.

    Input fields: [{field_name, field_type, options: [str], original_label}]
    Returns: {field_name: {question, explanation, translated_options: {orig: translated}}}

    Falls back to static lookup when Groq unavailable.
    """
    client = _groq_client()
    if client is None:
        return _static_fallback(fields, user_language)

    target = LANGUAGE_NAMES.get(user_language, user_language)
    source = LANGUAGE_NAMES.get(document_language, document_language)

    # Compact field list for the prompt
    field_lines: list[str] = []
    for f in fields:
        line = f"- {f['field_name']} (type={f['field_type']}"
        if f.get("options"):
            line += f", options={f['options']}"
        if f.get("original_label") and f["original_label"] != f["field_name"]:
            line += f", label='{f['original_label']}'"
        line += ")"
        field_lines.append(line)

    prompt = f"""You help immigrants fill out official forms. The form is in {source}. The user speaks {target}.

Translate each form field below into {target}. For each field provide:
- "question": a clear, short question to ask the user in {target}
- "explanation": one sentence of guidance in {target} (what format is expected, e.g. DD.MM.YYYY for dates)
- "translated_options": for radio/select/checkbox fields, a dict mapping each original option to its {target} translation

Form fields from the {source} document:
{chr(10).join(field_lines)}

Reply with a single JSON object. Keys are exact field names. Example format:
{{
  "Familienstand": {{
    "question": "Quelle est votre situation familiale ?",
    "explanation": "Cochez la case correspondant à votre situation actuelle.",
    "translated_options": {{"ledig": "Célibataire", "verheiratet": "Marié(e)", "geschieden": "Divorcé(e)", "verwitwet": "Veuf/veuve"}}
  }},
  "Vorname": {{
    "question": "Quel est votre prénom ?",
    "explanation": "Entrez votre prénom exactement comme sur votre pièce d'identité.",
    "translated_options": {{}}
  }}
}}

Rules:
- Never invent options that don't exist in the original
- Use formal/polite register
- Keep questions concise (under 15 words)
- If the field type is 'signature', question = "Signez ici" (equivalent in {target})"""

    try:
        resp = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=4000,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return _static_fallback(fields, user_language)


def static_fallback(fields: list[dict], user_language: str) -> dict[str, dict]:
    """
    Fallback when Groq is unavailable. Uses the actual PDF label as the question text.

    This guarantees grounding: the question text is always the real label from the
    uploaded document, never an invented generic question from a lookup table.
    The label may be in the document language (e.g. German), but it is always
    traceable to a real field in the PDF.
    """
    result = {}
    for f in fields:
        # Use original_label (the real PDF text) as the question.
        # This is always grounded — it came from the PDF itself.
        # Fall back to field_name only if original_label is absent.
        label = f.get("original_label") or f.get("field_name", "")
        opts  = f.get("options", [])
        result[f["field_name"]] = {
            "question": label,
            "explanation": "",
            # Identity-map options: value shown as-is (PDF language) until Groq translates
            "translated_options": {o: o for o in opts},
        }
    return result


# Keep private alias for backward compat
_static_fallback = static_fallback
