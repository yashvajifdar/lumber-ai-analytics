"""
GeminiEngine — Google Gemini-backed implementation of the analytics chat engine.

Converts neutral TOOL_DEFINITIONS (JSON Schema) to Gemini's wire format
(types.FunctionDeclaration) and runs the two-turn function-calling flow:

  Turn 1: user question → Gemini selects function + params
  Turn 2: KPI result → Gemini generates natural language explanation

To switch providers, change AI_PROVIDER in .env. Nothing here needs to change.
Free tier available at aistudio.google.com.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from google import genai
from google.genai import types

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

_GENAI_TYPE_MAP = {
    "string":  types.Type.STRING,
    "integer": types.Type.INTEGER,
    "number":  types.Type.NUMBER,
    "boolean": types.Type.BOOLEAN,
    "array":   types.Type.ARRAY,
    "object":  types.Type.OBJECT,
}


def _json_schema_to_gemini(schema: dict[str, Any]) -> types.Schema:
    """Recursively convert a JSON Schema dict to a Gemini types.Schema."""
    schema_type = _GENAI_TYPE_MAP.get(schema.get("type", "string"), types.Type.STRING)
    properties = {
        name: types.Schema(
            type=_GENAI_TYPE_MAP.get(prop.get("type", "string"), types.Type.STRING),
            description=prop.get("description", ""),
            enum=prop.get("enum"),
        )
        for name, prop in schema.get("properties", {}).items()
    }
    return types.Schema(
        type=schema_type,
        properties=properties or None,
        required=schema.get("required") or None,
    )


def _to_gemini_tools(
    tool_defs: list[dict[str, Any]],
) -> list[types.Tool]:
    """
    Convert neutral tool definitions to Gemini's wire format.

    Neutral: {"name": ..., "description": ..., "parameters": <JSON Schema>}
    Gemini:  types.Tool(function_declarations=[types.FunctionDeclaration(...)])
    """
    declarations = [
        types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=_json_schema_to_gemini(t["parameters"]),
        )
        for t in tool_defs
    ]
    return [types.Tool(function_declarations=declarations)]


_GEMINI_TOOLS = _to_gemini_tools(TOOL_DEFINITIONS)


# ── engine ────────────────────────────────────────────────────────────────────

class GeminiEngine:
    """
    Analytics chat engine backed by Google Gemini.

    Interface: .ask(question: str) -> ChatResult
    Same contract as AnthropicEngine — the caller never knows which provider is running.
    """

    MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=_GEMINI_TOOLS,
            max_output_tokens=1024,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True  # manual loop — mirrors AnthropicEngine behaviour
            ),
        )

    def ask(self, question: str, history: list[dict[str, str]] | None = None) -> ChatResult:
        # ── turn 1: Gemini selects the function ──────────────────────────────
        contents: list[Any] = []
        if history:
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=question)]))

        response = self._client.models.generate_content(
            model=self.MODEL,
            contents=contents,
            config=self._config,
        )

        fn_call = self._extract_function_call(response)
        if fn_call is None:
            return ChatResult(
                text=self._extract_text(response)
                     or "I couldn't find relevant data for that question."
            )

        tool_name: str = fn_call.name
        tool_input: dict[str, Any] = dict(fn_call.args) if fn_call.args else {}

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

        # ── turn 2: Gemini explains the result ───────────────────────────────
        conversation: list[Any] = []
        if history:
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                conversation.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
        conversation.extend([
            types.Content(role="user", parts=[types.Part(text=question)]),
            response.candidates[0].content,
            types.Content(
                role="user",
                parts=[types.Part(
                    function_response=types.FunctionResponse(
                        name=tool_name,
                        response={"result": df_to_context(df)},
                    )
                )],
            ),
        ])

        explanation = self._client.models.generate_content(
            model=self.MODEL,
            contents=conversation,
            config=self._config,
        )

        return ChatResult(
            text=self._extract_text(explanation),
            df=df,
            chart_spec=CHART_SPECS.get(tool_name),
            kpi_called=tool_name,
            follow_ups=FOLLOW_UP_SUGGESTIONS.get(tool_name, []),
        )

    @staticmethod
    def _extract_function_call(response: Any) -> types.FunctionCall | None:
        try:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    return part.function_call
        except (IndexError, AttributeError):
            pass
        return None

    @staticmethod
    def _extract_text(response: Any) -> str:
        try:
            return "".join(
                part.text
                for part in response.candidates[0].content.parts
                if hasattr(part, "text") and part.text
            )
        except (IndexError, AttributeError):
            return ""
