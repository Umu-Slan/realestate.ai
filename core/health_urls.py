"""Health check URL routes."""
from django.urls import path
from .health_views import (
    health_db,
    health_redis,
    health_celery,
    health_vector,
    health_model,
    health_all,
    health_ready,
)

urlpatterns = [
    path("db/", health_db),
    path("redis/", health_redis),
    path("celery/", health_celery),
    path("vector/", health_vector),
    path("model/", health_model),
    path("ready/", health_ready),
    path("", health_all),
]
