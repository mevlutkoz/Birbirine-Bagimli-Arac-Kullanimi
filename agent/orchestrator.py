"""Core agent loop -- bridges the LLM decision layer and the execution layer.

The orchestrator:
  1. Accepts a user message.
  2. Feeds it (with history) to the LLM.
  3. If the LLM requests a tool call, runs it through guarded_dispatch.
  4. Feeds the tool result back to the LLM.
  5. Repeats until the LLM emits a final text answer.

It does NOT decide which tool to call or what to say -- those are the
LLM's responsibilities.  It only enforces execution safety and tracks state.
"""

import json
import logging
from typing import Any, Optional

from agent.llm_client import LLMClient
from agent.responder import format_tool_result, update_state_from_tool
from agent.selector import guarded_dispatch
from agent.state import AgentState

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 10  # safety limit to avoid infinite loops


class Orchestrator:
    """Multi-turn agent orchestrator."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
        self.state = AgentState()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_message(self, user_message: str) -> str:
        """Process one user turn and return the agent's text response.

        May execute multiple internal LLM + tool cycles before returning.
        """
        logger.info("=" * 60)
        logger.info("USER: %s", user_message)

        # Update state
        self.state.current_user_message = user_message
        self.state.final_answer = None
        self.state.error = None

        # Append to conversation history
        self.state.conversation_history.append({
            "role": "user",
            "content": user_message,
        })

        logger.info("State before loop: %s", self.state.summary())

        # --- Agent loop ---------------------------------------------------
        for iteration in range(1, MAX_ITERATIONS + 1):
            logger.info("--- Iteration %d ---", iteration)

            # Call LLM
            try:
                response = self.llm_client.chat(self.state.conversation_history)
            except Exception as exc:
                logger.error("LLM call failed: %s", exc, exc_info=True)
                self.state.error = str(exc)
                return (
                    "I'm sorry, I'm having trouble processing your request "
                    "right now. Please try again later."
                )

            stop_reason = response.stop_reason

            # ----- Final answer or clarification --------------------------
            if stop_reason == "end_turn":
                text = self._extract_text(response.content)
                self.state.conversation_history.append({
                    "role": "assistant",
                    "content": self._serialize_content(response.content),
                })
                self.state.final_answer = text
                logger.info("AGENT: %s", text)
                return text

            # ----- Tool use -----------------------------------------------
            if stop_reason == "tool_use":
                # Store the full assistant message (may contain text + tool_use blocks)
                self.state.conversation_history.append({
                    "role": "assistant",
                    "content": self._serialize_content(response.content),
                })

                # Execute each tool_use block
                tool_results: list[dict] = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name: str = block.name
                    tool_args: dict = block.input
                    tool_use_id: str = block.id

                    logger.info(
                        "Tool call: %s(%s) [id=%s]",
                        tool_name,
                        json.dumps(tool_args),
                        tool_use_id,
                    )

                    result = guarded_dispatch(tool_name, tool_args, self.state)
                    update_state_from_tool(self.state, tool_name, result, tool_args=tool_args)

                    logger.info("Tool result: %s", json.dumps(result, default=str))

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": format_tool_result(tool_name, result),
                    })

                # Feed tool results back as the next user message
                self.state.conversation_history.append({
                    "role": "user",
                    "content": tool_results,
                })

                logger.info("State after tools: %s", self.state.summary())
                continue  # next iteration

            # ----- Unexpected stop reason ---------------------------------
            logger.warning("Unexpected stop_reason: %s", stop_reason)
            text = self._extract_text(response.content)
            if text:
                self.state.conversation_history.append({
                    "role": "assistant",
                    "content": self._serialize_content(response.content),
                })
                return text

        # Max iterations exhausted
        logger.error("Max iterations (%d) reached", MAX_ITERATIONS)
        return (
            "I'm sorry, I wasn't able to resolve your request within the "
            "expected number of steps. Could you please rephrase or simplify "
            "your question?"
        )

    def reset(self) -> None:
        """Start a fresh conversation."""
        self.state = AgentState()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(content: list) -> str:
        """Pull plain text from a list of content blocks."""
        parts: list[str] = []
        for block in content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts) if parts else ""

    @staticmethod
    def _serialize_content(content: list) -> list[dict]:
        """Convert API content blocks to plain dicts for message history."""
        serialized: list[dict] = []
        for block in content:
            if hasattr(block, "model_dump"):
                serialized.append(block.model_dump())
            elif isinstance(block, dict):
                serialized.append(block)
            else:
                # Fallback for mock objects in tests
                serialized.append(
                    {k: v for k, v in vars(block).items() if not k.startswith("_")}
                )
        return serialized
