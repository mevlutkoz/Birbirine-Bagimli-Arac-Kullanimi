"""Transaction lookup tool. Reads from data/transactions.json on every call."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def get_recent_transactions(user_id: str, limit: int) -> list[dict]:
    """Get recent transactions for a user, sorted by created_at descending.

    Returns:
        List of transaction dicts, each containing transaction_id, amount,
        status, and created_at.
    """
    with open(DATA_DIR / "transactions.json", "r", encoding="utf-8") as f:
        all_transactions = json.load(f)

    user_txns = [t for t in all_transactions if t["user_id"] == user_id]
    user_txns.sort(key=lambda t: t["created_at"], reverse=True)

    return [
        {
            "transaction_id": t["transaction_id"],
            "amount": t["amount"],
            "status": t["status"],
            "created_at": t["created_at"],
        }
        for t in user_txns[:limit]
    ]
