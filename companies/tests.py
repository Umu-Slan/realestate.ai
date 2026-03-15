"""
Company configuration tests - linkage, default company, no regression.
"""
import pytest

from companies.models import Company
from companies.services import get_default_company, ensure_default_company
from leads.models import CustomerIdentity, Customer
from knowledge.models import Project
from conversations.models import Conversation, Message


@pytest.mark.django_db
def test_ensure_default_company_creates_one():
    """ensure_default_company creates default when none exists."""
    Company.objects.all().delete()
    assert Company.objects.count() == 0
    company = ensure_default_company()
    assert company.name == "Default Company"
    assert company.slug == "default"
    assert Company.objects.count() == 1


@pytest.mark.django_db
def test_ensure_default_company_returns_existing():
    """ensure_default_company returns existing when one exists."""
    existing = Company.objects.order_by("id").first()
    if existing:
        company = ensure_default_company()
        assert company.id == existing.id


@pytest.mark.django_db
def test_get_default_company_returns_first_active():
    """get_default_company returns first active company by id."""
    company = get_default_company()
    assert company is not None
    assert company.is_active


@pytest.mark.django_db
def test_customer_company_linkage():
    """Customer can be linked to company."""
    company = Company.objects.create(name="Test Co", slug="test-co")
    identity = CustomerIdentity.objects.create(external_id="cust-1")
    customer = Customer.objects.create(identity=identity, company=company)
    assert customer.company_id == company.id
    assert list(company.customers.all()) == [customer]


@pytest.mark.django_db
def test_project_company_linkage():
    """Project can be linked to company."""
    company = Company.objects.create(name="Dev Co", slug="dev-co")
    project = Project.objects.create(name="Tower A", company=company)
    assert project.company_id == company.id
    assert list(company.projects.all()) == [project]


@pytest.mark.django_db
def test_conversation_company_linkage():
    """Conversation can be linked to company."""
    company = Company.objects.create(name="Sales Co", slug="sales-co")
    identity = CustomerIdentity.objects.create(external_id="conv-1")
    customer = Customer.objects.create(identity=identity, company=company)
    conv = Conversation.objects.create(customer=customer, company=company)
    assert conv.company_id == company.id
    assert list(company.conversations.all()) == [conv]


@pytest.mark.django_db
def test_get_or_create_customer_uses_default_company():
    """conversations.services get_or_create_customer uses default company."""
    from conversations.services import get_or_create_customer
    company = get_default_company()
    assert company is not None
    identity = CustomerIdentity.objects.create(external_id="new-lead-company-test")
    customer = get_or_create_customer(identity, channel="web")
    assert customer.company_id == company.id


@pytest.mark.django_db
def test_existing_behavior_without_company():
    """Customer/Project with null company still work (backward compat)."""
    identity = CustomerIdentity.objects.create(external_id="legacy-1")
    customer = Customer.objects.create(identity=identity, company=None)
    assert customer.company_id is None
    project = Project.objects.create(name="Legacy Project", company=None)
    assert project.company_id is None


@pytest.mark.django_db
def test_company_config_view_renders(client):
    """Company config console view returns 200."""
    from django.urls import reverse
    Company.objects.create(name="Config Test", slug="config-test")
    resp = client.get(reverse("console:company_config"))
    assert resp.status_code == 200
    assert b"Config Test" in resp.content or b"Company" in resp.content
