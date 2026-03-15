"""
Retrieval planning - what to retrieve based on intent and qualification.
Deterministic, inspectable. Covers project docs, brochures, FAQs, structured facts,
location content, support docs, sales scripts.
"""
from dataclasses import dataclass
from typing import Optional


# Document types per source category (from core.enums.DocumentType)
DOC_PROJECT = ["project_pdf", "project_brochure", "project_details"]
DOC_BROCHURE = ["project_brochure"]
DOC_FAQ = ["faq"]
DOC_SALES = ["sales_script", "objection_handling"]
DOC_SUPPORT = ["support_sop", "legal_compliance"]
DOC_LOCATION = ["project_pdf", "project_brochure"]  # location is chunk_type


@dataclass
class RetrievalPlan:
    """What to retrieve and why."""
    query: str
    document_types: list[str] = ()
    chunk_types: list[str] = ()
    project_id: Optional[int] = None
    use_structured_pricing: bool = False
    use_structured_availability: bool = False
    limit: int = 10
    reason: str = ""


def _resolve_project_id(project_preference: str) -> Optional[int]:
    """Resolve project_id from project name/preference (substring match)."""
    if not (project_preference or "").strip():
        return None
    try:
        from knowledge.models import Project
        pref = (project_preference or "").strip().lower()
        for proj in Project.objects.filter(is_active=True).only("id", "name", "name_ar"):
            if pref in (proj.name or "").lower() or pref in (proj.name_ar or "").lower():
                return proj.id
    except Exception:
        pass
    return None


def plan_retrieval(
    *,
    message_text: str,
    intent_primary: str = "",
    project_preference: str = "",
    project_id: Optional[int] = None,
    is_support: bool = False,
) -> RetrievalPlan:
    """
    Plan retrieval based on intent and context.
    Maps to: project documents, brochures, FAQs, structured facts,
    location content, support docs, sales scripts.
    """
    intent = (intent_primary or "").lower()
    pid = project_id or _resolve_project_id(project_preference)

    # Support path -> support docs, FAQs, legal
    if is_support or "support" in intent or "complaint" in intent or "installment" in intent:
        return RetrievalPlan(
            query=message_text,
            document_types=DOC_SUPPORT + DOC_FAQ,
            chunk_types=["support_procedure", "faq_topic", "general"],
            project_id=pid,
            use_structured_pricing=False,
            use_structured_availability=False,
            limit=8,
            reason="Support intent - support SOPs and FAQs",
        )

    # Price inquiry -> structured pricing + payment plan chunks + brochures
    if "price" in intent or "pricing" in intent:
        return RetrievalPlan(
            query=message_text,
            document_types=DOC_PROJECT + DOC_FAQ + DOC_BROCHURE,
            chunk_types=["payment_plan", "project_section"],
            project_id=pid,
            use_structured_pricing=True,
            use_structured_availability=True,
            limit=8,
            reason="Price inquiry - prefer structured pricing",
        )

    # Brochure request -> brochures, project details
    if "brochure" in intent:
        return RetrievalPlan(
            query=message_text,
            document_types=DOC_BROCHURE + DOC_PROJECT,
            chunk_types=["project_section", "amenities"],
            project_id=pid,
            limit=8,
            reason="Brochure request",
        )

    # Location inquiry -> location chunks
    if "location" in intent:
        return RetrievalPlan(
            query=message_text,
            document_types=DOC_LOCATION,
            chunk_types=["location", "project_section"],
            project_id=pid,
            limit=6,
            reason="Location inquiry",
        )

    # Visit/schedule -> project details, sales scripts
    if "visit" in intent or "schedule" in intent:
        return RetrievalPlan(
            query=message_text,
            document_types=DOC_PROJECT + DOC_SALES,
            chunk_types=["project_section", "objection_topic"],
            project_id=pid,
            limit=8,
            reason="Visit planning - project + sales scripts",
        )

    # Project inquiry -> project docs, brochures, case studies, FAQs
    if "project" in intent:
        return RetrievalPlan(
            query=message_text,
            document_types=DOC_PROJECT + ["case_study"] + DOC_FAQ,
            chunk_types=["project_section", "amenities", "faq_topic"],
            project_id=pid,
            limit=10,
            reason="Project inquiry",
        )

    # General - broad retrieval, avoid over-filtering
    return RetrievalPlan(
        query=message_text,
        document_types=DOC_PROJECT + DOC_FAQ + DOC_BROCHURE,
        chunk_types=[],
        project_id=pid,
        limit=8,
        reason="General retrieval",
    )
