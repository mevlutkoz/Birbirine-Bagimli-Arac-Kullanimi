"""Response formatting and state-update helpers.

The responder translates raw tool results into strings that go back to the
LLM, and keeps the AgentState in sync with what has been learned so far.
"""

import json
import logging
from typing import Any

from agent.state import AgentState

logger = logging.getLogger(__name__)


def format_tool_result(tool_name: str, result: dict[str, Any]) -> str:
    """Serialize a guarded_dispatch result dict for inclusion in a tool_result message."""
    return json.dumps(result, indent=2, default=str)


def update_state_from_tool(
    state: AgentState,
    tool_name: str,
    result: dict[str, Any],
    tool_args: dict[str, Any] | None = None,
) -> None:
    """Update agent state based on a successful (or failed) tool execution.

    This keeps the orchestration layer's view of the world current so that
    precondition checks and logging remain accurate.

    ``tool_args`` is optional and used to capture inputs that aren't echoed
    back in the result (e.g. the email address passed to get_user_details).
    """
    state.last_tool_result = result

    if not result.get("success"):
        state.error = result.get("error")
        return

    # Clear previous error on success
    state.error = None
    data = result.get("data")

    if tool_name == "get_user_details" and data:
        state.user_id = data.get("user_id")
        state.account_status = data.get("account_status")
        if tool_args:
            state.email = tool_args.get("email")
        logger.info(
            "State: email=%s, user_id=%s, account_status=%s",
            state.email,
            state.user_id,
            state.account_status,
        )

    elif tool_name == "get_recent_transactions" and isinstance(data, list):
        state.candidate_transactions = data
        failed = [t for t in data if t.get("status") == "failed"]
        logger.info(
            "State: %d transactions fetched, %d failed",
            len(data),
            len(failed),
        )

    elif tool_name == "check_fraud_reason" and data:
        state.selected_transaction_id = data.get("transaction_id")
        logger.info(
            "State: fraud reason retrieved for %s",
            state.selected_transaction_id,
        )
