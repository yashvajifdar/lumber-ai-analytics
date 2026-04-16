"""
FastAPI wrapper for the Lumber AI Analytics engine.

Exposes:
  POST /ask   — run a question through the analytics engine
  GET  /health — liveness check

Designed to be deployed on Railway, Render, or any Python host.
The personal website at yashvajifdar.com proxies requests here via
/api/lumber/ask so the backend URL stays hidden from the browser.

Run locally:
  cd /path/to/lumber-ai-analytics
  source venv/bin/activate
  uvicorn app.api:app --reload --port 8001
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Allow running as `uvicorn app.api:app` from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.engine_factory import build_engine  # noqa: E402  (after sys.path fix)
from app.engine_tools import ChatResult  # noqa: E402


# ── startup: build engine once ────────────────────────────────────────────────

_engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine
    _engine = build_engine()
    if _engine is None:
        raise RuntimeError(
            "Engine failed to initialize — "
            "check AI_PROVIDER and the corresponding API key are set in environment variables."
        )
    yield


app = FastAPI(title="Lumber AI Analytics API", lifespan=lifespan)

# Allow requests from the personal website and local dev
_ALLOWED_ORIGINS = [
    "https://yashvajifdar.com",
    "https://www.yashvajifdar.com",
    "http://localhost:3000",
    "http://localhost:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ── request / response models ─────────────────────────────────────────────────

class Message(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class AskRequest(BaseModel):
    question: str
    history: list[Message] = []


class FollowUp(BaseModel):
    label: str
    question: str


class AskResponse(BaseModel):
    text: str
    follow_ups: list[FollowUp] = []
    chart_spec: dict[str, Any] | None = None
    chart_data: list[dict[str, Any]] | None = None
    kpi_called: str | None = None
    error: str | None = None


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not initialized — missing API key.")
    history = [{"role": m.role, "content": m.content} for m in req.history]
    result: ChatResult = _engine.ask(req.question, history or None)

    chart_data = None
    if result.df is not None:
        # Serialize DataFrame — replace NaN/NaT with None for JSON safety
        chart_data = result.df.where(result.df.notna(), other=None).to_dict(
            orient="records"
        )

    follow_ups = [
        FollowUp(label=label, question=question)
        for label, question in result.follow_ups
    ]

    return AskResponse(
        text=result.text,
        follow_ups=follow_ups,
        chart_spec=result.chart_spec,
        chart_data=chart_data,
        kpi_called=result.kpi_called,
        error=result.error,
    )
