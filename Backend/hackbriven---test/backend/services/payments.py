from __future__ import annotations

import hmac
import hashlib
import logging

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.razorpay.com/v1"


class PaymentError(RuntimeError):
    pass


class SignatureVerificationError(PaymentError):
    pass


def create_order(
    *,
    receipt: str,
    amount_paise: int | None = None,
    credits: int | None = None,
    notes: dict | None = None,
) -> dict:
    """Create a Razorpay order - by default for the one configured top-up
    package, or for an explicit amount/credits (a pack or a plan).
    Returns the fields a frontend needs to open Razorpay Checkout
    (order_id, amount, currency, key_id) - never the key secret."""
    if not settings.has_razorpay:
        raise PaymentError("RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET not configured")

    payload = {
        "amount": amount_paise if amount_paise is not None else settings.razorpay_package_amount_paise,
        "currency": "INR",
        "receipt": receipt,
    }
    if notes:
        payload["notes"] = notes
    with httpx.Client(
        timeout=settings.provider_timeout_seconds,
        auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
    ) as client:
        response = client.post(f"{_BASE_URL}/orders", json=payload)
        response.raise_for_status()
        order = response.json()

    return {
        "order_id": order["id"],
        "amount": order["amount"],
        "currency": order["currency"],
        "key_id": settings.razorpay_key_id,
        "credits": credits if credits is not None else settings.razorpay_package_credits,
    }


def verify_payment_signature(*, order_id: str, payment_id: str, signature: str) -> None:
    """Verify a completed payment's signature per Razorpay's documented
    scheme (HMAC-SHA256 of "order_id|payment_id" using the key secret).
    Raises SignatureVerificationError if it doesn't match - callers must
    never credit an account on an unverified payment."""
    if not settings.has_razorpay:
        raise PaymentError("RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET not configured")

    message = f"{order_id}|{payment_id}".encode("utf-8")
    expected = hmac.new(settings.razorpay_key_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise SignatureVerificationError("payment signature did not match")
