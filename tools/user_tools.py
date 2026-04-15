"""User lookup tool. Reads from data/users.json on every call."""

import json
from pathlib import Path

from tools.errors import UserNotFoundError

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def get_user_details(email: str) -> dict:
    """Look up a user by email.

    Returns:
        dict with user_id and account_status.

    Raises:
        UserNotFoundError: if no user matches the email.
    """
    with open(DATA_DIR / "users.json", "r", encoding="utf-8") as f:
        users = json.load(f)

    for user in users:
        if user["email"].lower() == email.lower():
            return {
                "user_id": user["user_id"],
                "account_status": user["account_status"],
            }

    raise UserNotFoundError(email)
