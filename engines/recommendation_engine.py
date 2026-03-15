"""
Recommendation Engine - structured project matching for Egyptian real estate.
Inputs: budget, area/location, property type, purpose (investment vs residence), urgency, historical preferences.
Output: top matches, match reasons, confidence, alternatives, trade-offs.
Supports Arabic and English. Degrades gracefully when data is partial.
Never fabricate; mark unverified facts explicitly.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from django.db.models import Q


# Location aliases: Arabic/English -> canonical search terms
LOCATION_ALIASES = {
    "معادي": ["معادي", "maadi", "المعادي"],
    "maadi": ["maadi", "معادي", "المعادي"],
    "أكتوبر": ["أكتوبر", "october", "6 october", "6أكتوبر"],
    "october": ["october", "أكتوبر", "6 october"],
    "القاهرة الجديدة": ["القاهرة الجديدة", "new cairo", "newcairo"],
    "new cairo": ["new cairo", "القاهرة الجديدة", "newcairo"],
    "المعادي": ["المعادي", "maadi", "معادي"],
    "السادات": ["السادات", "sadat", "مدينة السادات"],
    "العاشر": ["العاشر", "10th", "tenth", "العاشر من رمضان"],
    "مدينة نصر": ["مدينة نصر", "nasr city", "nasr"],
    "nasr city": ["nasr city", "مدينة نصر"],
    "الشروق": ["الشروق", "shorouk", "الشروق"],
    "zayed": ["zayed", "زايد"],
    "زايد": ["زايد", "zayed"],
}

PURPOSE_ALIASES = {
    "residence": ["residence", "سكن", "residential", "living"],
    "سكن": ["سكن", "residence", "residential"],
    "investment": ["investment", "استثمار", "استثمار"],
    "استثمار": ["استثمار", "investment"],
}


def _normalize_location(location: str) -> str:
    """Normalize location for matching - expand aliases."""
    if not location or not location.strip():
        return ""
    loc = location.strip().lower()
    for canonical, aliases in LOCATION_ALIASES.items():
        if any(a in loc for a in [c.lower() for c in aliases]):
            return canonical
    return location.strip()


def _normalize_purpose(purpose: str) -> str:
    """Normalize purpose to residence | investment | empty."""
    if not purpose or not purpose.strip():
        return ""
    p = purpose.strip().lower()
    for key, aliases in PURPOSE_ALIASES.items():
        if any(a in p for a in [x.lower() for x in aliases]):
            return key
    return ""


@dataclass
class ProjectMatch:
    """A recommended project with rationale, metadata, and market context."""
    project_id: int
    project_name: str
    project_name_ar: str = ""
    location: str = ""
    price_min: Optional[Decimal] = None
    price_max: Optional[Decimal] = None
    rationale: str = ""
    fit_score: float = 0.0
    match_reasons: list[str] = field(default_factory=list)
    confidence: float = 0.0
    trade_offs: list[str] = field(default_factory=list)
    has_verified_pricing: bool = False
    market_context: Optional[dict] = None  # ProjectMarketContext.to_safe_dict()


@dataclass
class RecommendationResult:
    """Structured recommendation output."""
    matches: list[ProjectMatch]
    overall_confidence: float
    alternatives: list[ProjectMatch]
    qualification_summary: str
    data_completeness: str  # full | partial | minimal


def recommend_projects(
    *,
    budget_min: Optional[Decimal] = None,
    budget_max: Optional[Decimal] = None,
    location_preference: str = "",
    property_type: str = "",
    purpose: str = "",
    urgency: str = "",
    bedroom_preference: Optional[int] = None,
    financing_preference: str = "",
    payment_method: str = "",
    journey_stage: str = "",
    historical_project_ids: list[int] | None = None,
    limit: int = 5,
) -> RecommendationResult:
    """
    Recommend top matching projects via production Property Matching Engine.
    Deterministic, explainable. Returns structured result with match_score,
    top_reasons, tradeoffs. Persistence stores rationale metadata.
    Returns empty matches for unsupported markets (e.g. Dubai, UAE, Riyadh).
    """
    from knowledge.models import Project
    from orchestration.recommendation_eligibility import _is_location_unsupported_market

    # Market validation: no Egypt inventory for Dubai/UAE/Riyadh/etc.
    if _is_location_unsupported_market(location_preference):
        return RecommendationResult(
            matches=[],
            overall_confidence=0.0,
            alternatives=[],
            qualification_summary="",
            data_completeness="minimal",
        )
    from knowledge.services.structured_facts import get_project_structured_facts
    from knowledge.services.market_context import get_project_market_context, get_projects_market_context
    from engines.property_matching import match_projects

    loc_norm = _normalize_location(location_preference)
    loc_search_terms = list(LOCATION_ALIASES.get(loc_norm, [loc_norm])) if loc_norm else []
    purpose_norm = _normalize_purpose(purpose)
    loc_terms = list(set(loc_search_terms + (location_preference.split() if location_preference else [])))

    # Data completeness for confidence
    has_budget = budget_min is not None or budget_max is not None
    has_location = bool(loc_norm or location_preference)
    has_purpose = bool(purpose_norm)
    if has_budget and has_location and (has_purpose or property_type):
        data_completeness = "full"
    elif has_budget or has_location:
        data_completeness = "partial"
    else:
        data_completeness = "minimal"

    # Filter candidates (same as before)
    qs = Project.objects.filter(is_active=True).order_by("name")
    if loc_terms:
        loc_filters = Q()
        for term in set(t for t in loc_terms if t):
            term_clean = term.strip()
            if len(term_clean) >= 2:
                loc_filters |= (
                    Q(location__icontains=term_clean) |
                    Q(name__icontains=term_clean) |
                    Q(name_ar__icontains=term_clean)
                )
        if loc_filters:
            qs = qs.filter(loc_filters)
    if budget_min is not None or budget_max is not None:
        if budget_min and budget_max:
            qs = qs.filter(
                (Q(price_min__lte=budget_max) | Q(price_min__isnull=True)) &
                (Q(price_max__gte=budget_min) | Q(price_max__isnull=True))
            )
        elif budget_max:
            qs = qs.filter(Q(price_min__lte=budget_max) | Q(price_min__isnull=True))
        elif budget_min:
            qs = qs.filter(Q(price_max__gte=budget_min) | Q(price_max__isnull=True))

    projects = list(qs[:limit * 3])

    # Production matching engine (weighted, inspectable)
    match_results = match_projects(
        projects=projects,
        budget_min=budget_min,
        budget_max=budget_max,
        location_preference=location_preference,
        loc_search_terms=loc_terms,
        property_type=property_type,
        bedroom_preference=bedroom_preference,
        purpose=purpose,
        financing_preference=financing_preference,
        payment_method=payment_method,
        urgency=urgency,
        journey_stage=journey_stage,
        historical_project_ids=historical_project_ids,
        get_structured_facts=get_project_structured_facts,
        get_market_context=get_project_market_context,
    )

    completeness_mult = 1.2 if data_completeness == "full" else 1.0 if data_completeness == "partial" else 0.8
    matches: list[ProjectMatch] = []
    for mr in match_results:
        matches.append(ProjectMatch(
            project_id=mr.project_id,
            project_name=mr.project_name,
            project_name_ar=mr.project_name_ar or "",
            location=mr.location or "",
            price_min=Decimal(str(mr.price_min)) if mr.price_min is not None else None,
            price_max=Decimal(str(mr.price_max)) if mr.price_max is not None else None,
            rationale=mr.rationale,
            fit_score=mr.match_score,
            match_reasons=mr.top_reasons,
            confidence=min(1.0, mr.match_score * completeness_mult),
            trade_offs=mr.tradeoffs,
            has_verified_pricing=mr.has_verified_pricing,
        ))

    top = matches[:limit]
    alternatives = matches[limit : limit + 3]

    # Enrich with market context
    project_ids = [m.project_id for m in top + alternatives]
    market_ctx_map = get_projects_market_context(project_ids)
    for m in top + alternatives:
        ctx = market_ctx_map.get(m.project_id)
        if ctx:
            m.market_context = ctx.to_safe_dict()

    overall_conf = sum(m.confidence for m in top) / len(top) if top else 0.0

    qual_parts = []
    if budget_min or budget_max:
        qual_parts.append(f"Budget: {budget_min or '?'}–{budget_max or '?'} EGP")
    if loc_norm or location_preference:
        qual_parts.append(f"Area: {loc_norm or location_preference}")
    if property_type:
        qual_parts.append(f"Type: {property_type}")
    if purpose_norm:
        qual_parts.append(f"Purpose: {purpose_norm}")
    qual_summary = "; ".join(qual_parts) if qual_parts else "General inquiry"

    return RecommendationResult(
        matches=top,
        overall_confidence=overall_conf,
        alternatives=alternatives,
        qualification_summary=qual_summary,
        data_completeness=data_completeness,
    )


def _build_rationale(p, reasons: list[str], budget_min, budget_max, has_verified: bool) -> str:
    """Build human-readable rationale. Mark unverified explicitly."""
    parts = []
    if "budget_fit" in reasons or "budget_near" in reasons:
        if p.price_min and p.price_max:
            pmin, pmax = float(p.price_min), float(p.price_max)
            if has_verified:
                parts.append(f"Fits budget (from {pmin:,.0f} to {pmax:,.0f} EGP)")
            else:
                parts.append(f"Typical range {pmin:,.0f}–{pmax:,.0f} EGP (confirm with sales)")
        else:
            parts.append("Within typical range")
    if "location_match" in reasons:
        parts.append(f"Location: {p.location}")
    if "returning_interest" in reasons:
        parts.append("Matches your previous interest")
    if "investment_friendly" in reasons:
        parts.append("Suitable for investment")
    if "residential" in reasons:
        parts.append("Residential focus")
    return "; ".join(parts) if parts else "Recommended based on your criteria"
