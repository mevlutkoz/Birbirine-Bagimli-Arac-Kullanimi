"""Shared test utilities -- mock LLM client and content-block helpers.

These mocks let us test the orchestration layer deterministically without
making real API calls.  The mock objects expose the same attributes that the
Anthropic SDK response objects do (``type``, ``text``, ``name``, ``input``,
``id``, ``stop_reason``, ``content``, ``model_dump``).
"""

import sys
import os
from typing import Any

# Ensure the project root is on sys.path so ``from agent...`` and
# ``from tools...`` imports work regardless of how pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# --------------------------------------------------------------------------
# Mock content blocks
# --------------------------------------------------------------------------

class MockBlock:
    """Lightweight stand-in for ``anthropic.types.TextBlock`` /
    ``anthropic.types.ToolUseBlock``."""

    def __init__(self, **kwargs: Any):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def model_dump(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


def make_text(text: str) -> MockBlock:
    """Create a mock TextBlock."""
    return MockBlock(type="text", text=text)


def make_tool_use(tool_use_id: str, name: str, input_data: dict) -> MockBlock:
    """Create a mock ToolUseBlock."""
    return MockBlock(type="tool_use", id=tool_use_id, name=name, input=input_data)


# --------------------------------------------------------------------------
# Mock response
# --------------------------------------------------------------------------

class MockResponse:
    """Mimics ``anthropic.types.Message``."""

    def __init__(self, content: list[MockBlock], stop_reason: str):
        self.content = content
        self.stop_reason = stop_reason


# --------------------------------------------------------------------------
# Mock LLM client
# --------------------------------------------------------------------------

class MockLLMClient:
    """Returns a predetermined sequence of responses, one per ``chat`` call.

    Useful for scripting the exact LLM behavior so we can verify the
    orchestrator's dispatch, state updates, and error handling in isolation.
    """

    def __init__(self, responses: list[MockResponse]):
        self._responses = list(responses)
        self.call_count: int = 0
        self.call_history: list[list[dict]] = []

    def chat(self, messages: list[dict]) -> MockResponse:
        # Shallow-copy message list for forensics
        self.call_history.append(list(messages))

        if self.call_count >= len(self._responses):
            raise RuntimeError(
                f"MockLLMClient exhausted: {self.call_count} calls made, "
                f"only {len(self._responses)} responses configured."
            )
        response = self._responses[self.call_count]
        self.call_count += 1
        return response
