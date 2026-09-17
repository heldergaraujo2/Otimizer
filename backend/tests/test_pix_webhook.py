import json

import pytest

from otimizer_api.pix_webhook import PixWebhookError, compute_signature, parse_event, verify_signature


SECRET = "development-webhook-secret"


def body(**overrides):
    payload = {
        "event_id": "evt-001",
        "payment_id": "pay-001",
        "amount_cents": 2990,
        "status": "confirmed",
    }
    payload.update(overrides)
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def test_signature_round_trip_accepts_current_event():
    raw = body()
    timestamp = "1700000000"
    signature = compute_signature(SECRET, timestamp, raw)
    verify_signature(SECRET, timestamp, signature, raw, now=1700000001)
    event = parse_event(raw)
    assert event.event_id == "evt-001"
    assert event.payment_id == "pay-001"
    assert event.amount_cents == 2990


def test_signature_accepts_sha256_prefix():
    raw = body()
    timestamp = "1700000000"
    signature = "sha256=" + compute_signature(SECRET, timestamp, raw)
    verify_signature(SECRET, timestamp, signature, raw, now=1700000000)


def test_signature_rejects_tampered_body():
    raw = body()
    timestamp = "1700000000"
    signature = compute_signature(SECRET, timestamp, raw)
    with pytest.raises(PixWebhookError, match="invalid webhook signature"):
        verify_signature(SECRET, timestamp, signature, body(amount_cents=3990), now=1700000000)


def test_signature_rejects_replay_outside_tolerance():
    raw = body()
    timestamp = "1700000000"
    signature = compute_signature(SECRET, timestamp, raw)
    with pytest.raises(PixWebhookError, match="outside the allowed window"):
        verify_signature(SECRET, timestamp, signature, raw, now=1700000401, tolerance_seconds=300)


@pytest.mark.parametrize("field", ["event_id", "payment_id", "amount_cents", "status"])
def test_parser_rejects_missing_required_fields(field):
    payload = json.loads(body())
    payload.pop(field)
    with pytest.raises(PixWebhookError):
        parse_event(json.dumps(payload).encode())


def test_parser_rejects_unsupported_status_and_non_positive_amount():
    with pytest.raises(PixWebhookError, match="unsupported webhook status"):
        parse_event(body(status="paid"))
    with pytest.raises(PixWebhookError, match="amount_cents must be positive"):
        parse_event(body(amount_cents=0))
