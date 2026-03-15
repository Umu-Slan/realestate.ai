"""
Explicit structured schemas for all multi-agent sales agents.
Typed, validated, JSON-serializable. Suitable for persistence and observability.
"""
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Optional, get_args, get_origin

# --- Validation constants ---
INTENT_OPTIONS = frozenset({
    "project_inquiry", "price_inquiry", "schedule_visit", "brochure_request",
    "location_inquiry", "investment_inquiry", "property_purchase",
    "support_complaint", "contract_issue", "maintenance_issue", "delivery_inquiry",
    "general_support", "documentation_inquiry", "payment_proof_inquiry",
    "installment_inquiry", "broker_inquiry", "spam", "other",
})
CONFIDENCE_LEVELS = frozenset({"high", "medium", "low", "unknown"})
DATA_COMPLETENESS = frozenset({"full", "partial", "minimal"})
APPROACH_OPTIONS = frozenset({"nurture", "qualify", "convert", "support", "objection_handling"})
TONE_OPTIONS = frozenset({"professional", "empathetic", "neutral"})
SALES_CTA_OPTIONS = frozenset({
    "ask_budget", "ask_location", "ask_property_type", "ask_bedrooms",
    "recommend_projects", "propose_visit", "create_urgency", "address_objection",
    "move_to_human", "nurture",
})


class SchemaValidationError(ValueError):
    """Raised when schema validation fails."""

    def __init__(self, schema: str, field_name: str, message: str):
        self.schema = schema
        self.field_name = field_name
        self.message = message
        super().__init__(f"{schema}.{field_name}: {message}")


def _validate_confidence(value: float) -> None:
    """Ensure confidence is numeric. Clamping to 0-1 is done in __post_init__."""
    if not isinstance(value, (int, float)):
        raise SchemaValidationError("IntentAgentOutput", "confidence", "must be numeric")


def _validate_confidence_str(value: str, schema: str, field: str) -> None:
    if value and value not in CONFIDENCE_LEVELS:
        raise SchemaValidationError(schema, field, f"must be one of {sorted(CONFIDENCE_LEVELS)}")


# --- Intent Agent ---
SALES_INTENT_OPTIONS = frozenset({
    "property_search", "price_inquiry", "location_inquiry", "project_details",
    "investment_inquiry", "visit_request", "booking_intent", "support_request",
    "negotiation", "unclear",
})


@dataclass(frozen=False)
class IntentAgentOutput:
    """Intent classification output. Sales intent + legacy primary (routing), entities, stage hint."""
    primary: str  # Legacy IntentCategory for routing
    secondary: list[str] = field(default_factory=list)
    confidence: float = 0.0
    is_support: bool = False
    is_spam: bool = False
    is_broker: bool = False
    sales_intent: str = ""  # True intent: property_search, price_inquiry, etc.
    entities: dict = field(default_factory=dict)
    stage_hint: str = ""

    def __post_init__(self) -> None:
        self.primary = (self.primary or "other").strip() or "other"
        if self.primary not in INTENT_OPTIONS:
            self.primary = "other"
        self.secondary = list(self.secondary or [])
        _validate_confidence(self.confidence)
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        self.sales_intent = (self.sales_intent or "").strip()
        if self.sales_intent and self.sales_intent not in SALES_INTENT_OPTIONS:
            self.sales_intent = "unclear"
        self.entities = dict(self.entities or {})
        self.stage_hint = (self.stage_hint or "").strip()[:50]

    def to_dict(self) -> dict:
        return {
            "primary": self.primary,
            "secondary": self.secondary,
            "confidence": self.confidence,
            "is_support": self.is_support,
            "is_spam": self.is_spam,
            "is_broker": self.is_broker,
            "sales_intent": self.sales_intent,
            "entities": self.entities,
            "stage_hint": self.stage_hint,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IntentAgentOutput":
        return cls(
            primary=d.get("primary", "other"),
            secondary=d.get("secondary", []) or [],
            confidence=float(d.get("confidence", 0)),
            is_support=bool(d.get("is_support")),
            is_spam=bool(d.get("is_spam")),
            is_broker=bool(d.get("is_broker")),
            sales_intent=d.get("sales_intent", ""),
            entities=dict(d.get("entities") or {}),
            stage_hint=d.get("stage_hint", ""),
        )


# --- Memory Agent ---
@dataclass(frozen=False)
class MemoryAgentOutput:
    """Aggregated conversation + structured customer memory profile."""
    conversation_summary: str = ""
    customer_type_hint: str = ""
    key_facts: list[str] = field(default_factory=list)
    prior_intents: list[str] = field(default_factory=list)
    message_count: int = 0
    customer_profile: dict = field(default_factory=dict)  # Structured memory for downstream agents

    def __post_init__(self) -> None:
        self.conversation_summary = (self.conversation_summary or "")[:500]
        self.customer_type_hint = (self.customer_type_hint or "").strip() or "new_lead"
        self.key_facts = list(self.key_facts or [])[:20]
        self.prior_intents = list(self.prior_intents or [])[:10]
        self.message_count = max(0, int(self.message_count))
        self.customer_profile = dict(self.customer_profile or {})

    def to_dict(self) -> dict:
        return {
            "conversation_summary": self.conversation_summary,
            "customer_type_hint": self.customer_type_hint,
            "key_facts": self.key_facts,
            "prior_intents": self.prior_intents,
            "message_count": self.message_count,
            "customer_profile": self.customer_profile,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryAgentOutput":
        return cls(
            conversation_summary=d.get("conversation_summary", ""),
            customer_type_hint=d.get("customer_type_hint", "new_lead"),
            key_facts=d.get("key_facts", []) or [],
            prior_intents=d.get("prior_intents", []) or [],
            message_count=int(d.get("message_count", 0)),
            customer_profile=dict(d.get("customer_profile") or {}),
        )


# --- Lead Qualification Agent ---
@dataclass(frozen=False)
class LeadQualificationAgentOutput:
    """Extracted lead qualification + scoring (lead_score, temperature, reasoning, next_best_action)."""
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    location_preference: str = ""
    project_preference: str = ""
    property_type: str = ""
    purpose: str = ""
    urgency: str = ""
    bedrooms: Optional[int] = None
    missing_fields: list[str] = field(default_factory=list)
    confidence: str = "unknown"
    lead_score: int = 0
    lead_temperature: str = "nurture"
    reasoning: list[dict] = field(default_factory=list)
    next_best_action: str = ""

    def __post_init__(self) -> None:
        self.missing_fields = list(self.missing_fields or [])
        self.reasoning = list(self.reasoning or [])
        _validate_confidence_str(self.confidence, "LeadQualificationAgentOutput", "confidence")
        if self.budget_min is not None and not isinstance(self.budget_min, Decimal):
            self.budget_min = Decimal(str(self.budget_min))
        if self.budget_max is not None and not isinstance(self.budget_max, Decimal):
            self.budget_max = Decimal(str(self.budget_max))
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise SchemaValidationError(
                "LeadQualificationAgentOutput", "budget", "budget_min must be <= budget_max"
            )
        self.lead_score = max(0, min(100, int(self.lead_score or 0)))

    def to_dict(self) -> dict:
        return {
            "budget_min": str(self.budget_min) if self.budget_min is not None else None,
            "budget_max": str(self.budget_max) if self.budget_max is not None else None,
            "location_preference": (self.location_preference or "").strip(),
            "project_preference": (self.project_preference or "").strip(),
            "property_type": (self.property_type or "").strip(),
            "purpose": (self.purpose or "").strip(),
            "urgency": (self.urgency or "").strip(),
            "bedrooms": self.bedrooms,
            "missing_fields": self.missing_fields,
            "confidence": self.confidence,
            "lead_score": self.lead_score,
            "lead_temperature": self.lead_temperature or "nurture",
            "reasoning": [r if isinstance(r, dict) else {"factor": getattr(r, "factor", ""), "contribution": getattr(r, "contribution", 0), "note": getattr(r, "note", "")} for r in self.reasoning],
            "next_best_action": (self.next_best_action or "").strip(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LeadQualificationAgentOutput":
        bmin = d.get("budget_min")
        bmax = d.get("budget_max")
        reasoning = d.get("reasoning", [])
        reasoning = [r if isinstance(r, dict) else {"factor": "", "contribution": 0, "note": ""} for r in reasoning]
        return cls(
            budget_min=Decimal(str(bmin)) if bmin is not None else None,
            budget_max=Decimal(str(bmax)) if bmax is not None else None,
            location_preference=d.get("location_preference", ""),
            project_preference=d.get("project_preference", ""),
            property_type=d.get("property_type", ""),
            purpose=d.get("purpose", ""),
            urgency=d.get("urgency", ""),
            bedrooms=int(d["bedrooms"]) if d.get("bedrooms") is not None else None,
            missing_fields=d.get("missing_fields", []) or [],
            confidence=d.get("confidence", "unknown"),
            lead_score=int(d.get("lead_score", 0)),
            lead_temperature=d.get("lead_temperature", "nurture"),
            reasoning=reasoning,
            next_best_action=d.get("next_best_action", ""),
        )


# --- Retrieval Agent ---
@dataclass(frozen=False)
class RetrievalSource:
    """Single retrieval source with relevance, verification, and content snippet."""
    chunk_id: int = 0
    document_title: str = ""
    content_snippet: str = ""
    relevance_score: float = 0.0
    source_of_truth: bool = False
    verification_status: str = ""
    is_fresh: bool = True
    document_type: str = ""
    chunk_type: str = ""

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_title": self.document_title or "",
            "content_snippet": self.content_snippet or "",
            "relevance_score": self.relevance_score,
            "source_of_truth": self.source_of_truth,
            "verification_status": self.verification_status,
            "is_fresh": self.is_fresh,
            "document_type": self.document_type,
            "chunk_type": self.chunk_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RetrievalSource":
        return cls(
            chunk_id=int(d.get("chunk_id", 0)),
            document_title=str(d.get("document_title", "")),
            content_snippet=str(d.get("content_snippet", "")),
            relevance_score=float(d.get("relevance_score", 0)),
            source_of_truth=bool(d.get("source_of_truth")),
            verification_status=str(d.get("verification_status", "")),
            is_fresh=bool(d.get("is_fresh", True)),
            document_type=str(d.get("document_type", "")),
            chunk_type=str(d.get("chunk_type", "")),
        )


@dataclass(frozen=False)
class RetrievalAgentOutput:
    """Knowledge retrieval output - production grade with structured summary."""
    query: str = ""
    document_types: list[str] = field(default_factory=list)
    retrieval_sources: list[RetrievalSource] = field(default_factory=list)
    has_verified_pricing: bool = False
    has_verified_availability: bool = False
    retrieval_error: Optional[str] = None
    sources_count: int = 0
    structured_summary: str = ""
    source_of_truth_count: int = 0

    def __post_init__(self) -> None:
        self.retrieval_sources = [
            s if isinstance(s, RetrievalSource) else RetrievalSource.from_dict(s)
            for s in (self.retrieval_sources or [])
        ]
        self.sources_count = len(self.retrieval_sources)
        self.source_of_truth_count = sum(1 for s in self.retrieval_sources if getattr(s, "source_of_truth", False))

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "document_types": list(self.document_types or []),
            "retrieval_sources": [s.to_dict() if isinstance(s, RetrievalSource) else s for s in self.retrieval_sources],
            "has_verified_pricing": self.has_verified_pricing,
            "has_verified_availability": self.has_verified_availability,
            "retrieval_error": self.retrieval_error,
            "sources_count": self.sources_count,
            "structured_summary": self.structured_summary,
            "source_of_truth_count": self.source_of_truth_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RetrievalAgentOutput":
        sources = [
            RetrievalSource.from_dict(x) if isinstance(x, dict) else x
            for x in (d.get("retrieval_sources") or [])
        ]
        return cls(
            query=d.get("query", ""),
            document_types=d.get("document_types", []) or [],
            retrieval_sources=sources,
            has_verified_pricing=bool(d.get("has_verified_pricing")),
            has_verified_availability=bool(d.get("has_verified_availability")),
            retrieval_error=d.get("retrieval_error"),
            structured_summary=str(d.get("structured_summary", "")),
            source_of_truth_count=int(d.get("source_of_truth_count", 0)),
        )


# --- Property Matching Agent ---
@dataclass(frozen=False)
class PropertyMatch:
    """Single property/project match with optional market context."""
    project_id: int
    project_name: str
    location: str = ""
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    rationale: str = ""
    fit_score: float = 0.0
    match_reasons: list[str] = field(default_factory=list)
    confidence: float = 0.0
    trade_offs: list[str] = field(default_factory=list)
    has_verified_pricing: bool = False
    market_context: Optional[dict] = None  # ProjectMarketContext.to_safe_dict()

    def __post_init__(self) -> None:
        self.project_id = int(self.project_id)
        self.project_name = (self.project_name or "").strip()
        self.fit_score = max(0.0, min(1.0, float(self.fit_score or 0)))
        self.confidence = max(0.0, min(1.0, float(self.confidence or 0)))
        self.match_reasons = list(self.match_reasons or [])
        self.trade_offs = list(self.trade_offs or [])
        self.market_context = self.market_context if isinstance(self.market_context, dict) else None

    def to_dict(self) -> dict:
        out = {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "location": self.location,
            "price_min": self.price_min,
            "price_max": self.price_max,
            "rationale": self.rationale,
            "fit_score": self.fit_score,
            "match_score": self.fit_score,
            "match_reasons": self.match_reasons,
            "top_reasons": self.match_reasons,
            "trade_offs": self.trade_offs,
            "tradeoffs": self.trade_offs,
            "confidence": self.confidence,
            "has_verified_pricing": self.has_verified_pricing,
        }
        if self.market_context:
            out["market_context"] = self.market_context
        return out

    @classmethod
    def from_dict(cls, d: dict) -> "PropertyMatch":
        return cls(
            project_id=int(d.get("project_id", 0)),
            project_name=str(d.get("project_name", "")),
            location=str(d.get("location", "")),
            price_min=float(d["price_min"]) if d.get("price_min") is not None else None,
            price_max=float(d["price_max"]) if d.get("price_max") is not None else None,
            rationale=str(d.get("rationale", "")),
            fit_score=float(d.get("fit_score", 0)),
            match_reasons=list(d.get("match_reasons", []) or []),
            confidence=float(d.get("confidence", 0)),
            trade_offs=list(d.get("trade_offs", []) or []),
            has_verified_pricing=bool(d.get("has_verified_pricing")),
            market_context=d.get("market_context") if isinstance(d.get("market_context"), dict) else None,
        )


@dataclass(frozen=False)
class PropertyMatchingAgentOutput:
    """Property matching result."""
    matches: list[PropertyMatch] = field(default_factory=list)
    overall_confidence: float = 0.0
    data_completeness: str = "minimal"
    qualification_summary: str = ""
    alternatives: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.matches = [
            m if isinstance(m, PropertyMatch) else PropertyMatch.from_dict(m)
            for m in (self.matches or [])
        ]
        self.overall_confidence = max(0.0, min(1.0, float(self.overall_confidence or 0)))
        if self.data_completeness and self.data_completeness not in DATA_COMPLETENESS:
            self.data_completeness = "minimal"
        self.alternatives = list(self.alternatives or [])

    def to_dict(self) -> dict:
        return {
            "matches": [m.to_dict() if isinstance(m, PropertyMatch) else m for m in self.matches],
            "overall_confidence": self.overall_confidence,
            "data_completeness": self.data_completeness,
            "qualification_summary": self.qualification_summary,
            "alternatives": self.alternatives,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PropertyMatchingAgentOutput":
        matches = [
            PropertyMatch.from_dict(x) if isinstance(x, dict) else x
            for x in (d.get("matches") or [])
        ]
        return cls(
            matches=matches,
            overall_confidence=float(d.get("overall_confidence", 0)),
            data_completeness=d.get("data_completeness", "minimal"),
            qualification_summary=d.get("qualification_summary", ""),
            alternatives=list(d.get("alternatives", []) or []),
        )


# --- Recommendation Agent ---
WEAK_FIT_THRESHOLD = 0.55  # When top match < this, surface alternatives more prominently


@dataclass(frozen=False)
class RecommendationMatch:
    """Single recommendation match (alias for PropertyMatch structure in recommendation context)."""
    project_id: int
    project_name: str
    location: str = ""
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    rationale: str = ""
    fit_score: float = 0.0
    match_reasons: list[str] = field(default_factory=list)
    confidence: float = 0.0
    trade_offs: list[str] = field(default_factory=list)
    has_verified_pricing: bool = False

    def to_dict(self) -> dict:
        why = self.match_reasons or []
        if self.rationale and self.rationale not in why:
            why = why + [self.rationale] if why else [self.rationale]
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "location": self.location,
            "price_min": self.price_min,
            "price_max": self.price_max,
            "rationale": self.rationale,
            "fit_score": self.fit_score,
            "match_reasons": self.match_reasons,
            "why_it_matches": why,
            "confidence": self.confidence,
            "trade_offs": self.trade_offs,
            "tradeoffs": self.trade_offs,
            "has_verified_pricing": self.has_verified_pricing,
        }


@dataclass(frozen=False)
class RecommendationAlternative:
    """Alternative recommendation when exact fit is weak."""
    project_id: int
    project_name: str
    rationale: str = ""
    why_it_matches: list[str] = field(default_factory=list)
    tradeoffs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "rationale": self.rationale,
            "why_it_matches": self.why_it_matches,
            "tradeoffs": self.tradeoffs,
        }


@dataclass(frozen=False)
class RecommendationAgentOutput:
    """
    Production-grade recommendation output.
    Returns: top_recommendations, why_it_matches (per item), tradeoffs (per item),
    recommendation_confidence, alternatives (when fit is weak).
    Eligibility: recommendation_ready and recommendation_block_reason control when to show projects.
    """
    matches: list[dict] = field(default_factory=list)
    alternatives: list[dict] = field(default_factory=list)
    qualification_summary: str = ""
    data_completeness: str = "minimal"
    overall_confidence: float = 0.0
    response_text: str = ""
    # Canonical production fields (derived from matches/alternatives)
    top_recommendations: list[dict] = field(default_factory=list)
    recommendation_confidence: float = 0.0
    # Eligibility: only show recommendations when recommendation_ready=True
    recommendation_ready: bool = False
    recommendation_block_reason: str = ""

    def __post_init__(self) -> None:
        self.matches = list(self.matches or [])
        self.alternatives = list(self.alternatives or [])
        self.top_recommendations = list(self.top_recommendations or self.matches or [])
        self.overall_confidence = max(0.0, min(1.0, float(self.overall_confidence or 0)))
        self.recommendation_confidence = max(0.0, min(1.0, float(self.recommendation_confidence or self.overall_confidence or 0)))
        if self.data_completeness and self.data_completeness not in DATA_COMPLETENESS:
            self.data_completeness = "minimal"

    def to_dict(self) -> dict:
        d = {
            "matches": self.matches,
            "top_recommendations": self.top_recommendations,
            "alternatives": self.alternatives,
            "qualification_summary": self.qualification_summary,
            "data_completeness": self.data_completeness,
            "overall_confidence": self.overall_confidence,
            "recommendation_confidence": self.recommendation_confidence,
            "response_text": self.response_text,
            "recommendation_ready": self.recommendation_ready,
            "recommendation_block_reason": self.recommendation_block_reason,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "RecommendationAgentOutput":
        top = d.get("top_recommendations") or d.get("matches") or []
        return cls(
            matches=list(d.get("matches", []) or []),
            top_recommendations=list(top),
            alternatives=list(d.get("alternatives", []) or []),
            qualification_summary=d.get("qualification_summary", ""),
            data_completeness=d.get("data_completeness", "minimal"),
            overall_confidence=float(d.get("overall_confidence", 0)),
            recommendation_confidence=float(d.get("recommendation_confidence", d.get("overall_confidence", 0))),
            response_text=d.get("response_text", ""),
            recommendation_ready=bool(d.get("recommendation_ready", False)),
            recommendation_block_reason=str(d.get("recommendation_block_reason", "")),
        )


# --- Sales Strategy Agent ---
@dataclass(frozen=False)
class ScoringSummary:
    """Scoring summary for observability."""
    score: int = 0
    temperature: str = "nurture"
    confidence: str = "unknown"
    next_best_action: str = ""
    recommended_route: str = "nurture"
    reason_codes: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.score = max(0, min(100, int(self.score or 0)))
        _validate_confidence_str(self.confidence, "ScoringSummary", "confidence")
        self.reason_codes = list(self.reason_codes or [])

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "temperature": self.temperature,
            "confidence": self.confidence,
            "next_best_action": self.next_best_action,
            "recommended_route": self.recommended_route,
            "reason_codes": self.reason_codes,
        }


@dataclass(frozen=False)
class SalesStrategyAgentOutput:
    """Sales strategy output - strategy, objective, persuasive angle, recommended CTA."""
    approach: str = "nurture"
    objection_key: Optional[str] = None
    next_best_action: str = ""
    tone: str = "professional"
    key_points: list[str] = field(default_factory=list)
    scoring: Optional[ScoringSummary] = None
    # Production fields for conversational next move
    strategy: str = "nurture"
    objective: str = ""
    persuasive_angle: str = ""
    recommended_cta: str = "nurture"

    def __post_init__(self) -> None:
        if self.approach and self.approach not in APPROACH_OPTIONS:
            self.approach = "nurture"
        if self.tone and self.tone not in TONE_OPTIONS:
            self.tone = "professional"
        self.key_points = list(self.key_points or [])
        if self.recommended_cta and self.recommended_cta not in SALES_CTA_OPTIONS:
            self.recommended_cta = "nurture"
        if self.scoring is not None and not isinstance(self.scoring, ScoringSummary):
            self.scoring = ScoringSummary(**self.scoring) if isinstance(self.scoring, dict) else None

    def to_dict(self) -> dict:
        sc = self.scoring.to_dict() if self.scoring else {"score": 0, "temperature": "nurture", "confidence": "unknown", "next_best_action": "", "recommended_route": "nurture", "reason_codes": []}
        return {
            "approach": self.approach,
            "objection_key": self.objection_key,
            "next_best_action": self.next_best_action,
            "tone": self.tone,
            "key_points": self.key_points,
            "scoring": sc,
            "strategy": self.strategy,
            "objective": self.objective,
            "persuasive_angle": self.persuasive_angle,
            "recommended_cta": self.recommended_cta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SalesStrategyAgentOutput":
        sc = d.get("scoring")
        return cls(
            approach=d.get("approach", "nurture"),
            objection_key=d.get("objection_key"),
            next_best_action=d.get("next_best_action", ""),
            tone=d.get("tone", "professional"),
            key_points=d.get("key_points", []) or [],
            scoring=ScoringSummary(**sc) if isinstance(sc, dict) else None,
            strategy=d.get("strategy", "nurture"),
            objective=d.get("objective", ""),
            persuasive_angle=d.get("persuasive_angle", ""),
            recommended_cta=d.get("recommended_cta", "nurture"),
        )


# --- Journey Stage Agent ---
# support_retention = enum value used for persistence; "support" acceptable as alias
JOURNEY_STAGES = frozenset({
    "awareness", "exploration", "consideration", "shortlisting",
    "visit_planning", "negotiation", "booking", "post_booking",
    "support", "support_retention",
})


@dataclass(frozen=False)
class JourneyStageAgentOutput:
    """Buyer journey stage detection output."""
    stage: str = "awareness"
    confidence: float = 0.0
    stage_reasoning: list[str] = field(default_factory=list)
    next_sales_move: str = ""

    def __post_init__(self) -> None:
        self.stage = (self.stage or "awareness").strip().lower()
        if self.stage not in JOURNEY_STAGES:
            self.stage = "awareness"
        self.confidence = max(0.0, min(1.0, float(self.confidence or 0)))
        self.stage_reasoning = list(self.stage_reasoning or [])[:10]
        self.next_sales_move = (self.next_sales_move or "").strip()[:255]

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "confidence": self.confidence,
            "stage_reasoning": self.stage_reasoning,
            "next_sales_move": self.next_sales_move,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "JourneyStageAgentOutput":
        return cls(
            stage=d.get("stage", "awareness"),
            confidence=float(d.get("confidence", 0)),
            stage_reasoning=list(d.get("stage_reasoning", []) or []),
            next_sales_move=d.get("next_sales_move", ""),
        )


# --- Conversation Planning Agent ---
@dataclass(frozen=False)
class ConversationPlanAgentOutput:
    """
    Internal conversation plan: what we know, need, objective, best next move.
    Not exposed to end users—guides Response Composer only.
    """
    what_we_know: list[str] = field(default_factory=list)
    what_we_still_need: list[str] = field(default_factory=list)
    sales_objective_now: str = ""
    best_next_question_or_suggestion: str = ""

    def __post_init__(self) -> None:
        self.what_we_know = list(self.what_we_know or [])[:15]
        self.what_we_still_need = list(self.what_we_still_need or [])[:10]
        self.sales_objective_now = (self.sales_objective_now or "").strip()[:200]
        self.best_next_question_or_suggestion = (self.best_next_question_or_suggestion or "").strip()[:300]

    def to_dict(self) -> dict:
        return {
            "what_we_know": self.what_we_know,
            "what_we_still_need": self.what_we_still_need,
            "sales_objective_now": self.sales_objective_now,
            "best_next_question_or_suggestion": self.best_next_question_or_suggestion,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConversationPlanAgentOutput":
        return cls(
            what_we_know=list(d.get("what_we_know", []) or []),
            what_we_still_need=list(d.get("what_we_still_need", []) or []),
            sales_objective_now=d.get("sales_objective_now", ""),
            best_next_question_or_suggestion=d.get("best_next_question_or_suggestion", ""),
        )


# --- Persuasion and Objection Handling Agent ---
PERSUASION_OBJECTION_TYPES = frozenset({
    "price_too_high", "unsure_about_area", "comparing_projects",
    "wants_more_time", "investment_value_concern", "delivery_concerns",
    "financing_concerns", "trust_credibility",
})


@dataclass(frozen=False)
class PersuasionAgentOutput:
    """Ethical persuasion output: objection_type, handling_strategy, persuasive_points, preferred_CTA."""
    objection_type: str = ""
    handling_strategy: str = ""
    persuasive_points: list[str] = field(default_factory=list)
    preferred_cta: str = "address_objection"

    def __post_init__(self) -> None:
        self.persuasive_points = list(self.persuasive_points or [])
        if self.preferred_cta and self.preferred_cta not in SALES_CTA_OPTIONS and self.preferred_cta != "address_objection":
            self.preferred_cta = "address_objection"

    def to_dict(self) -> dict:
        return {
            "objection_type": self.objection_type,
            "handling_strategy": self.handling_strategy,
            "persuasive_points": self.persuasive_points,
            "preferred_cta": self.preferred_cta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PersuasionAgentOutput":
        return cls(
            objection_type=d.get("objection_type", ""),
            handling_strategy=d.get("handling_strategy", ""),
            persuasive_points=list(d.get("persuasive_points", []) or []),
            preferred_cta=d.get("preferred_cta", "address_objection"),
        )


# --- Response Composer Agent ---
@dataclass(frozen=False)
class ResponseComposerAgentOutput:
    """Production-grade composed response: reply_text, CTA, reasoning for operator."""
    reply_text: str = ""
    cta: str = ""
    reasoning_summary_for_operator: str = ""
    composed_from: list[str] = field(default_factory=list)
    draft_response: str = ""  # Backward compat: equals reply_text

    def __post_init__(self) -> None:
        self.reply_text = self.reply_text or self.draft_response or ""
        self.draft_response = self.draft_response or self.reply_text or ""
        self.cta = (self.cta or "").strip()[:80]
        self.reasoning_summary_for_operator = (self.reasoning_summary_for_operator or "").strip()[:500]
        self.composed_from = list(self.composed_from or [])

    def to_dict(self) -> dict:
        d = {
            "reply_text": self.reply_text,
            "cta": self.cta,
            "reasoning_summary_for_operator": self.reasoning_summary_for_operator,
            "composed_from": self.composed_from,
            "draft_response": self.draft_response or self.reply_text,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ResponseComposerAgentOutput":
        reply = d.get("reply_text", "") or d.get("draft_response", "")
        draft = d.get("draft_response", "") or reply
        return cls(
            reply_text=reply,
            cta=d.get("cta", ""),
            reasoning_summary_for_operator=d.get("reasoning_summary_for_operator", ""),
            composed_from=d.get("composed_from", []) or [],
            draft_response=draft,
        )


# --- Follow-up Agent ---
FOLLOW_UP_TYPES = frozenset({
    "gentle_reminder",
    "alternative_recommendation",
    "visit_prompt",
    "value_based_follow_up",
})


@dataclass(frozen=False)
class FollowUpAgentOutput:
    """
    Follow-up recommendations for dormant leads.
    Structured records only—auto_send_enabled=False by policy; never auto-send unless system enables.
    """
    recommendations: list[dict] = field(default_factory=list)
    auto_send_enabled: bool = False  # Policy flag; agent never enables—caller checks system policy
    lead_ref: str = ""

    def __post_init__(self) -> None:
        self.recommendations = list(self.recommendations or [])
        self.lead_ref = (self.lead_ref or "").strip()[:255]

    def to_dict(self) -> dict:
        return {
            "recommendations": self.recommendations,
            "auto_send_enabled": self.auto_send_enabled,
            "lead_ref": self.lead_ref,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FollowUpAgentOutput":
        return cls(
            recommendations=list(d.get("recommendations", []) or []),
            auto_send_enabled=bool(d.get("auto_send_enabled")),
            lead_ref=d.get("lead_ref", ""),
        )


# --- Schema registry for validation tests ---
__all__ = [
    "ConversationPlanAgentOutput",
    "IntentAgentOutput",
    "MemoryAgentOutput",
    "PersuasionAgentOutput",
    "LeadQualificationAgentOutput",
    "JourneyStageAgentOutput",
    "RetrievalSource",
    "RetrievalAgentOutput",
    "PropertyMatch",
    "PropertyMatchingAgentOutput",
    "RecommendationAgentOutput",
    "RecommendationMatch",
    "RecommendationAlternative",
    "ScoringSummary",
    "SalesStrategyAgentOutput",
    "ResponseComposerAgentOutput",
    "FollowUpAgentOutput",
    "SchemaValidationError",
    "AGENT_SCHEMAS",
]

AGENT_SCHEMAS = {
    "intent": IntentAgentOutput,
    "memory": MemoryAgentOutput,
    "persuasion": PersuasionAgentOutput,
    "conversation_plan": ConversationPlanAgentOutput,
    "lead_qualification": LeadQualificationAgentOutput,
    "journey_stage": JourneyStageAgentOutput,
    "retrieval": RetrievalAgentOutput,
    "property_matching": PropertyMatchingAgentOutput,
    "recommendation": RecommendationAgentOutput,
    "sales_strategy": SalesStrategyAgentOutput,
    "response_composer": ResponseComposerAgentOutput,
    "follow_up": FollowUpAgentOutput,
}
