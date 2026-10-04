from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings
from backend.models.schemas import MotionTier

# A video generation credit balance must survive a process restart (a judge
# demo, a server redeploy) - unlike the rest of this pipeline's deliberately
# in-memory state (see RULES.md "no database"), real money is on the other
# side of this one. MongoDB is the durable backing store when MONGODB_URI is
# configured (needed because this pipeline deploys on Hugging Face Spaces,
# whose storage is typically ephemeral); a local SQLite file is the fallback
# for offline/local dev with no URI set.
_SQLITE_FILENAME = "credits.db"
_sqlite_lock = threading.Lock()
_mongo_client = None

TIER_COST = {
    MotionTier.MAX: 10,
    MotionTier.BALANCED: 4,
    MotionTier.BASIC: 1,
}

_BALANCE_DOC_ID = "balance"

# Anonymous / legacy callers (and every balance that existed before accounts
# did) live in this account; its Mongo balance document keeps the original
# "balance" id so an existing live balance is untouched.
DEFAULT_ACCOUNT = "default"


def _balance_doc_id(account: str) -> str:
    return _BALANCE_DOC_ID if account == DEFAULT_ACCOUNT else f"{_BALANCE_DOC_ID}:{account}"


class InsufficientCreditsError(RuntimeError):
    def __init__(self, required: int, available: int) -> None:
        self.required = required
        self.available = available
        super().__init__(f"insufficient credits: need {required}, have {available}")


def cost_for_tier(tier: MotionTier) -> int:
    return TIER_COST[tier]


def cost_for_job(tier: MotionTier, surcharge: int = 0) -> int:
    """Price of one job: the motion tier's cost plus any resolution surcharge."""
    return TIER_COST[tier] + max(0, surcharge)


def _use_mongo() -> bool:
    return bool(settings.mongodb_uri)


def _mongo_collections():
    global _mongo_client
    if _mongo_client is None:
        import pymongo

        _mongo_client = pymongo.MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=10000)
    db = _mongo_client[settings.mongodb_db_name]
    return db["credit_balance"], db["credit_transactions"]


def _sqlite_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.storage_path / _SQLITE_FILENAME)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            delta INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    # Ledgers created before accounts existed have no account column; those
    # rows all belong to the default account.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(ledger)")}
    if "account" not in columns:
        conn.execute("ALTER TABLE ledger ADD COLUMN account TEXT NOT NULL DEFAULT 'default'")
    conn.commit()
    return conn


def get_balance(account: str = DEFAULT_ACCOUNT) -> int:
    if _use_mongo():
        balance_col, _ = _mongo_collections()
        doc = balance_col.find_one({"_id": _balance_doc_id(account)})
        return int(doc["value"]) if doc else 0

    with _sqlite_lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT COALESCE(SUM(delta), 0) FROM ledger WHERE account = ?", (account,)).fetchone()
        return int(row[0])


def charge(tier: MotionTier, *, reason: str, account: str = DEFAULT_ACCOUNT, surcharge: int = 0) -> int:
    """Deduct the credit cost for one job. Raises InsufficientCreditsError
    and charges nothing if the balance can't cover it - callers must check
    this before starting a pipeline run, not after."""
    amount = cost_for_job(tier, surcharge)

    if _use_mongo():
        import pymongo

        balance_col, tx_col = _mongo_collections()
        doc_id = _balance_doc_id(account)
        # Atomic check-and-deduct: the filter requires value >= amount, so a
        # concurrent request can never push the balance negative - either
        # this update matches and deducts, or it matches nothing and we know
        # the balance was insufficient at the moment of the attempt.
        result = balance_col.find_one_and_update(
            {"_id": doc_id, "value": {"$gte": amount}},
            {"$inc": {"value": -amount}},
            return_document=pymongo.ReturnDocument.AFTER,
        )
        if result is None:
            current = balance_col.find_one({"_id": doc_id})
            available = int(current["value"]) if current else 0
            raise InsufficientCreditsError(required=amount, available=available)

        tx_col.insert_one(
            {"delta": -amount, "reason": reason, "account": account, "created_at": datetime.now(timezone.utc)}
        )
        return amount

    with _sqlite_lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT COALESCE(SUM(delta), 0) FROM ledger WHERE account = ?", (account,)).fetchone()
        balance = int(row[0])
        if balance < amount:
            raise InsufficientCreditsError(required=amount, available=balance)
        conn.execute("INSERT INTO ledger (delta, reason, account) VALUES (?, ?, ?)", (-amount, reason, account))
        conn.commit()
    return amount


def add_credits(amount: int, *, reason: str, account: str = DEFAULT_ACCOUNT) -> int:
    """Top up the balance (e.g. after a verified Razorpay payment). Returns
    the new balance."""
    if amount <= 0:
        raise ValueError("amount must be positive")

    if _use_mongo():
        import pymongo

        balance_col, tx_col = _mongo_collections()
        result = balance_col.find_one_and_update(
            {"_id": _balance_doc_id(account)},
            {"$inc": {"value": amount}},
            upsert=True,
            return_document=pymongo.ReturnDocument.AFTER,
        )
        tx_col.insert_one(
            {"delta": amount, "reason": reason, "account": account, "created_at": datetime.now(timezone.utc)}
        )
        return int(result["value"])

    with _sqlite_lock, _sqlite_connect() as conn:
        conn.execute("INSERT INTO ledger (delta, reason, account) VALUES (?, ?, ?)", (amount, reason, account))
        conn.commit()
        row = conn.execute("SELECT COALESCE(SUM(delta), 0) FROM ledger WHERE account = ?", (account,)).fetchone()
        return int(row[0])
