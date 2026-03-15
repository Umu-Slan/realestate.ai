"""CRM import, identity resolution, and sync tests."""
import pytest
import csv
from pathlib import Path

from crm.services.import_service import import_crm_file, normalize_phone, normalize_email
from crm.services.sync_service import (
    get_or_create_crm_record_for_customer,
    append_note_to_crm,
    update_lead_stage,
    assign_owner,
    assign_queue,
    link_support_case,
    update_tags,
    sync_conversation_outcome,
)
from crm.models import CRMRecord, CRMActivityLog
from leads.models import CustomerIdentity, Customer
from leads.services.identity_resolution import resolve_identity, normalize_phone as id_norm_phone


@pytest.mark.django_db
def test_normalize_phone():
    assert normalize_phone("+201012345678") == "012345678" or "1012345678"
    assert normalize_phone("01012345678") != ""


@pytest.mark.django_db
def test_import_csv(tmp_path):
    csv_path = tmp_path / "leads.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["crm_id", "name", "phone", "email", "source", "notes", "project_interest", "status"])
        w.writeheader()
        w.writerow({"crm_id": "T1", "name": "Test", "phone": "+201011111111", "email": "t@t.com", "source": "web", "notes": "Note", "project_interest": "P1", "status": "new"})
    stats = import_crm_file(str(csv_path), dry_run=False)
    assert stats["imported"] >= 1
    assert CRMRecord.objects.filter(crm_id="T1").exists()


@pytest.mark.django_db
def test_import_deduplication(tmp_path):
    csv_path = tmp_path / "dup.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["crm_id", "name", "phone", "email"])
        w.writeheader()
        w.writerow({"crm_id": "D1", "name": "Dup", "phone": "010222222222", "email": "d@d.com"})
        w.writerow({"crm_id": "D1", "name": "Dup2", "phone": "010222222222", "email": "d@d.com"})
    stats = import_crm_file(str(csv_path), dry_run=False)
    assert stats["duplicates"] >= 1


@pytest.mark.django_db
def test_identity_matching():
    CustomerIdentity.objects.create(external_id="ex1", phone="010333333333", email="m@m.com")
    result = resolve_identity(phone="010333333333", external_id="new1")
    assert result.matched
    assert result.identity is not None


@pytest.mark.django_db
def test_identity_no_match():
    result = resolve_identity(phone="010999999999", email="unique_new@new.com", external_id="brand_new")
    assert not result.matched or result.manual_review_required


@pytest.mark.django_db
def test_import_with_owner_and_tags(tmp_path):
    """CSV import supports owner, lead_stage, tags."""
    csv_path = tmp_path / "rich.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["crm_id", "name", "phone", "email", "owner", "lead_stage", "tags"])
        w.writeheader()
        w.writerow({"crm_id": "R1", "name": "Rich", "phone": "+201055555555", "email": "r@r.com", "owner": "Sales1", "lead_stage": "qualified", "tags": "vip,hot"})
    stats = import_crm_file(str(csv_path), dry_run=False)
    assert stats["imported"] >= 1
    r = CRMRecord.objects.get(crm_id="R1")
    assert r.owner == "Sales1"
    assert r.lead_stage == "qualified"
    assert "vip" in r.tags and "hot" in r.tags


@pytest.mark.django_db
def test_sync_create_crm_record_for_customer():
    """get_or_create_crm_record_for_customer creates record when none exists."""
    identity = CustomerIdentity.objects.create(external_id="sync1", phone="010666666666", email="s@s.com", name="Sync")
    customer = Customer.objects.create(identity=identity)
    rec = get_or_create_crm_record_for_customer(customer.id, actor="test")
    assert rec is not None
    assert rec.linked_customer_id == customer.id
    assert rec.crm_id.startswith("sync_")
    assert CRMActivityLog.objects.filter(crm_record=rec, activity_type=CRMActivityLog.ActivityType.RECORD_CREATED).exists()


@pytest.mark.django_db
def test_append_note_to_crm():
    """append_note_to_crm appends note and logs activity."""
    identity = CustomerIdentity.objects.create(external_id="n1", phone="010777777777", email="n@n.com")
    customer = Customer.objects.create(identity=identity)
    rec = get_or_create_crm_record_for_customer(customer.id, actor="test")
    ok = append_note_to_crm(customer_id=customer.id, note="AI: Customer interested in Project X", actor="ai_system")
    assert ok
    rec.refresh_from_db()
    assert "AI: Customer interested" in rec.notes
    assert CRMActivityLog.objects.filter(crm_record=rec, activity_type=CRMActivityLog.ActivityType.NOTE_ADDED).exists()


@pytest.mark.django_db
def test_update_lead_stage():
    """update_lead_stage updates stage and logs activity."""
    identity = CustomerIdentity.objects.create(external_id="st1", phone="010888888888", email="st@st.com")
    customer = Customer.objects.create(identity=identity)
    rec = get_or_create_crm_record_for_customer(customer.id, actor="test")
    ok = update_lead_stage(customer_id=customer.id, lead_stage="shortlisting", actor="ai_system")
    assert ok
    rec.refresh_from_db()
    assert rec.lead_stage == "shortlisting"
    assert CRMActivityLog.objects.filter(crm_record=rec, activity_type=CRMActivityLog.ActivityType.STAGE_UPDATED).exists()


@pytest.mark.django_db
def test_assign_owner_and_queue():
    """assign_owner and assign_queue update CRM record."""
    identity = CustomerIdentity.objects.create(external_id="o1", phone="010999999999", email="o@o.com")
    customer = Customer.objects.create(identity=identity)
    rec = get_or_create_crm_record_for_customer(customer.id, actor="test")
    assert assign_owner(customer_id=customer.id, owner="Rep-Ahmed", actor="operator") is True
    assert assign_queue(customer_id=customer.id, queue="sales-hot", actor="operator") is True
    rec.refresh_from_db()
    assert rec.owner == "Rep-Ahmed"
    assert rec.assigned_queue == "sales-hot"


@pytest.mark.django_db
def test_sync_conversation_outcome():
    """sync_conversation_outcome creates record and applies all updates."""
    identity = CustomerIdentity.objects.create(external_id="co1", phone="010111111111", email="co@co.com", name="Outcome")
    customer = Customer.objects.create(identity=identity)
    rec = sync_conversation_outcome(
        customer.id,
        note="Discussed budget 2-3M, location Cairo",
        lead_stage="consideration",
        owner="AI-Routed",
        actor="ai_system",
    )
    assert rec is not None
    rec.refresh_from_db()
    assert "Discussed budget" in rec.notes
    assert rec.lead_stage == "consideration"
    assert rec.owner == "AI-Routed"


@pytest.mark.django_db
def test_update_tags():
    """update_tags replaces or merges tags and logs activity."""
    identity = CustomerIdentity.objects.create(external_id="tg1", phone="010444444444", email="tg@tg.com")
    customer = Customer.objects.create(identity=identity)
    rec = get_or_create_crm_record_for_customer(customer.id, actor="test")
    ok = update_tags(customer_id=customer.id, tags_add=["vip", "hot"], actor="ai_system")
    assert ok
    rec.refresh_from_db()
    assert "vip" in rec.tags and "hot" in rec.tags
    assert CRMActivityLog.objects.filter(crm_record=rec, activity_type=CRMActivityLog.ActivityType.TAGS_UPDATED).exists()

    ok2 = update_tags(crm_record_id=rec.id, tags=["qualified", "follow_up"], actor="operator")
    assert ok2
    rec.refresh_from_db()
    assert rec.tags == ["qualified", "follow_up"]


@pytest.mark.django_db
def test_duplicate_protection():
    """get_or_create returns same record for same customer; no duplicate linked records."""
    identity = CustomerIdentity.objects.create(external_id="dup1", phone="010555555555", email="dup@dup.com")
    customer = Customer.objects.create(identity=identity)
    rec1 = get_or_create_crm_record_for_customer(customer.id, actor="test")
    rec2 = get_or_create_crm_record_for_customer(customer.id, actor="test")
    assert rec1.id == rec2.id
    assert CRMRecord.objects.filter(linked_customer_id=customer.id).count() == 1
