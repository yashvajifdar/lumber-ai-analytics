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

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("lumber_api")

# Allow running as `uvicorn app.api:app` from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.engine_factory import build_engine  # noqa: E402  (after sys.path fix)
from app.engine_tools import ChatResult  # noqa: E402


# ── startup: seed database if missing, then build engine ─────────────────────

_engine = None

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "lumber.db")


def _ensure_database() -> None:
    """Run ETL if the database doesn't exist. Handles Render deploys where the
    build step may not have run the ETL scripts."""
    if os.path.exists(_DB_PATH):
        logger.info("Database found at %s", _DB_PATH)
        return
    logger.info("Database not found — running ETL pipeline")
    import subprocess
    root = os.path.dirname(os.path.dirname(__file__))
    subprocess.run(["python", "etl/generate_data.py"], cwd=root, check=True)
    subprocess.run(["python", "etl/loader.py"], cwd=root, check=True)
    logger.info("ETL complete — database ready")


def _friendly_error(raw: str) -> str:
    """Map internal error strings to user-facing messages. The real error is
    always logged server-side; this is what the user sees."""
    low = raw.lower()
    if "503" in raw or "unavailable" in low or "high demand" in low:
        return "The AI service is temporarily busy — please try again in a moment."
    if "no such table" in low or "operationalerror" in low:
        return "There was a problem accessing the data. Please try again."
    if "quota" in low or "rate limit" in low or "429" in raw:
        return "Request limit reached — please try again in a few seconds."
    if "timeout" in low:
        return "The request timed out — please try again."
    return "Something went wrong retrieving that data. Try rephrasing your question."


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine
    logger.info("Starting up Lumber AI Analytics API")
    _ensure_database()
    _engine = build_engine()
    if _engine is None:
        raise RuntimeError(
            "Engine failed to initialize — "
            "check AI_PROVIDER and the corresponding API key are set in environment variables."
        )
    logger.info("Engine initialized: %s", type(_engine).__name__)
    yield
    logger.info("Shutting down")


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

    t0 = time.perf_counter()
    logger.info("question=%r history_turns=%d", req.question, len(req.history))

    try:
        history = [{"role": m.role, "content": m.content} for m in req.history]
        result: ChatResult = _engine.ask(req.question, history or None)
    except Exception as exc:
        logger.error("Unhandled engine error: %s", exc, exc_info=True)
        return AskResponse(
            text="I ran into a problem answering that question.",
            error=_friendly_error(str(exc)),
        )

    elapsed = time.perf_counter() - t0

    if result.error:
        logger.warning("Engine error (kpi=%s, %.2fs): %s", result.kpi_called, elapsed, result.error)
    else:
        logger.info("OK kpi=%s elapsed=%.2fs", result.kpi_called, elapsed)

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
        error=_friendly_error(result.error) if result.error else None,
    )
