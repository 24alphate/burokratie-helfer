"""
Stateless PDF token — signs the uploaded PDF bytes alongside the extracted field map.

The token lets the backend reconstruct the PDF on the /fill-pdf call without any
database or filesystem lookup.  This makes the pipeline cold-start-proof: no state
is stored between the two requests.

Token contents (signed, NOT encrypted):
  {
    "pdf_b64":  zlib-compressed + base64-encoded original PDF bytes,
    "field_ids": list of extracted field_ids (authoritative grounding list),
    "filename":  original filename (for Content-Disposition on download),
  }

Security:
  The token is HMAC-SHA1 signed.  Its payload is readable (not encrypted), which
  is fine because the PDF was already uploaded by the user — there is no server-side
  secret embedded in it.  The signature prevents forgery.

Expiry:
  Default 4 hours.  After expiry the user must re-upload.  This is the correct
  behavior on Vercel serverless where /tmp is ephemeral anyway.
"""
from __future__ import annotations

import base64
import zlib

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

_SALT = "pdf-token-v1"
_MAX_AGE = 4 * 60 * 60  # 4 hours in seconds


def _serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt=_SALT)


def sign_pdf_token(
    pdf_bytes: bytes,
    field_ids: list[str],
    filename: str,
    secret_key: str,
    template_id: str | None = None,
) -> str:
    """
    Sign a PDF token.  Returns a URL-safe signed string.

    The PDF bytes are zlib-compressed before base64 encoding to reduce token size.
    A 200 KB PDF compresses to ~100 KB → ~137 KB base64 → ~183 KB final token.
    This fits comfortably within Vercel's 4.5 MB request body limit.
    """
    compressed = zlib.compress(pdf_bytes, level=9)
    pdf_b64 = base64.b64encode(compressed).decode("ascii")
    payload = {
        "pdf_b64":     pdf_b64,
        "field_ids":   field_ids,
        "filename":    filename,
        "template_id": template_id,  # None for AcroForm/unknown PDFs
    }
    return _serializer(secret_key).dumps(payload)


def verify_pdf_token(token: str, secret_key: str) -> dict:
    """
    Verify and decode a PDF token.

    Returns a dict with:
        pdf_bytes : bytes        — decompressed original PDF
        field_ids : list[str]   — extracted field_ids (ground truth)
        filename  : str          — original filename

    Raises:
        SignatureExpired  — token is older than 4 hours
        BadSignature     — token is tampered or wrong secret_key
    """
    payload = _serializer(secret_key).loads(token, max_age=_MAX_AGE)
    compressed = base64.b64decode(payload["pdf_b64"])
    return {
        "pdf_bytes":   zlib.decompress(compressed),
        "field_ids":   payload["field_ids"],
        "filename":    payload.get("filename", "form.pdf"),
        "template_id": payload.get("template_id"),   # None for old tokens / AcroForm
    }
