"""
Tests for the AI engine layer and chart builder.

Covers:
  1. AnthropicEngine.ask() — two-turn tool-use flow (Anthropic client mocked)
  2. df_to_context() — DataFrame serialisation helper
  3. build_engine() — factory routing by AI_PROVIDER env var
  4. build_chart() — every chart spec produces a figure
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.anthropic_engine import AnthropicEngine
from app.engine_factory import build_engine
from app.engine_tools import CHART_SPECS, ChatResult, KPI_DISPATCH, df_to_context
from app.chart_builder import build_chart


# ── mock response builders ────────────────────────────────────────────────────

def _tool_use_response(tool_name: str, tool_input: dict) -> MagicMock:
    """Simulate a Claude response that selects a tool."""
    block = SimpleNamespace(
        type="tool_use",
        id="tu_test_001",
        name=tool_name,
        input=tool_input,
    )
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [block]
    return response


def _text_response(text: str) -> MagicMock:
    """Simulate a Claude response that returns plain text."""
    block = SimpleNamespace(text=text)
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    return response


# ── AnthropicEngine.ask ───────────────────────────────────────────────────────

class TestAnthropicEngineAsk:
    """Verifies the two-turn tool-use flow without hitting the real API."""

    def _make_engine(self, first_response, second_response) -> AnthropicEngine:
        engine = AnthropicEngine.__new__(AnthropicEngine)
        client = MagicMock()
        client.messages.create.side_effect = [first_response, second_response]
        engine._client = client
        return engine

    def test_returns_chat_result(self, test_db):
        engine = self._make_engine(
            _tool_use_response("get_revenue_over_time", {}),
            _text_response("Revenue is looking strong this quarter."),
        )
        result = engine.ask("How is revenue trending?")
        assert isinstance(result, ChatResult)

    def test_text_from_second_response(self, test_db):
        explanation = "Revenue is up 12% month-over-month."
        engine = self._make_engine(
            _tool_use_response("get_revenue_over_time", {"period": "month"}),
            _text_response(explanation),
        )
        result = engine.ask("Show me revenue trend")
        assert result.text == explanation

    def test_kpi_called_is_set(self, test_db):
        engine = self._make_engine(
            _tool_use_response("get_top_products", {"n": 5}),
            _text_response("Top products by revenue."),
        )
        result = engine.ask("What are the top products?")
        assert result.kpi_called == "get_top_products"

    def test_df_is_populated(self, test_db):
        engine = self._make_engine(
            _tool_use_response("get_top_products", {}),
            _text_response("Here are your top products."),
        )
        result = engine.ask("Top products?")
        assert result.df is not None
        assert isinstance(result.df, pd.DataFrame)
        assert len(result.df) > 0

    def test_chart_spec_matches_tool(self, test_db):
        engine = self._make_engine(
            _tool_use_response("get_revenue_by_category", {}),
            _text_response("Category breakdown."),
        )
        result = engine.ask("Revenue by category?")
        assert result.chart_spec is not None
        assert result.chart_spec["type"] == "pie"

    def test_no_tool_call_returns_fallback_text(self, test_db):
        """If Claude responds without tool use, return the text directly."""
        response = _text_response("I'm not sure how to help with that.")
        response.stop_reason = "end_turn"

        engine = AnthropicEngine.__new__(AnthropicEngine)
        client = MagicMock()
        client.messages.create.return_value = response
        engine._client = client

        result = engine.ask("What is the capital of France?")
        assert isinstance(result.text, str)
        assert result.df is None

    def test_unknown_tool_name_returns_error_result(self, test_db):
        engine = self._make_engine(
            _tool_use_response("get_nonexistent_metric", {}),
            _text_response("This should not be reached."),
        )
        result = engine.ask("Something weird")
        assert result.error is not None
        assert "Unknown tool" in result.error

    def test_kpi_exception_returns_error_result(self, test_db, monkeypatch):
        def bad_fn(**kwargs):
            raise RuntimeError("DB connection failed")

        import app.engine_tools as tools_mod
        monkeypatch.setitem(tools_mod.KPI_DISPATCH, "get_revenue_over_time", bad_fn)

        engine = self._make_engine(
            _tool_use_response("get_revenue_over_time", {}),
            _text_response("This should not be reached."),
        )
        result = engine.ask("Revenue?")
        assert result.error == "DB connection failed"

    def test_tool_input_forwarded_to_kpi_function(self, test_db):
        """Parameters the model returns must reach the KPI function unchanged."""
        calls = []
        original_fn = KPI_DISPATCH["get_top_products"]

        def tracking_fn(**kwargs):
            calls.append(kwargs)
            return original_fn(**kwargs)

        import app.engine_tools as tools_mod
        tools_mod.KPI_DISPATCH["get_top_products"] = tracking_fn
        try:
            engine = self._make_engine(
                _tool_use_response("get_top_products", {"n": 3, "by": "gross_profit"}),
                _text_response("Top 3 products by gross profit."),
            )
            engine.ask("Top 3 by profit?")
            assert calls == [{"n": 3, "by": "gross_profit"}]
        finally:
            tools_mod.KPI_DISPATCH["get_top_products"] = original_fn

    def test_two_api_calls_made_per_question(self, test_db):
        engine = self._make_engine(
            _tool_use_response("get_revenue_over_time", {}),
            _text_response("Revenue data here."),
        )
        engine.ask("Revenue?")
        assert engine._client.messages.create.call_count == 2

    def test_history_prepended_to_messages(self, test_db):
        """Prior conversation turns must appear before the current question."""
        engine = self._make_engine(
            _tool_use_response("get_revenue_over_time", {}),
            _text_response("Revenue data here."),
        )
        history = [
            {"role": "user", "content": "Which products have the highest margin?"},
            {"role": "assistant", "content": "I can show gross profit or the lowest-margin products."},
        ]
        engine.ask("Sure", history=history)

        call_args = engine._client.messages.create.call_args_list[0]
        messages_sent = call_args.kwargs["messages"]
        # History comes first
        assert messages_sent[0]["role"] == "user"
        assert "highest margin" in messages_sent[0]["content"]
        # Current question follows history at index len(history)
        assert messages_sent[len(history)]["content"] == "Sure"

    def test_no_history_behaves_as_before(self, test_db):
        """Calling ask() without history must still work."""
        engine = self._make_engine(
            _tool_use_response("get_revenue_over_time", {}),
            _text_response("Revenue data here."),
        )
        result = engine.ask("Revenue?")
        assert isinstance(result, ChatResult)


# ── df_to_context ─────────────────────────────────────────────────────────────

class TestDfToContext:
    def test_returns_string(self):
        df = pd.DataFrame({"period": ["2024-01", "2024-02"], "revenue": [1000.0, 1200.0]})
        assert isinstance(df_to_context(df), str)

    def test_contains_data_values(self):
        df = pd.DataFrame({"period": ["2024-01"], "revenue": [9999.0]})
        assert "9999" in df_to_context(df)

    def test_truncation_note_when_over_limit(self):
        df = pd.DataFrame({"x": range(30), "y": range(30)})
        assert "10 of 30" in df_to_context(df, max_rows=10)

    def test_no_truncation_note_when_under_limit(self):
        df = pd.DataFrame({"x": range(5), "y": range(5)})
        result = df_to_context(df, max_rows=25)
        assert "of 5" not in result

    def test_summary_includes_numeric_column(self):
        df = pd.DataFrame({"revenue": [100.0, 200.0, 300.0]})
        result = df_to_context(df)
        assert "revenue" in result
        assert "600" in result  # total

    def test_handles_empty_dataframe(self):
        df = pd.DataFrame({"revenue": pd.Series([], dtype=float)})
        assert isinstance(df_to_context(df), str)


# ── build_engine factory ──────────────────────────────────────────────────────

class TestBuildEngine:
    def test_returns_none_when_no_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("AI_PROVIDER", raising=False)
        assert build_engine() is None

    def test_returns_none_when_key_is_placeholder(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "your_key_here")
        monkeypatch.delenv("AI_PROVIDER", raising=False)
        assert build_engine() is None

    def test_returns_anthropic_engine_by_default(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-12345")
        monkeypatch.delenv("AI_PROVIDER", raising=False)
        engine = build_engine()
        assert isinstance(engine, AnthropicEngine)

    def test_returns_anthropic_engine_when_provider_set_explicitly(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-12345")
        engine = build_engine()
        assert isinstance(engine, AnthropicEngine)

    def test_returns_gemini_engine_when_provider_set(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "gemini")
        monkeypatch.setenv("GOOGLE_API_KEY", "AIza-test-key-12345")
        from app.gemini_engine import GeminiEngine
        engine = build_engine()
        assert isinstance(engine, GeminiEngine)

    def test_returns_none_when_gemini_selected_but_no_key(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "gemini")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        assert build_engine() is None

    def test_raises_on_unknown_provider(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "openai")
        with pytest.raises(ValueError, match="Unknown AI_PROVIDER"):
            build_engine()


# ── chart_builder ─────────────────────────────────────────────────────────────

class TestChartBuilder:
    """Every chart spec in CHART_SPECS must produce a non-None figure."""

    SAMPLE_DATA: dict[str, pd.DataFrame] = {
        "get_revenue_over_time": pd.DataFrame({
            "period": ["2024-01", "2024-02"],
            "revenue": [10000.0, 12000.0],
        }),
        "get_margin_trend": pd.DataFrame({
            "period": ["2024-01", "2024-02"],
            "margin_pct": [32.0, 28.0],
            "revenue": [10000.0, 12000.0],
            "gross_profit": [3200.0, 3360.0],
        }),
        "get_top_products": pd.DataFrame({
            "name": ["Lumber", "Plywood"],
            "category": ["Dimensional Lumber", "Sheet Goods"],
            "revenue": [5000.0, 3000.0],
            "gross_profit": [2000.0, 900.0],
            "quantity": [500, 200],
            "margin_pct": [40.0, 30.0],
        }),
        "get_bottom_margin_products": pd.DataFrame({
            "name": ["Plywood", "Lumber"],
            "category": ["Sheet Goods", "Dimensional Lumber"],
            "revenue": [3000.0, 5000.0],
            "margin_pct": [20.0, 35.0],
        }),
        "get_revenue_by_category": pd.DataFrame({
            "category": ["Dimensional Lumber", "Sheet Goods"],
            "revenue": [5000.0, 3000.0],
            "gross_profit": [2000.0, 900.0],
            "margin_pct": [40.0, 30.0],
        }),
        "get_top_customers": pd.DataFrame({
            "customer_id": ["C001", "C002"],
            "customer_name": ["ProBuild LLC", "John Smith"],
            "type": ["Contractor", "Retail"],
            "revenue": [8000.0, 2000.0],
            "gross_profit": [3200.0, 600.0],
            "orders": [10, 3],
        }),
        "get_customer_type_split": pd.DataFrame({
            "type": ["Contractor", "Retail"],
            "revenue": [8000.0, 2000.0],
            "customers": [5, 10],
            "orders": [20, 15],
        }),
        "get_repeat_customer_rate": pd.DataFrame({
            "type": ["Contractor", "Retail"],
            "total_customers": [5, 10],
            "repeat_customers": [4, 3],
            "repeat_rate_pct": [80.0, 30.0],
        }),
        "get_revenue_by_location": pd.DataFrame({
            "location": ["Yard A", "Yard A", "Yard B", "Yard B"],
            "period": ["2024-01", "2024-02", "2024-01", "2024-02"],
            "revenue": [6000.0, 7000.0, 4000.0, 5000.0],
            "gross_profit": [2400.0, 2800.0, 1600.0, 2000.0],
            "margin_pct": [40.0, 40.0, 40.0, 40.0],
        }),
        "get_inventory_health": pd.DataFrame({
            "name": ["Lumber", "Plywood"],
            "category": ["Dimensional Lumber", "Sheet Goods"],
            "location": ["Yard A", "Yard A"],
            "stock_level": [50, 200],
            "reorder_point": [100, 50],
            "below_reorder": [1, 0],
            "inventory_value": [175.0, 2400.0],
        }),
        "get_slow_moving_inventory": pd.DataFrame({
            "name": ["Plywood"],
            "category": ["Sheet Goods"],
            "total_stock": [200],
            "units_sold_90d": [0],
            "inventory_value": [2400.0],
        }),
        "get_top_products_by_category": pd.DataFrame({
            "name": ["2x4x8 Lumber", "2x6x8 Lumber"],
            "category": ["Dimensional Lumber", "Dimensional Lumber"],
            "revenue": [5000.0, 3000.0],
            "gross_profit": [2000.0, 900.0],
            "margin_pct": [40.0, 30.0],
        }),
        "get_top_customers_by_type": pd.DataFrame({
            "customer_id": ["C001", "C003"],
            "customer_name": ["ProBuild LLC", "SunriseDev Inc"],
            "type": ["Contractor", "Contractor"],
            "revenue": [8000.0, 4000.0],
            "gross_profit": [3200.0, 1600.0],
            "orders": [10, 5],
        }),
        "get_sales_by_rep": pd.DataFrame({
            "sales_rep": ["Mike Torres", "Sarah Chen"],
            "location": ["Yard A - Providence", "Yard A - Providence"],
            "revenue": [12000.0, 9000.0],
            "gross_profit": [4800.0, 3600.0],
            "margin_pct": [40.0, 40.0],
            "orders": [15, 12],
            "customers": [8, 6],
        }),
        "get_inactive_customers": pd.DataFrame({
            "customer_id": ["C010", "C020"],
            "type": ["Contractor", "Retail"],
            "location": ["Yard A - Providence", "Yard B - Boston"],
            "last_order_date": ["2024-06-01", "2024-05-15"],
            "lifetime_revenue": [5000.0, 1200.0],
            "total_orders": [4, 2],
        }),
    }

    @pytest.mark.parametrize("tool_name", list(CHART_SPECS.keys()))
    def test_produces_figure_for_all_specs(self, tool_name):
        df = self.SAMPLE_DATA[tool_name]
        spec = CHART_SPECS[tool_name]
        fig = build_chart(df, spec)
        assert fig is not None, f"build_chart returned None for {tool_name}"

    def test_unknown_chart_type_returns_none(self):
        df = pd.DataFrame({"x": [1, 2]})
        assert build_chart(df, {"type": "unknown_chart_type"}) is None
