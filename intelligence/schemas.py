"""
Structured output schemas for conversation intelligence.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class IntentResult:
    """Intent classification result - multi-label capable."""
    primary: str  # primary IntentCategory value
    secondary: list[str] = field(default_factory=list)
    confidence: float = 0.0
    is_support: bool = False
    is_spam: bool = False
    is_broker: bool = False


@dataclass
class QualificationExtraction:
    """Extracted lead qualification from conversation."""
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    budget_clarity: str = ""  # explicit_range, approximate, none, unclear
    location_preference: str = ""
    project_preference: str = ""
    property_type: str = ""
    residence_vs_investment: str = ""  # residence, investment, both, unknown
    payment_method: str = ""  # cash, installments, both, unknown
    purchase_timeline: str = ""
    financing_readiness: str = ""  # ready, exploring, not_ready, unknown
    family_size: Optional[int] = None
    urgency: str = ""  # immediate, soon, exploring, unknown
    missing_fields: list[str] = field(default_factory=list)
    confidence: str = "unknown"


@dataclass
class ReasonCode:
    """Explainable factor in scoring."""
    factor: str
    contribution: int
    note: str = ""


@dataclass
class ScoringResult:
    """Deterministic scoring output."""
    score: int
    temperature: str  # hot, warm, cold, nurture
    confidence: str  # high, medium, low, unknown
    reason_codes: list[ReasonCode] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    next_best_action: str = ""
    recommended_route: str = ""


@dataclass
class RoutingDecision:
    """Business routing output."""
    route: str
    queue: str = ""
    priority: str = "normal"
    requires_human_review: bool = False
    safe_response_policy: bool = False
    escalation_ready: bool = False
    quarantine: bool = False
    handoff_type: str = ""  # sales, support, legal, clarification
    reason: str = ""


@dataclass
class ConversationIntelligenceResult:
    """Full pipeline result for an incoming message."""
    customer_type: str  # new_lead, existing_customer, returning_lead, broker, spam, support_customer
    intent: IntentResult
    qualification: QualificationExtraction
    scoring: ScoringResult
    routing: RoutingDecision
    support_category: str = ""  # for existing customers
    is_ambiguous: bool = False
    requires_clarification: bool = False
