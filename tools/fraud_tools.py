"""Fraud reason lookup tool. Reads from data/fraud_reasons.json on every call."""

import json
from pathlib import Path

from tools.errors import FraudReasonNotFoundError

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def check_fraud_reason(transaction_id: str) -> dict:
    """Check why a transaction was rejected.

    Returns:
        dict with transaction_id and reason.

    Raises:
        FraudReasonNotFoundError: if no reason exists for the transaction.
    """
    with open(DATA_DIR / "fraud_reasons.json", "r", encoding="utf-8") as f:
        reasons = json.load(f)

    if transaction_id not in reasons:
        raise FraudReasonNotFoundError(transaction_id)

    return {
        "transaction_id": transaction_id,
        "reason": reasons[transaction_id],
    }
