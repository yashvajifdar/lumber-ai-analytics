"""
Engine factory — returns the configured AI engine based on environment variables.

This is the only file main.py needs to import from.
Provider implementations are in anthropic_engine.py and gemini_engine.py.

Usage in .env:
  AI_PROVIDER=anthropic   →  AnthropicEngine  (default, requires ANTHROPIC_API_KEY)
  AI_PROVIDER=gemini      →  GeminiEngine     (requires GOOGLE_API_KEY, free tier available)

Adding a new provider:
  1. Create app/<provider>_engine.py with a class implementing .ask(str) -> ChatResult
  2. Add a branch below
  3. Document the new key in .env.example
"""

from __future__ import annotations

import os

from app.engine_tools import ChatResult  # re-exported for callers that need the type


def _get_secret(key: str, default: str = "") -> str:
    """
    Read a config value from st.secrets (Streamlit Cloud) with fallback to
    environment variables (local .env). Streamlit is not available in tests,
    so the import is deferred and failures are silently ignored.
    """
    try:
        import streamlit as st
        return st.secrets.get(key, os.environ.get(key, default))
    except Exception:
        return os.environ.get(key, default)


def build_engine():
    """
    Load keys from st.secrets (Streamlit Cloud) or .env (local) and return
    the right engine. Returns None if the required key is not configured.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    provider = _get_secret("AI_PROVIDER", os.environ.get("AI_PROVIDER", "anthropic")).lower()

    if provider == "gemini":
        api_key = _get_secret("GOOGLE_API_KEY")
        if not api_key or api_key == "your_key_here":
            return None
        from app.gemini_engine import GeminiEngine
        return GeminiEngine(api_key=api_key)

    if provider == "anthropic":
        api_key = _get_secret("ANTHROPIC_API_KEY")
        if not api_key or api_key == "your_key_here":
            return None
        from app.anthropic_engine import AnthropicEngine
        return AnthropicEngine(api_key=api_key)

    # Unknown provider — fail clearly rather than silently
    raise ValueError(
        f"Unknown AI_PROVIDER '{provider}'. "
        "Supported values: anthropic, gemini"
    )
