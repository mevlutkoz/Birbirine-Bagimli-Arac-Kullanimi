"""Test: user has multiple failed transactions -- agent should ask for clarification.

USR002 (ayse@firma.com) has two failed transactions: TXN003 and TXN004.
The LLM should present both and ask which one the user means.
"""

from conftest import MockLLMClient, MockResponse, make_text, make_tool_use
from agent.orchestrator import Orchestrator


def test_multiple_failed_triggers_clarification():
    """Agent lists candidates and asks instead of silently picking one."""

    responses = [
        # 1. Look up user
        MockResponse(
            content=[make_tool_use("c1", "get_user_details", {"email": "ayse@firma.com"})],
            stop_reason="tool_use",
        ),
        # 2. Fetch transactions
        MockResponse(
            content=[make_tool_use("c2", "get_recent_transactions", {"user_id": "USR002", "limit": 10})],
            stop_reason="tool_use",
        ),
        # 3. LLM sees two failed txns and asks for clarification
        MockResponse(
            content=[
                make_text(
                    "I found two failed transactions on your account:\n\n"
                    "1. TXN003 -- 5,000.00 TL on April 14 at 09:15\n"
                    "2. TXN004 -- 300.00 TL on April 14 at 11:45\n\n"
                    "Which one would you like me to investigate?"
                ),
            ],
            stop_reason="end_turn",
        ),
    ]

    client = MockLLMClient(responses)
    orch = Orchestrator(llm_client=client)

    answer = orch.handle_message(
        "Why was my payment rejected? My email is ayse@firma.com"
    )

    # State should have multiple candidate transactions
    failed = [t for t in orch.state.candidate_transactions if t["status"] == "failed"]
    assert len(failed) == 2

    # No transaction should have been selected yet
    assert orch.state.selected_transaction_id is None

    # Answer should mention both candidates
    assert "TXN003" in answer or "5,000" in answer or "5000" in answer
    assert "TXN004" in answer or "300" in answer


def test_clarification_then_resolution():
    """After the user clarifies, the agent resolves the chosen transaction."""

    responses = [
        # Turn 1: discover user and transactions
        MockResponse(
            content=[make_tool_use("c1", "get_user_details", {"email": "ayse@firma.com"})],
            stop_reason="tool_use",
        ),
        MockResponse(
            content=[make_tool_use("c2", "get_recent_transactions", {"user_id": "USR002", "limit": 10})],
            stop_reason="tool_use",
        ),
        MockResponse(
            content=[make_text("I found two failed transactions. Which one?")],
            stop_reason="end_turn",
        ),
        # Turn 2: user picks TXN004 -> check fraud reason -> answer
        MockResponse(
            content=[make_tool_use("c3", "check_fraud_reason", {"transaction_id": "TXN004"})],
            stop_reason="tool_use",
        ),
        MockResponse(
            content=[
                make_text(
                    "Your 300 TL transaction (TXN004) was declined because it "
                    "exceeded your daily transaction limit of 2000 TL."
                ),
            ],
            stop_reason="end_turn",
        ),
    ]

    client = MockLLMClient(responses)
    orch = Orchestrator(llm_client=client)

    # Turn 1
    orch.handle_message("Why was my payment rejected? Email: ayse@firma.com")
    assert orch.state.selected_transaction_id is None

    # Turn 2
    answer = orch.handle_message("The 300 TL one")
    assert orch.state.selected_transaction_id == "TXN004"
    assert "limit" in answer.lower() or "2000" in answer
