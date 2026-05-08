"""
Tests for GET /api/v1/templates/verified — Level 1 verified-template catalog.

Covers:
  - Endpoint returns 200
  - Response shape: count + templates list
  - Each template has field_count, write_spec_count, locale_coverage
  - jobcenter_but_v1 appears with expected coverage

Run with:  pytest tests/test_templates_endpoint.py -v
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class TestVerifiedTemplatesEndpoint:
    def test_endpoint_returns_200(self):
        response = client.get("/api/v1/templates/verified")
        assert response.status_code == 200

    def test_response_shape(self):
        response = client.get("/api/v1/templates/verified")
        body = response.json()
        assert "count" in body
        assert "templates" in body
        assert isinstance(body["templates"], list)
        assert body["count"] == len(body["templates"])

    def test_jobcenter_but_v1_present(self):
        response = client.get("/api/v1/templates/verified")
        body = response.json()
        ids = [t["template_id"] for t in body["templates"]]
        assert "jobcenter_but_v1" in ids

    def test_template_has_required_fields(self):
        response = client.get("/api/v1/templates/verified")
        body = response.json()
        for t in body["templates"]:
            assert "template_id" in t
            assert "name" in t
            assert "field_count" in t and isinstance(t["field_count"], int)
            assert "non_signature_count" in t
            assert "write_spec_count" in t
            assert "locale_coverage" in t

    def test_locale_coverage_includes_all_9_locales(self):
        response = client.get("/api/v1/templates/verified")
        body = response.json()
        EXPECTED = {"en", "de", "fr", "ar", "tr", "sq", "es", "ru", "uk"}
        for t in body["templates"]:
            assert set(t["locale_coverage"].keys()) == EXPECTED

    def test_jobcenter_but_v1_full_coverage(self):
        response = client.get("/api/v1/templates/verified")
        body = response.json()
        but = next(t for t in body["templates"] if t["template_id"] == "jobcenter_but_v1")
        # Every non-signature field must have a question in every locale
        for locale, cov in but["locale_coverage"].items():
            assert cov["covered"] == cov["total"], (
                f"jobcenter_but_v1 incomplete coverage for {locale}: "
                f"{cov['covered']}/{cov['total']}"
            )
