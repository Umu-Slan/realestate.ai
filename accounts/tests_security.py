"""Security and access control tests."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.models import UserProfile, Role

User = get_user_model()


def _create_user(username: str, role: str, password: str = "testpass123"):
    """Create user with profile."""
    user = User.objects.create_user(username=username, password=password)
    UserProfile.objects.create(user=user, role=role)
    return user


@pytest.mark.django_db
def test_console_redirects_anonymous_to_login(client):
    """Anonymous access to console redirects to login."""
    r = client.get("/console/", follow=False)
    assert r.status_code == 302
    assert "/accounts/login" in r["Location"]


@pytest.mark.django_db
def test_login_success_redirects_to_console(client):
    """Successful login redirects to console."""
    User.objects.create_user(username="op", password="testpass123")
    r = client.post(
        reverse("accounts:login"),
        {"username": "op", "password": "testpass123", "next": "/console/"},
    )
    assert r.status_code == 302
    assert r["Location"] in ("/console/", "http://testserver/console/")


@pytest.mark.django_db
def test_company_config_admin_only(client):
    """Company config requires admin role."""
    admin_user = _create_user("admin1", Role.ADMIN)
    operator_user = _create_user("operator1", Role.OPERATOR)
    demo_user = _create_user("demo1", Role.DEMO)

    client.force_login(admin_user)
    r = client.get(reverse("console:company_config"))
    assert r.status_code == 200

    client.force_login(operator_user)
    r = client.get(reverse("console:company_config"))
    assert r.status_code == 302
    assert "dashboard" in r["Location"]

    client.force_login(demo_user)
    r = client.get(reverse("console:company_config"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_submit_feedback_requires_auth(client):
    """Submit feedback requires authenticated user with correction permission."""
    from conversations.models import Conversation, Message
    from leads.models import Customer, CustomerIdentity

    identity = CustomerIdentity.objects.create(external_id="sec_test", phone="010111111111")
    customer = Customer.objects.create(identity=identity)
    conv = Conversation.objects.create(customer=customer)
    msg = Message.objects.create(conversation=conv, role="assistant", content="Hi")

    r = client.post(
        reverse("console:submit_feedback"),
        {"message_id": msg.id, "is_good": "1"},
    )
    assert r.status_code == 302  # Redirect to login

    operator_user = _create_user("operator2", Role.OPERATOR)
    client.force_login(operator_user)
    client.get("/console/")  # Get CSRF cookie
    r = client.post(
        reverse("console:submit_feedback"),
        {"message_id": msg.id, "is_good": "1"},
        follow=False,
    )
    assert r.status_code == 200
    import json
    data = json.loads(r.content)
    assert data.get("ok") is True


@pytest.mark.django_db
def test_demo_user_cannot_submit_correction(client):
    """Demo role cannot submit corrections."""
    from conversations.models import Conversation, Message
    from leads.models import Customer, CustomerIdentity

    identity = CustomerIdentity.objects.create(external_id="sec_demo", phone="010222222222")
    customer = Customer.objects.create(identity=identity)
    conv = Conversation.objects.create(customer=customer)
    msg = Message.objects.create(conversation=conv, role="assistant", content="Test")

    demo_user = _create_user("demo2", Role.DEMO)
    client.force_login(demo_user)
    r = client.post(
        reverse("console:submit_feedback"),
        {"message_id": msg.id, "is_good": "0", "corrected_response": "Fixed", "issue_type": "accuracy"},
        follow=False,
    )
    assert r.status_code == 403


@pytest.mark.django_db
def test_public_engines_remain_accessible(client):
    """Engines chat API remains public for customer-facing widget."""
    from companies.services import ensure_default_company
    ensure_default_company()
    r = client.post(
        "/api/engines/sales/",
        {"message": "مرحبا", "mode": "warm_lead"},
        content_type="application/json",
    )
    assert r.status_code == 200


@pytest.mark.django_db
def test_internal_api_requires_auth(client):
    """Internal APIs require authentication."""
    r = client.get("/api/leads/search/")
    assert r.status_code == 403

    user = _create_user("api_user", Role.OPERATOR)
    client.force_login(user)
    r = client.get("/api/leads/search/")
    assert r.status_code == 200
