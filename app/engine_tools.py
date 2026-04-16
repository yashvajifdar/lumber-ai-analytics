"""
Provider-agnostic engine building blocks.

Everything in this file is shared across all AI providers:
  - TOOL_DEFINITIONS    neutral JSON Schema format (not Anthropic, not Gemini)
  - CHART_SPECS         chart rendering specs keyed by tool name
  - KPI_DISPATCH        tool name → KPI function mapping
  - ChatResult          return type contract for all engines
  - SYSTEM_PROMPT       business context prompt (provider-independent)
  - df_to_context()     DataFrame → string for LLM context window

Each provider adapter (anthropic_engine.py, gemini_engine.py) imports from here
and converts TOOL_DEFINITIONS to its own format. Adding a new provider means
creating one new file — nothing here changes.

Tool definition format (neutral):
  {
    "name":        str,
    "description": str,
    "parameters":  JSON Schema object  ← standard, not Anthropic input_schema
  }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from metrics import kpis

# ── system prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an AI analytics assistant for a lumber and building supply business
with multiple yard locations. You help owners and managers understand their business performance.

ALWAYS call a tool to retrieve data before responding — even if the same question was asked earlier
in the conversation. Never skip the tool call or summarize from memory.

Response format:
- Lead with 1 sentence: the single most important finding, with a specific number.
- Follow with 2–4 bullet points for supporting detail. Each bullet is one line — a name, a number, and why it matters.
- Use **bold** for key figures and product/location names.
- No headers. No paragraphs. No more than 4 bullets.
- Format currency as $X.XK or $X.XM.

Example of good format:
Engineered Wood is your top category at **$17.5M** revenue and a **38% margin**.

- **Treated Lumber** — 47% margin, your strongest in the portfolio
- **Fasteners** — 36.5% margin, below average despite solid volume
- **Doors & Windows** — $11.7M revenue but margin lagging at 31%

You are talking to a business owner. Be direct. Never fabricate numbers."""

# ── neutral tool definitions (JSON Schema) ────────────────────────────────────
# Standard JSON Schema under "parameters" — no provider-specific keys.
# Each engine adapter converts this to its own wire format.

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_revenue_over_time",
        "description": (
            "Revenue, COGS, gross profit, margin, and order count over time. "
            "Use for questions about sales performance, revenue trends, financial overview, "
            "or how the business is doing overall."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["day", "week", "month"],
                    "description": "Aggregation period. Default: month.",
                },
            },
        },
    },
    {
        "name": "get_margin_trend",
        "description": (
            "Gross margin percentage trend over time alongside revenue and gross profit. "
            "Use for questions specifically about margin, profitability trends, or why profit changed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["day", "week", "month"],
                    "description": "Aggregation period. Default: month.",
                },
            },
        },
    },
    {
        "name": "get_top_products",
        "description": (
            "Top N products ranked by revenue, gross profit, quantity sold, or margin percentage. "
            "Use for questions about best-performing products, top SKUs, highest margin products, "
            "or what's selling most."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "n": {
                    "type": "integer",
                    "description": "Number of products to return. Default: 10.",
                },
                "by": {
                    "type": "string",
                    "enum": ["revenue", "gross_profit", "quantity", "margin_pct"],
                    "description": "Sort metric. Default: revenue. Use margin_pct for highest margin products.",
                },
            },
        },
    },
    {
        "name": "get_bottom_margin_products",
        "description": (
            "Products with the lowest gross margin percentage (minimum $5K revenue). "
            "Use for questions about worst-margin products, margin compression, or pricing issues."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "n": {
                    "type": "integer",
                    "description": "Number of products to return. Default: 10.",
                },
            },
        },
    },
    {
        "name": "get_revenue_by_category",
        "description": (
            "Revenue, gross profit, and margin broken down by product category. "
            "Use for questions about category performance or product mix."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_top_customers",
        "description": (
            "Top N customers ranked by revenue, with their type, gross profit, and order count. "
            "Use for questions about best customers, key accounts, or customer value."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "n": {
                    "type": "integer",
                    "description": "Number of customers to return. Default: 10.",
                },
            },
        },
    },
    {
        "name": "get_customer_type_split",
        "description": (
            "Revenue, customer count, and order count split between Contractor and Retail customers. "
            "Use for questions about customer mix or contractor vs. retail breakdown."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_repeat_customer_rate",
        "description": (
            "Repeat purchase rate by customer type — percentage of customers with more than one order. "
            "Use for questions about customer loyalty, retention, or repeat business."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_revenue_by_location",
        "description": (
            "Revenue, gross profit, and margin broken down by yard location over time. "
            "Use for questions about location performance or comparing yards."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["month", "week", "total"],
                    "description": "Aggregation period. Default: month.",
                },
            },
        },
    },
    {
        "name": "get_inventory_health",
        "description": (
            "Current inventory levels by product and location, items below reorder point, "
            "and total inventory value. Use for questions about stock levels or what needs reordering."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_slow_moving_inventory",
        "description": (
            "Products with high stock but low sales velocity in the last 90 days. "
            "Use for questions about dead stock, slow movers, or inventory that isn't selling."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_top_products_by_category",
        "description": (
            "Top products within a specific product category, ranked by revenue, with margin. "
            "Use when the user asks about products in a specific category like 'framing lumber' or "
            "'fasteners', or drills down from a category view."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "The product category to filter by (e.g. 'Framing Lumber').",
                },
                "n": {
                    "type": "integer",
                    "description": "Number of products to return. Default: 10.",
                },
            },
            "required": ["category"],
        },
    },
    {
        "name": "get_top_customers_by_type",
        "description": (
            "Top customers within a specific customer type (Contractor or Retail), ranked by revenue. "
            "Use when the user asks about contractor customers specifically, retail customers specifically, "
            "or drills down from the customer type split."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_type": {
                    "type": "string",
                    "enum": ["Contractor", "Retail"],
                    "description": "Customer type to filter by.",
                },
                "n": {
                    "type": "integer",
                    "description": "Number of customers to return. Default: 10.",
                },
            },
            "required": ["customer_type"],
        },
    },
]

# ── chart specs (keyed by tool name) ─────────────────────────────────────────

CHART_SPECS: dict[str, dict[str, Any]] = {
    "get_revenue_over_time": {
        "type": "bar",
        "x": "period", "y": "revenue",
        "color_seq": ["#2563EB"],
        "labels": {"period": "", "revenue": "Revenue ($)"},
    },
    "get_margin_trend": {
        "type": "line",
        "x": "period", "y": "margin_pct",
        "color_seq": ["#16A34A"],
        "labels": {"period": "", "margin_pct": "Margin %"},
    },
    "get_top_products": {
        "type": "horizontal_bar",
        "x": "revenue", "y": "name",
        "color_col": "margin_pct", "color_scale": "RdYlGn",
        "labels": {"name": "", "revenue": "Revenue ($)", "margin_pct": "Margin %"},
    },
    "get_bottom_margin_products": {
        "type": "horizontal_bar",
        "x": "margin_pct", "y": "name",
        "color_col": "margin_pct", "color_scale": "RdYlGn",
        "labels": {"name": "", "margin_pct": "Margin %"},
    },
    "get_revenue_by_category": {
        "type": "pie",
        "names": "category", "values": "revenue",
        "drill_key": "category",
        "drill_question": "Show me the top products in {category}",
    },
    "get_top_customers": {
        "type": "horizontal_bar",
        "x": "revenue", "y": "customer_id",
        "color_col": "type",
        "color_map": {"Contractor": "#2563EB", "Retail": "#F59E0B"},
        "labels": {"customer_id": "", "revenue": "Revenue ($)"},
    },
    "get_customer_type_split": {
        "type": "pie",
        "names": "type", "values": "revenue",
        "color_map": {"Contractor": "#2563EB", "Retail": "#F59E0B"},
        "drill_key": "type",
        "drill_question": "Show me the top {type} customers by revenue",
    },
    "get_repeat_customer_rate": {
        "type": "bar",
        "x": "type", "y": "repeat_rate_pct",
        "color_seq": ["#7C3AED"],
        "labels": {"type": "Customer Type", "repeat_rate_pct": "Repeat Rate (%)"},
    },
    "get_revenue_by_location": {
        "type": "line_multi",
        "x": "period", "y": "revenue", "color_col": "location",
        "labels": {"period": "", "revenue": "Revenue ($)"},
    },
    "get_inventory_health": {
        "type": "table",
        "columns": ["name", "category", "location",
                    "stock_level", "reorder_point", "below_reorder", "inventory_value"],
    },
    "get_slow_moving_inventory": {
        "type": "scatter",
        "x": "units_sold_90d", "y": "total_stock",
        "size": "inventory_value", "color_col": "category", "hover": "name",
        "labels": {"units_sold_90d": "Units Sold (90d)", "total_stock": "Stock Level"},
    },
    "get_top_products_by_category": {
        "type": "horizontal_bar",
        "x": "revenue", "y": "name",
        "labels": {"name": "", "revenue": "Revenue ($)", "margin_pct": "Margin %"},
    },
    "get_top_customers_by_type": {
        "type": "horizontal_bar",
        "x": "revenue", "y": "customer_id",
        "labels": {"customer_id": "", "revenue": "Revenue ($)"},
    },
}

# ── KPI dispatch (tool name → function) ──────────────────────────────────────

KPI_DISPATCH: dict[str, Any] = {
    "get_revenue_over_time":      kpis.revenue_over_time,
    "get_margin_trend":           kpis.margin_trend,
    "get_top_products":           kpis.top_products,
    "get_bottom_margin_products": kpis.bottom_margin_products,
    "get_revenue_by_category":    kpis.revenue_by_category,
    "get_top_customers":          kpis.top_customers,
    "get_customer_type_split":    kpis.customer_type_split,
    "get_repeat_customer_rate":   kpis.repeat_customer_rate,
    "get_revenue_by_location":    kpis.revenue_by_location,
    "get_inventory_health":       kpis.inventory_health,
    "get_slow_moving_inventory":       kpis.slow_moving_inventory,
    "get_top_products_by_category":    kpis.top_products_by_category,
    "get_top_customers_by_type":       kpis.top_customers_by_type,
}

# ── curated follow-up suggestions (keyed by tool name) ───────────────────────
# Only questions that map to real KPI functions are included.

# Each entry is (short_label, full_question). The UI shows the label; the engine receives the question.
FOLLOW_UP_SUGGESTIONS: dict[str, list[tuple[str, str]]] = {
    "get_revenue_over_time": [
        ("📉 Margin trend",        "How has our margin trended over the same period?"),
        ("🏪 By location",         "Which location drives the most revenue?"),
        ("📦 Top products",        "Which products are generating the most revenue?"),
    ],
    "get_margin_trend": [
        ("📉 Lowest margins",      "Which products have the lowest margin?"),
        ("💰 Total sales",         "What were our total sales this year?"),
        ("🗂️ Best category",       "Which category has the best margin?"),
    ],
    "get_top_products": [
        ("📉 Lowest margins",      "Which products have the lowest margin?"),
        ("🗂️ By category",         "What does revenue by category look like?"),
        ("📈 Revenue trend",       "How has overall revenue trended over time?"),
    ],
    "get_bottom_margin_products": [
        ("💰 Top revenue",         "Which products generate the most revenue?"),
        ("📈 Margin over time",    "How has margin trended over time?"),
        ("🗂️ By category",         "What does revenue by category look like?"),
    ],
    "get_revenue_by_category": [
        ("📈 Highest margins",     "Which products have the highest margin?"),
        ("📉 Lowest margins",      "Which products have the lowest margin?"),
        ("💰 Total sales",         "What were total sales this year?"),
    ],
    "get_top_customers": [
        ("👷 Contractor vs retail", "What is the split between contractor and retail revenue?"),
        ("🔄 Repeat rate",          "What is our repeat customer rate?"),
        ("💰 Total sales",          "What were total sales this year?"),
    ],
    "get_customer_type_split": [
        ("👷 Top customers",       "Who are our top customers by revenue?"),
        ("🔄 Repeat rate",         "What is our repeat customer rate?"),
        ("📈 Revenue trend",       "How has revenue trended over time?"),
    ],
    "get_repeat_customer_rate": [
        ("👷 Top customers",       "Who are our top customers by revenue?"),
        ("👷 Contractor split",    "What is the contractor vs retail revenue split?"),
        ("💰 Total sales",         "What were total sales this year?"),
    ],
    "get_revenue_by_location": [
        ("💰 Total sales",         "What were total sales this year?"),
        ("📉 Margin trend",        "How has margin trended over time?"),
        ("👷 Top customers",       "Who are our top customers by revenue?"),
    ],
    "get_inventory_health": [
        ("🐌 Slow-moving stock",   "Which inventory is slow-moving?"),
        ("💰 Total sales",         "What were total sales this year?"),
        ("📉 Lowest margins",      "Which products have the lowest margin?"),
    ],
    "get_slow_moving_inventory": [
        ("📦 Inventory health",    "What is our current inventory health?"),
        ("💰 Top revenue",         "Which products generate the most revenue?"),
        ("💰 Total sales",         "What were total sales this year?"),
    ],
    "get_top_products_by_category": [
        ("🗂️ All categories",      "What does revenue by category look like?"),
        ("📦 Top products",        "Which products are generating the most revenue overall?"),
        ("📉 Lowest margins",      "Which products have the lowest margin?"),
    ],
    "get_top_customers_by_type": [
        ("👷 Customer mix",        "What is the split between contractor and retail revenue?"),
        ("👷 All top customers",   "Who are our top customers by revenue?"),
        ("🔄 Repeat rate",         "What is our repeat customer rate?"),
    ],
}

# ── shared return type ────────────────────────────────────────────────────────

@dataclass
class ChatResult:
    """
    Common return contract for all engine implementations.
    The UI layer only ever sees this — never a provider SDK type.
    """
    text: str
    df: pd.DataFrame | None = None
    chart_spec: dict[str, Any] | None = None
    kpi_called: str | None = None
    error: str | None = None
    follow_ups: list[tuple[str, str]] = field(default_factory=list)


# ── shared helper ─────────────────────────────────────────────────────────────

def df_to_context(df: pd.DataFrame, max_rows: int = 25) -> str:
    """
    Serialize a DataFrame to a compact string for the LLM context window.
    Sends the data rows plus a summary of key numeric columns.
    """
    rows = df.head(max_rows)
    table = rows.to_string(index=False)

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if numeric_cols:
        parts = []
        for col in numeric_cols[:4]:
            parts.append(f"{col}: total={df[col].sum():,.2f}, avg={df[col].mean():,.2f}")
        summary = "Summary: " + " | ".join(parts)
    else:
        summary = ""

    note = f"\n(showing {len(rows)} of {len(df)} rows)" if len(df) > max_rows else ""
    return f"{table}{note}\n\n{summary}".strip()
