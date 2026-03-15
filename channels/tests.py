"""Channel abstraction and normalized inbound tests."""
import pytest

from channels.schema import NormalizedInboundMessage, CANONICAL_ORCHESTRATION_FIELDS
from channels.adapters.web import WebChannelAdapter
from channels.adapters.whatsapp import WhatsAppChannelAdapter
from channels.service import normalize_inbound, process_inbound_message
from channels.persistence import get_or_create_whatsapp_customer_conversation


def test_normalized_message_schema():
    """NormalizedInboundMessage has required fields and to_orchestration_params."""
    msg = NormalizedInboundMessage(
        content="Hello",
        source_channel="web",
        external_id="u1",
        phone="+201012345678",
        campaign="utm_campaign",
        source="google",
    )
    assert msg.content == "Hello"
    assert msg.source_channel == "web"
    assert msg.phone == "+201012345678"
    assert msg.campaign == "utm_campaign"
    assert msg.source == "google"
    assert msg.timestamp is not None
    params = msg.to_orchestration_params()
    assert params["raw_content"] == "Hello"
    assert params["channel"] == "web"
    assert params["external_id"] == "u1"
    assert params["phone"] == "+201012345678"


def test_web_adapter_normalize():
    """Web adapter produces NormalizedInboundMessage from web payload."""
    adapter = WebChannelAdapter()
    payload = {
        "content": "  أسعار الشقق  ",
        "channel": "web",
        "external_id": "anon_123",
        "phone": "+201011111111",
        "campaign": "summer2025",
        "conversation_id": 1,
    }
    msg = adapter.normalize(payload)
    assert msg.content == "أسعار الشقق"
    assert msg.source_channel == "web"
    assert msg.external_id == "anon_123"
    assert msg.phone == "+201011111111"
    assert msg.campaign == "summer2025"
    assert msg.conversation_id == 1
    assert msg.metadata.get("use_llm") is True


def test_web_adapter_requires_content():
    """Web adapter raises ValueError when content empty."""
    adapter = WebChannelAdapter()
    with pytest.raises(ValueError, match="content is required"):
        adapter.normalize({"channel": "web"})


def test_whatsapp_adapter_direct_shape():
    """WhatsApp adapter handles direct/test payload with content and phone."""
    adapter = WhatsAppChannelAdapter()
    payload = {
        "content": "Hi from WhatsApp",
        "phone": "+201022222222",
        "external_id": "wa_123",
    }
    msg = adapter.normalize(payload)
    assert msg.content == "Hi from WhatsApp"
    assert msg.source_channel == "whatsapp"
    assert msg.phone == "201022222222"  # Normalized (digits)
    assert msg.external_id == "wa_123"


def test_whatsapp_adapter_webhook_shape():
    """WhatsApp adapter parses webhook payload structure."""
    adapter = WhatsAppChannelAdapter()
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "messages": [{
                        "from": "201033333333",
                        "id": "wamid.xyz",
                        "timestamp": "1234567890",
                        "text": {"body": "عايز أسعار"},
                        "type": "text",
                    }],
                    "contacts": [{"profile": {"name": "Ahmed"}}],
                },
                "field": "messages",
            }],
        }],
    }
    msg = adapter.normalize(payload)
    assert msg.content == "عايز أسعار"
    assert msg.source_channel == "whatsapp"
    assert msg.phone == "201033333333"
    assert msg.external_id == "whatsapp:201033333333"
    assert msg.external_message_id == "wamid.xyz"
    assert msg.name == "Ahmed"


def test_channel_normalization_same_orchestration_schema():
    """Web and WhatsApp adapters produce identical orchestration param keys."""
    web = WebChannelAdapter()
    wa = WhatsAppChannelAdapter()

    web_payload = {
        "content": "أسعار الشقق",
        "channel": "web",
        "external_id": "anon_123",
        "phone": "+201011111111",
        "campaign": "summer2025",
        "conversation_id": 1,
        "use_llm": True,
    }
    wa_payload = {
        "content": "أسعار الشقق",
        "phone": "+201011111111",
        "external_id": "wa_123",
    }

    web_msg = web.normalize(web_payload)
    wa_msg = wa.normalize(wa_payload)

    web_params = web_msg.to_orchestration_params()
    wa_params = wa_msg.to_orchestration_params()

    web_keys = set(web_params.keys())
    wa_keys = set(wa_params.keys())
    assert web_keys == wa_keys, f"Schema mismatch: web={web_keys}, wa={wa_keys}"
    assert web_keys >= set(CANONICAL_ORCHESTRATION_FIELDS), "Missing canonical fields"
    assert web_params["raw_content"] == wa_params["raw_content"] == "أسعار الشقق"
    # WhatsApp normalizes phone to digits; web keeps raw. Both include phone.
    assert "phone" in web_params and "phone" in wa_params
    assert wa_params["phone"] == "201011111111"


def test_channel_metadata_preserved():
    """to_channel_metadata preserves channel-specific fields for audit."""
    msg = NormalizedInboundMessage(
        content="Test",
        source_channel="whatsapp",
        external_id="wa:123",
        phone="201012345678",
        external_message_id="wamid.abc",
    )
    meta = msg.to_channel_metadata()
    assert meta["source_channel"] == "whatsapp"
    assert meta["phone"] == "201012345678"
    assert meta["external_message_id"] == "wamid.abc"
    assert "message_timestamp" in meta


def test_channel_normalization_optional_fields_defaults():
    """Optional orchestration fields have consistent defaults across channels."""
    web = WebChannelAdapter()
    wa = WhatsAppChannelAdapter()
    web_msg = web.normalize({"content": "Hi", "channel": "web", "external_id": "x"})
    wa_msg = wa.normalize({"content": "Hi", "phone": "+201012345678", "external_id": "y"})

    for params in [web_msg.to_orchestration_params(), wa_msg.to_orchestration_params()]:
        assert "use_llm" in params
        assert "sales_mode" in params
        assert params.get("sales_mode") == "warm_lead"
        assert "lang" in params
        assert params.get("lang") == "ar"
        assert "is_angry" in params
        assert params.get("is_angry") is False


@pytest.mark.django_db
def test_normalize_inbound_web():
    """normalize_inbound returns NormalizedInboundMessage for web channel."""
    payload = {"content": "Test", "channel": "web", "external_id": "t1"}
    msg = normalize_inbound("web", payload)
    assert isinstance(msg, NormalizedInboundMessage)
    assert msg.content == "Test"
    assert msg.source_channel == "web"


@pytest.mark.django_db
def test_process_inbound_runs_orchestration():
    """process_inbound_message normalizes and runs orchestration."""
    payload = {
        "content": "عايز أعرف أسعار",
        "channel": "web",
        "external_id": "proc_test",
        "use_llm": False,
    }
    msg, run = process_inbound_message("web", payload)
    assert msg.content == "عايز أعرف أسعار"
    assert run.run_id
    assert run.final_response or run.status.value


@pytest.mark.django_db
def test_whatsapp_persistence_and_pipeline():
    """WhatsApp inbound goes through canonical pipeline and persists."""
    from companies.services import ensure_default_company
    ensure_default_company()

    from conversations.models import Message
    from leads.models import Customer
    from core.enums import SourceChannel

    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "1",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "messages": [{
                        "from": "201055512345",
                        "id": "wamid.test123",
                        "timestamp": "1234567890",
                        "text": {"body": "عايز بروشور"},
                        "type": "text",
                    }],
                    "contacts": [{"profile": {"name": "Test User"}}],
                },
                "field": "messages",
            }],
        }],
    }
    msg, run = process_inbound_message("whatsapp", payload)
    assert msg.phone == "201055512345"
    assert run.run_id
    assert run.final_response or ""

    cust = Customer.objects.filter(identity__external_id="whatsapp:201055512345").first()
    assert cust is not None
    assert cust.source_channel == SourceChannel.WHATSAPP
    msgs = Message.objects.filter(conversation__customer=cust).order_by("created_at")
    assert msgs.count() >= 2
    roles = list(msgs.values_list("role", flat=True))
    assert "user" in roles
    assert "assistant" in roles
    user_msg = msgs.filter(role="user").first()
    assert user_msg.metadata.get("phone") == "201055512345"
    assert user_msg.metadata.get("external_message_id") == "wamid.test123"


@pytest.mark.django_db
def test_whatsapp_persistence_get_or_create():
    """get_or_create_whatsapp_customer_conversation creates identity and conversation."""
    from companies.services import ensure_default_company
    ensure_default_company()

    customer, conversation = get_or_create_whatsapp_customer_conversation(
        phone="+201011111111",
        contact_name="أحمد",
    )
    assert customer.id
    assert conversation.id
    assert conversation.channel == "whatsapp"
    assert customer.identity.external_id == "whatsapp:201011111111"
    assert customer.identity.name == "أحمد"

    customer2, conv2 = get_or_create_whatsapp_customer_conversation(phone="201011111111")
    assert customer2.id == customer.id
    assert conv2.id == conversation.id


@pytest.mark.django_db
def test_whatsapp_webhook_verification(client):
    """Webhook GET verification returns challenge when token matches."""
    from django.conf import settings
    token = "my_verify_token"
    settings.WHATSAPP_VERIFY_TOKEN = token
    try:
        r = client.get(
            "/api/channels/whatsapp/webhook/",
            {"hub.mode": "subscribe", "hub.verify_token": token, "hub.challenge": "challenge123"},
        )
        assert r.status_code == 200
        assert r.content == b"challenge123"
    finally:
        settings.WHATSAPP_VERIFY_TOKEN = ""


@pytest.mark.django_db
def test_whatsapp_webhook_status_update_skipped(client):
    """Webhook POST with status update (no messages) returns 200 without processing."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "1",
            "changes": [{
                "value": {"statuses": [{"id": "wamid.xyz", "status": "read"}]},
                "field": "messages",
            }],
        }],
    }
    r = client.post("/api/channels/whatsapp/webhook/", payload, content_type="application/json")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "no messages" in data.get("message", "").lower() or "status update" in data.get("message", "").lower()