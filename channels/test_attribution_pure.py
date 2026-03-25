"""Pure unit tests — no database."""
from channels.attribution import campaign_bucket_label, extract_attribution_payload


def test_extract_attribution_from_metadata():
    m = extract_attribution_payload(
        {"utm_source": "facebook", "utm_campaign": "spring", "country": "EG", "attribution": {"city": "Cairo"}}
    )
    assert m["utm_source"] == "facebook"
    assert m["utm_campaign"] == "spring"
    assert m["country"] == "EG"
    assert m["city"] == "Cairo"


def test_campaign_bucket_label():
    assert "summer" in campaign_bucket_label({"utm_campaign": "summer_sale"})
    assert "google" in campaign_bucket_label({"utm_source": "google", "utm_medium": "cpc"}).lower()
