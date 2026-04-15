"""Tool definitions for the Claude API tool-use interface."""

TOOL_DEFINITIONS = [
    {
        "name": "get_user_details",
        "description": (
            "Look up a user's account details by their email address. "
            "Returns user_id and account_status. Use this as the first step "
            "when you have a user's email and need to find their account."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "The email address of the user to look up.",
                }
            },
            "required": ["email"],
        },
    },
    {
        "name": "get_recent_transactions",
        "description": (
            "Get recent transactions for a user, sorted by date descending "
            "(most recent first). Requires a valid user_id obtained from "
            "get_user_details. Returns transaction_id, amount, status, and "
            "created_at for each transaction."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The user ID obtained from get_user_details.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of transactions to return.",
                },
            },
            "required": ["user_id", "limit"],
        },
    },
    {
        "name": "check_fraud_reason",
        "description": (
            "Check why a specific transaction was rejected or flagged by the "
            "fraud detection system. Requires a valid transaction_id obtained "
            "from get_recent_transactions. Only use this for failed/rejected "
            "transactions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {
                    "type": "string",
                    "description": "The ID of the failed transaction to check.",
                }
            },
            "required": ["transaction_id"],
        },
    },
]
