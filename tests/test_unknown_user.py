"""Test: user provides an email that does not exist in the database.

The tool raises UserNotFoundError; the orchestrator catches it and the LLM
responds naturally.
"""

from conftest import MockLLMClient, MockResponse, make_text, make_tool_use
from agent.orchestrator import Orchestrator
from agent.selector import guarded_dispatch
from agent.state import AgentState
from tools.errors import UserNotFoundError

import pytest


def test_unknown_email_via_orchestrator():
    """Full orchestrator run: tool errors are fed back; LLM explains."""

    responses = [
        # LLM tries to look up the unknown email
        MockResponse(
            content=[make_tool_use("c1", "get_user_details", {"email": "bilinmeyen@test.com"})],
            stop_reason="tool_use",
        ),
        # LLM receives the error and informs the user
        MockResponse(
            content=[
                make_text(
                    "I'm sorry, I couldn't find an account associated with "
                    "bilinmeyen@test.com. Please double-check the email address "
                    "and try again."
                ),
            ],
            stop_reason="end_turn",
        ),
    ]

    client = MockLLMClient(responses)
    orch = Orchestrator(llm_client=client)

    answer = orch.handle_message("Why was my payment rejected? Email: bilinmeyen@test.com")

    # State should NOT have a user_id
    assert orch.state.user_id is None

    # LLM should have been called twice (tool call + error explanation)
    assert client.call_count == 2

    # Error should have been recorded
    assert orch.state.error is not None
    assert "bilinmeyen@test.com" in answer


def test_unknown_email_guarded_dispatch():
    """Direct dispatch test: UserNotFoundError -> structured error result."""

    state = AgentState()
    result = guarded_dispatch("get_user_details", {"email": "yok@yok.com"}, state)

    assert result["success"] is False
    assert "yok@yok.com" in result["error"]


def test_user_not_found_error_directly():
    """The tool itself raises UserNotFoundError."""
    from tools.user_tools import get_user_details

    with pytest.raises(UserNotFoundError):
        get_user_details("does-not-exist@example.com")


def test_malformed_email():
    """A malformed email that matches no record still returns a structured error."""

    state = AgentState()
    result = guarded_dispatch("get_user_details", {"email": "not-an-email"}, state)

    assert result["success"] is False
    assert "not-an-email" in result["error"]
