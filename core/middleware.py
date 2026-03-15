"""
Request lifecycle middleware - correlation IDs, logging context.
"""
import logging
import uuid
from typing import Callable

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)
CORRELATION_ID_ATTR = "correlation_id"


def get_correlation_id(request: HttpRequest) -> str:
    """Get or create correlation ID for request."""
    return getattr(request, CORRELATION_ID_ATTR, "") or ""


class CorrelationIdMiddleware:
    """
    Inject correlation_id into each request for tracing.
    Reads X-Correlation-Id header or generates new.
    Binds context for structured logging.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        cid = request.headers.get("X-Correlation-Id") or f"req_{uuid.uuid4().hex[:12]}"
        setattr(request, CORRELATION_ID_ATTR, cid)
        try:
            from core.observability import bind_context, clear_context
            bind_context(correlation_id=cid)
        except ImportError:
            pass
        try:
            response = self.get_response(request)
        finally:
            try:
                from core.observability import clear_context
                clear_context()
            except ImportError:
                pass
        response["X-Correlation-Id"] = cid
        return response
