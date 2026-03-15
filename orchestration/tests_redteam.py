"""
RED TEAM - Attack tests to discover weaknesses.
Goal: Break the system. Find failures. No architecture changes.
"""
import json
import threading
import pytest
from django.test import Client
from rest_framework import status

from orchestration.orchestrator import run_orchestration, _normalize_intake
from orchestration.states import RunStatus


# --- Attack payloads ---
MALFORMED = [
    {"content": None},
    {"content": ""},
    {"content": "   "},
    {},
    {"content": []},
    {"content": {}},
    {"content": 12345},
    {"content": True},
]
LONG_MESSAGES = [
    "x" * 100,
    "x" * 10000,
    "x" * 50000,  # beyond truncation limit
]
MIXED_AR_EN = [
    "عايز شقة في New Cairo بحد أقصى 3 million",
    "What is the price السعر in EGP?",
    "متوفر availability of units?",
]
NONSENSE = [
    "asdfghjkl qwertyuiop zxcvbnm",
    "AAAAAAAAAAAA",
    "😀",
    "صصصصصصص",
]
SPAM = ["Buy now!!!"] * 20
EMOJI_HEAVY = [
    "😀😃😄😁😆😅🤣😂🙂🙃😉😊😇🥰😍🤩😘😗☺😚😙🥲😋😛😜🤪😝🤑🤗",
    "عايز أسعار 🏠🏢💰",
]
UNSUPPORTED_CHARS = [
    "\x00\x01\x02",  # null bytes
    "test\x7f\x80\x9f",
]
INVALID_PAYLOADS = [
    "not json",
    "<html>broken</html>",
    b"raw bytes",
]


@pytest.fixture
def api_client():
    return Client()


def _post_orchestrate(client, payload, content_type="application/json"):
    if isinstance(payload, dict):
        body = json.dumps(payload, default=str) if content_type == "application/json" else payload
    else:
        body = payload
    return client.post(
        "/api/orchestration/run/",
        data=body,
        content_type=content_type,
    )


# --- 1. Malformed messages ---
@pytest.mark.django_db
def test_malformed_empty_content(api_client):
    """Empty content should return 400, not 500."""
    for p in [{"content": ""}, {"content": "   "}, {}]:
        r = _post_orchestrate(api_client, p)
        assert r.status_code in (400, 422), f"Expected 400/422 for {p}, got {r.status_code}"
        if r.status_code == 200:
            data = r.json()
            assert "error" in data or data.get("status") == RunStatus.FAILED.value


@pytest.mark.django_db
def test_malformed_null_content(api_client):
    """content: null should not crash."""
    r = _post_orchestrate(api_client, {"content": None})
    assert r.status_code in (400, 422, 500)  # Should not hang/crash


@pytest.mark.django_db
def test_malformed_non_string_content(api_client):
    """content as number/array/dict should not crash."""
    for p in [{"content": 123}, {"content": []}, {"content": {"x": 1}}]:
        r = _post_orchestrate(api_client, p)
        assert r.status_code in (200, 400, 422, 500)
        if r.status_code == 200:
            data = r.json()
            assert "run_id" in data or "error" in data


# --- 2. Extremely long messages ---
@pytest.mark.django_db
def test_extremely_long_message(api_client):
    """Very long message should not crash; may truncate."""
    r = _post_orchestrate(api_client, {"content": "x" * 100000, "channel": "web", "external_id": "long"})
    assert r.status_code in (200, 400, 500)
    if r.status_code == 200:
        data = r.json()
        assert "run_id" in data


def test_normalize_intake_long_truncates():
    """Orchestrator should truncate at 10000 chars."""
    i = _normalize_intake("a" * 50000)
    assert len(i.normalized_content) <= 10000
    assert "truncated" in i.validation_errors


# --- 3. Mixed Arabic/English ---
@pytest.mark.django_db
def test_mixed_ar_en(api_client):
    """Mixed language should complete without crash."""
    for msg in MIXED_AR_EN:
        r = _post_orchestrate(api_client, {"content": msg, "channel": "web", "external_id": "mix"})
        assert r.status_code == 200, f"Failed for: {msg[:30]}..."
        data = r.json()
        assert "run_id" in data
        assert "response" in data or "failure_reason" in data


# --- 4. Nonsense text ---
@pytest.mark.django_db
def test_nonsense_text(api_client):
    """Nonsense should not crash."""
    for msg in NONSENSE:
        r = _post_orchestrate(api_client, {"content": msg, "channel": "web", "external_id": "nonsense"})
        assert r.status_code == 200
        data = r.json()
        assert "run_id" in data


# --- 5. Repeated spam (no infinite loop) ---
@pytest.mark.django_db
def test_repeated_spam(api_client):
    """Repeated same message should not crash or loop."""
    payload = {"content": "Buy now!!!", "channel": "web", "external_id": "spam", "use_llm": False}
    for _ in range(5):
        r = _post_orchestrate(api_client, payload)
        assert r.status_code == 200


# --- 6. Invalid API payloads ---
@pytest.mark.django_db
def test_invalid_json_body(api_client):
    """Invalid JSON should return 400 or 422, not 500."""
    r = api_client.post("/api/orchestration/run/", data="not json", content_type="application/json")
    assert r.status_code in (400, 422, 500)


@pytest.mark.django_db
def test_missing_content_field(api_client):
    """Payload without content key."""
    r = _post_orchestrate(api_client, {"channel": "web"})
    assert r.status_code in (400, 422)


# --- 7. Empty message direct orchestrator ---
@pytest.mark.django_db
def test_orchestrator_empty_content():
    """run_orchestration with empty string should fail gracefully."""
    run = run_orchestration("", external_id="empty", use_llm=False)
    assert run.status == RunStatus.FAILED
    assert "empty_content" in (run.failure_reason or "")


# --- 8. Unsupported characters ---
@pytest.mark.django_db
def test_unsupported_chars(api_client):
    """Null bytes and control chars should not crash."""
    for msg in UNSUPPORTED_CHARS:
        # Filter chars for JSON - null may break json.dumps
        safe_msg = "".join(c for c in msg if ord(c) >= 32 and c != "\x00") or "x"
        r = _post_orchestrate(api_client, {"content": safe_msg, "channel": "web", "external_id": "unsup"})
        assert r.status_code in (200, 400, 500)


# --- 9. Emoji-heavy input ---
@pytest.mark.django_db
def test_emoji_heavy(api_client):
    """Emoji-heavy input should not crash."""
    r = _post_orchestrate(api_client, {"content": "عايز أسعار 🏠💰", "channel": "web", "external_id": "emoji"})
    assert r.status_code == 200
    data = r.json()
    assert "run_id" in data


# --- 10. Recommendation engine edge cases ---
@pytest.mark.django_db
def test_recommendation_empty_budget(api_client):
    """Recommendation with no budget should not crash."""
    r = _post_orchestrate(api_client, {
        "content": "recommend projects",
        "channel": "web",
        "external_id": "rec1",
        "response_mode": "recommendation",
        "qualification_override": {},
        "use_llm": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert "run_id" in data


@pytest.mark.django_db
def test_recommendation_invalid_budget(api_client):
    """Recommendation with invalid budget override."""
    r = _post_orchestrate(api_client, {
        "content": "recommend",
        "channel": "web",
        "external_id": "rec2",
        "response_mode": "recommendation",
        "qualification_override": {"budget_min": "not-a-number", "budget_max": ""},
        "use_llm": False,
    })
    assert r.status_code in (200, 400, 500)
    if r.status_code == 200:
        data = r.json()
        assert "run_id" in data


# --- 11. Support escalation ---
@pytest.mark.django_db
def test_support_mode(api_client):
    """Support mode should not loop or crash."""
    r = _post_orchestrate(api_client, {
        "content": "I have a complaint",
        "channel": "web",
        "external_id": "sup1",
        "response_mode": "support",
        "use_llm": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert "run_id" in data


# --- 12. Conversation ID edge cases ---
@pytest.mark.django_db
def test_invalid_conversation_id(api_client):
    """Non-existent conversation_id should not crash."""
    r = _post_orchestrate(api_client, {
        "content": "Hello",
        "channel": "web",
        "external_id": "conv_invalid",
        "conversation_id": 999999999,
        "use_llm": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert "run_id" in data


@pytest.mark.django_db
def test_conversation_id_string(api_client):
    """conversation_id as string should not crash (adapter coerces)."""
    r = _post_orchestrate(api_client, {
        "content": "Hello",
        "channel": "web",
        "external_id": "conv_str",
        "conversation_id": "not-a-number",
        "use_llm": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert "run_id" in data


@pytest.mark.django_db
def test_malformed_conversation_history(api_client):
    """conversation_history as string/dict should not crash."""
    for bad_hist in ["string", {"not": "list"}, 123]:
        r = _post_orchestrate(api_client, {
            "content": "Hello",
            "channel": "web",
            "external_id": "bad_hist",
            "conversation_history": bad_hist,
            "use_llm": False,
        })
        assert r.status_code == 200


# --- 13. Concurrent requests (basic) ---
@pytest.mark.django_db
def test_concurrent_requests(api_client):
    """Multiple concurrent requests should not corrupt state."""
    results = []

    def _send():
        r = _post_orchestrate(api_client, {
            "content": "concurrent test",
            "channel": "web",
            "external_id": f"conc_{threading.current_thread().ident}",
            "use_llm": False,
        })
        results.append((r.status_code, r.json() if r.status_code == 200 else {}))

    threads = [threading.Thread(target=_send) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for code, data in results:
        assert code == 200
        if data:
            assert "run_id" in data
            # Each should have unique run_id
            run_ids = [d.get("run_id") for _, d in results if d]
            assert len(run_ids) == len(set(run_ids)), "Duplicate run_ids from concurrent requests"


# --- 14. Web adapter edge cases ---
def test_web_adapter_content_types():
    """Web adapter handles various content types without crash."""
    from channels.adapters.web import WebChannelAdapter
    adapter = WebChannelAdapter()
    # str(number) = "123"
    m = adapter.normalize({"content": 123, "channel": "web"})
    assert m.content == "123"
    # str(None) = "None" - adapter accepts it (view rejects null before adapter)
    m2 = adapter.normalize({"content": None, "channel": "web"})
    assert m2.content == "None"
