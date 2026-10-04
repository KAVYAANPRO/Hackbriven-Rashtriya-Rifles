from __future__ import annotations

from datetime import datetime, timezone

from backend.core import docstore

"""Payment orders we created. Razorpay's signature only proves that an
(order_id, payment_id) pair is genuine - it says nothing about *what* was
bought or *who* bought it, and the same signed pair can be replayed forever.
So every order we open is recorded here, and verification consumes it exactly
once (pending -> paid) for the account that created it."""

_COLL = "orders"


def create_pending(
    order_id: str, *, account: str, kind: str, credits: int, amount_paise: int, plan: str | None = None
) -> None:
    docstore.insert(
        _COLL,
        order_id,
        {
            "order_id": order_id,
            "account": account,
            "kind": kind,  # "pack" | "plan" | "legacy"
            "plan": plan,
            "credits": credits,
            "amount_paise": amount_paise,
            "status": "pending",
            "payment_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def get(order_id: str) -> dict | None:
    return docstore.get(_COLL, order_id)


def claim_paid(order_id: str, payment_id: str) -> dict | None:
    """Atomically move pending -> paid. None means it was already consumed (or never existed)."""
    return docstore.claim(
        _COLL,
        order_id,
        {"status": "pending"},
        {"status": "paid", "payment_id": payment_id, "paid_at": datetime.now(timezone.utc).isoformat()},
    )


def release(order_id: str) -> None:
    """Put a claimed order back to pending - used when granting the purchase failed, so the buyer can retry."""
    docstore.update(_COLL, order_id, {"status": "pending", "payment_id": None})
