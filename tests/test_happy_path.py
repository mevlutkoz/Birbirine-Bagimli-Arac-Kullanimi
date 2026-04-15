"""Happy-path test: email -> user -> transactions -> fraud reason -> answer.

Verifies that the orchestrator correctly chains tool calls driven by the
(mocked) LLM and that agent state is updated at each step.
"""

from conftest import MockLLMClient, MockResponse, make_text, make_tool_use
from agent.orchestrator import Orchestrator


def test_happy_path_full_chain():
    """The LLM resolves email -> user_id -> transactions -> fraud reason."""

    responses = [
        # 1. LLM decides to look up the user
        MockResponse(
            content=[
                make_tool_use("call_1", "get_user_details", {"email": "ali@sirket.com"}),
            ],
            stop_reason="tool_use",
        ),
        # 2. LLM fetches recent transactions
        MockResponse(
            content=[
                make_tool_use("call_2", "get_recent_transactions", {"user_id": "USR001", "limit": 5}),
            ],
            stop_reason="tool_use",
        ),
        # 3. LLM picks the failed transaction and checks the fraud reason
        MockResponse(
            content=[
                make_tool_use("call_3", "check_fraud_reason", {"transaction_id": "TXN001"}),
            ],
            stop_reason="tool_use",
        ),
        # 4. LLM composes a final answer
        MockResponse(
            content=[
                make_text(
                    "Your payment of 1,500.00 TL on April 14 was rejected because "
                    "our fraud detection system flagged an unusual spending pattern "
                    "outside your normal geographic region."
                ),
            ],
            stop_reason="end_turn",
        ),
    ]

    client = MockLLMClient(responses)
    orch = Orchestrator(llm_client=client)

    answer = orch.handle_message(
        "Why was the payment I tried to make yesterday with ali@sirket.com rejected?"
    )

    # Verify state was built up correctly
    assert orch.state.user_id == "USR001"
    assert orch.state.account_status == "active"
    assert len(orch.state.candidate_transactions) > 0
    assert orch.state.selected_transaction_id == "TXN001"

    # Verify all four LLM calls were made
    assert client.call_count == 4

    # Verify the final answer was returned
    assert "unusual spending pattern" in answer


def test_happy_path_state_persists_across_turns():
    """After the first turn resolves the user, a follow-up can reuse state."""

    turn1_responses = [
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
            content=[make_text("Your payment was rejected due to unusual activity.")],
            stop_reason="end_turn",
        ),
    ]

    turn2_responses = [
        MockResponse(
            content=[make_text("Your account status is currently active.")],
            stop_reason="end_turn",
        ),
    ]

    client = MockLLMClient(turn1_responses + turn2_responses)
    orch = Orchestrator(llm_client=client)

    orch.handle_message("Why was my payment with ali@sirket.com rejected?")
    assert orch.state.user_id == "USR001"

    answer2 = orch.handle_message("What is my account status?")
    assert "active" in answer2.lower()

    # Conversation history should span both turns
    assert len(orch.state.conversation_history) > 4
