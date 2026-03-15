"""
Leads API: search customer, unified profile, identity candidates, merge approve/reject.
"""
from django.db import models

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from leads.models import Customer, CustomerIdentity, IdentityMergeCandidate
from leads.services.timeline import build_timeline
from leads.services.customer_memory import get_long_term_memory


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_customer(request):
    """
    Search customers by phone, email, name, external_id.
    Query params: q, phone, email, external_id
    """
    q = request.query_params.get("q", "").strip()
    phone = request.query_params.get("phone", "").strip()
    email = request.query_params.get("email", "").strip()
    external_id = request.query_params.get("external_id", "").strip()

    identities = CustomerIdentity.objects.filter(merged_into__isnull=True)
    if phone:
        identities = identities.filter(phone__icontains=phone)
    if email:
        identities = identities.filter(email__icontains=email)
    if external_id:
        identities = identities.filter(external_id__icontains=external_id)
    if q:
        identities = identities.filter(
            models.Q(name__icontains=q) | models.Q(phone__icontains=q) | models.Q(email__icontains=q) | models.Q(external_id__icontains=q)
        )

    results = []
    for ident in identities[:20]:
        cust = ident.customers.filter(is_active=True).first()
        if cust:
            results.append({
                "customer_id": cust.id,
                "identity_id": ident.id,
                "name": ident.name,
                "phone": ident.phone,
                "email": ident.email,
                "external_id": ident.external_id,
            })
    return Response(results)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def customer_profile(request, customer_id):
    """Unified profile: identity, memories, timeline preview."""
    customer = Customer.objects.filter(id=customer_id).select_related("identity").first()
    if not customer:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    identity = customer.identity
    memories = get_long_term_memory(customer)
    timeline = build_timeline(customer, limit=30)

    return Response({
        "customer_id": customer.id,
        "identity": {
            "id": identity.id if identity else None,
            "name": identity.name if identity else "",
            "phone": identity.phone if identity else "",
            "email": identity.email if identity else "",
            "external_id": identity.external_id if identity else "",
        } if identity else {},
        "customer_type": customer.customer_type,
        "memories": memories,
        "timeline": timeline,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def identity_candidates(request):
    """List pending identity merge candidates."""
    candidates = IdentityMergeCandidate.objects.filter(
        review_status="pending"
    ).select_related("identity_a", "identity_b")[:50]
    data = [
        {
            "id": c.id,
            "identity_a_id": c.identity_a_id,
            "identity_b_id": c.identity_b_id,
            "identity_a": {"name": c.identity_a.name, "phone": c.identity_a.phone, "email": c.identity_a.email},
            "identity_b": {"name": c.identity_b.name, "phone": c.identity_b.phone, "email": c.identity_b.email},
            "confidence_score": c.confidence_score,
            "match_reasons": c.match_reasons,
        }
        for c in candidates
    ]
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def merge_approve(request, candidate_id):
    """Approve identity merge. Merges identity_b into identity_a."""
    from leads.services.identity_resolution import merge_identities

    candidate = IdentityMergeCandidate.objects.filter(id=candidate_id, review_status="pending").first()
    if not candidate:
        return Response({"error": "Not found or already processed"}, status=status.HTTP_404_NOT_FOUND)

    merge_identities(candidate.identity_a, candidate.identity_b, actor=str(request.user))
    candidate.review_status = "manual_approved"
    candidate.reviewed_by = str(request.user)
    candidate.merged_identity_id = candidate.identity_a_id
    candidate.save()

    return Response({"status": "merged", "kept_identity_id": candidate.identity_a_id})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def merge_reject(request, candidate_id):
    """Reject identity merge."""
    candidate = IdentityMergeCandidate.objects.filter(id=candidate_id, review_status="pending").first()
    if not candidate:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    candidate.review_status = "rejected"
    candidate.reviewed_by = str(request.user)
    candidate.save()
    return Response({"status": "rejected"})
