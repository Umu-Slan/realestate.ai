"""
Customer timeline: messages, CRM notes, activity logs, scores, support cases, recommendations, escalations.
"""
from django.db.models import Q

from leads.models import Customer
from crm.models import CRMRecord, CRMActivityLog


def build_timeline(customer: Customer, limit: int = 100) -> list[dict]:
    """
    Build unified timeline: messages, CRM notes, activity logs, lead temperatures, support, recommendations, escalations.
    """
    events = []

    # CRM records and activity logs
    for r in CRMRecord.objects.filter(linked_customer_id=customer.id).prefetch_related("activity_logs").order_by("-imported_at")[:20]:
        if r.notes:
            events.append({
                "type": "crm_note",
                "timestamp": r.imported_at,
                "content": r.notes[:500],
                "source": "crm_import",
                "metadata": {"crm_id": r.crm_id},
            })
        events.append({
            "type": "crm_record",
            "timestamp": r.imported_at,
            "content": f"Imported: {r.external_name or r.crm_id} - {r.historical_classification or r.status or r.lead_stage}",
            "source": "crm_import",
            "metadata": {"crm_id": r.crm_id, "owner": r.owner, "lead_stage": r.lead_stage},
        })
        for act in r.activity_logs.all()[:10]:
            events.append({
                "type": "crm_activity",
                "timestamp": act.created_at,
                "content": f"{act.get_activity_type_display()}: {act.content[:200] if act.content else '-'}",
                "source": "crm_sync",
                "metadata": {"activity_type": act.activity_type, "actor": act.actor},
            })

    # Lead scores (temperatures)
    for s in customer.scores.all().order_by("-created_at")[:10]:
        events.append({
            "type": "lead_score",
            "timestamp": s.created_at,
            "content": f"Score: {s.score} ({s.temperature})",
            "source": "scoring",
            "metadata": {"score": s.score, "tier": s.temperature},
        })

    # Support cases
    from support.models import SupportCase
    for sc in SupportCase.objects.filter(customer=customer).order_by("-created_at")[:10]:
        events.append({
            "type": "support_case",
            "timestamp": sc.created_at,
            "content": f"Support: {sc.category} - {sc.summary[:200] if sc.summary else 'No summary'}",
            "source": "support",
            "metadata": {"category": sc.category},
        })

    # Escalations
    for e in customer.escalations.all().order_by("-created_at")[:10]:
        events.append({
            "type": "escalation",
            "timestamp": e.created_at,
            "content": f"Escalation: {e.reason} - {e.status}",
            "source": "escalation",
            "metadata": {"reason": e.reason, "status": e.status},
        })

    # Recommendations
    for rec in customer.recommendations.all().order_by("-created_at")[:10]:
        events.append({
            "type": "recommendation",
            "timestamp": rec.created_at,
            "content": f"Recommended: {rec.project.name if rec.project else 'N/A'}",
            "source": "recommendations",
            "metadata": {"project_id": rec.project_id},
        })

    # Messages from conversations
    for conv in customer.conversations.all().order_by("-created_at")[:5]:
        for msg in conv.messages.all().order_by("-created_at")[:10]:
            events.append({
                "type": "message",
                "timestamp": msg.created_at,
                "content": msg.content[:300],
                "source": "conversation",
                "metadata": {"role": msg.role, "conversation_id": conv.id},
            })

    events.sort(key=lambda x: x["timestamp"], reverse=True)
    for e in events:
        e["timestamp"] = e["timestamp"].isoformat() if hasattr(e["timestamp"], "isoformat") else str(e["timestamp"])
    return events[:limit]
