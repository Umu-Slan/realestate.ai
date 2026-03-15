"""
Structured fact layer: pricing, payment plan, availability, delivery, unit categories.
Source of truth for exact numbers. Response layer distinguishes verified vs unverified.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from django.utils import timezone

from knowledge.models import Project, ProjectPaymentPlan, ProjectDeliveryTimeline, ProjectUnitCategory


# Max days since last_verified_at to consider fact "verified" for safe display
VERIFIED_STALE_DAYS = 90


@dataclass
class VerifiedFact:
    """A structured fact with verification state."""
    value: any
    is_verified: bool
    last_verified_at: Optional[str] = None
    source: str = "manual"


@dataclass
class ProjectStructuredFacts:
    """All structured facts for a project, with verification flags."""
    project_id: int
    project_name: str
    project_name_ar: str = ""
    pricing: VerifiedFact = field(default_factory=lambda: VerifiedFact(None, False))
    payment_plan: VerifiedFact = field(default_factory=lambda: VerifiedFact(None, False))
    availability: VerifiedFact = field(default_factory=lambda: VerifiedFact(None, False))
    delivery: VerifiedFact = field(default_factory=lambda: VerifiedFact(None, False))
    unit_categories: list[dict] = field(default_factory=list)

    @property
    def has_verified_pricing(self) -> bool:
        return self.pricing.is_verified and self.pricing.value is not None

    @property
    def has_verified_availability(self) -> bool:
        return self.availability.is_verified and self.availability.value is not None

    @property
    def has_verified_payment_plan(self) -> bool:
        return self.payment_plan.is_verified and self.payment_plan.value is not None

    @property
    def has_verified_delivery(self) -> bool:
        return self.delivery.is_verified and self.delivery.value is not None


def _is_verified(last_verified_at, max_days: int = VERIFIED_STALE_DAYS) -> bool:
    """Fact is verified if last_verified_at is within max_days."""
    if not last_verified_at:
        return False
    delta = timezone.now() - last_verified_at
    return delta.days <= max_days


def get_project_structured_facts(project_id: int) -> Optional[ProjectStructuredFacts]:
    """
    Load all structured facts for a project with verification flags.
    Returns None if project not found.
    """
    p = Project.objects.filter(id=project_id, is_active=True).select_related().first()
    if not p:
        return None

    # Pricing (project-level)
    price_value = None
    if p.price_min is not None or p.price_max is not None:
        price_value = {
            "price_min": float(p.price_min) if p.price_min else None,
            "price_max": float(p.price_max) if p.price_max else None,
        }
    pricing_verified = _is_verified(p.last_verified_at)
    pricing = VerifiedFact(
        value=price_value,
        is_verified=pricing_verified,
        last_verified_at=p.last_verified_at.isoformat() if p.last_verified_at else None,
        source=getattr(p, "pricing_source", "manual") or "manual",
    )

    # Availability (project-level)
    avail_value = p.availability_status or None
    avail_verified = _is_verified(p.last_verified_at) and bool(avail_value)
    availability = VerifiedFact(
        value=avail_value,
        is_verified=avail_verified,
        last_verified_at=p.last_verified_at.isoformat() if p.last_verified_at else None,
        source=getattr(p, "availability_source", "manual") or "manual",
    )

    # Payment plan (from ProjectPaymentPlan)
    plans = list(ProjectPaymentPlan.objects.filter(project=p).order_by("id"))
    pp_value = None
    pp_verified = False
    pp_last = None
    pp_source = "manual"
    if plans:
        plan = plans[0]
        pp_value = {
            "down_payment_pct_min": float(plan.down_payment_pct_min) if plan.down_payment_pct_min else None,
            "down_payment_pct_max": float(plan.down_payment_pct_max) if plan.down_payment_pct_max else None,
            "installment_years_min": plan.installment_years_min,
            "installment_years_max": plan.installment_years_max,
        }
        pp_verified = _is_verified(plan.last_verified_at)
        pp_last = plan.last_verified_at.isoformat() if plan.last_verified_at else None
        pp_source = plan.source or "manual"
    payment_plan = VerifiedFact(value=pp_value, is_verified=pp_verified, last_verified_at=pp_last, source=pp_source)

    # Delivery (from ProjectDeliveryTimeline)
    deliveries = list(ProjectDeliveryTimeline.objects.filter(project=p).order_by("expected_start_date", "id"))
    dlv_value = None
    dlv_verified = False
    dlv_last = None
    dlv_source = "manual"
    if deliveries:
        d = deliveries[0]
        dlv_value = {
            "phase_name": d.phase_name,
            "phase_name_ar": d.phase_name_ar or "",
            "expected_start_date": d.expected_start_date.isoformat() if d.expected_start_date else None,
            "expected_end_date": d.expected_end_date.isoformat() if d.expected_end_date else None,
        }
        dlv_verified = _is_verified(d.last_verified_at)
        dlv_last = d.last_verified_at.isoformat() if d.last_verified_at else None
        dlv_source = d.source or "manual"
    delivery = VerifiedFact(value=dlv_value, is_verified=dlv_verified, last_verified_at=dlv_last, source=dlv_source)

    # Unit categories
    units = list(ProjectUnitCategory.objects.filter(project=p, is_active=True).order_by("category_name"))
    unit_cats = []
    for u in units:
        unit_cats.append({
            "category_name": u.category_name,
            "category_name_ar": u.category_name_ar or "",
            "price_min": float(u.price_min) if u.price_min else None,
            "price_max": float(u.price_max) if u.price_max else None,
            "quantity_available": u.quantity_available,
            "is_verified": _is_verified(u.last_verified_at),
            "last_verified_at": u.last_verified_at.isoformat() if u.last_verified_at else None,
            "source": u.source or "manual",
        })

    return ProjectStructuredFacts(
        project_id=p.id,
        project_name=p.name,
        project_name_ar=p.name_ar or "",
        pricing=pricing,
        payment_plan=payment_plan,
        availability=availability,
        delivery=delivery,
        unit_categories=unit_cats,
    )


def get_safe_language_for_fact(
    fact_type: str,
    has_value: bool,
    is_verified: bool,
    *,
    lang: str = "ar",
) -> str:
    """
    Return safe phrase for when exact numbers are unavailable or unverified.
    Use to avoid overclaiming.
    """
    if has_value and is_verified:
        return ""  # No disclaimer needed

    phrases_ar = {
        "pricing": "الأسعار الدقيقة تتطلب التأكد من فريق المبيعات.",
        "payment_plan": "تفاصيل الأقساط قد تختلف—يرجى التواصل مع الفريق للتأكيد.",
        "availability": "التوفر يتحدث يومياً—تواصل مع فريق المبيعات للحصول على آخر المستجدات.",
        "delivery": "جداول التسليم تختلف حسب الوحدة—فريقنا يوفر التفاصيل الدقيقة.",
        "unit_category": "تفاصيل الوحدات متوفرة لدى فريق المبيعات.",
    }
    phrases_en = {
        "pricing": "Exact pricing requires confirmation from our sales team.",
        "payment_plan": "Installment details may vary—please confirm with our team.",
        "availability": "Availability changes daily—contact sales for the latest.",
        "delivery": "Delivery schedules vary by unit—our team provides exact dates.",
        "unit_category": "Unit details are available from our sales team.",
    }
    phrases = phrases_ar if lang == "ar" else phrases_en
    return phrases.get(fact_type, phrases["pricing"])


def format_pricing_for_response(
    facts: ProjectStructuredFacts,
    *,
    lang: str = "ar",
    include_disclaimer: bool = True,
) -> str:
    """Format pricing for response text, with safe language when unverified."""
    if not facts.pricing.value:
        return get_safe_language_for_fact("pricing", False, False, lang=lang)

    p = facts.pricing.value
    pmin, pmax = p.get("price_min"), p.get("price_max")
    if pmin is not None and pmax is not None:
        if lang == "ar":
            s = f"نطاق أسعار تقريبي: {pmin:,.0f}–{pmax:,.0f} جنيه"
            if not facts.pricing.is_verified and include_disclaimer:
                s += " (يُرجع التأكد من فريق المبيعات)"
            return s
        s = f"Approx. price range: {pmin:,.0f}–{pmax:,.0f} EGP"
        if not facts.pricing.is_verified and include_disclaimer:
            s += " (confirm with sales)"
        return s

    single = pmin or pmax
    if single is not None:
        if lang == "ar":
            return f"من {single:,.0f} جنيه" + (" (يُرجع التأكد)" if not facts.pricing.is_verified and include_disclaimer else "")
        return f"From {single:,.0f} EGP" + (" (confirm with sales)" if not facts.pricing.is_verified and include_disclaimer else "")

    return get_safe_language_for_fact("pricing", False, False, lang=lang)
