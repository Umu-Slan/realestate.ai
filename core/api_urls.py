"""API route aggregation."""
from django.urls import path, include

urlpatterns = [
    path("channels/", include("channels.urls")),
    path("conversations/", include("conversations.urls")),
    path("leads/", include("leads.urls")),
    path("knowledge/", include("knowledge.urls")),
    path("crm/", include("crm.urls")),
    path("intelligence/", include("intelligence.urls")),
    path("engines/", include("engines.urls")),
    path("orchestration/", include("orchestration.urls")),
]
