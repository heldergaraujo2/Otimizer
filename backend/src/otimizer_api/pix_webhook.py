"""Authenticated, replay-resistant Pix webhook verification primitives.

This module is provider-neutral: a concrete PSP adapter should map its webhook
payload to ``PixWebhookEvent`` only after the provider's documented signature
contract has been verified. No provider secret belongs in source code or the
Android client.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass


class PixWebhookError(ValueError):
    """Raised when a webhook cannot be trusted or parsed."""


@dataclass(frozen=True)
class PixWebhookEvent:
    event_id: str
    payment_id: str
    amount_cents: int
    status: str


def signature_payload(timestamp: str, raw_body: bytes) -> bytes:
    return timestamp.encode("ascii") + b"." + raw_body


def compute_signature(secret: str, timestamp: str, raw_body: bytes) -> str:
    if not secret:
        raise PixWebhookError("webhook secret is required")
    return hmac.new(secret.encode("utf-8"), signature_payload(timestamp, raw_body), hashlib.sha256).hexdigest()


def verify_signature(
    secret: str,
    timestamp: str,
    signature: str,
    raw_body: bytes,
    *,
    now: float | None = None,
    tolerance_seconds: int = 300,
) -> None:
    if not secret:
        raise PixWebhookError("webhook secret is required")
    if not timestamp.isdigit():
        raise PixWebhookError("invalid webhook timestamp")
    if tolerance_seconds <= 0:
        raise PixWebhookError("webhook tolerance must be positive")
    timestamp_value = int(timestamp)
    current = time.time() if now is None else now
    if abs(current - timestamp_value) > tolerance_seconds:
        raise PixWebhookError("webhook timestamp is outside the allowed window")
    expected = compute_signature(secret, timestamp, raw_body)
    provided = signature.strip()
    if provided.startswith("sha256="):
        provided = provided[7:]
    if not hmac.compare_digest(expected, provided):
        raise PixWebhookError("invalid webhook signature")


def parse_event(raw_body: bytes) -> PixWebhookEvent:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PixWebhookError("invalid webhook JSON") from exc
    if not isinstance(payload, dict):
        raise PixWebhookError("webhook payload must be an object")
    event_id = str(payload.get("event_id") or "").strip()
    payment_id = str(payload.get("payment_id") or "").strip()
    status = str(payload.get("status") or "").strip().lower()
    try:
        amount_cents = int(payload["amount_cents"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PixWebhookError("amount_cents is required") from exc
    if not event_id or len(event_id) > 200:
        raise PixWebhookError("event_id is required")
    if not payment_id or len(payment_id) > 200:
        raise PixWebhookError("payment_id is required")
    if amount_cents <= 0:
        raise PixWebhookError("amount_cents must be positive")
    if status not in {"confirmed", "settled"}:
        raise PixWebhookError("unsupported webhook status")
    return PixWebhookEvent(event_id, payment_id, amount_cents, status)
