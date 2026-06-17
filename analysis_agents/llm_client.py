"""Shared Gemini JSON helper for signal analysis agents."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover - dependency/runtime guard
    genai = None
    types = None


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
DISABLE_LLM = os.getenv("SIGNAL_ANALYSIS_DISABLE_LLM", "").lower() in {"1", "true", "yes"}
LLM_TIMEOUT_MS = int(os.getenv("SIGNAL_ANALYSIS_LLM_TIMEOUT_MS", "10000"))
_CLIENT = (
    genai.Client(
        api_key=GOOGLE_API_KEY,
        http_options=types.HttpOptions(timeout=LLM_TIMEOUT_MS) if types else None,
    )
    if genai and GOOGLE_API_KEY
    else None
)
_CIRCUIT_OPEN_UNTIL = 0.0


def llm_enabled() -> bool:
    """Return whether Gemini is configured for extraction."""
    return _CLIENT is not None and not DISABLE_LLM and time.time() >= _CIRCUIT_OPEN_UNTIL


def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"signals": parsed}
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def generate_json(prompt: str, max_output_tokens: int = 1800) -> Optional[Dict[str, Any]]:
    """Generate a JSON object from Gemini.

    The helper fails closed and returns None so each agent can fall back to
    deterministic rules when the model or API key is unavailable.
    """
    global _CIRCUIT_OPEN_UNTIL

    if _CLIENT is None or types is None or DISABLE_LLM or time.time() < _CIRCUIT_OPEN_UNTIL:
        return None

    try:
        response = _CLIENT.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=max_output_tokens,
                response_mime_type="application/json",
            ),
        )
        return _parse_json(response.text or "")
    except Exception as exc:
        print(f"generate_json error: {exc}")
        message = str(exc).lower()
        if "503" in message or "unavailable" in message or "high demand" in message:
            _CIRCUIT_OPEN_UNTIL = time.time() + int(os.getenv("SIGNAL_ANALYSIS_LLM_COOLDOWN_SECONDS", "300"))
        return None
