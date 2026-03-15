from django.contrib import admin
from .models import CustomerIdentity, Customer, LeadProfile, LeadQualification, LeadScore, IdentityMergeCandidate, CustomerMemory


@admin.register(CustomerIdentity)
class CustomerIdentityAdmin(admin.ModelAdmin):
    list_display = ("external_id", "phone", "email", "name")
    search_fields = ("external_id", "phone", "email")
    list_filter = ()


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "identity", "customer_type", "source_channel", "is_active")
    list_filter = ("customer_type", "source_channel")
    search_fields = ("identity__external_id", "identity__phone", "identity__email")
    raw_id_fields = ("identity",)


@admin.register(LeadProfile)
class LeadProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "source_channel", "project_interest")
    list_filter = ("source_channel",)
    raw_id_fields = ("customer",)


@admin.register(LeadQualification)
class LeadQualificationAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "version", "budget_min", "budget_max", "property_type", "confidence")
    list_filter = ("confidence",)
    raw_id_fields = ("customer",)


@admin.register(IdentityMergeCandidate)
class IdentityMergeCandidateAdmin(admin.ModelAdmin):
    list_display = ("id", "identity_a", "identity_b", "confidence_score", "review_status")
    list_filter = ("review_status",)
    raw_id_fields = ("identity_a", "identity_b")


@admin.register(CustomerMemory)
class CustomerMemoryAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "memory_type", "source")
    list_filter = ("memory_type",)
    raw_id_fields = ("customer",)


@admin.register(LeadScore)
class LeadScoreAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "score", "temperature", "journey_stage", "rule_version")
    list_filter = ("temperature", "journey_stage")
    raw_id_fields = ("customer", "lead_profile")
