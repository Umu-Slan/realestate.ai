from django.contrib import admin
from .models import (
    Project,
    RawDocument,
    IngestedDocument,
    DocumentVersion,
    DocumentChunk,
    ProjectDocument,
    ProjectPaymentPlan,
    ProjectDeliveryTimeline,
    ProjectUnitCategory,
)


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ("document", "version_number")
    raw_id_fields = ("document",)


class ProjectPaymentPlanInline(admin.TabularInline):
    model = ProjectPaymentPlan
    extra = 0
    fields = ("down_payment_pct_min", "down_payment_pct_max", "installment_years_min", "installment_years_max", "last_verified_at", "source")


class ProjectDeliveryTimelineInline(admin.TabularInline):
    model = ProjectDeliveryTimeline
    extra = 0
    fields = ("phase_name", "phase_name_ar", "expected_start_date", "expected_end_date", "last_verified_at", "source")


class ProjectUnitCategoryInline(admin.TabularInline):
    model = ProjectUnitCategory
    extra = 0
    fields = ("category_name", "category_name_ar", "price_min", "price_max", "quantity_available", "last_verified_at", "source", "is_active")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "price_min", "price_max", "availability_status", "last_verified_at", "pricing_source", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "name_ar", "location")
    inlines = [ProjectPaymentPlanInline, ProjectDeliveryTimelineInline, ProjectUnitCategoryInline]


@admin.register(RawDocument)
class RawDocumentAdmin(admin.ModelAdmin):
    list_display = ("file_name", "document_type", "source_name", "uploaded_at")
    list_filter = ("document_type",)


class DocumentChunkInline(admin.TabularInline):
    model = DocumentChunk
    extra = 0
    fields = ("chunk_index", "chunk_type", "section_title", "content")


@admin.register(IngestedDocument)
class IngestedDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "document_type", "source_name", "source_of_truth", "status", "verification_status", "language")
    list_filter = ("document_type", "status", "verification_status")
    raw_id_fields = ("raw_document", "project")
    inlines = [DocumentChunkInline]
    search_fields = ("title", "source_name")


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "chunk_index", "chunk_type", "section_title")
    list_filter = ("chunk_type",)
    raw_id_fields = ("document",)


@admin.register(ProjectDocument)
class ProjectDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "source_type", "status")
    list_filter = ("source_type", "status")
    raw_id_fields = ("project",)


@admin.register(ProjectPaymentPlan)
class ProjectPaymentPlanAdmin(admin.ModelAdmin):
    list_display = ("project", "down_payment_pct_min", "down_payment_pct_max", "installment_years_min", "installment_years_max", "last_verified_at", "source")
    list_filter = ("source",)
    raw_id_fields = ("project",)


@admin.register(ProjectDeliveryTimeline)
class ProjectDeliveryTimelineAdmin(admin.ModelAdmin):
    list_display = ("project", "phase_name", "expected_start_date", "expected_end_date", "last_verified_at", "source")
    list_filter = ("source",)
    raw_id_fields = ("project",)


@admin.register(ProjectUnitCategory)
class ProjectUnitCategoryAdmin(admin.ModelAdmin):
    list_display = ("project", "category_name", "price_min", "price_max", "quantity_available", "last_verified_at", "source", "is_active")
    list_filter = ("source", "is_active")
    raw_id_fields = ("project",)
