"""
Explicit enums for domain model. PostgreSQL-friendly choices.
"""
from django.db import models


class CustomerType(models.TextChoices):
    """Customer classification in lifecycle."""
    NEW_LEAD = "new_lead", "New Lead"
    EXISTING_CUSTOMER = "existing_customer", "Existing Customer"
    RETURNING_LEAD = "returning_lead", "Returning Lead"
    BROKER = "broker", "Broker"
    SPAM = "spam", "Spam"
    SUPPORT_CUSTOMER = "support_customer", "Support Customer"


class LeadTemperature(models.TextChoices):
    """Lead qualification temperature for routing."""
    HOT = "hot", "Hot"
    WARM = "warm", "Warm"
    COLD = "cold", "Cold"
    NURTURE = "nurture", "Nurture"
    UNQUALIFIED = "unqualified", "Unqualified"
    SPAM = "spam", "Spam"


class BuyerJourneyStage(models.TextChoices):
    """Where the lead/customer is in the buying journey."""
    AWARENESS = "awareness", "Awareness"
    EXPLORATION = "exploration", "Exploration"
    CONSIDERATION = "consideration", "Consideration"
    SHORTLISTING = "shortlisting", "Shortlisting"
    VISIT_PLANNING = "visit_planning", "Visit Planning"
    NEGOTIATION = "negotiation", "Negotiation"
    BOOKING = "booking", "Booking"
    POST_BOOKING = "post_booking", "Post-Booking"
    SUPPORT_RETENTION = "support_retention", "Support/Retention"
    # Legacy
    DECISION = "decision", "Decision"
    PURCHASE = "purchase", "Purchase"
    POST_PURCHASE = "post_purchase", "Post-Purchase"
    UNKNOWN = "unknown", "Unknown"


class IntentType(models.TextChoices):
    """Primary intent classification (legacy, prefer IntentCategory)."""
    PROJECT_INQUIRY = "project_inquiry", "Project Inquiry"
    PRICING = "pricing", "Pricing"
    AVAILABILITY = "availability", "Availability"
    SCHEDULE_VISIT = "schedule_visit", "Schedule Visit"
    SUPPORT = "support", "Support"
    GENERAL_INFO = "general_info", "General Info"
    SPAM = "spam", "Spam"
    OTHER = "other", "Other"


class IntentCategory(models.TextChoices):
    """Conversation intelligence intent - multi-label capable."""
    PROPERTY_PURCHASE = "property_purchase", "Property Purchase Inquiry"
    INVESTMENT_INQUIRY = "investment_inquiry", "Investment Inquiry"
    PROJECT_INQUIRY = "project_inquiry", "Project Inquiry"
    PRICE_INQUIRY = "price_inquiry", "Price Inquiry"
    LOCATION_INQUIRY = "location_inquiry", "Location Inquiry"
    INSTALLMENT_INQUIRY = "installment_inquiry", "Installment Inquiry"
    BROCHURE_REQUEST = "brochure_request", "Brochure Request"
    SCHEDULE_VISIT = "schedule_visit", "Schedule Visit"
    SUPPORT_COMPLAINT = "support_complaint", "Support Complaint"
    CONTRACT_ISSUE = "contract_issue", "Contract Issue"
    MAINTENANCE_ISSUE = "maintenance_issue", "Maintenance Issue"
    DELIVERY_INQUIRY = "delivery_inquiry", "Delivery Inquiry"
    DOCUMENTATION_INQUIRY = "documentation_inquiry", "Documentation Inquiry"
    PAYMENT_PROOF_INQUIRY = "payment_proof_inquiry", "Payment Proof Inquiry"
    GENERAL_SUPPORT = "general_support", "General Support"
    SPAM = "spam", "Spam"
    BROKER_INQUIRY = "broker_inquiry", "Broker Inquiry"
    OTHER = "other", "Other"


class SupportCategory(models.TextChoices):
    """Support case categorization - existing customers."""
    INSTALLMENT = "installment", "Installment"
    CONTRACT = "contract", "Contract"
    MAINTENANCE = "maintenance", "Maintenance"
    DELIVERY = "delivery", "Delivery"
    HANDOVER = "handover", "Handover"
    COMPLAINT = "complaint", "Complaint"
    DOCUMENTATION = "documentation", "Documentation"
    GENERAL_SUPPORT = "general_support", "General Support"
    AFTER_SALE = "after_sale", "After-Sale"
    WARRANTY = "warranty", "Warranty"
    PAYMENT = "payment", "Payment"
    PAYMENT_PROOF = "payment_proof", "Payment Proof"
    GENERAL = "general", "General"


class SupportSeverity(models.TextChoices):
    """Support case severity."""
    CRITICAL = "critical", "Critical"
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class SupportSLABucket(models.TextChoices):
    """SLA response bucket."""
    P1 = "p1", "P1 (2h)"
    P2 = "p2", "P2 (8h)"
    P3 = "p3", "P3 (24h)"
    P4 = "p4", "P4 (72h)"


class SupportStatus(models.TextChoices):
    """Support case status."""
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In Progress"
    PENDING_CUSTOMER = "pending_customer", "Pending Customer"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"


class EscalationReason(models.TextChoices):
    """Reasons for human escalation - enterprise-grade triggers."""
    ANGRY_CUSTOMER = "angry_customer", "Angry Customer"
    LEGAL_CONTRACT = "legal_contract", "Legal/Contract Issue"
    PRICING_EXCEPTION = "pricing_exception", "Pricing Exception"
    UNAVAILABLE_CRITICAL_INFO = "unavailable_critical_info", "Unavailable Critical Info"
    LOW_CONFIDENCE = "low_confidence", "Low Confidence"
    VIP_LEAD = "vip_lead", "VIP Lead"
    SEVERE_COMPLAINT = "severe_complaint", "Severe Complaint"
    NEGOTIATION_BEYOND_POLICY = "negotiation_beyond_policy", "Negotiation Beyond Policy"
    # Legacy / aliases
    PRICING_REQUEST = "pricing_request", "Pricing Request"
    COMPLEX_INQUIRY = "complex_inquiry", "Complex Inquiry"
    COMPLAINT = "complaint", "Complaint"
    URGENT = "urgent", "Urgent"
    VIP = "vip", "VIP"
    MANUAL = "manual", "Manual"


class SourceChannel(models.TextChoices):
    """Where the interaction originated."""
    WEB = "web", "Web"
    WHATSAPP = "whatsapp", "WhatsApp"
    INSTAGRAM = "instagram", "Instagram"
    PHONE = "phone", "Phone"
    EMAIL = "email", "Email"
    CRM_IMPORT = "crm_import", "CRM Import"
    API = "api", "API"
    DEMO = "demo", "Demo"


class ConfidenceLevel(models.TextChoices):
    """Confidence in classification/extraction."""
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"
    UNKNOWN = "unknown", "Unknown"


class EscalationStatus(models.TextChoices):
    """Escalation workflow status."""
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In Progress"
    RESOLVED = "resolved", "Resolved"
    CANCELLED = "cancelled", "Cancelled"


class ConversationStatus(models.TextChoices):
    """Conversation state."""
    ACTIVE = "active", "Active"
    CLOSED = "closed", "Closed"
    ARCHIVED = "archived", "Archived"


class DocumentSourceType(models.TextChoices):
    """Knowledge document source type."""
    PROJECT = "project", "Project"
    CASE_STUDY = "case_study", "Case Study"
    ACHIEVEMENT = "achievement", "Achievement"
    CREDIBILITY = "credibility", "Credibility"
    DELIVERY = "delivery", "Delivery"
    OTHER = "other", "Other"


class AuditAction(models.TextChoices):
    """Audit event actions."""
    MESSAGE_PROCESSED = "message_processed", "Message Processed"
    LEAD_SCORED = "lead_scored", "Lead Scored"
    ORCHESTRATION_STARTED = "orchestration_started", "Orchestration Started"
    ORCHESTRATION_STAGE = "orchestration_stage", "Orchestration Stage"
    ORCHESTRATION_COMPLETED = "orchestration_completed", "Orchestration Completed"
    ORCHESTRATION_FAILED = "orchestration_failed", "Orchestration Failed"
    ESCALATION_CREATED = "escalation_created", "Escalation Created"
    ESCALATION_RESOLVED = "escalation_resolved", "Escalation Resolved"
    CORRECTION_APPLIED = "correction_applied", "Correction Applied"
    CRM_IMPORTED = "crm_imported", "CRM Imported"
    KNOWLEDGE_INGESTED = "knowledge_ingested", "Knowledge Ingested"
    KNOWLEDGE_REINDEXED = "knowledge_reindexed", "Knowledge Reindexed"
    KNOWLEDGE_VERIFIED = "knowledge_verified", "Knowledge Verified"
    IDENTITY_AUTO_MERGED = "identity_auto_merged", "Identity Auto Merged"
    IDENTITY_MANUAL_MERGED = "identity_manual_merged", "Identity Manual Merged"
    IDENTITY_CONFLICT = "identity_conflict", "Identity Conflict"
    PROFILE_UPDATED = "profile_updated", "Profile Updated"


class CorrectionIssueType(models.TextChoices):
    """Issue type for human corrections - reusable for prompt/rule tuning."""
    ACCURACY = "accuracy", "Accuracy"
    TONE = "tone", "Tone"
    HALLUCINATION = "hallucination", "Hallucination"
    INCOMPLETE = "incomplete", "Incomplete"
    WRONG_INTENT = "wrong_intent", "Wrong Intent"
    OFF_TOPIC = "off_topic", "Off Topic"
    COMPLETENESS = "completeness", "Completeness"
    # Sales-specific
    STRATEGY_MISMATCH = "strategy_mismatch", "Strategy Mismatch"
    OBJECTION_HANDLING = "objection_handling", "Objection Handling"
    RECOMMENDATION_QUALITY = "recommendation_quality", "Recommendation Quality"
    STAGE_DECISION = "stage_decision", "Stage Decision"
    OTHER = "other", "Other"


class ResponseQuality(models.TextChoices):
    """3-way rating for AI response quality."""
    GOOD = "good", "Good"
    WEAK = "weak", "Weak"
    WRONG = "wrong", "Wrong"


class MergeReviewStatus(models.TextChoices):
    """Identity merge review status."""
    PENDING = "pending", "Pending"
    AUTO_APPROVED = "auto_approved", "Auto Approved"
    MANUAL_APPROVED = "manual_approved", "Manual Approved"
    REJECTED = "rejected", "Rejected"


class MemoryType(models.TextChoices):
    """Unified customer memory type."""
    PREFERENCE = "preference", "Preference"
    PAST_INTENT = "past_intent", "Past Intent"
    PAST_PROJECT = "past_project", "Past Project"
    OLD_OBJECTION = "old_objection", "Old Objection"
    PRIOR_CLASSIFICATION = "prior_classification", "Prior Classification"
    SUPPORT_HISTORY = "support_history", "Support History"
    CRM_IMPORTED = "crm_imported", "CRM Imported"
    IDENTITY_AUTO_MERGED = "identity_auto_merged", "Identity Auto Merged"
    IDENTITY_MANUAL_MERGED = "identity_manual_merged", "Identity Manual Merged"
    IDENTITY_CONFLICT = "identity_conflict", "Identity Conflict"
    PROFILE_UPDATED = "profile_updated", "Profile Updated"


class DocumentType(models.TextChoices):
    """Knowledge document type – production categories for real estate AI."""
    PROJECT_BROCHURE = "project_brochure", "Project Brochure"
    PROJECT_DETAILS = "project_details", "Project Details"
    PROJECT_PDF = "project_pdf", "Project PDF"
    PAYMENT_PLAN = "payment_plan", "Payment Plan"
    FAQ = "faq", "FAQ"
    SALES_SCRIPT = "sales_script", "Sales Script"
    SUPPORT_SOP = "support_sop", "Support SOP"
    OBJECTION_HANDLING = "objection_handling", "Objection Handling"
    COMPANY_ACHIEVEMENT = "company_achievement", "Company Achievement"
    LEGAL_COMPLIANCE = "legal_compliance", "Legal/Compliance"
    ACHIEVEMENT = "achievement", "Achievement"
    CASE_STUDY = "case_study", "Case Study"
    DELIVERY_HISTORY = "delivery_history", "Delivery History"
    PROJECT_METADATA_CSV = "project_metadata_csv", "Project Metadata CSV"
    CREDIBILITY = "credibility", "Credibility"
    OTHER = "other", "Other"


class AccessLevel(models.TextChoices):
    """Document access level for retrieval and visibility."""
    PUBLIC = "public", "Public"
    INTERNAL = "internal", "Internal"
    RESTRICTED = "restricted", "Restricted"


class FactSource(models.TextChoices):
    """Origin of structured facts - for future ERP/CRM/inventory integration."""
    MANUAL = "manual", "Manual"
    CSV_IMPORT = "csv_import", "CSV Import"
    ERP = "erp", "ERP"
    CRM = "crm", "CRM"


class VerificationStatus(models.TextChoices):
    """Document verification status."""
    UNVERIFIED = "unverified", "Unverified"
    PENDING = "pending", "Pending"
    VERIFIED = "verified", "Verified"
    STALE = "stale", "Stale"
    SUPERSEDED = "superseded", "Superseded"


class ChunkType(models.TextChoices):
    """Business-aware chunk types for Egyptian real estate."""
    PROJECT_SECTION = "project_section", "Project Section"
    PAYMENT_PLAN = "payment_plan", "Payment Plan"
    AMENITIES = "amenities", "Amenities"
    LOCATION = "location", "Location"
    COMPANY_ACHIEVEMENT = "company_achievement", "Company Achievement"
    DELIVERY_PROOF = "delivery_proof", "Delivery Proof"
    FAQ_TOPIC = "faq_topic", "FAQ Topic"
    OBJECTION_TOPIC = "objection_topic", "Objection Topic"
    SUPPORT_PROCEDURE = "support_procedure", "Support Procedure"
    GENERAL = "general", "General"


class ContentLanguage(models.TextChoices):
    """Content language."""
    AR = "ar", "Arabic"
    EN = "en", "English"
    AR_EN = "ar_en", "Arabic & English"
    UNKNOWN = "unknown", "Unknown"
