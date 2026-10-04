from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from backend.config import settings

"""Tiny document store for accounts and payment orders.

Same two-mode pattern as the credits ledger: MongoDB when MONGODB_URI is set
(durable on an ephemeral host), otherwise a local SQLite file. Mongo
collections are prefixed `ideafeed_` on purpose - the database this app
shares may already hold other applications' `users`/`orders` collections.
"""

_SQLITE_FILENAME = "accounts.db"
_sqlite_lock = threading.Lock()
_mongo_client = None


def _use_mongo() -> bool:
    return bool(settings.mongodb_uri)


def _mongo_collection(coll: str):
    global _mongo_client
    if _mongo_client is None:
        import pymongo

        _mongo_client = pymongo.MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=10000)
    return _mongo_client[settings.mongodb_db_name][f"ideafeed_{coll}"]


def _sqlite_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.storage_path / _SQLITE_FILENAME, timeout=15)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS docs (coll TEXT NOT NULL, id TEXT NOT NULL, doc TEXT NOT NULL, PRIMARY KEY (coll, id))"
    )
    return conn


def insert(coll: str, doc_id: str, doc: dict[str, Any]) -> bool:
    """Insert only if the id is free. False means it already existed."""
    if _use_mongo():
        import pymongo

        try:
            _mongo_collection(coll).insert_one({"_id": doc_id, **doc})
            return True
        except pymongo.errors.DuplicateKeyError:
            return False
    with _sqlite_lock, _sqlite_connect() as conn:
        try:
            conn.execute("INSERT INTO docs (coll, id, doc) VALUES (?, ?, ?)", (coll, doc_id, json.dumps(doc)))
        except sqlite3.IntegrityError:
            return False
        return True


def get(coll: str, doc_id: str) -> dict[str, Any] | None:
    if _use_mongo():
        found = _mongo_collection(coll).find_one({"_id": doc_id})
        if found is None:
            return None
        found.pop("_id", None)
        return found
    with _sqlite_lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT doc FROM docs WHERE coll = ? AND id = ?", (coll, doc_id)).fetchone()
    return json.loads(row[0]) if row else None


def delete(coll: str, doc_id: str) -> bool:
    if _use_mongo():
        return _mongo_collection(coll).delete_one({"_id": doc_id}).deleted_count > 0
    with _sqlite_lock, _sqlite_connect() as conn:
        return conn.execute("DELETE FROM docs WHERE coll = ? AND id = ?", (coll, doc_id)).rowcount > 0


def update(coll: str, doc_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    """Merge `fields` into an existing document; returns the new document, or None if it doesn't exist."""
    return claim(coll, doc_id, {}, fields)


def claim(coll: str, doc_id: str, expect: dict[str, Any], set_fields: dict[str, Any]) -> dict[str, Any] | None:
    """Atomic compare-and-set: apply `set_fields` only if every key in
    `expect` currently has the expected value. Returns the updated document,
    or None when the document is missing or the precondition didn't hold.
    This is what makes "mark this order paid exactly once" safe under
    concurrent/replayed requests."""
    if _use_mongo():
        import pymongo

        updated = _mongo_collection(coll).find_one_and_update(
            {"_id": doc_id, **expect},
            {"$set": set_fields},
            return_document=pymongo.ReturnDocument.AFTER,
        )
        if updated is None:
            return None
        updated.pop("_id", None)
        return updated
    with _sqlite_lock, _sqlite_connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT doc FROM docs WHERE coll = ? AND id = ?", (coll, doc_id)).fetchone()
        if row is None:
            return None
        doc = json.loads(row[0])
        if any(doc.get(k) != v for k, v in expect.items()):
            return None
        doc.update(set_fields)
        conn.execute("UPDATE docs SET doc = ? WHERE coll = ? AND id = ?", (json.dumps(doc), coll, doc_id))
        return doc
