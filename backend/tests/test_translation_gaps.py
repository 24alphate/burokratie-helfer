"""
#2 — anthropic_available() requires both a key AND an importable SDK.
#3 — strict locale lookups stop the deterministic table from shadowing the AI
     with English for locales it doesn't cover.
"""
import builtins

import app.services.question_translator as qt
from app.services.question_translator import (
    get_deterministic_translation,
    anthropic_available,
)


def test_deterministic_strict_vs_permissive_for_uncovered_locale():
    # "Vorname" is in the table for French but NOT for Italian.
    assert get_deterministic_translation("Vorname", "fr") is not None
    # permissive: Italian missing -> English fallback (non-None) — the old shadow
    assert get_deterministic_translation("Vorname", "it") is not None
    # strict: Italian missing -> None, so the caller routes the field to AI
    assert get_deterministic_translation("Vorname", "it", strict=True) is None
    # strict: a covered locale still returns its value
    assert get_deterministic_translation("Vorname", "fr", strict=True) is not None
    # unknown label -> None regardless of strict
    assert get_deterministic_translation("Zzxq Not A Real Label", "fr", strict=True) is None


def test_anthropic_available_requires_key_and_sdk(monkeypatch):
    # No key -> False (even though the SDK is installed in the venv)
    monkeypatch.setattr(qt, "_resolve_anthropic_key", lambda: "")
    assert anthropic_available() is False

    # Key set + SDK importable -> True
    monkeypatch.setattr(qt, "_resolve_anthropic_key", lambda: "sk-ant-fake")
    assert anthropic_available() is True

    # Key set but SDK import fails -> False (the global-interpreter footgun)
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "anthropic":
            raise ImportError("simulated: anthropic missing on this interpreter")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert anthropic_available() is False
