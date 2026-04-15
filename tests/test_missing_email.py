"""Test: user asks about a rejection without providing an email.

The agent should ask for the email, then continue normally once provided.
"""

from conftest import MockLLMClient, MockResponse, make_text, make_tool_use
from agent.orchestrator import Orchestrator


def test_agent_asks_for_email_then_continues():
    """Turn 1: no email -> clarification.  Turn 2: email provided -> resolution."""

    responses = [
        # Turn 1 -- LLM notices no email and asks
        MockResponse(
            content=[
                make_text(
                    "I'd be happy to help you look into that. "
                    "Could you please provide me with the email address "
                    "associated with your account?"
                ),
            ],
            stop_reason="end_turn",
        ),
        # Turn 2 -- LLM resolves the full chain
        MockResponse(
            content=[make_tool_use("c1", "get_user_details", {"email": "ali@sirket.com"})],
            stop_reason="tool_use",
        ),
        MockResponse(
            content=[make_tool_use("c2", "get_recent_transactions", {"user_id": "USR001", "limit": 5})],
            stop_reason="tool_use",
        ),
        MockResponse(
            content=[make_tool_use("c3", "check_fraud_reason", {"transaction_id": "TXN001"})],
            stop_reason="tool_use",
        ),
        MockResponse(
            content=[make_text("Your payment was rejected due to unusual geographic activity.")],
            stop_reason="end_turn",
        ),
    ]

    client = MockLLMClient(responses)
    orch = Orchestrator(llm_client=client)

    # Turn 1 -- no email
    reply1 = orch.handle_message("Why was my payment rejected?")
    assert "email" in reply1.lower()
    assert orch.state.user_id is None  # nothing resolved yet

    # Turn 2 -- email provided
    reply2 = orch.handle_message("My email is ali@sirket.com")
    assert orch.state.user_id == "USR001"
    assert orch.state.selected_transaction_id == "TXN001"
    assert "rejected" in reply2.lower() or "unusual" in reply2.lower()


def test_conversation_history_spans_turns():
    """The second turn should include messages from the first turn."""

    responses = [
        MockResponse(content=[make_text("Please provide your email.")], stop_reason="end_turn"),
        MockResponse(
            content=[make_tool_use("c1", "get_user_details", {"email": "ali@sirket.com"})],
            stop_reason="tool_use",
        ),
        MockResponse(content=[make_text("Found your account.")], stop_reason="end_turn"),
    ]

    client = MockLLMClient(responses)
    orch = Orchestrator(llm_client=client)

    orch.handle_message("Why was my payment rejected?")
    orch.handle_message("ali@sirket.com")

    # The LLM should have seen the full history on the second-turn call
    second_turn_messages = client.call_history[1]  # messages sent on 2nd LLM call
    roles = [m["role"] for m in second_turn_messages]
    # Should have: user, assistant (turn 1), user (turn 2)
    assert roles.count("user") >= 2
    assert roles.count("assistant") >= 1
