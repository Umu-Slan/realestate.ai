"""Operator console views."""
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import admin_required

from conversations.models import Conversation, Message
from leads.models import Customer, CustomerIdentity, LeadScore, LeadQualification, LeadProfile
from leads.services.timeline import build_timeline
from support.models import SupportCase, Escalation
from recommendations.models import Recommendation
from knowledge.models import IngestedDocument, DocumentChunk, Project, ProjectPaymentPlan, ProjectDeliveryTimeline, ProjectUnitCategory
from knowledge.retrieval import RetrievalPolicy, retrieve_by_query, get_safe_fallback_note
from knowledge.services.structured_facts import get_project_structured_facts
from audit.models import ActionLog, HumanCorrection
from crm.models import CRMRecord
from core.enums import EscalationStatus, CorrectionIssueType


def _stats():
    return {
        "conversations": Conversation.objects.count(),
        "customers": Customer.objects.filter(is_active=True).count(),
        "support_cases": SupportCase.objects.count(),
        "escalations_open": Escalation.objects.filter(status=EscalationStatus.OPEN).count(),
    }


def notifications(request):
    """Operator notifications: recent escalations, support cases, new leads."""
    from datetime import timedelta
    from django.utils import timezone
    since = timezone.now() - timedelta(days=7)
    escalations = Escalation.objects.filter(created_at__gte=since).select_related("conversation__customer__identity")[:20]
    support_cases = SupportCase.objects.filter(created_at__gte=since).select_related("customer__identity")[:15]
    new_leads = Customer.objects.filter(
        is_active=True,
        customer_type__in=("new_lead", "returning_lead"),
        created_at__gte=since,
    ).select_related("identity")[:15]
    return render(request, "console/notifications.html", {
        "escalations": escalations,
        "support_cases": support_cases,
        "new_leads": new_leads,
        "nav_section": "dashboard",
    })


def search(request):
    """Global search across customers, conversations, support cases, projects."""
    q = (request.GET.get("q") or "").strip()[:100]
    results = {"customers": [], "conversations": [], "support_cases": [], "projects": [], "documents": []}
    if q:
        from django.db.models import Q, Count
        results["customers"] = list(
            Customer.objects.filter(is_active=True)
            .filter(
                Q(identity__name__icontains=q)
                | Q(identity__email__icontains=q)
                | Q(identity__external_id__icontains=q)
            )
            .select_related("identity")[:10]
        )
        conv_qs = Conversation.objects.select_related("customer__identity").annotate(message_count=Count("messages"))
        if q.isdigit():
            conv_qs = conv_qs.filter(id=int(q))[:10]
        else:
            conv_qs = conv_qs.filter(
                Q(customer__identity__name__icontains=q)
                | Q(customer__identity__external_id__icontains=q)
            )[:10]
        results["conversations"] = list(conv_qs)
        results["support_cases"] = list(
            SupportCase.objects.filter(
                Q(summary__icontains=q) | Q(category__icontains=q)
            ).select_related("customer__identity")[:10]
        )
        results["projects"] = list(
            Project.objects.filter(is_active=True)
            .filter(
                Q(name__icontains=q) | Q(name_ar__icontains=q) | Q(location__icontains=q)
            )[:10]
        )
        results["documents"] = list(
            IngestedDocument.objects.filter(title__icontains=q)[:10]
        )
    return render(request, "console/search.html", {
        "q": q,
        "results": results,
        "nav_section": "dashboard",
    })


def _build_activity_timeline(since, limit=15):
    """Build unified activity timeline from escalations, support, conversations, recommendations."""
    from django.urls import reverse
    from django.utils.timesince import timesince
    from django.utils.translation import gettext as _
    events = []
    for e in Escalation.objects.filter(created_at__gte=since).select_related("customer__identity")[:10]:
        name = (e.customer.identity.name or e.customer.identity.external_id or f"#{e.customer_id}") if e.customer.identity else f"Customer #{e.customer_id}"
        events.append({
            "ts": e.created_at,
            "title": str(e.reason) if hasattr(e.reason, "upper") else str(e.reason) if e.reason else _("Escalation"),
            "description": name,
            "url": reverse("console:escalation_detail", args=[e.id]),
            "color": "red",
        })
    for sc in SupportCase.objects.filter(created_at__gte=since).select_related("customer__identity")[:10]:
        name = (sc.customer.identity.name or sc.customer.identity.external_id or f"#{sc.customer_id}") if (sc.customer and sc.customer.identity) else f"Case #{sc.id}"
        events.append({
            "ts": sc.created_at,
            "title": _("Support case") + f" #{sc.id}",
            "description": f"{sc.category} · {name}",
            "url": reverse("console:support_case_detail", args=[sc.id]),
            "color": "amber",
        })
    for c in Conversation.objects.filter(created_at__gte=since).select_related("customer__identity").order_by("-created_at")[:10]:
        name = (c.customer.identity.name or c.customer.identity.external_id or f"Customer #{c.customer_id}") if c.customer.identity else f"Customer #{c.customer_id}"
        events.append({
            "ts": c.created_at,
            "title": f"{name} " + _("started conversation"),
            "description": c.channel,
            "url": reverse("console:conversation_detail", args=[c.id]),
            "color": "teal",
        })
    for r in Recommendation.objects.filter(created_at__gte=since).select_related("customer__identity", "project")[:10]:
        cust_name = (r.customer.identity.name or r.customer.identity.external_id or f"#{r.customer_id}") if r.customer and r.customer.identity else f"Customer #{r.customer_id}"
        proj = r.project.name if r.project else "—"
        events.append({
            "ts": r.created_at,
            "title": _("AI recommended") + f" {proj}",
            "description": cust_name,
            "url": reverse("console:recommendations"),
            "color": "blue",
        })
    events.sort(key=lambda x: x["ts"], reverse=True)
    for e in events[:limit]:
        e["timestamp"] = timesince(e["ts"]) + " " + _("ago")
    return events[:limit]


def dashboard(request):
    from console.services.analytics import get_dashboard_metrics
    from django.utils import timezone
    from datetime import timedelta
    days = int(request.GET.get("days", "30"))
    metrics = get_dashboard_metrics(days=days)
    since = timezone.now() - timedelta(days=days)
    recent_escalations = Escalation.objects.filter(created_at__gte=since).select_related("conversation__customer__identity")[:5]
    recent_support = SupportCase.objects.filter(created_at__gte=since).select_related("customer__identity")[:5]
    activity_events = _build_activity_timeline(since)
    return render(request, "console/dashboard.html", {
        "stats": _stats(),
        "metrics": metrics,
        "recent_escalations": recent_escalations,
        "recent_support": recent_support,
        "activity_events": activity_events,
        "nav_section": "dashboard",
    })


def analytics(request):
    """Analytics views: top intents, support categories, objections, avg score by source, escalation reasons."""
    from console.services.analytics import (
        get_top_intents,
        get_top_support_categories,
        get_top_objections,
        get_average_score_by_source,
        get_escalation_reasons,
    )
    days = int(request.GET.get("days", "30"))
    return render(request, "console/analytics.html", {
        "top_intents": get_top_intents(limit=10, days=days),
        "top_support_categories": get_top_support_categories(limit=10, days=days),
        "top_objections": get_top_objections(limit=10, days=days),
        "avg_score_by_source": get_average_score_by_source(days=days),
        "escalation_reasons": get_escalation_reasons(days=days),
        "days": days,
        "nav_section": "analytics",
    })


def conversations(request):
    from django.db.models import Count, Q
    convs = (
        Conversation.objects
        .select_related("customer", "customer__identity")
        .annotate(message_count=Count("messages"))
        .order_by("-created_at")
    )
    q = (request.GET.get("q") or "").strip()[:50]
    if q:
        if q.isdigit():
            convs = convs.filter(id=int(q))[:50]
        else:
            convs = convs.filter(
                Q(customer__identity__name__icontains=q)
                | Q(customer__identity__external_id__icontains=q)
            )[:50]
    else:
        convs = convs[:50]
    return render(request, "console/conversations.html", {
        "conversations": list(convs),
        "search_q": q,
        "nav_section": "conversations",
        "stats": _stats(),
    })


def conversation_detail(request, pk):
    from django.db.models import Count
    from console.models import OrchestrationSnapshot, ResponseFeedback
    from console.services.operator_assist import build_operator_assist

    conv = get_object_or_404(Conversation.objects.select_related("customer__identity"), pk=pk)
    q = (request.GET.get("q") or "").strip()[:50]
    conv_list = (
        Conversation.objects.select_related("customer", "customer__identity")
        .annotate(message_count=Count("messages"))
        .order_by("-created_at")
    )
    if q:
        if q.isdigit():
            conv_list = conv_list.filter(id=int(q))[:30]
        else:
            from django.db.models import Q
            conv_list = conv_list.filter(
                Q(customer__identity__name__icontains=q)
                | Q(customer__identity__external_id__icontains=q)
            )[:30]
    else:
        conv_list = conv_list[:30]
    conv_list = list(conv_list)
    # Ensure current conversation is in list when filtered
    if conv_list and conv.id not in [c.id for c in conv_list]:
        conv_list = [conv] + [c for c in conv_list if c.id != conv.id][:29]
    messages = list(conv.messages.all().order_by("created_at"))
    snapshot_map = {s.message_id: s for s in OrchestrationSnapshot.objects.filter(conversation=conv).select_related("message") if s.message_id is not None}
    msg_ids = [m.id for m in messages]
    feedback_list = ResponseFeedback.objects.filter(message_id__in=msg_ids).order_by("-created_at")
    feedback_map = {}
    for f in feedback_list:
        if f.message_id not in feedback_map:
            feedback_map[f.message_id] = f
    message_snapshots = [(m, snapshot_map.get(m.id), feedback_map.get(m.id)) for m in messages]
    latest_snapshot = OrchestrationSnapshot.objects.filter(conversation=conv).order_by("-created_at").first()
    latest_score = conv.customer.scores.first()
    latest_qual = conv.customer.qualifications.first()
    logs = ActionLog.objects.filter(subject_type="conversation", subject_id=str(conv.id)).order_by("-created_at")[:20]
    conv_escalations = Escalation.objects.filter(conversation=conv).order_by("-created_at")[:10]
    conv_support_cases = SupportCase.objects.filter(conversation=conv).order_by("-created_at")[:10]
    crm_record = CRMRecord.objects.filter(linked_customer_id=conv.customer_id).order_by("-imported_at").first()
    cust_recommendations = conv.customer.recommendations.select_related("project").order_by("-created_at")[:5]
    from core.enums import CorrectionIssueType

    operator_assist = build_operator_assist(
        conversation=conv,
        latest_snapshot=latest_snapshot,
        latest_score=latest_score,
        latest_qual=latest_qual,
        messages=messages,
        recommendations=cust_recommendations,
        escalations=conv_escalations,
        support_cases=conv_support_cases,
    )

    return render(request, "console/conversation_detail.html", {
        "conversation": conv,
        "conversations": conv_list,
        "message_snapshots": message_snapshots,
        "latest_snapshot": latest_snapshot,
        "latest_score": latest_score,
        "latest_qual": latest_qual,
        "operator_assist": operator_assist,
        "action_logs": logs,
        "escalations": conv_escalations,
        "support_cases": conv_support_cases,
        "cust_recommendations": cust_recommendations,
        "crm_record": crm_record,
        "issue_type_choices": CorrectionIssueType.choices,
        "can_submit_correction": _can_submit_correction(request),
        "search_q": q,
        "nav_section": "conversations",
    })


def customers(request):
    custs = Customer.objects.select_related("identity").filter(is_active=True).order_by("-created_at")
    temp = (request.GET.get("temp") or "").strip().lower()
    if temp in ("hot", "warm", "cold", "nurture"):
        custs = custs.filter(
            id__in=LeadScore.objects.filter(temperature=temp).values_list("customer_id", flat=True)
        )
    return render(request, "console/customers.html", {
        "customers": list(custs[:50]),
        "filter_temp": temp,
        "nav_section": "customers",
    })


def customer_detail(request, pk):
    cust = get_object_or_404(Customer.objects.select_related("identity"), pk=pk)
    timeline = build_timeline(cust, limit=50)
    crm_records = list(CRMRecord.objects.filter(linked_customer_id=cust.id).prefetch_related("activity_logs").order_by("-imported_at")[:20])
    scores = cust.scores.all().order_by("-created_at")[:10]
    qualifications = cust.qualifications.all().order_by("-created_at")[:10]
    convs = cust.conversations.all().order_by("-created_at")[:20]
    support_cases = SupportCase.objects.filter(customer=cust).order_by("-created_at")[:10]
    cust_escalations = Escalation.objects.filter(customer=cust).order_by("-created_at")[:10]
    recommendations = cust.recommendations.select_related("project").order_by("-created_at")[:10]
    project_interests = list(cust.lead_profiles.values_list("project_interest", flat=True))
    project_interests = [p for p in project_interests if p]
    cust_corrections = HumanCorrection.objects.filter(customer=cust).select_related("message", "conversation").order_by("-id")[:20]
    cust_feedback = []
    if hasattr(cust, "response_feedback"):
        cust_feedback = list(cust.response_feedback.select_related("message", "conversation").order_by("-created_at")[:20])
    return render(request, "console/customer_detail.html", {
        "customer": cust,
        "timeline": timeline,
        "crm_records": crm_records,
        "scores": scores,
        "qualifications": qualifications,
        "conversations": convs,
        "support_cases": support_cases,
        "escalations": cust_escalations,
        "recommendations": recommendations,
        "project_interests": project_interests,
        "corrections": cust_corrections,
        "feedback": cust_feedback,
        "nav_section": "customers",
    })


def support_cases(request):
    qs = (
        SupportCase.objects
        .select_related("customer", "customer__identity", "conversation", "escalation")
        .order_by("-created_at")
    )
    cat = (request.GET.get("category") or "").strip()
    sev = (request.GET.get("severity") or "").strip()
    if cat:
        qs = qs.filter(category__icontains=cat)
    if sev:
        qs = qs.filter(severity=sev)
    cases = list(qs[:100])
    # Kanban columns: open, in_progress, resolved, escalated
    columns = {"open": [], "in_progress": [], "resolved": [], "escalated": []}
    for c in cases:
        if c.escalation_id:
            columns["escalated"].append(c)
        elif c.status == "open":
            columns["open"].append(c)
        elif c.status == "in_progress":
            columns["in_progress"].append(c)
        else:
            columns["resolved"].append(c)
    return render(request, "console/support_cases.html", {
        "cases": cases,
        "columns": columns,
        "stats": _stats(),
        "filter_category": cat,
        "filter_severity": sev,
        "nav_section": "support",
    })


def support_case_detail(request, pk):
    import json
    case = get_object_or_404(
        SupportCase.objects.select_related("customer", "customer__identity", "conversation", "escalation"),
        pk=pk,
    )
    metadata_json = json.dumps(case.metadata or {}, indent=2)
    return render(request, "console/support_case_detail.html", {
        "case": case,
        "metadata_json": metadata_json,
        "nav_section": "support",
    })


def escalations(request):
    escal = (
        Escalation.objects
        .select_related("customer", "customer__identity", "conversation")
        .prefetch_related("support_cases")
        .order_by("-created_at")[:100]
    )
    return render(request, "console/escalations.html", {
        "escalations": escal,
        "stats": _stats(),
        "nav_section": "escalations",
    })


def escalation_detail(request, pk):
    import json
    esc = get_object_or_404(
        Escalation.objects.select_related("customer", "customer__identity", "conversation").prefetch_related("support_cases"),
        pk=pk,
    )
    handoff_json = json.dumps(esc.handoff_summary or {}, indent=2, default=str)
    return render(request, "console/escalation_detail.html", {
        "escalation": esc,
        "handoff_json": handoff_json,
        "nav_section": "escalations",
    })


def _ensure_recommendation_samples():
    """Create sample recommendations when table is empty (e.g. fresh deploy)."""
    if Recommendation.objects.exists():
        return
    from companies.services import ensure_default_company
    from core.enums import SourceChannel

    company = ensure_default_company()
    projects = list(Project.objects.filter(company=company, is_active=True)[:2])
    if not projects:
        projects = [
            Project.objects.get_or_create(name="مشروع النخيل", company=company, defaults={"location": "القاهرة الجديدة", "price_min": 2500000, "price_max": 8000000})[0],
            Project.objects.get_or_create(name="مشروع الريف", company=company, defaults={"location": "6 أكتوبر", "price_min": 1500000, "price_max": 4000000})[0],
        ]
    customers = list(Customer.objects.filter(company=company, is_active=True).select_related("identity")[:5])
    if not customers:
        for i, (ext_id, name, email) in enumerate([
            ("rec_sample_1", "أحمد محمد", "ahmed.sample@demo.local"),
            ("rec_sample_2", "سارة علي", "sara.sample@demo.local"),
            ("rec_sample_3", "خالد حسن", "khalid.sample@demo.local"),
        ]):
            identity, _ = CustomerIdentity.objects.get_or_create(external_id=ext_id, defaults={"name": name, "email": email})
            cust, _ = Customer.objects.get_or_create(identity=identity, company=company, defaults={"source_channel": SourceChannel.DEMO})
            customers.append(cust)
    conv = None
    if customers:
        conv = Conversation.objects.filter(customer=customers[0], company=company).first()
        if not conv:
            conv = Conversation.objects.create(customer=customers[0], company=company)
    samples = [
        {"rationale": "مناسب للميزانية والموقع المطلوب", "confidence": 0.88, "reasons": ["مطابق للميزانية", "الموقع المفضل", "وحدات عائلية"]},
        {"rationale": "توافق جيد مع خطط الدفع والتقسيط", "confidence": 0.82, "reasons": ["خطط تقسيط مناسبة", "قرب من الخدمات"]},
        {"rationale": "مشروع مميز للاستثمار - عائد متوقع جيد", "confidence": 0.75, "reasons": ["موقع استراتيجي", "طلب عالي"],
         "tradeoffs": ["التسليم خلال ١٨ شهراً"]},
        {"rationale": "وحدات بمساحات متعددة تناسب الاحتياجات", "confidence": 0.91, "reasons": ["تنوع المساحات", "تشطيب فائق"]},
        {"rationale": "قيمة ممتازة ضمن النطاق السعري", "confidence": 0.78, "reasons": ["سعر تنافسي", "مرافق متكاملة"],
         "tradeoffs": ["بعيد قليلاً عن المركز"]},
    ]
    for i, s in enumerate(samples):
        cust = customers[i % len(customers)]
        proj = projects[i % len(projects)]
        rec_conv = Conversation.objects.filter(customer=cust, company=company).first() or conv
        Recommendation.objects.create(
            customer=cust,
            conversation=rec_conv,
            project=proj,
            rationale=s["rationale"],
            rank=i + 1,
            metadata={
                "confidence": s["confidence"],
                "match_reasons": s["reasons"],
                "why_it_matches": s["reasons"],
                "tradeoffs": s.get("tradeoffs", []),
            },
        )


def _recommendations_vercel_fallback() -> HttpResponse:
    """Full UI + sample cards; template rendered without RequestContext (no DB in context processors)."""
    from django.template.loader import get_template

    html = get_template("console/recommendations_vercel.html").render({})
    return HttpResponse(html, content_type="text/html; charset=utf-8")


def recommendations_view(request):
    from django.conf import settings

    host = (request.get_host() or "").lower()
    if ".vercel.app" in host or getattr(settings, "IS_VERCEL_DEPLOY", False):
        return _recommendations_vercel_fallback()
    recs = []
    try:
        _ensure_recommendation_samples()
        recs = list(
            Recommendation.objects
            .select_related("customer", "customer__identity", "project", "conversation")
            .order_by("-created_at")[:20]
        )
        for r in recs:
            m = r.metadata if isinstance(r.metadata, dict) else {}
            r.display_meta = {
                "confidence": m.get("confidence"),
                "match_reasons": m.get("why_it_matches") or m.get("match_reasons") or m.get("top_reasons") or [],
                "tradeoffs": m.get("tradeoffs") or m.get("trade_offs") or [],
            }
        return render(request, "console/recommendations.html", {
            "recommendations": recs,
            "nav_section": "recommendations",
        })
    except Exception as e:
        return HttpResponse(
            f"<h2>Recommendations</h2><p>Error: {type(e).__name__}: {e}</p>",
            content_type="text/html",
        )


def knowledge(request):
    from core.enums import DocumentType, AccessLevel

    qs = IngestedDocument.objects.select_related("project").order_by("-created_at")
    # Filters
    doc_type = request.GET.get("document_type", "").strip()
    if doc_type and doc_type in [c[0] for c in DocumentType.choices]:
        qs = qs.filter(document_type=doc_type)
    access = request.GET.get("access_level", "").strip()
    if access and access in [c[0] for c in AccessLevel.choices]:
        qs = qs.filter(access_level=access)
    verification = request.GET.get("verification_status", "").strip()
    if verification:
        qs = qs.filter(verification_status=verification)
    from django.db.models import Count
    qs = qs.annotate(_chunk_count=Count("chunks"))
    docs = list(qs[:50])
    # Compute freshness per doc for display
    for d in docs:
        d._is_fresh = RetrievalPolicy.is_fresh(d)
    return render(request, "console/knowledge.html", {
        "documents": docs,
        "document_types": DocumentType.choices,
        "access_levels": AccessLevel.choices,
        "verification_statuses": [("", "All"), ("unverified", "Unverified"), ("verified", "Verified"), ("stale", "Stale")],
        "nav_section": "knowledge",
    })


def knowledge_doc_detail(request, pk):
    doc = get_object_or_404(IngestedDocument.objects.select_related("project"), pk=pk)
    chunks = list(doc.chunks.all().order_by("chunk_index")[:50])
    # Enrich chunks with retrieval metadata (from chunk metadata or document)
    meta_default = lambda ch, key, default: (ch.metadata or {}).get(key, default)
    for ch in chunks:
        ch._retrieval_meta = {
            "document_type": meta_default(ch, "document_type", doc.document_type),
            "verification_status": meta_default(ch, "verification_status", doc.verification_status),
            "access_level": meta_default(ch, "access_level", getattr(doc, "access_level", "internal")),
        }
    # Live retrieval test if query provided
    query = request.GET.get("q", "").strip()
    retrieval_results = []
    fallback_note = ""
    if query:
        retrieval_results = retrieve_by_query(query, limit=5, project_id=doc.project_id)
        fallback_note = get_safe_fallback_note(retrieval_results)
    return render(request, "console/knowledge_doc_detail.html", {
        "document": doc,
        "chunks": chunks,
        "query": query,
        "retrieval_results": retrieval_results,
        "fallback_note": fallback_note,
        "is_fresh": RetrievalPolicy.is_fresh(doc),
        "nav_section": "knowledge",
    })


def structured_facts(request):
    """List projects with structured facts and verification summary."""
    projects = list(Project.objects.filter(is_active=True).prefetch_related(
        "payment_plans", "delivery_timelines", "unit_categories"
    ).order_by("name"))
    rows = []
    for p in projects:
        facts = get_project_structured_facts(p.id)
        rows.append({
            "project": p,
            "facts": facts,
            "has_pricing": facts.pricing.value is not None,
            "has_payment_plan": facts.payment_plan.value is not None,
            "has_delivery": facts.delivery.value is not None,
            "has_units": len(facts.unit_categories) > 0,
        })
    return render(request, "console/structured_facts.html", {
        "rows": rows,
        "nav_section": "structured_facts",
    })


def structured_facts_project(request, pk):
    """Project detail with all structured facts for operator inspection."""
    project = get_object_or_404(Project.objects.prefetch_related(
        "payment_plans", "delivery_timelines", "unit_categories"
    ), pk=pk)
    facts = get_project_structured_facts(project.id)
    return render(request, "console/structured_facts_project.html", {
        "project": project,
        "facts": facts,
        "nav_section": "structured_facts",
    })


@admin_required
def company_config(request):
    """Company configuration - branding, tone, channels. Admin only."""
    from companies.services import get_default_company
    company = get_default_company()
    return render(request, "console/company_config.html", {
        "company": company,
        "nav_section": "company",
    })


def audit(request):
    qs = ActionLog.objects.order_by("-created_at")
    if request.GET.get("subject_type") == "conversation" and request.GET.get("subject_id", "").isdigit():
        qs = qs.filter(subject_type="conversation", subject_id=request.GET["subject_id"])
    logs = list(qs[:100])
    return render(request, "console/audit.html", {
        "logs": logs,
        "nav_section": "audit",
    })


def operations(request):
    """Operations dashboard: health checks, key state, recent runs (success/failed), escalations, support cases."""
    from core.health_views import run_health_checks
    from console.models import OrchestrationSnapshot
    from audit.models import ActionLog
    from support.models import Escalation, SupportCase

    checks, ok_count = run_health_checks()
    stats = _stats()

    # Filters from GET
    conv_id = request.GET.get("conversation_id", "").strip()
    run_id_filter = request.GET.get("run_id", "").strip()
    status_filter = request.GET.get("status", "all")  # all|success|failed|escalated

    # Base querysets
    snapshot_qs = OrchestrationSnapshot.objects.select_related("conversation", "conversation__customer").order_by("-created_at")
    failed_qs = ActionLog.objects.filter(action="orchestration_failed").order_by("-created_at")

    if conv_id and conv_id.isdigit():
        cid = int(conv_id)
        snapshot_qs = snapshot_qs.filter(conversation_id=cid)
        failed_qs = failed_qs.filter(payload__conversation_id=cid)

    if run_id_filter:
        snapshot_qs = snapshot_qs.filter(run_id__icontains=run_id_filter)
        failed_qs = failed_qs.filter(subject_id__icontains=run_id_filter)

    if status_filter == "success":
        recent_successful = list(snapshot_qs.filter(escalation_flag=False)[:15])
        recent_runs = list(snapshot_qs.filter(escalation_flag=False)[:20])
    elif status_filter == "escalated":
        recent_successful = []
        recent_runs = list(snapshot_qs.filter(escalation_flag=True)[:20])
    elif status_filter == "failed":
        recent_successful = []
        recent_runs = []
    else:
        recent_successful = list(snapshot_qs.filter(escalation_flag=False)[:15])
        recent_runs = list(snapshot_qs[:20])

    recent_failed = list(failed_qs[:15])

    # Recent escalations and support cases
    esc_qs = Escalation.objects.select_related("customer", "conversation").order_by("-created_at")
    sup_qs = SupportCase.objects.select_related("customer", "conversation").order_by("-created_at")
    if conv_id and conv_id.isdigit():
        esc_qs = esc_qs.filter(conversation_id=int(conv_id))
        sup_qs = sup_qs.filter(conversation_id=int(conv_id))
    recent_escalations = list(esc_qs[:15])
    recent_support_cases = list(sup_qs[:15])

    return render(request, "console/operations.html", {
        "checks": checks,
        "ok_count": ok_count,
        "stats": stats,
        "recent_runs": recent_runs,
        "recent_successful": recent_successful,
        "recent_failed": recent_failed,
        "recent_escalations": recent_escalations,
        "recent_support_cases": recent_support_cases,
        "filters": {
            "conversation_id": conv_id,
            "run_id": run_id_filter,
            "status": status_filter,
        },
        "nav_section": "operations",
    })


def corrections(request):
    from console.models import ResponseFeedback
    corrs = HumanCorrection.objects.select_related("message", "conversation", "customer").order_by("-id")[:100]
    feedback_list = ResponseFeedback.objects.select_related("message", "conversation", "customer").order_by("-created_at")[:100]
    return render(request, "console/corrections.html", {
        "corrections": corrs,
        "feedback_list": feedback_list,
        "can_submit_correction": _can_submit_correction(request),
        "issue_type_choices": CorrectionIssueType.choices,
        "nav_section": "corrections",
    })


def improvement_insights(request):
    """Improvement Insights - recurring quality problems, operator recommendations."""
    from improvement.models import ImprovementSignal
    from improvement.services.aggregation import aggregate_improvement_signals
    from improvement.services.recommendations import generate_operator_recommendations

    days = int(request.GET.get("days", "30"))
    agg_result = None
    if request.GET.get("refresh") == "1":
        try:
            agg_result = aggregate_improvement_signals(days=days)
        except Exception as e:
            agg_result = {"error": str(e)}

    signals = list(
        ImprovementSignal.objects
        .filter(review_status="pending")
        .order_by("-frequency", "-last_seen_at")[:100]
    )
    by_issue = {}
    for s in signals:
        by_issue.setdefault(s.issue_type, []).append(s)
    recommendations = generate_operator_recommendations(limit=50)

    return render(request, "console/improvement_insights.html", {
        "signals": signals,
        "by_issue": by_issue,
        "recommendations": recommendations,
        "agg_result": agg_result,
        "days": days,
        "nav_section": "improvement",
    })


def demo_scenarios(request):
    return render(request, "console/demo_scenarios.html", {
        "nav_section": None,
    })


def demo_eval_mode(request):
    """Demo mode: pick scenario, replay, inspect output."""
    from demo.models import DemoScenario, DemoEvalRun
    scenarios = list(DemoScenario.objects.order_by("scenario_type", "name"))
    by_type = {}
    for s in scenarios:
        by_type.setdefault(s.scenario_type, []).append(s)
    last_run = DemoEvalRun.objects.order_by("-created_at").first()
    return render(request, "console/demo_eval.html", {
        "scenarios": scenarios,
        "by_type": by_type,
        "last_run": last_run,
        "nav_section": None,
    })


def demo_replay(request, pk):
    """Replay a single scenario and show pipeline output."""
    from demo.models import DemoScenario
    from demo.eval_runner import run_scenario
    scenario = get_object_or_404(DemoScenario, pk=pk)
    run_result = None
    if request.GET.get("run") == "1":
        try:
            actual, failures, run_time_ms = run_scenario(scenario, use_llm=True)
            run_result = {
                "actual": actual,
                "failures": failures,
                "passed": len(failures) == 0,
                "run_time_ms": run_time_ms,
                "expected": {
                    "customer_type": scenario.expected_customer_type,
                    "intent": scenario.expected_intent,
                    "temperature": scenario.expected_temperature,
                    "support_category": scenario.expected_support_category,
                    "route": scenario.expected_route,
                    "escalation": scenario.expected_escalation,
                },
            }
        except Exception as e:
            run_result = {"error": str(e), "actual": {}, "failures": [str(e)], "passed": False}
    # Format for display
    if run_result:
        import json
        q = run_result.get("actual", {}).get("qualification") or {}
        run_result["qualification_json"] = json.dumps(q, indent=2, default=str)
    return render(request, "console/demo_replay.html", {
        "scenario": scenario,
        "run_result": run_result,
        "nav_section": None,
    })


def sales_eval(request):
    """Sales evaluation harness: scenarios, runs, metrics."""
    from evaluation.models import SalesEvalScenario, SalesEvalRun
    scenarios = list(SalesEvalScenario.objects.order_by("category", "name"))
    by_category = {}
    for s in scenarios:
        by_category.setdefault(s.category, []).append(s)
    runs = list(SalesEvalRun.objects.order_by("-created_at")[:20])
    last_run = runs[0] if runs else None
    return render(request, "console/sales_eval.html", {
        "scenarios": scenarios,
        "by_category": by_category,
        "runs": runs,
        "last_run": last_run,
        "nav_section": None,
    })


def sales_eval_run_detail(request, run_id):
    """Sales eval run detail with per-scenario results and scores."""
    from evaluation.models import SalesEvalRun
    run = get_object_or_404(SalesEvalRun, run_id=run_id)
    results = list(run.results.select_related("scenario").order_by("scenario__category", "scenario__name"))
    return render(request, "console/sales_eval_run_detail.html", {
        "run": run,
        "results": results,
        "nav_section": None,
    })


def _can_submit_correction(request):
    """Check if user can submit corrections (admin, operator, reviewer). Requires auth."""
    if not request.user.is_authenticated:
        return False
    profile = getattr(request.user, "profile", None)
    return profile and profile.can_edit_corrections


def _extract_sales_linkage_from_snapshot(snap):
    """Extract strategy, objection_type, stage from OrchestrationSnapshot for correction linkage."""
    out = {"strategy": "", "objection_type": "", "recommendation_quality": "", "stage_decision": ""}
    if not snap:
        return out
    routing = getattr(snap, "routing", None) or {}
    if isinstance(routing, dict):
        out["strategy"] = (routing.get("approach") or routing.get("strategy") or routing.get("recommended_route") or "")[:64]
        out["objection_type"] = (routing.get("objection_key") or "")[:64]
    if not out["objection_type"]:
        policy = getattr(snap, "policy_decision", None) or {}
        if isinstance(policy, dict):
            out["objection_type"] = (policy.get("objection_key") or policy.get("objection_type") or "")[:64]
    out["stage_decision"] = (getattr(snap, "journey_stage", None) or "")[:64]
    return out


@require_POST
def submit_feedback(request):
    """Submit response feedback - good/weak/wrong. Links to strategy, objection, stage. Writes better version + issue type."""
    from console.models import ResponseFeedback, OrchestrationSnapshot
    from core.enums import ResponseQuality

    if not _can_submit_correction(request):
        return JsonResponse({"error": "Permission denied"}, status=403)
    msg_id = request.POST.get("message_id")
    quality_raw = (request.POST.get("quality") or request.POST.get("is_good") or "").strip()
    is_good_legacy = request.POST.get("is_good") == "1"
    corrected = request.POST.get("corrected_response", "")
    reason = request.POST.get("reason", "")
    category = request.POST.get("category", "")
    issue_type = request.POST.get("issue_type", "") or category
    created_by = request.POST.get("created_by") or (getattr(request.user, "username", None) or "operator")
    if not msg_id:
        return JsonResponse({"error": "message_id required"}, status=400)
    msg = get_object_or_404(Message, pk=msg_id)
    conv = msg.conversation
    customer = conv.customer
    mode = ""
    snap = OrchestrationSnapshot.objects.filter(message=msg).order_by("-created_at").first()
    linkage = _extract_sales_linkage_from_snapshot(snap)
    if snap:
        mode = snap.mode or ""

    if quality_raw in ("good", "weak", "wrong"):
        quality = quality_raw
        is_good = quality == "good"
    else:
        quality = "good" if is_good_legacy else ("wrong" if corrected else "weak")
        is_good = is_good_legacy

    fb = ResponseFeedback.objects.create(
        message=msg,
        conversation=conv,
        customer=customer,
        mode=mode,
        is_good=is_good,
        quality=quality,
        corrected_response=corrected,
        reason=reason,
        category=category,
        issue_type=issue_type,
        strategy=linkage["strategy"],
        objection_type=linkage["objection_type"],
        recommendation_quality=request.POST.get("recommendation_quality", "")[:64],
        stage_decision=linkage["stage_decision"],
        created_by=created_by,
    )
    if quality in ("weak", "wrong"):
        sales_linkage = {
            "strategy": linkage["strategy"],
            "objection_type": linkage["objection_type"],
            "recommendation_quality": fb.recommendation_quality,
            "stage_decision": linkage["stage_decision"],
        }
        HumanCorrection.objects.create(
            subject_type="message",
            subject_id=str(msg_id),
            field_name="response",
            original_value=msg.content,
            corrected_value=corrected or msg.content,
            corrected_by=created_by,
            reason=reason,
            message=msg,
            conversation=conv,
            customer=customer,
            mode=mode,
            issue_type=issue_type,
            is_correct=False,
            sales_linkage=sales_linkage,
        )
    return JsonResponse({"ok": True})


@require_POST
def submit_correction(request):
    """Submit human correction via HumanCorrection model. Links to message/conversation/customer when message_id provided."""
    if not _can_submit_correction(request):
        return JsonResponse({"error": "Permission denied"}, status=403)
    subject_type = request.POST.get("subject_type", "message")
    subject_id = request.POST.get("subject_id")
    message_id = request.POST.get("message_id") or (subject_id if subject_type == "message" else None)
    field_name = request.POST.get("field_name", "response")
    original_value = request.POST.get("original_value", "")
    corrected_value = request.POST.get("corrected_value", "")
    reason = request.POST.get("reason", "")
    issue_type = request.POST.get("issue_type", "")
    corrected_by = request.POST.get("corrected_by") or (getattr(request.user, "username", None) or "operator")
    if not subject_id or not corrected_value:
        return JsonResponse({"error": "subject_id and corrected_value required"}, status=400)
    msg = conv = customer = None
    mode = ""
    sales_linkage = {}
    if message_id:
        try:
            msg = Message.objects.select_related("conversation", "conversation__customer").get(pk=message_id)
            conv = msg.conversation
            customer = conv.customer
            from console.models import OrchestrationSnapshot
            snap = OrchestrationSnapshot.objects.filter(message=msg).order_by("-created_at").first()
            if snap:
                mode = snap.mode or ""
                linkage = _extract_sales_linkage_from_snapshot(snap)
                sales_linkage = {
                    "strategy": linkage["strategy"],
                    "objection_type": linkage["objection_type"],
                    "recommendation_quality": request.POST.get("recommendation_quality", "")[:64],
                    "stage_decision": linkage["stage_decision"],
                }
        except Message.DoesNotExist:
            pass
    HumanCorrection.objects.create(
        subject_type=subject_type,
        subject_id=subject_id,
        field_name=field_name,
        original_value=original_value,
        corrected_value=corrected_value,
        corrected_by=corrected_by,
        reason=reason,
        message=msg,
        conversation=conv,
        customer=customer,
        mode=mode,
        issue_type=issue_type,
        is_correct=False,
        sales_linkage=sales_linkage,
    )
    return JsonResponse({"ok": True})
