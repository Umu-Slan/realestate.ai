"""Context processors for console templates."""
import os

from support.models import Escalation
from core.enums import EscalationStatus


def console_stats(request):
    """Provide stats, company name, and notifications for top bar."""
    base = {"stats": {"escalations_open": 0}, "company_name": None}
    if not request.user.is_authenticated:
        return base
    # Vercel: avoid extra Neon queries on every console page (hangs / 500)
    if os.environ.get("VERCEL") == "1":
        return base
    try:
        from companies.services import get_default_company
        company = get_default_company()
        return {
            "stats": {"escalations_open": Escalation.objects.filter(status=EscalationStatus.OPEN).count()},
            "company_name": company.name if company else None,
        }
    except Exception:
        return base
