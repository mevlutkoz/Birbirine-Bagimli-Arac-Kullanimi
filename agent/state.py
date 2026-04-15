"""Agent state management for multi-turn conversations."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentState:
    """Tracks all context the agent accumulates across turns and tool calls.

    The orchestrator reads and writes this state.  The LLM never sees the
    Python object directly -- it receives tool results via messages -- but the
    orchestration layer uses these fields to enforce preconditions and log
    progress.
    """

    # Conversation
    conversation_history: list[dict] = field(default_factory=list)
    current_user_message: str = ""

    # User info (populated by get_user_details)
    email: Optional[str] = None
    user_id: Optional[str] = None
    account_status: Optional[str] = None

    # Transaction info (populated by get_recent_transactions)
    candidate_transactions: list[dict] = field(default_factory=list)

    # Selection (populated by check_fraud_reason)
    selected_transaction_id: Optional[str] = None

    # Latest results
    last_tool_result: Optional[dict[str, Any]] = None
    final_answer: Optional[str] = None
    error: Optional[str] = None

    def summary(self) -> dict[str, Any]:
        """Compact snapshot for logging."""
        return {
            "email": self.email,
            "user_id": self.user_id,
            "account_status": self.account_status,
            "num_candidate_transactions": len(self.candidate_transactions),
            "selected_transaction_id": self.selected_transaction_id,
            "has_error": self.error is not None,
        }
