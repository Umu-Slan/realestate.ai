"""
Support triage - deterministic category, severity, SLA, queue assignment.
Integrated with canonical AI pipeline.
"""
from dataclasses import dataclass
from typing import Optional

from core.enums import SupportCategory, SupportSeverity, SupportSLABucket


@dataclass
class SupportTriageResult:
    """Triage output for support case creation."""
    category: str
    severity: str
    sla_bucket: str
    assigned_queue: str
    escalation_trigger: str = ""


def triage_support(
    intent_primary: str,
    support_category: str = "",
    is_angry: bool = False,
    routing_route: str = "",
    routing_escalation_ready: bool = False,
) -> SupportTriageResult:
    """
    Deterministic triage: category, severity, SLA, queue.
    """
    primary = (intent_primary or "").lower()
    route = (routing_route or "").lower()

    # Category from intent or override
    category = _resolve_category(primary, support_category)

    # Severity: angry/complaint = high or critical
    if is_angry or "complaint" in primary or "شكوى" in primary:
        severity = SupportSeverity.HIGH.value if routing_escalation_ready else SupportSeverity.MEDIUM.value
    elif "contract" in primary or "عقد" in primary:
        severity = SupportSeverity.HIGH.value
    elif "maintenance" in primary or "صيانة" in primary:
        severity = SupportSeverity.MEDIUM.value
    else:
        severity = SupportSeverity.MEDIUM.value

    # SLA bucket
    sla = _sla_for_severity(severity, is_angry)

    # Queue
    queue = _queue_for_category(category, severity, route)

    # Escalation trigger
    esc_trigger = ""
    if is_angry:
        esc_trigger = "angry_customer"
    elif routing_escalation_ready:
        esc_trigger = "routing_escalation_ready"
    elif "contract" in primary:
        esc_trigger = "contract_legal"

    return SupportTriageResult(
        category=category,
        severity=severity,
        sla_bucket=sla,
        assigned_queue=queue,
        escalation_trigger=esc_trigger,
    )


def _resolve_category(primary: str, override: str) -> str:
    """Resolve support category from intent or override."""
    if override and override in [c[0] for c in SupportCategory.choices]:
        return override
    mapping = {
        "installment_inquiry": SupportCategory.INSTALLMENT.value,
        "contract_issue": SupportCategory.CONTRACT.value,
        "maintenance_issue": SupportCategory.MAINTENANCE.value,
        "delivery_inquiry": SupportCategory.DELIVERY.value,
        "support_complaint": SupportCategory.COMPLAINT.value,
        "general_support": SupportCategory.GENERAL_SUPPORT.value,
        "documentation_inquiry": SupportCategory.DOCUMENTATION.value,
        "payment_proof_inquiry": SupportCategory.PAYMENT_PROOF.value,
    }
    for k, v in mapping.items():
        if k in primary:
            return v
    if "تقسيط" in primary or "قسط" in primary or "installment" in primary:
        return SupportCategory.INSTALLMENT.value
    if "عقد" in primary or "contract" in primary:
        return SupportCategory.CONTRACT.value
    if "صيانة" in primary or "maintenance" in primary:
        return SupportCategory.MAINTENANCE.value
    if "تسليم" in primary or "ميناء" in primary or "delivery" in primary or "handover" in primary or "استلام" in primary:
        return SupportCategory.HANDOVER.value
    if "مستند" in primary or "إشعار" in primary or "documentation" in primary or "document" in primary:
        return SupportCategory.DOCUMENTATION.value
    if "إثبات" in primary or "دفع" in primary or "payment proof" in primary:
        return SupportCategory.PAYMENT_PROOF.value
    if "شكوى" in primary or "complaint" in primary:
        return SupportCategory.COMPLAINT.value
    return SupportCategory.GENERAL_SUPPORT.value


def _sla_for_severity(severity: str, is_angry: bool) -> str:
    if is_angry or severity == SupportSeverity.CRITICAL.value:
        return SupportSLABucket.P1.value
    if severity == SupportSeverity.HIGH.value:
        return SupportSLABucket.P2.value
    if severity == SupportSeverity.MEDIUM.value:
        return SupportSLABucket.P3.value
    return SupportSLABucket.P4.value


def _queue_for_category(category: str, severity: str, route: str) -> str:
    if "urgent" in route or "escalation" in route:
        return "urgent_support"
    if category == SupportCategory.CONTRACT.value:
        return "legal_review"
    if category in (SupportCategory.COMPLAINT.value, SupportCategory.MAINTENANCE.value):
        return "priority_support"
    if category == SupportCategory.INSTALLMENT.value:
        return "installment_queue"
    if category == SupportCategory.DOCUMENTATION.value:
        return "documentation_queue"
    return "general_support"
