"""Context processors for console templates."""
from django.conf import settings

from support.models import Escalation
from core.enums import EscalationStatus


def _skip_console_db(request) -> bool:
    host = (request.get_host() or "").lower()
    return ".vercel.app" in host or getattr(settings, "IS_VERCEL_DEPLOY", False)


def console_stats(request):
    """Provide stats, company name, and notifications for top bar."""
    base = {"stats": {"escalations_open": 0}, "company_name": None}
    if not request.user.is_authenticated:
        return base
    if _skip_console_db(request):
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
