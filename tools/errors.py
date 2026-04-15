"""Custom exception classes for tool errors."""


class ToolError(Exception):
    """Base exception for all tool-related errors."""
    pass


class UserNotFoundError(ToolError):
    """Raised when no user matches the given email."""

    def __init__(self, email: str):
        self.email = email
        super().__init__(f"No user found with email: {email}")


class FraudReasonNotFoundError(ToolError):
    """Raised when no fraud reason exists for a transaction."""

    def __init__(self, transaction_id: str):
        self.transaction_id = transaction_id
        super().__init__(f"No fraud reason found for transaction: {transaction_id}")
