from __future__ import annotations

import hashlib
import hmac
from unittest.mock import MagicMock, patch

import pytest

from backend.services import payments


@patch("backend.services.payments.settings")
@patch("backend.services.payments.httpx.Client")
def test_create_order_returns_checkout_fields(mock_client_cls, mock_settings):
    mock_settings.has_razorpay = True
    mock_settings.razorpay_key_id = "rzp_test_abc"
    mock_settings.razorpay_key_secret = "secret123"
    mock_settings.razorpay_package_amount_paise = 9900
    mock_settings.razorpay_package_credits = 50
    mock_settings.provider_timeout_seconds = 20.0

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"id": "order_abc", "amount": 9900, "currency": "INR"}

    client = MagicMock()
    client.post.return_value = response
    mock_client_cls.return_value.__enter__.return_value = client

    result = payments.create_order(receipt="topup_1")

    assert result == {
        "order_id": "order_abc",
        "amount": 9900,
        "currency": "INR",
        "key_id": "rzp_test_abc",
        "credits": 50,
    }
    # key secret must never leak into the response a frontend receives
    assert "secret123" not in str(result)


@patch("backend.services.payments.settings")
def test_create_order_raises_when_not_configured(mock_settings):
    mock_settings.has_razorpay = False

    with pytest.raises(payments.PaymentError, match="not configured"):
        payments.create_order(receipt="topup_1")


@patch("backend.services.payments.settings")
def test_verify_payment_signature_accepts_correct_signature(mock_settings):
    mock_settings.has_razorpay = True
    mock_settings.razorpay_key_secret = "secret123"

    order_id, payment_id = "order_abc", "pay_xyz"
    message = f"{order_id}|{payment_id}".encode("utf-8")
    valid_signature = hmac.new(b"secret123", message, hashlib.sha256).hexdigest()

    payments.verify_payment_signature(order_id=order_id, payment_id=payment_id, signature=valid_signature)


@patch("backend.services.payments.settings")
def test_verify_payment_signature_rejects_wrong_signature(mock_settings):
    mock_settings.has_razorpay = True
    mock_settings.razorpay_key_secret = "secret123"

    with pytest.raises(payments.SignatureVerificationError):
        payments.verify_payment_signature(order_id="order_abc", payment_id="pay_xyz", signature="not-the-real-signature")


@patch("backend.services.payments.settings")
def test_verify_payment_signature_raises_when_not_configured(mock_settings):
    mock_settings.has_razorpay = False

    with pytest.raises(payments.PaymentError, match="not configured"):
        payments.verify_payment_signature(order_id="o", payment_id="p", signature="s")
