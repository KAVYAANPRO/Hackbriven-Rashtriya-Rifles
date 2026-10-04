from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.core import credits
from backend.models.schemas import MotionTier


@pytest.fixture(autouse=True)
def _isolated_sqlite_storage(tmp_path: Path):
    with patch("backend.core.credits.settings") as mock_settings:
        mock_settings.storage_path = tmp_path
        mock_settings.mongodb_uri = ""  # force the SQLite path by default
        yield tmp_path


def test_balance_starts_at_zero():
    assert credits.get_balance() == 0


def test_add_credits_increases_balance():
    new_balance = credits.add_credits(50, reason="test topup")
    assert new_balance == 50
    assert credits.get_balance() == 50


def test_add_credits_rejects_non_positive_amount():
    with pytest.raises(ValueError):
        credits.add_credits(0, reason="x")
    with pytest.raises(ValueError):
        credits.add_credits(-5, reason="x")


def test_charge_deducts_tier_cost():
    credits.add_credits(100, reason="seed")
    charged = credits.charge(MotionTier.BASIC, reason="job")
    assert charged == credits.cost_for_tier(MotionTier.BASIC)
    assert credits.get_balance() == 100 - charged


def test_charge_raises_when_insufficient_and_does_not_deduct():
    credits.add_credits(1, reason="seed")
    with pytest.raises(credits.InsufficientCreditsError) as exc_info:
        credits.charge(MotionTier.MAX, reason="job")

    assert exc_info.value.available == 1
    assert exc_info.value.required == credits.cost_for_tier(MotionTier.MAX)
    assert credits.get_balance() == 1  # unchanged - nothing was deducted


def test_balance_persists_across_connections(tmp_path: Path):
    credits.add_credits(30, reason="seed")
    # Every ledger function opens a fresh sqlite3 connection via _connect()
    # rather than caching in a Python-level variable, so re-reading the
    # balance proves it's coming from the on-disk file, not an in-process
    # cache that a real process restart would lose.
    assert credits.get_balance() == 30


# --- MongoDB backend (used when MONGODB_URI is configured) ---


@pytest.fixture(autouse=False)
def _mongo_mode():
    from unittest.mock import MagicMock

    with patch("backend.core.credits.settings") as mock_settings, \
         patch("backend.core.credits._mongo_collections") as mock_collections:
        mock_settings.mongodb_uri = "mongodb://fake"
        mock_settings.mongodb_db_name = "testdb"
        balance_col, tx_col = MagicMock(), MagicMock()
        mock_collections.return_value = (balance_col, tx_col)
        yield balance_col, tx_col


def test_mongo_get_balance_returns_zero_when_no_document(_mongo_mode):
    balance_col, _ = _mongo_mode
    balance_col.find_one.return_value = None
    assert credits.get_balance() == 0


def test_mongo_get_balance_reads_value_field(_mongo_mode):
    balance_col, _ = _mongo_mode
    balance_col.find_one.return_value = {"_id": "balance", "value": 77}
    assert credits.get_balance() == 77


def test_mongo_charge_uses_atomic_conditional_update(_mongo_mode):
    balance_col, tx_col = _mongo_mode
    balance_col.find_one_and_update.return_value = {"_id": "balance", "value": 96}

    charged = credits.charge(MotionTier.BASIC, reason="job")

    assert charged == credits.cost_for_tier(MotionTier.BASIC)
    filter_arg = balance_col.find_one_and_update.call_args[0][0]
    assert filter_arg == {"_id": "balance", "value": {"$gte": charged}}
    tx_col.insert_one.assert_called_once()


def test_mongo_charge_raises_when_conditional_update_matches_nothing(_mongo_mode):
    balance_col, tx_col = _mongo_mode
    balance_col.find_one_and_update.return_value = None  # filter didn't match -> insufficient
    balance_col.find_one.return_value = {"_id": "balance", "value": 2}

    with pytest.raises(credits.InsufficientCreditsError) as exc_info:
        credits.charge(MotionTier.MAX, reason="job")

    assert exc_info.value.available == 2
    tx_col.insert_one.assert_not_called()


def test_mongo_add_credits_upserts_and_increments(_mongo_mode):
    balance_col, tx_col = _mongo_mode
    balance_col.find_one_and_update.return_value = {"_id": "balance", "value": 50}

    new_balance = credits.add_credits(50, reason="razorpay:pay_1")

    assert new_balance == 50
    kwargs = balance_col.find_one_and_update.call_args
    assert kwargs[1]["upsert"] is True
    tx_col.insert_one.assert_called_once()
