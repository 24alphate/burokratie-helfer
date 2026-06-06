"""
_check_ai_runtime() — the loud startup guard against the interpreter footgun
(running uvicorn on a Python that has a key configured but no `anthropic` SDK,
which silently degrades translation to German and breaks scanning).
"""
import builtins
import logging

import app.main as m
import app.services.question_translator as qt


def test_warns_when_key_set_but_sdk_missing(monkeypatch, caplog):
    monkeypatch.setattr(qt, "_resolve_anthropic_key", lambda: "sk-ant-fake-key")
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "anthropic":
            raise ImportError("simulated: anthropic not installed on this interpreter")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with caplog.at_level(logging.CRITICAL, logger="burokratie.main"):
        m._check_ai_runtime()
    assert any("AI MISCONFIGURED" in r.getMessage() for r in caplog.records)


def test_ok_when_key_and_sdk_present(monkeypatch, caplog):
    monkeypatch.setattr(qt, "_resolve_anthropic_key", lambda: "sk-ant-fake-key")
    with caplog.at_level(logging.INFO, logger="burokratie.main"):
        m._check_ai_runtime()
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "AI runtime OK" in msgs
    assert "AI MISCONFIGURED" not in msgs


def test_silent_table_path_when_no_key(monkeypatch, caplog):
    monkeypatch.setattr(qt, "_resolve_anthropic_key", lambda: "")
    with caplog.at_level(logging.INFO, logger="burokratie.main"):
        m._check_ai_runtime()
    assert any("no Anthropic key" in r.getMessage() for r in caplog.records)
