"""
Correction loop tests - permissions, linkage, feedback flow.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from leads.models import CustomerIdentity, Customer
from conversations.models import Conversation, Message
from console.models import ResponseFeedback, OrchestrationSnapshot
from audit.models import HumanCorrection
from accounts.models import UserProfile
from accounts.models import Role

User = get_user_model()


@pytest.fixture
def conv_with_assistant_msg():
    ident = CustomerIdentity.objects.create(external_id="corr-test-1")
    cust = Customer.objects.create(identity=ident, customer_type="new_lead")
    conv = Conversation.objects.create(customer=cust, channel="web")
    user_msg = Message.objects.create(conversation=conv, role="user", content="Hi")
    assist_msg = Message.objects.create(conversation=conv, role="assistant", content="Hello, how can I help?")
    snap = OrchestrationSnapshot.objects.create(
        conversation=conv,
        message=assist_msg,
        run_id="r1",
        intent={"primary": "general"},
        mode="sales",
        routing={"approach": "nurture", "objection_key": "price_too_high"},
        journey_stage="consideration",
    )
    return conv, assist_msg


@pytest.fixture
def user_reviewer():
    u = User.objects.create_user(username="reviewer1", password="test")
    UserProfile.objects.create(user=u, role=Role.REVIEWER)
    return u


@pytest.mark.django_db
def test_submit_feedback_creates_linkage(client, conv_with_assistant_msg, user_reviewer):
    """submit_feedback creates ResponseFeedback with conversation, customer, mode."""
    conv, msg = conv_with_assistant_msg
    client.force_login(user_reviewer)
    resp = client.post(reverse("console:submit_feedback"), data={
        "message_id": msg.id,
        "is_good": "1",
    })
    assert resp.status_code == 200
    fb = ResponseFeedback.objects.get(message=msg)
    assert fb.is_good is True
    assert fb.conversation_id == conv.id
    assert fb.customer_id == conv.customer_id
    assert fb.mode == "sales"


@pytest.mark.django_db
def test_submit_feedback_correction_creates_humancorrection(client, conv_with_assistant_msg, user_reviewer):
    """submit_feedback with is_good=0 creates HumanCorrection with linkage."""
    conv, msg = conv_with_assistant_msg
    client.force_login(user_reviewer)
    resp = client.post(reverse("console:submit_feedback"), data={
        "message_id": msg.id,
        "is_good": "0",
        "corrected_response": "Corrected text",
        "reason": "Wrong tone",
        "issue_type": "tone",
    })
    assert resp.status_code == 200
    fb = ResponseFeedback.objects.get(message=msg)
    assert fb.is_good is False
    hc = HumanCorrection.objects.get(message=msg)
    assert hc.corrected_value == "Corrected text"
    assert hc.conversation_id == conv.id
    assert hc.customer_id == conv.customer_id
    assert hc.mode == "sales"
    assert hc.issue_type == "tone"
    assert hc.is_correct is False


@pytest.mark.django_db
def test_submit_correction_with_message_links(client, conv_with_assistant_msg, user_reviewer):
    """submit_correction with subject_id=message_id creates linked HumanCorrection."""
    conv, msg = conv_with_assistant_msg
    client.force_login(user_reviewer)
    resp = client.post(reverse("console:submit_correction"), data={
        "subject_type": "message",
        "subject_id": str(msg.id),
        "corrected_value": "Fixed response",
        "original_value": msg.content,
        "reason": "Accuracy",
        "issue_type": "accuracy",
    })
    assert resp.status_code == 200
    hc = HumanCorrection.objects.get(subject_id=str(msg.id))
    assert hc.message_id == msg.id
    assert hc.conversation_id == conv.id
    assert hc.customer_id == conv.customer_id
    assert hc.mode == "sales"
    assert hc.issue_type == "accuracy"


@pytest.fixture
def user_demo():
    u = User.objects.create_user(username="demo1", password="test")
    UserProfile.objects.create(user=u, role=Role.DEMO)
    return u


@pytest.mark.django_db
def test_reviewer_can_submit_feedback(client, conv_with_assistant_msg, user_reviewer):
    """Reviewer role can submit feedback."""
    conv, msg = conv_with_assistant_msg
    client.force_login(user_reviewer)
    resp = client.post(reverse("console:submit_feedback"), data={
        "message_id": msg.id,
        "is_good": "1",
    })
    assert resp.status_code == 200
    assert ResponseFeedback.objects.filter(message=msg).exists()


@pytest.mark.django_db
def test_demo_cannot_submit_feedback(client, conv_with_assistant_msg, user_demo):
    """Demo role cannot submit feedback (403)."""
    conv, msg = conv_with_assistant_msg
    client.force_login(user_demo)
    resp = client.post(reverse("console:submit_feedback"), data={
        "message_id": msg.id,
        "is_good": "1",
    })
    assert resp.status_code == 403
    assert not ResponseFeedback.objects.filter(message=msg).exists()


@pytest.mark.django_db
def test_demo_cannot_submit_correction(client, conv_with_assistant_msg, user_demo):
    """Demo role cannot submit correction (403)."""
    conv, msg = conv_with_assistant_msg
    client.force_login(user_demo)
    resp = client.post(reverse("console:submit_correction"), data={
        "subject_type": "message",
        "subject_id": str(msg.id),
        "corrected_value": "Fixed",
    })
    assert resp.status_code == 403
    assert not HumanCorrection.objects.filter(subject_id=str(msg.id)).exists()


@pytest.mark.django_db
def test_submit_feedback_quality_weak_captures_linkage(client, conv_with_assistant_msg, user_reviewer):
    """submit_feedback with quality=weak creates ResponseFeedback with sales linkage."""
    conv, msg = conv_with_assistant_msg
    client.force_login(user_reviewer)
    resp = client.post(reverse("console:submit_feedback"), data={
        "message_id": msg.id,
        "quality": "weak",
        "corrected_response": "Improved response",
        "issue_type": "objection_handling",
    })
    assert resp.status_code == 200
    fb = ResponseFeedback.objects.get(message=msg)
    assert fb.quality == "weak"
    assert fb.strategy == "nurture"
    assert fb.objection_type == "price_too_high"
    assert fb.stage_decision == "consideration"
    assert fb.issue_type == "objection_handling"
    hc = HumanCorrection.objects.get(message=msg)
    assert hc.sales_linkage.get("strategy") == "nurture"
    assert hc.sales_linkage.get("objection_type") == "price_too_high"


@pytest.mark.django_db
def test_submit_feedback_quality_good_no_humancorrection(client, conv_with_assistant_msg, user_reviewer):
    """submit_feedback with quality=good does not create HumanCorrection."""
    conv, msg = conv_with_assistant_msg
    client.force_login(user_reviewer)
    resp = client.post(reverse("console:submit_feedback"), data={
        "message_id": msg.id,
        "quality": "good",
    })
    assert resp.status_code == 200
    fb = ResponseFeedback.objects.get(message=msg)
    assert fb.quality == "good"
    assert fb.is_good is True
    assert not HumanCorrection.objects.filter(message=msg).exists()
