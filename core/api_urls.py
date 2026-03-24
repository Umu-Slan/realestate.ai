"""API route aggregation."""
from django.http import HttpResponse
from django.urls import path, include

def _ping(request):
    return HttpResponse("ok", content_type="text/plain")

urlpatterns = [
    path("ping/", _ping),
    path("channels/", include("channels.urls")),
    path("conversations/", include("conversations.urls")),
    path("leads/", include("leads.urls")),
    path("knowledge/", include("knowledge.urls")),
    path("crm/", include("crm.urls")),
    path("intelligence/", include("intelligence.urls")),
    path("engines/", include("engines.urls")),
    path("orchestration/", include("orchestration.urls")),
]
