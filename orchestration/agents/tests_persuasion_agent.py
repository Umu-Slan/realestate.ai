"""
Tests for Persuasion and Objection Handling Agent.
Arabic examples for detection and ethical persuasion outputs.
"""
import pytest
from unittest.mock import MagicMock

from engines.persuasion import (
    detect_objection_type,
    get_persuasion_output,
    map_legacy_objection_to_type,
    OBJECTION_TYPES,
)
from orchestration.agents.persuasion_agent import PersuasionAgent
from orchestration.agents.schemas import PersuasionAgentOutput
from orchestration.agents.base import AgentContext


# --- Arabic examples ---
def test_detect_price_too_high_ar():
    """السعر غالي / price too high."""
    assert detect_objection_type("السعر غالي جداً") == "price_too_high"
    assert detect_objection_type("غالية عليا") == "price_too_high"
    assert detect_objection_type("ميزانيتي أقل من كده") == "price_too_high"


def test_detect_unsure_about_area_ar():
    """مش متأكد من المنطقة / unsure about area."""
    assert detect_objection_type("مش متأكد من المنطقة") == "unsure_about_area"
    assert detect_objection_type("الموقع بعيد عن شغلي") == "unsure_about_area"


def test_detect_comparing_projects_ar():
    """بين مشروعين / comparing projects."""
    assert detect_objection_type("بين مشروعين دي أيهما أفضل") == "comparing_projects"
    assert detect_objection_type("أقارن بين التجمع وأكتوبر") == "comparing_projects"


def test_detect_wants_more_time_ar():
    """هستنى وأفكر / wants more time."""
    assert detect_objection_type("هستنى وأفكر") == "wants_more_time"
    assert detect_objection_type("مش مستعجل دلوقتي") == "wants_more_time"


def test_detect_investment_value_concern_ar():
    """قيمة الاستثمار / investment value concern."""
    assert detect_objection_type("مش متأكد من العائد") == "investment_value_concern"
    assert detect_objection_type("worried about investment value") == "investment_value_concern"


def test_detect_delivery_concerns_ar():
    """مخاوف التسليم / delivery concerns."""
    assert detect_objection_type("متى التسليم؟") == "delivery_concerns"
    assert detect_objection_type("التسليم بيتأخر") == "delivery_concerns"


def test_detect_financing_concerns_ar():
    """التقسيط / financing concerns."""
    assert detect_objection_type("التقسيط مناسب؟") == "financing_concerns"
    assert detect_objection_type("المقدم كتير") == "financing_concerns"


def test_persuasion_output_has_required_fields():
    """Output includes objection_type, handling_strategy, persuasive_points, preferred_cta."""
    po = get_persuasion_output("price_too_high")
    assert po.objection_type == "price_too_high"
    assert po.handling_strategy
    assert len(po.persuasive_points) >= 1
    assert po.preferred_cta


def test_persuasion_avoids_false_urgency():
    """Persuasive points avoid pressure and false scarcity phrases."""
    forbidden = ["must buy", "act now", "limited time only", "last chance", "فوراً اشتر"]
    for obj_type in ["wants_more_time", "price_too_high", "investment_value_concern"]:
        po = get_persuasion_output(obj_type)
        joined = " ".join(po.persuasive_points).lower()
        for phrase in forbidden:
            assert phrase not in joined


def test_map_legacy_objection():
    """Legacy objection keys map to persuasion types."""
    assert map_legacy_objection_to_type("waiting_hesitation") == "wants_more_time"
    assert map_legacy_objection_to_type("location_concern") == "unsure_about_area"
    assert map_legacy_objection_to_type("payment_plan_mismatch") == "financing_concerns"


def test_persuasion_agent_detects_and_returns_output():
    """Agent populates persuasion_output when objection detected."""
    ctx = AgentContext(
        run_id="t1",
        message_text="السعر غالي جداً",
        conversation_history=[],
        sales_strategy_output={"objection_key": "price_too_high"},
    )
    agent = PersuasionAgent()
    result = agent.run(ctx)
    assert result.success
    out = ctx.persuasion_output
    assert out["objection_type"] == "price_too_high"
    assert out["handling_strategy"]
    assert out["persuasive_points"]
    assert out["preferred_cta"]


def test_persuasion_agent_no_objection():
    """Agent returns empty output when no objection."""
    ctx = AgentContext(
        run_id="t1",
        message_text="مرحبا أريد شقة في المعادي",
        conversation_history=[],
    )
    agent = PersuasionAgent()
    result = agent.run(ctx)
    assert result.success
    out = ctx.persuasion_output
    assert not out.get("objection_type")


def test_persuasion_agent_output_schema_roundtrip():
    """PersuasionAgentOutput round-trip."""
    o = PersuasionAgentOutput(
        objection_type="comparing_projects",
        handling_strategy="comparison_support",
        persuasive_points=["Comparing is wise—we can highlight key differences."],
        preferred_cta="recommend_projects",
    )
    d = o.to_dict()
    assert d["objection_type"] == "comparing_projects"
    restored = PersuasionAgentOutput.from_dict(d)
    assert restored.objection_type == o.objection_type
    assert restored.persuasive_points == o.persuasive_points
