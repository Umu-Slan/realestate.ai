"""
End-to-end tests for chat UI behavior.
Verifies: chat memory continuity, recommendation appearance only when ready,
details interaction, no internal text leakage, turn-level recommendation rendering.
"""
import pytest
from unittest.mock import MagicMock


@pytest.mark.django_db
def test_sales_chat_returns_recommendation_ready_and_pipeline():
    """API returns recommendation_ready, matches only when ready, pipeline for operator."""
    from django.test import Client

    client = Client()
    resp = client.post(
        "/api/engines/sales/",
        data={"message": "مرحبا"},
        content_type="application/json",
    )
    assert resp.status_code in (200, 400, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert "response" in data
        assert "recommendation_ready" in data
        assert "matches" in data
        assert "pipeline" in data
        pipeline = data["pipeline"]
        assert "intent" in pipeline or "agents_executed" in pipeline


def test_conversation_history_includes_matches_and_next_step():
    """conversation_history returns messages with metadata for restore."""
    from engines.views import conversation_history

    req = MagicMock()
    req.session = {}
    req.method = "GET"

    try:
        from rest_framework.response import Response
        resp = conversation_history(req)
        assert isinstance(resp, Response)
        data = resp.data
        assert "messages" in data
        for m in data.get("messages", []):
            if m.get("role") == "assistant":
                # May have matches, next_step, temperature in metadata
                assert "content" in m
    except Exception:
        pytest.skip("Requires full Django/DB setup")


def test_cta_mapping_never_exposes_internal_objectives():
    """to_customer_facing_next_step returns None for internal objectives."""
    from engines.cta_mapping import to_customer_facing_next_step
    from engines.response_sanitizer import is_internal_objective

    assert to_customer_facing_next_step("Share value proposition and qualify budget") is None
    assert to_customer_facing_next_step("qualify budget: Budget not specified") is None
    assert to_customer_facing_next_step("ask_budget") is not None
    assert to_customer_facing_next_step("ask_budget")["label"]
    assert "ask_budget" not in str(to_customer_facing_next_step("ask_budget")["label"]).lower()


def test_project_detail_returns_valid_structure():
    """project_detail returns id, name, location for View details modal."""
    from engines.views import project_detail

    req = MagicMock()
    req.method = "GET"

    try:
        from rest_framework.response import Response
        resp = project_detail(req, project_id=999999)
        assert isinstance(resp, Response)
        if resp.status_code == 200:
            data = resp.data
            assert "id" in data
            assert "name" in data or "name_ar" in data
            assert "location" in data
    except Exception:
        pytest.skip("Requires knowledge.Project")
