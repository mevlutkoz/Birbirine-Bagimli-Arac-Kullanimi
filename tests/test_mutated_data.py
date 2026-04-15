"""Test: modified fraud-reason text is reflected in tool output.

Proves that the tools read from disk on every call (no caching).
The evaluator may change fraud_reasons.json at any time and the
system must use the new value.
"""

import json
from pathlib import Path

from tools.fraud_tools import check_fraud_reason
from tools.user_tools import get_user_details
from tools.transaction_tools import get_recent_transactions

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FRAUD_FILE = DATA_DIR / "fraud_reasons.json"


def _read_fraud_file() -> dict:
    with open(FRAUD_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_fraud_file(data: dict) -> None:
    with open(FRAUD_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def test_fraud_reason_reflects_file_change():
    """Modify fraud_reasons.json, call the tool, verify the new text."""

    original = _read_fraud_file()

    modified = original.copy()
    modified["TXN001"] = "CUSTOM REASON: account under manual review by compliance team"

    _write_fraud_file(modified)
    try:
        result = check_fraud_reason("TXN001")
        assert result["reason"] == "CUSTOM REASON: account under manual review by compliance team"
    finally:
        _write_fraud_file(original)

    # After restore, original text should be back
    result_after = check_fraud_reason("TXN001")
    assert result_after["reason"] == original["TXN001"]


def test_new_fraud_reason_added():
    """Add a brand-new entry; the tool should find it immediately."""

    original = _read_fraud_file()

    modified = original.copy()
    modified["TXN_NEW"] = "Blocked: test scenario injected by evaluator"

    _write_fraud_file(modified)
    try:
        result = check_fraud_reason("TXN_NEW")
        assert result["reason"] == "Blocked: test scenario injected by evaluator"
    finally:
        _write_fraud_file(original)


def test_user_data_reflects_file_change():
    """Proves user_tools also reads fresh data each time."""

    users_file = DATA_DIR / "users.json"
    with open(users_file, "r", encoding="utf-8") as f:
        original = json.load(f)

    modified = [u.copy() for u in original]
    modified.append({
        "email": "evaluator@test.com",
        "user_id": "USR_EVAL",
        "account_status": "active",
    })

    with open(users_file, "w", encoding="utf-8") as f:
        json.dump(modified, f, indent=2)

    try:
        result = get_user_details("evaluator@test.com")
        assert result["user_id"] == "USR_EVAL"
    finally:
        with open(users_file, "w", encoding="utf-8") as f:
            json.dump(original, f, indent=2)


def test_transactions_reflect_file_change():
    """Proves transaction_tools reads fresh data each time."""

    txn_file = DATA_DIR / "transactions.json"
    with open(txn_file, "r", encoding="utf-8") as f:
        original = json.load(f)

    modified = list(original)
    modified.append({
        "transaction_id": "TXN_EVAL",
        "user_id": "USR001",
        "amount": 9999.99,
        "status": "failed",
        "created_at": "2026-04-15T00:00:00Z",
    })

    with open(txn_file, "w", encoding="utf-8") as f:
        json.dump(modified, f, indent=2)

    try:
        txns = get_recent_transactions("USR001", limit=10)
        ids = [t["transaction_id"] for t in txns]
        assert "TXN_EVAL" in ids
        # TXN_EVAL should be first (most recent)
        assert txns[0]["transaction_id"] == "TXN_EVAL"
    finally:
        with open(txn_file, "w", encoding="utf-8") as f:
            json.dump(original, f, indent=2)
