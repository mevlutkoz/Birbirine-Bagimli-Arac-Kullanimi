"""Thin wrapper around the Anthropic Messages API."""

import logging
import os
from typing import Any

import anthropic

from agent.prompts import SYSTEM_PROMPT
from tools.schemas import TOOL_DEFINITIONS

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"


class LLMClient:
    """Sends messages to Claude and returns raw API responses.

    The client owns the model, system prompt, and tool definitions.
    It does NOT interpret the response -- that is the orchestrator's job.
    """

    def __init__(self, model: str | None = None):
        self.client = anthropic.Anthropic()          # uses ANTHROPIC_API_KEY env var
        self.model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
        self.system_prompt = SYSTEM_PROMPT
        self.tools = TOOL_DEFINITIONS

    def chat(self, messages: list[dict]) -> Any:
        """Call the Messages API with the full conversation so far.

        Returns the raw ``anthropic.types.Message`` object so the caller
        can inspect ``stop_reason`` and ``content`` blocks.
        """
        logger.debug("LLM request: %d messages, model=%s", len(messages), self.model)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=self.system_prompt,
            tools=self.tools,
            messages=messages,
        )

        logger.debug(
            "LLM response: stop_reason=%s, content_blocks=%d",
            response.stop_reason,
            len(response.content),
        )
        return response
