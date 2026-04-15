"""Guarded tool dispatch -- validates preconditions and catches errors.

This module is the thin safety net between the LLM's tool-call decisions
and actual execution.  It does NOT decide *which* tool to call -- that is
the LLM's job.  It only verifies that the call is safe to execute and
returns a structured result either way.
"""

import logging
from typing import Any, Callable

from agent.state import AgentState
from tools.errors import ToolError
from tools.fraud_tools import check_fraud_reason
from tools.transaction_tools import get_recent_transactions
from tools.user_tools import get_user_details

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, Callable[..., Any]] = {
    "get_user_details": get_user_details,
    "get_recent_transactions": get_recent_transactions,
    "check_fraud_reason": check_fraud_reason,
}

# ---------------------------------------------------------------------------
# Precondition checks
# Each returns (ok: bool, message: str).
# ---------------------------------------------------------------------------

PreconditionCheck = Callable[[dict, AgentState], tuple[bool, str]]


def _check_user_details(args: dict, state: AgentState) -> tuple[bool, str]:
    email = args.get("email")
    if not email or not isinstance(email, str) or email.strip() == "":
        return False, (
            "Cannot look up user: email is required. "
            "Ask the user for their email address."
        )
    return True, ""


def _check_recent_transactions(args: dict, state: AgentState) -> tuple[bool, str]:
    uid = args.get("user_id")
    if not uid or not isinstance(uid, str) or uid.strip() == "":
        return False, (
            "Cannot fetch transactions: user_id is required. "
            "Call get_user_details first to obtain a user_id from an email address."
        )
    return True, ""


def _check_fraud_reason(args: dict, state: AgentState) -> tuple[bool, str]:
    tid = args.get("transaction_id")
    if not tid or not isinstance(tid, str) or tid.strip() == "":
        return False, (
            "Cannot check fraud reason: transaction_id is required. "
            "Call get_recent_transactions first to identify the relevant transaction."
        )
    return True, ""


PRECONDITIONS: dict[str, PreconditionCheck] = {
    "get_user_details": _check_user_details,
    "get_recent_transactions": _check_recent_transactions,
    "check_fraud_reason": _check_fraud_reason,
}

# ---------------------------------------------------------------------------
# Guarded dispatch
# ---------------------------------------------------------------------------


def guarded_dispatch(
    tool_name: str,
    args: dict,
    state: AgentState,
) -> dict[str, Any]:
    """Execute a tool call with precondition validation and error handling.

    Returns a dict of the form::

        {"success": True,  "data": <tool output>}
        {"success": False, "error": "<human-readable message>"}

    The orchestrator feeds this dict back to the LLM as a tool_result so
    it can decide how to proceed.
    """
    logger.info("Dispatch: %s(%s)", tool_name, args)

    # 1. Unknown tool
    if tool_name not in TOOL_REGISTRY:
        msg = f"Unknown tool: {tool_name}"
        logger.error(msg)
        return {"success": False, "error": msg}

    # 2. Precondition check
    if tool_name in PRECONDITIONS:
        ok, msg = PRECONDITIONS[tool_name](args, state)
        if not ok:
            logger.warning("Precondition failed for %s: %s", tool_name, msg)
            return {"success": False, "error": msg}

    # 3. Execute
    try:
        result = TOOL_REGISTRY[tool_name](**args)
        logger.info("Tool %s succeeded", tool_name)
        return {"success": True, "data": result}
    except ToolError as exc:
        logger.warning("Tool %s raised ToolError: %s", tool_name, exc)
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        logger.error("Tool %s raised unexpected error: %s", tool_name, exc, exc_info=True)
        return {"success": False, "error": f"Internal error while calling {tool_name}: {exc}"}
