"""
AnthropicEngine — Claude-backed implementation of the analytics chat engine.

Converts neutral TOOL_DEFINITIONS (JSON Schema) to Anthropic's wire format
(input_schema key) and runs the two-turn tool-use flow:

  Turn 1: user question → Claude selects tool + params
  Turn 2: KPI result → Claude generates natural language explanation

To switch providers, change AI_PROVIDER in .env. Nothing here needs to change.
"""

from __future__ import annotations

from typing import Any

import anthropic
import pandas as pd

from app.engine_tools import (
    CHART_SPECS,
    FOLLOW_UP_SUGGESTIONS,
    KPI_DISPATCH,
    SYSTEM_PROMPT,
    TOOL_DEFINITIONS,
    ChatResult,
    df_to_context,
)


# ── format conversion ─────────────────────────────────────────────────────────

def _to_anthropic_tools(
    tool_defs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Convert neutral tool definitions to Anthropic's wire format.

    Neutral:   {"name": ..., "description": ..., "parameters": <JSON Schema>}
    Anthropic: {"name": ..., "description": ..., "input_schema": <JSON Schema>}

    Only the key name changes. The JSON Schema content is identical.
    """
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        }
        for t in tool_defs
    ]


_ANTHROPIC_TOOLS = _to_anthropic_tools(TOOL_DEFINITIONS)


# ── engine ────────────────────────────────────────────────────────────────────

class AnthropicEngine:
    """
    Analytics chat engine backed by Anthropic Claude.

    Interface: .ask(question: str) -> ChatResult
    Same contract as GeminiEngine — the caller never knows which provider is running.
    """

    MODEL = "claude-sonnet-4-6"
    MAX_TOKENS = 1024

    def __init__(self, api_key: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)

    def ask(self, question: str, history: list[dict[str, str]] | None = None) -> ChatResult:
        messages: list[dict[str, Any]] = []
        if history:
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": question})

        # ── turn 1: Claude selects the tool ──────────────────────────────────
        response = self._client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=_ANTHROPIC_TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            text = self._extract_text(response)
            return ChatResult(text=text or "I couldn't find relevant data for that question.")

        tool_block = next(b for b in response.content if b.type == "tool_use")
        tool_name: str = tool_block.name
        tool_input: dict[str, Any] = tool_block.input

        # ── execute the KPI function ──────────────────────────────────────────
        fn = KPI_DISPATCH.get(tool_name)
        if fn is None:
            return ChatResult(
                text="I encountered an unknown analytics function.",
                error=f"Unknown tool: {tool_name}",
            )

        try:
            df: pd.DataFrame = fn(**tool_input)
        except Exception as exc:
            return ChatResult(
                text="I ran into a problem retrieving that data.",
                error=str(exc),
            )

        # ── turn 2: Claude explains the data ─────────────────────────────────
        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": df_to_context(df),
            }],
        })

        explanation = self._client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=_ANTHROPIC_TOOLS,
            messages=messages,
        )

        return ChatResult(
            text=self._extract_text(explanation),
            df=df,
            chart_spec=CHART_SPECS.get(tool_name),
            kpi_called=tool_name,
            follow_ups=FOLLOW_UP_SUGGESTIONS.get(tool_name, []),
        )

    @staticmethod
    def _extract_text(response: anthropic.types.Message) -> str:
        return next(
            (b.text for b in response.content if hasattr(b, "text")),
            "",
        )
