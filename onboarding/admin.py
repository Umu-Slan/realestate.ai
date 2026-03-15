from django.contrib import admin
from .models import OnboardingBatch, OnboardingItem


class OnboardingItemInline(admin.TabularInline):
    model = OnboardingItem
    extra = 0
    readonly_fields = ("item_type", "source_name", "status", "error_message", "document_id", "project_id")


@admin.register(OnboardingBatch)
class OnboardingBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "batch_type", "status", "imported_count", "skipped_count", "failed_count", "created_at", "company")
    list_filter = ("batch_type", "status")
    search_fields = ("name", "created_by")
    inlines = [OnboardingItemInline]


@admin.register(OnboardingItem)
class OnboardingItemAdmin(admin.ModelAdmin):
    list_display = ("id", "batch", "item_type", "source_name", "status", "document_id", "project_id")
    list_filter = ("status", "item_type")
