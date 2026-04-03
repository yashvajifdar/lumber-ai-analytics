"""
Chart rendering layer.

Takes a (DataFrame, chart_spec dict) and returns a Plotly figure.
Spec keys are defined in chat_engine.CHART_SPECS.

Keeping this separate from chat_engine (data/AI) and main (UI) means
chart logic is testable and neither layer needs to import the other.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def build_chart(df: pd.DataFrame, spec: dict[str, Any]) -> go.Figure | None:
    """
    Return a Plotly figure from df + spec, or None if the spec type is unrecognised.
    The caller is responsible for rendering the figure.
    """
    chart_type = spec.get("type")

    if chart_type == "bar":
        return _bar(df, spec)

    if chart_type == "line":
        return _line(df, spec)

    if chart_type == "line_multi":
        return _line_multi(df, spec)

    if chart_type == "horizontal_bar":
        return _horizontal_bar(df, spec)

    if chart_type == "pie":
        return _pie(df, spec)

    if chart_type == "scatter":
        return _scatter(df, spec)

    if chart_type == "table":
        return _table(df, spec)

    return None


# ── chart builders ────────────────────────────────────────────────────────────

def _bar(df: pd.DataFrame, spec: dict) -> go.Figure:
    fig = px.bar(
        df,
        x=spec["x"],
        y=spec["y"],
        color_discrete_sequence=spec.get("color_seq", ["#2563EB"]),
        labels=spec.get("labels", {}),
    )
    fig.update_layout(margin=dict(t=10))
    return fig


def _line(df: pd.DataFrame, spec: dict) -> go.Figure:
    fig = px.line(
        df,
        x=spec["x"],
        y=spec["y"],
        color_discrete_sequence=spec.get("color_seq", ["#16A34A"]),
        labels=spec.get("labels", {}),
    )
    fig.update_layout(margin=dict(t=10))
    return fig


def _line_multi(df: pd.DataFrame, spec: dict) -> go.Figure:
    fig = px.line(
        df,
        x=spec["x"],
        y=spec["y"],
        color=spec["color_col"],
        labels=spec.get("labels", {}),
    )
    fig.update_layout(margin=dict(t=10))
    return fig


def _horizontal_bar(df: pd.DataFrame, spec: dict) -> go.Figure:
    color_col   = spec.get("color_col")
    color_scale = spec.get("color_scale")
    color_map   = spec.get("color_map")

    kwargs: dict[str, Any] = {
        "x": spec["x"],
        "y": spec["y"],
        "orientation": "h",
        "labels": spec.get("labels", {}),
    }

    if color_map:
        kwargs["color"] = color_col
        kwargs["color_discrete_map"] = color_map
    elif color_scale and color_col:
        kwargs["color"] = color_col
        kwargs["color_continuous_scale"] = color_scale

    fig = px.bar(df, **kwargs)
    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        margin=dict(t=10),
    )
    return fig


def _pie(df: pd.DataFrame, spec: dict) -> go.Figure:
    kwargs: dict[str, Any] = {
        "names": spec["names"],
        "values": spec["values"],
    }
    color_map = spec.get("color_map")
    if color_map:
        kwargs["color"] = spec["names"]
        kwargs["color_discrete_map"] = color_map
    else:
        kwargs["color_discrete_sequence"] = px.colors.qualitative.Pastel

    fig = px.pie(df, **kwargs)
    fig.update_layout(margin=dict(t=10))
    return fig


def _scatter(df: pd.DataFrame, spec: dict) -> go.Figure:
    fig = px.scatter(
        df,
        x=spec["x"],
        y=spec["y"],
        size=spec.get("size"),
        color=spec.get("color_col"),
        hover_name=spec.get("hover"),
        labels=spec.get("labels", {}),
    )
    fig.update_layout(margin=dict(t=10))
    return fig


def _table(df: pd.DataFrame, spec: dict) -> go.Figure:
    cols = spec.get("columns", df.columns.tolist())
    subset = df[cols].head(50)

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=[f"<b>{c}</b>" for c in subset.columns],
                    fill_color="#1e3a5f",
                    font=dict(color="white", size=12),
                    align="left",
                ),
                cells=dict(
                    values=[subset[c].tolist() for c in subset.columns],
                    fill_color=[
                        ["#f0f4ff" if i % 2 == 0 else "white"
                         for i in range(len(subset))]
                    ],
                    align="left",
                    font=dict(size=11),
                ),
            )
        ]
    )
    fig.update_layout(margin=dict(t=10, b=0))
    return fig
