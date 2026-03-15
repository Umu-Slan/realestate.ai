"""
Market/Context Intelligence Layer for AI sales system.
Provides structured project/area context: area attractiveness, family suitability,
investment suitability, price segment, delivery horizon, financing style, demand cues.
Honesty: Only returns data we have. No hallucination or inference.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProjectMarketContext:
    """
    Structured market context for a project. All fields optional.
    Only populated when we have supported data - never fabricated.
    """
    project_id: int = 0
    # Area/location intelligence
    area_attractiveness: Optional[str] = None  # e.g. high, medium, low
    # Suitability signals
    family_suitability: Optional[bool] = None
    investment_suitability: Optional[bool] = None
    # Price positioning
    price_segment: Optional[str] = None  # entry, mid, premium, luxury
    # Delivery timing (from structured facts when available)
    delivery_horizon: Optional[str] = None  # immediate, 2025, 2026_plus, unknown
    # Financing
    financing_style: Optional[str] = None  # installments, cash, flexible
    # Demand indicators
    demand_cues: Optional[list[str]] = None  # high_demand, limited_units, new_release, etc.
    # Metadata for honesty
    source: str = "manual"
    last_updated: Optional[str] = None

    def to_safe_dict(self) -> dict:
        """Return only fields with values - safe for agents, no empty placeholders."""
        out = {"project_id": self.project_id}
        if self.area_attractiveness is not None:
            out["area_attractiveness"] = self.area_attractiveness
        if self.family_suitability is not None:
            out["family_suitability"] = self.family_suitability
        if self.investment_suitability is not None:
            out["investment_suitability"] = self.investment_suitability
        if self.price_segment is not None:
            out["price_segment"] = self.price_segment
        if self.delivery_horizon is not None:
            out["delivery_horizon"] = self.delivery_horizon
        if self.financing_style is not None:
            out["financing_style"] = self.financing_style
        if self.demand_cues:
            out["demand_cues"] = list(self.demand_cues)
        if self.source:
            out["source"] = self.source
        return out

    @property
    def has_any(self) -> bool:
        """True if we have at least one supported fact."""
        return any([
            self.area_attractiveness,
            self.family_suitability is not None,
            self.investment_suitability is not None,
            self.price_segment,
            self.delivery_horizon,
            self.financing_style,
            self.demand_cues,
        ])


def get_project_market_context(project_id: int) -> Optional[ProjectMarketContext]:
    """
    Load market context for a project.
    Source: Project.metadata["market_context"] + derived from structured facts.
    Returns None if project not found. Only includes supported facts.
    """
    try:
        from knowledge.models import Project
        from knowledge.services.structured_facts import get_project_structured_facts
    except ImportError:
        return None

    p = Project.objects.filter(id=project_id, is_active=True).first()
    if not p:
        return None

    meta = getattr(p, "metadata", None) or {}
    mc = meta.get("market_context") or {}
    if not isinstance(mc, dict):
        mc = {}

    ctx = ProjectMarketContext(project_id=project_id)
    # Only set what we have
    if mc.get("area_attractiveness"):
        ctx.area_attractiveness = str(mc["area_attractiveness"]).strip().lower()[:50]
    if "family_suitability" in mc and mc["family_suitability"] is not None:
        ctx.family_suitability = bool(mc["family_suitability"])
    if "investment_suitability" in mc and mc["investment_suitability"] is not None:
        ctx.investment_suitability = bool(mc["investment_suitability"])
    if mc.get("price_segment"):
        ctx.price_segment = str(mc["price_segment"]).strip().lower()[:30]
    if mc.get("financing_style"):
        ctx.financing_style = str(mc["financing_style"]).strip().lower()[:50]
    if mc.get("demand_cues"):
        cues = mc["demand_cues"]
        if isinstance(cues, list):
            ctx.demand_cues = [str(c).strip().lower()[:30] for c in cues if c][:10]
        elif isinstance(cues, str):
            ctx.demand_cues = [cues.strip().lower()[:30]] if cues.strip() else []
    if mc.get("source"):
        ctx.source = str(mc["source"])[:20]
    if mc.get("last_updated"):
        ctx.last_updated = str(mc["last_updated"])[:50]

    # Delivery horizon: derive from structured facts when we have them
    facts = get_project_structured_facts(project_id)
    if facts and facts.delivery.value:
        dlv = facts.delivery.value
        end_date = dlv.get("expected_end_date") if isinstance(dlv, dict) else None
        if end_date:
            try:
                from datetime import date
                y = int(str(end_date)[:4])
                if y <= date.today().year:
                    ctx.delivery_horizon = "immediate"
                elif y <= date.today().year + 1:
                    ctx.delivery_horizon = str(date.today().year + 1)
                else:
                    ctx.delivery_horizon = "2026_plus"
            except (ValueError, TypeError):
                ctx.delivery_horizon = mc.get("delivery_horizon") or "unknown"
        elif not ctx.delivery_horizon:
            ctx.delivery_horizon = mc.get("delivery_horizon")
    elif mc.get("delivery_horizon") and not ctx.delivery_horizon:
        ctx.delivery_horizon = str(mc["delivery_horizon"]).strip().lower()[:20]

    # Price segment: derive from pricing when not in metadata
    if not ctx.price_segment and (p.price_min or p.price_max):
        try:
            pmax = float(p.price_max or p.price_min or 0)
            pmin = float(p.price_min or p.price_max or 0)
            avg = (pmax + pmin) / 2 if (pmax and pmin) else (pmax or pmin)
            if avg < 1_500_000:
                ctx.price_segment = "entry"
            elif avg < 3_000_000:
                ctx.price_segment = "mid"
            elif avg < 6_000_000:
                ctx.price_segment = "premium"
            else:
                ctx.price_segment = "luxury"
        except (TypeError, ValueError):
            pass

    return ctx if ctx.has_any or ctx.delivery_horizon or ctx.price_segment else None


def get_projects_market_context(project_ids: list[int]) -> dict[int, ProjectMarketContext]:
    """Batch load market context for multiple projects."""
    result = {}
    for pid in project_ids:
        ctx = get_project_market_context(pid)
        if ctx:
            result[pid] = ctx
    return result
