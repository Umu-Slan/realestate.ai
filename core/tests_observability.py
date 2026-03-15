"""
Tests for observability: context, bind, structured logging.
"""
import json
import logging

import pytest

from core.observability import (
    get_context,
    bind_context,
    clear_context,
    log_inbound,
    log_orchestration_start,
    log_orchestration_complete,
    log_orchestration_failed,
    log_scoring,
    log_crm_sync,
    log_pipeline_failure,
    log_exception,
    log_lead_temperature_assigned,
    log_buyer_stage_assigned,
    log_next_best_action_selected,
    log_recommendation_generated,
    log_support_severity_assigned,
    log_escalation_triggered,
    log_unverified_fact_blocked,
    ObservabilityFormatter,
)


class TestObservabilityContext:
    """Test context vars and bind/clear."""

    def test_get_context_empty(self):
        clear_context()
        ctx = get_context()
        assert ctx == {}

    def test_bind_and_get_context(self):
        clear_context()
        bind_context(correlation_id="cid1", conversation_id=42, run_id="run_abc")
        ctx = get_context()
        assert ctx["correlation_id"] == "cid1"
        assert ctx["conversation_id"] == 42
        assert ctx["run_id"] == "run_abc"

    def test_bind_partial(self):
        clear_context()
        bind_context(conversation_id=10)
        ctx = get_context()
        assert ctx.get("conversation_id") == 10

    def test_clear_context(self):
        bind_context(correlation_id="x", conversation_id=1)
        clear_context()
        ctx = get_context()
        assert ctx == {}


class TestObservabilityLogging:
    """Test that log helpers emit without error and include expected payload."""

    def test_log_inbound(self, caplog):
        clear_context()
        with caplog.at_level(logging.INFO, logger="realestate.observability"):
            log_inbound(channel="web", external_id="ext1", content_len=20)
        assert any("inbound_message" in r.message for r in caplog.records)
        last = caplog.records[-1]
        assert hasattr(last, "obs")
        assert last.obs.get("event") == "inbound_message"
        assert last.obs.get("channel") == "web"

    def test_log_orchestration_start(self, caplog):
        clear_context()
        with caplog.at_level(logging.INFO, logger="realestate.observability"):
            log_orchestration_start(run_id="run_xyz", channel="web", conversation_id=5)
        assert any("orchestration_start" in r.message for r in caplog.records)
        ctx = get_context()
        assert ctx.get("run_id") == "run_xyz"
        assert ctx.get("conversation_id") == 5

    def test_log_orchestration_complete(self, caplog):
        clear_context()
        with caplog.at_level(logging.INFO, logger="realestate.observability"):
            log_orchestration_complete(run_id="r1", status="success", route="sales", temperature="warm")
        assert any("orchestration_complete" in r.message for r in caplog.records)
        last = [r for r in caplog.records if "orchestration_complete" in r.message][-1]
        assert last.obs.get("status") == "success"
        assert last.obs.get("temperature") == "warm"

    def test_log_orchestration_failed(self, caplog):
        clear_context()
        with caplog.at_level(logging.ERROR, logger="realestate.observability"):
            log_orchestration_failed(run_id="r1", reason="intelligence error", stage="intelligence")
        assert any("orchestration_failed" in r.message for r in caplog.records)
        last = [r for r in caplog.records if "orchestration_failed" in r.message][-1]
        assert last.levelno == logging.ERROR
        assert last.obs.get("reason") == "intelligence error"

    def test_log_scoring(self, caplog):
        clear_context()
        with caplog.at_level(logging.INFO, logger="realestate.observability"):
            log_scoring(customer_id=1, score=75, temperature="hot")
        assert any("scoring" in r.message for r in caplog.records)

    def test_log_crm_sync(self, caplog):
        clear_context()
        with caplog.at_level(logging.INFO, logger="realestate.observability"):
            log_crm_sync(customer_id=2, action="sync_conversation_outcome")
        assert any("crm_sync" in r.message for r in caplog.records)

    def test_log_pipeline_failure(self, caplog):
        clear_context()
        with caplog.at_level(logging.ERROR, logger="realestate.observability"):
            log_pipeline_failure(component="persistence", error="DB timeout")
        assert any("pipeline_failure" in r.message for r in caplog.records)
        last = [r for r in caplog.records if "pipeline_failure" in r.message][-1]
        assert last.obs.get("component") == "persistence"


class TestObservabilityFormatter:
    """Test ObservabilityFormatter appends obs dict."""

    def test_formatter_with_obs(self):
        fmt = ObservabilityFormatter("%(message)s")
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "hello", (), None
        )
        record.obs = {"event": "test_event", "run_id": "r1"}
        out = fmt.format(record)
        assert "hello" in out
        assert "obs=" in out
        parsed = json.loads(out.split("obs=")[1])
        assert parsed["event"] == "test_event"
        assert parsed["run_id"] == "r1"

    def test_formatter_without_obs(self):
        fmt = ObservabilityFormatter("%(message)s")
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "plain", (), None
        )
        out = fmt.format(record)
        assert out == "plain"
        assert "obs=" not in out


class TestLogException:
    """Test log_exception emits full diagnostics."""

    def test_log_exception_structure(self, caplog):
        clear_context()
        bind_context(correlation_id="cid1", conversation_id=42, run_id="run_xyz")
        exc = ValueError("invalid input")
        with caplog.at_level(logging.ERROR, logger="realestate.observability"):
            log_exception(component="persistence", exc=exc, stage="persist_artifacts")
        assert any("exception" in r.message for r in caplog.records)
        last = [r for r in caplog.records if "exception" in r.message][-1]
        assert hasattr(last, "obs")
        obs = last.obs
        assert obs["event"] == "exception"
        assert obs["component"] == "persistence"
        assert obs["stage"] == "persist_artifacts"
        assert obs["exception_type"] == "ValueError"
        assert obs["error"] == "invalid input"
        assert "traceback" in obs
        assert obs["correlation_id"] == "cid1"
        assert obs["conversation_id"] == 42
        assert obs["run_id"] == "run_xyz"


class TestBusinessEvents:
    """Test new business event helpers emit correct event names."""

    def test_lead_temperature_assigned(self, caplog):
        clear_context()
        with caplog.at_level(logging.INFO, logger="realestate.observability"):
            log_lead_temperature_assigned(customer_id=1, temperature="hot", score=85)
        last = caplog.records[-1]
        assert last.obs["event"] == "lead_temperature_assigned"
        assert last.obs["temperature"] == "hot"

    def test_buyer_stage_assigned(self, caplog):
        clear_context()
        with caplog.at_level(logging.INFO, logger="realestate.observability"):
            log_buyer_stage_assigned(journey_stage="consideration", customer_type="new_lead")
        last = caplog.records[-1]
        assert last.obs["event"] == "buyer_stage_assigned"
        assert last.obs["journey_stage"] == "consideration"

    def test_next_best_action_selected(self, caplog):
        clear_context()
        with caplog.at_level(logging.INFO, logger="realestate.observability"):
            log_next_best_action_selected(action="schedule_call", reason="hot_lead")
        last = caplog.records[-1]
        assert last.obs["event"] == "next_best_action_selected"
        assert last.obs["action"] == "schedule_call"

    def test_recommendation_generated(self, caplog):
        clear_context()
        with caplog.at_level(logging.INFO, logger="realestate.observability"):
            log_recommendation_generated(match_count=3, customer_id=1, conversation_id=5)
        last = caplog.records[-1]
        assert last.obs["event"] == "recommendation_generated"
        assert last.obs["match_count"] == 3

    def test_support_severity_assigned(self, caplog):
        clear_context()
        with caplog.at_level(logging.INFO, logger="realestate.observability"):
            log_support_severity_assigned(case_id=10, severity="high", category="general_support")
        last = caplog.records[-1]
        assert last.obs["event"] == "support_severity_assigned"
        assert last.obs["severity"] == "high"

    def test_escalation_triggered(self, caplog):
        clear_context()
        with caplog.at_level(logging.INFO, logger="realestate.observability"):
            log_escalation_triggered(escalation_id=5, customer_id=1, reason="angry_customer")
        last = caplog.records[-1]
        assert last.obs["event"] == "escalation_triggered"
        assert last.obs["reason"] == "angry_customer"

    def test_unverified_fact_blocked(self, caplog):
        clear_context()
        with caplog.at_level(logging.INFO, logger="realestate.observability"):
            log_unverified_fact_blocked(block_reason="pricing", intent_hint="price_inquiry")
        last = caplog.records[-1]
        assert last.obs["event"] == "unverified_fact_blocked"
        assert last.obs["block_reason"] == "pricing"
