"""
Production-grade Property Matching Engine.
Weighted scoring across: budget, location, property type, bedroom, purpose,
financing, stage, family/lifestyle fit.
Inspectable, adjustable, honest (no fabricated reasons).
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

# --- Configurable weights (inspectable, adjustable) ---
FACTOR_WEIGHTS = {
    "budget_fit": 0.25,
    "location_fit": 0.22,
    "property_type_fit": 0.10,
    "bedroom_fit": 0.10,
    "purpose_fit": 0.12,
    "financing_fit": 0.08,
    "stage_fit": 0.06,
    "family_lifestyle_fit": 0.07,
}


@dataclass
class FactorContribution:
    """Single factor's contribution to match score."""
    factor: str
    score: float  # 0..1
    weight: float
    reason: str = ""
    tradeoff: str = ""

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


@dataclass
class ProjectMatchResult:
    """Per-project match result with score, reasons, tradeoffs."""
    project_id: int
    project_name: str
    project_name_ar: str = ""
    location: str = ""
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    match_score: float = 0.0
    top_reasons: list[str] = field(default_factory=list)
    tradeoffs: list[str] = field(default_factory=list)
    factor_contributions: list[FactorContribution] = field(default_factory=list)
    has_verified_pricing: bool = False
    rationale: str = ""


def _extract_bedroom_from_text(text: str) -> Optional[int]:
    """Extract bedroom count from text (e.g. '3br', 'شقة 3 غرف', '3 bedrooms')."""
    if not text or not str(text).strip():
        return None
    import re
    s = str(text).lower()
    # Arabic: ٣ غرف, 3 غرف, غرفتين
    for p in [r"(\d+)\s*غرف", r"غرف\s*(\d+)", r"(\d+)\s*bedroom", r"(\d+)\s*br", r"(\d+)\s*bed"]:
        m = re.search(p, s)
        if m:
            try:
                return int(m.group(1))
            except (ValueError, IndexError):
                pass
    return None


def _project_has_bedrooms(project, bedroom_preference: Optional[int]) -> Optional[bool]:
    """Check if project offers units with given bedroom count. Uses property_types, unit categories."""
    if bedroom_preference is None:
        return None
    # property_types may contain "apartment", "3br", "villa"
    types = getattr(project, "property_types", None) or []
    if isinstance(types, list):
        for t in types:
            extracted = _extract_bedroom_from_text(str(t))
            if extracted == bedroom_preference:
                return True
    # Check unit categories
    cats = getattr(project, "unit_categories_preview", None) or []
    if isinstance(cats, list):
        for c in cats:
            name = c.get("category_name", "") if isinstance(c, dict) else str(c)
            if _extract_bedroom_from_text(name) == bedroom_preference:
                return True
    # Fallback: project name/name_ar
    for attr in ["name", "name_ar"]:
        val = getattr(project, attr, None) or ""
        if _extract_bedroom_from_text(val) == bedroom_preference:
            return True
    return False


def _score_budget_fit(
    project,
    budget_min: Optional[Decimal],
    budget_max: Optional[Decimal],
    has_verified: bool,
) -> FactorContribution:
    """Score budget overlap. Honest: only use project prices when we have them."""
    w = FACTOR_WEIGHTS["budget_fit"]
    if not budget_min and not budget_max:
        return FactorContribution("budget_fit", 0.15, w, reason="budget_unknown")

    p_min = float(project.price_min) if project.price_min else None
    p_max = float(project.price_max) if project.price_max else None
    b_min = float(budget_min or 0)
    b_max = float(budget_max or float("inf")) if budget_max else float("inf")

    if p_min is not None and p_max is not None:
        overlap_min = max(p_min, b_min)
        overlap_max = min(p_max, b_max)
        if overlap_max >= overlap_min:
            return FactorContribution(
                "budget_fit", 1.0, w,
                reason="budget_fit",
            )
        if p_min <= b_max * 1.15:
            return FactorContribution(
                "budget_fit", 0.6, w,
                reason="budget_near",
                tradeoff="slightly_over_budget" if not has_verified else "above_budget",
            )
        return FactorContribution(
            "budget_fit", 0.2, w,
            reason="above_budget",
            tradeoff="above_budget",
        )
    return FactorContribution(
        "budget_fit", 0.2, w,
        reason="budget_unknown",
        tradeoff="pricing_unverified" if not has_verified else "",
    )


def _score_location_fit(
    project,
    location_preference: str,
    loc_search_terms: list[str],
) -> FactorContribution:
    """Score location match."""
    w = FACTOR_WEIGHTS["location_fit"]
    if not location_preference and not loc_search_terms:
        return FactorContribution("location_fit", 0.5, w, reason="location_unspecified")

    loc_str = (project.location or "").lower()
    name_str = ((project.name or "") + " " + (project.name_ar or "")).lower()
    terms = [t for t in loc_search_terms if t and len(str(t).strip()) >= 2]

    if terms and any(t.lower() in loc_str or t.lower() in name_str for t in terms):
        return FactorContribution("location_fit", 1.0, w, reason="location_match")
    if loc_str and location_preference:
        return FactorContribution(
            "location_fit", 0.35, w,
            reason="location_nearby",
            tradeoff="different_area",
        )
    return FactorContribution("location_fit", 0.1, w, reason="location_mismatch", tradeoff="different_area")


def _score_property_type_fit(project, property_type: str) -> FactorContribution:
    """Score property type match."""
    w = FACTOR_WEIGHTS["property_type_fit"]
    if not property_type or not str(property_type).strip():
        return FactorContribution("property_type_fit", 0.5, w, reason="property_type_unspecified")

    pt = str(property_type).strip().lower()
    types = getattr(project, "property_types", None) or []
    if isinstance(types, list) and pt in [str(x).lower() for x in types]:
        return FactorContribution("property_type_fit", 1.0, w, reason="property_type_match")
    if pt in (project.name or "").lower() or pt in (project.name_ar or "").lower():
        return FactorContribution("property_type_fit", 0.9, w, reason="property_type_match")
    return FactorContribution("property_type_fit", 0.0, w, reason="property_type_mismatch", tradeoff="different_type")


def _score_bedroom_fit(project, bedroom_preference: Optional[int], unit_categories: list) -> FactorContribution:
    """Score bedroom count match."""
    w = FACTOR_WEIGHTS["bedroom_fit"]
    if bedroom_preference is None:
        return FactorContribution("bedroom_fit", 0.5, w, reason="bedroom_unspecified")

    for cat in unit_categories:
        name = (cat.get("category_name") or "") + " " + (cat.get("category_name_ar") or "")
        if _extract_bedroom_from_text(name) == bedroom_preference:
            return FactorContribution("bedroom_fit", 1.0, w, reason="bedroom_match")
    if _extract_bedroom_from_text(project.name or "") == bedroom_preference:
        return FactorContribution("bedroom_fit", 0.9, w, reason="bedroom_match")
    types = getattr(project, "property_types", None) or []
    for t in types:
        if _extract_bedroom_from_text(str(t)) == bedroom_preference:
            return FactorContribution("bedroom_fit", 1.0, w, reason="bedroom_match")
    return FactorContribution("bedroom_fit", 0.2, w, reason="bedroom_unknown", tradeoff="bedroom_may_differ")


def _score_purpose_fit(project, purpose_norm: str, market_context: Optional[dict]) -> FactorContribution:
    """Score purpose (investment/residence) fit."""
    w = FACTOR_WEIGHTS["purpose_fit"]
    if not purpose_norm:
        return FactorContribution("purpose_fit", 0.5, w, reason="purpose_unspecified")

    if purpose_norm == "investment":
        inv_ok = market_context.get("investment_suitability") if market_context else None
        if inv_ok is True:
            return FactorContribution("purpose_fit", 1.0, w, reason="investment_friendly")
        return FactorContribution("purpose_fit", 0.7, w, reason="investment_friendly")
    if purpose_norm == "residence":
        fam_ok = market_context.get("family_suitability") if market_context else None
        if fam_ok is True:
            return FactorContribution("purpose_fit", 1.0, w, reason="residential_family_friendly")
        return FactorContribution("purpose_fit", 0.7, w, reason="residential")
    return FactorContribution("purpose_fit", 0.5, w, reason="purpose_general")


def _score_financing_fit(
    payment_plan: Optional[dict],
    financing_preference: str,
    payment_method: str,
) -> FactorContribution:
    """Score financing (installments vs cash) fit."""
    w = FACTOR_WEIGHTS["financing_fit"]
    prefers_installments = any(
        x in (financing_preference or "").lower() + (payment_method or "").lower()
        for x in ["installment", "قسط", "اقساط", "financing", "ready"]
    )
    prefers_cash = any(x in (payment_method or "").lower() for x in ["cash", "نقد", "كاش"])

    if payment_plan and (payment_plan.get("installment_years_min") or payment_plan.get("installment_years_max")):
        has_installments = True
    else:
        has_installments = False

    if prefers_installments and has_installments:
        return FactorContribution("financing_fit", 1.0, w, reason="installment_available")
    if prefers_cash:
        return FactorContribution("financing_fit", 0.8, w, reason="cash_accepted")
    if not financing_preference and not payment_method:
        return FactorContribution("financing_fit", 0.5, w, reason="financing_unspecified")
    return FactorContribution("financing_fit", 0.4, w, reason="financing_unknown", tradeoff="confirm_payment_options")


def _score_stage_fit(
    delivery_horizon: Optional[str],
    urgency: str,
    journey_stage: str,
) -> FactorContribution:
    """Score stage/timeline fit (delivery vs urgency)."""
    w = FACTOR_WEIGHTS["stage_fit"]
    is_urgent = urgency and any(u in str(urgency).lower() for u in ["immediate", "فوراً", "soon", "قريب", "urgent"])
    wants_soon = is_urgent or journey_stage in ("shortlisting", "visit_planning", "negotiation", "booking")

    if not delivery_horizon:
        return FactorContribution("stage_fit", 0.5, w, reason="delivery_unknown")

    if delivery_horizon == "immediate" and wants_soon:
        return FactorContribution("stage_fit", 1.0, w, reason="ready_delivery")
    if wants_soon and delivery_horizon and delivery_horizon != "2026_plus":
        return FactorContribution("stage_fit", 0.8, w, reason="delivery_soon")
    return FactorContribution("stage_fit", 0.5, w, reason="delivery_standard")


def _score_family_lifestyle_fit(purpose_norm: str, market_context: Optional[dict]) -> FactorContribution:
    """Score family/lifestyle fit (from market context)."""
    w = FACTOR_WEIGHTS["family_lifestyle_fit"]
    if purpose_norm != "residence":
        return FactorContribution("family_lifestyle_fit", 0.5, w, reason="not_residential_focus")

    fam = market_context.get("family_suitability") if market_context else None
    if fam is True:
        return FactorContribution("family_lifestyle_fit", 1.0, w, reason="family_suitable")
    return FactorContribution("family_lifestyle_fit", 0.5, w, reason="family_unknown")


def match_projects(
    *,
    projects: list,
    budget_min: Optional[Decimal] = None,
    budget_max: Optional[Decimal] = None,
    location_preference: str = "",
    loc_search_terms: list[str] | None = None,
    property_type: str = "",
    bedroom_preference: Optional[int] = None,
    purpose: str = "",
    financing_preference: str = "",
    payment_method: str = "",
    urgency: str = "",
    journey_stage: str = "",
    historical_project_ids: list[int] | None = None,
    get_structured_facts=None,
    get_market_context=None,
) -> list[ProjectMatchResult]:
    """
    Score and rank projects. Returns list of ProjectMatchResult sorted by match_score.
    """
    loc_terms = loc_search_terms or []
    purpose_norm = (purpose or "").strip().lower()
    if "استثمار" in purpose_norm or "investment" in purpose_norm:
        purpose_norm = "investment"
    elif "سكن" in purpose_norm or "residence" in purpose_norm or "residential" in purpose_norm:
        purpose_norm = "residence"

    results: list[ProjectMatchResult] = []
    for p in projects:
        facts = get_structured_facts(p.id) if get_structured_facts else None
        has_verified = facts.has_verified_pricing if facts else False
        mc = get_market_context(p.id) if get_market_context else None
        market_ctx = mc.to_safe_dict() if mc and hasattr(mc, "to_safe_dict") else (mc if isinstance(mc, dict) else None)
        unit_cats = (facts.unit_categories or []) if facts else []

        contributions: list[FactorContribution] = []

        contributions.append(_score_budget_fit(p, budget_min, budget_max, has_verified))
        contributions.append(_score_location_fit(p, location_preference, loc_terms))
        contributions.append(_score_property_type_fit(p, property_type))
        contributions.append(_score_bedroom_fit(p, bedroom_preference, unit_cats))
        contributions.append(_score_purpose_fit(p, purpose_norm, market_ctx))

        pp = facts.payment_plan.value if facts and facts.payment_plan else None
        contributions.append(_score_financing_fit(pp, financing_preference, payment_method))

        delivery = market_ctx.get("delivery_horizon") if market_ctx else None
        contributions.append(_score_stage_fit(delivery, urgency, journey_stage))
        contributions.append(_score_family_lifestyle_fit(purpose_norm, market_ctx))

        # Historical boost
        if historical_project_ids and p.id in historical_project_ids:
            contributions.append(FactorContribution("historical", 1.0, 0.08, reason="returning_interest"))

        total = sum(fc.weighted_score for fc in contributions)
        top_reasons = [
            fc.reason for fc in sorted(contributions, key=lambda x: -x.weighted_score)
            if fc.reason and fc.score > 0.3
        ][:5]
        tradeoffs = [fc.tradeoff for fc in contributions if fc.tradeoff]

        rationale = _build_rationale(p, top_reasons, budget_min, budget_max, has_verified)

        results.append(ProjectMatchResult(
            project_id=p.id,
            project_name=p.name,
            project_name_ar=p.name_ar or "",
            location=p.location or "",
            price_min=float(p.price_min) if p.price_min else None,
            price_max=float(p.price_max) if p.price_max else None,
            match_score=min(1.0, total),
            top_reasons=top_reasons,
            tradeoffs=tradeoffs,
            factor_contributions=contributions,
            has_verified_pricing=has_verified,
            rationale=rationale,
        ))

    results.sort(key=lambda r: r.match_score, reverse=True)
    return results


def _build_rationale(p, reasons: list[str], budget_min, budget_max, has_verified: bool) -> str:
    """Build human-readable rationale."""
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
    if "residential" in reasons or "residential_family_friendly" in reasons:
        parts.append("Residential focus")
    return "; ".join(parts) if parts else "Recommended based on your criteria"
