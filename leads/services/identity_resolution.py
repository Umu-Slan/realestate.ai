"""
Identity Resolution Engine - probabilistic linking across phone, email, external_id, username, name.
"""
from dataclasses import dataclass
import re

from leads.models import CustomerIdentity


@dataclass
class MatchResult:
    matched: bool
    identity: CustomerIdentity | None
    confidence_score: float
    match_reasons: list[str]
    manual_review_required: bool


def normalize_phone(phone: str) -> str:
    """Normalize for comparison."""
    if not phone:
        return ""
    s = "".join(c for c in phone if c.isdigit())
    if s.startswith("2"):
        s = s[1:]
    if s.startswith("0"):
        s = s[1:]
    return s[-9:] if len(s) >= 9 else s


def normalize_email(email: str) -> str:
    return (email or "").lower().strip()


def normalize_name(name: str) -> str:
    """Normalize for fuzzy: lower, strip, collapse, remove diacritics placeholder."""
    if not name:
        return ""
    s = " ".join((name or "").lower().split())
    return s


def name_similarity(a: str, b: str) -> float:
    """Simple Jaccard-ish on words. 0-1."""
    if not a or not b:
        return 0.0
    wa = set(normalize_name(a).split())
    wb = set(normalize_name(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


def resolve_identity(
    *,
    phone: str | None = None,
    email: str | None = None,
    external_id: str | None = None,
    username: str | None = None,
    name: str | None = None,
    auto_merge_threshold: float = 0.95,
) -> MatchResult:
    """
    Probabilistically find or create identity.
    Returns MatchResult with matched, identity, confidence, reasons, manual_review_required.
    """
    candidates = []
    reasons = []

    phone_n = normalize_phone(phone) if phone else ""
    email_n = normalize_email(email) if email else ""
    name_n = normalize_name(name) if name else ""

    # Exact external_id
    if external_id:
        exact = CustomerIdentity.objects.filter(external_id=external_id).first()
        if exact:
            return MatchResult(
                matched=True,
                identity=exact,
                confidence_score=1.0,
                match_reasons=["exact_external_id"],
                manual_review_required=False,
            )

    # Phone match
    if phone_n and len(phone_n) >= 9:
        for ident in CustomerIdentity.objects.filter(phone__isnull=False).exclude(phone=""):
            if normalize_phone(ident.phone or "") == phone_n:
                candidates.append((ident, 0.9, "exact_phone"))
                break

    # Email match
    if email_n:
        for ident in CustomerIdentity.objects.filter(email__isnull=False).exclude(email=""):
            if normalize_email(ident.email or "") == email_n:
                candidates.append((ident, 0.9, "exact_email"))
                break

    # Username match
    if username:
        ident = CustomerIdentity.objects.filter(metadata__username=username).first()
        if ident:
            candidates.append((ident, 0.85, "username"))
        ident = CustomerIdentity.objects.filter(external_id=username).first()
        if ident:
            candidates.append((ident, 0.9, "external_id_as_username"))

    if not candidates:
        return MatchResult(
            matched=False,
            identity=None,
            confidence_score=0.0,
            match_reasons=[],
            manual_review_required=False,
        )

    best = max(candidates, key=lambda x: x[1])
    identity, base_score, reason = best
    reasons.append(reason)

    # Name boost/penalty
    if name_n and identity.name:
        sim = name_similarity(name_n, identity.name)
        if sim >= 0.8:
            base_score = min(1.0, base_score + 0.1)
            reasons.append("name_match")
        elif sim < 0.3 and (phone_n or email_n):
            base_score -= 0.2
            reasons.append("name_mismatch")

    # Conflicting signals: same phone/email on different identities
    if phone_n:
        phone_matches = [i for i, _, _ in candidates if identity != i and normalize_phone(getattr(i.phone, "strip", lambda: i.phone or "")()) == phone_n]
        if identity.phone and normalize_phone(identity.phone) != phone_n and phone_n:
            pass
    if email_n:
        other_email = [i for i in CustomerIdentity.objects.exclude(id=identity.id) if normalize_email(i.email or "") == email_n]
        if other_email:
            base_score -= 0.3
            reasons.append("conflicting_email")

    confidence = max(0.0, min(1.0, base_score))
    manual_review = confidence < auto_merge_threshold and confidence >= 0.5

    # When we find candidates, matched=True (we identified the person).
    # manual_review_required means caller should flag for human approval before auto-linking.
    return MatchResult(
        matched=True,
        identity=identity,
        confidence_score=confidence,
        match_reasons=reasons,
        manual_review_required=manual_review,
    )


def merge_identities(keep: CustomerIdentity, merge_from: CustomerIdentity, actor: str = "") -> None:
    """Merge merge_from into keep. Update all references, then soft-merge identity."""
    from leads.models import Customer
    from audit.models import ActionLog
    from core.enums import AuditAction

    for cust in merge_from.customers.all():
        cust.identity = keep
        cust.save(update_fields=["identity"])
    merge_from.merged_into = keep
    merge_from.save(update_fields=["merged_into"])
    ActionLog.objects.create(
        action=AuditAction.IDENTITY_MANUAL_MERGED.value,
        actor=actor,
        subject_type="identity",
        subject_id=str(keep.id),
        payload={"merged_from_id": merge_from.id},
    )
