from django.contrib import admin
from .models import Recommendation


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "project", "rank", "created_at")
    list_filter = ("project",)
    raw_id_fields = ("customer", "conversation", "project")
