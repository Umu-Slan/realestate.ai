"""Leads: identity resolution, timeline, customer memory."""
import pytest

from leads.models import CustomerIdentity, Customer
from leads.services.identity_resolution import resolve_identity, merge_identities
from leads.services.timeline import build_timeline
from leads.services.customer_memory import add_memory, get_long_term_memory
from crm.models import CRMRecord
from core.enums import MemoryType


@pytest.mark.django_db
def test_resolve_identity_exact_match():
    ident = CustomerIdentity.objects.create(external_id="E1", phone="010123456789", email="e1@x.com")
    result = resolve_identity(external_id="E1")
    assert result.matched
    assert result.identity.id == ident.id
    assert not result.manual_review_required


@pytest.mark.django_db
def test_resolve_identity_phone_match():
    ident = CustomerIdentity.objects.create(external_id="P1", phone="010111222333")
    result = resolve_identity(phone="+2010111222333", external_id="P2")
    assert result.matched
    assert result.identity.id == ident.id


@pytest.mark.django_db
def test_resolve_identity_no_match():
    result = resolve_identity(phone="010000000000", email="nonexistent@x.com", external_id="NEW")
    assert not result.matched
    assert result.confidence_score == 0


@pytest.mark.django_db
def test_merge_identities():
    a = CustomerIdentity.objects.create(external_id="A", phone="010aaa")
    b = CustomerIdentity.objects.create(external_id="B", phone="010bbb")
    cust_b = Customer.objects.create(identity=b)
    merge_identities(a, b, actor="test")
    cust_b.refresh_from_db()
    assert cust_b.identity_id == a.id
    b.refresh_from_db()
    assert b.merged_into_id == a.id


@pytest.mark.django_db
def test_timeline_build():
    ident = CustomerIdentity.objects.create(external_id="T1", name="Timeline Test")
    cust = Customer.objects.create(identity=ident)
    CRMRecord.objects.create(
        crm_id="T1-CRM",
        external_name="Timeline Test",
        notes="Had a question",
        linked_customer_id=cust.id,
    )
    timeline = build_timeline(cust, limit=10)
    assert len(timeline) >= 1
    assert any(e["type"] == "crm_record" or e["type"] == "crm_note" for e in timeline)


@pytest.mark.django_db
def test_customer_memory():
    ident = CustomerIdentity.objects.create(external_id="M1")
    cust = Customer.objects.create(identity=ident)
    add_memory(cust, MemoryType.PREFERENCE, "Prefers 3BR", source="conversation")
    mems = get_long_term_memory(cust)
    assert len(mems) >= 1
    assert mems[0]["memory_type"] == "preference"
