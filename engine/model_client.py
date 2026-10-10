"""Model client infrastructure for Groq LLMs.

Supports:
- 'llama-3.1-8b-instant'
- 'qwen/qwen3.8-27b'
- 'llama-3.3-70b-versatile'

Provides wall-clock latency tracking and safe mock fallback when
GROQ_API_KEY is not configured or in case of client/network errors.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

logger = logging.getLogger(__name__)

# Supported model identifiers
SUPPORTED_MODELS: List[str] = [
    "llama-3.1-8b-instant",
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
]

_cached_client: Any = None


def get_groq_client() -> Any:
    """Retrieve or initialize the Groq client instance if API key is present."""
    global _cached_client
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or not api_key.strip():
        return None

    if _cached_client is None:
        try:
            from groq import Groq
            _cached_client = Groq(api_key=api_key.strip())
        except Exception as exc:
            logger.warning("Failed to initialize Groq client: %s", exc)
            return None

    return _cached_client


# Module-level client initialization as requested in specifications
client = get_groq_client()


def _mock_generate(
    model_name: str,
    prompt: str,
    system_prompt: str = "",
    start_time: Optional[float] = None,
    note: str = "GROQ_API_KEY not configured",
) -> Dict[str, Any]:
    """Generate safe mock response without throwing unhandled crashes."""
    if start_time is None:
        start_time = time.perf_counter()

    # Small simulated wall-clock delay for realism
    time.sleep(0.005)
    latency_ms = (time.perf_counter() - start_time) * 1000.0

    full_input = f"{system_prompt}\n{prompt}".strip() if system_prompt else prompt
    # Estimate token counts based on word count
    input_tokens = max(1, len(full_input.split()))

    mock_text = (
        f"[Mock Fallback ({model_name})]: Simulated response ({note}). "
        f"Prompt summary: '{prompt[:60]}...'"
    )
    output_tokens = max(1, len(mock_text.split()))

    return {
        "text": mock_text,
        "latency_ms": round(latency_ms, 2),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "model": model_name,
    }


def generate(
    model_name: str,
    prompt: str,
    system_prompt: str = "",
) -> Dict[str, Any]:
    """Generate completion using Groq LLM or safe mock fallback.

    Args:
        model_name: Target model identifier ('llama-3.1-8b-instant',
            'qwen/qwen3.8-27b', 'llama-3.3-70b-versatile').
        prompt: User prompt content.
        system_prompt: Optional system prompt instructions.

    Returns:
        dict: {"text": str, "latency_ms": float, "input_tokens": int, "output_tokens": int, "model": str}
    """
    start_time = time.perf_counter()

    # Verify or refresh client
    groq_client = get_groq_client()

    if groq_client is None:
        logger.info(
            "GROQ_API_KEY is not configured or invalid. Using safe mock fallback for %s.",
            model_name,
        )
        return _mock_generate(
            model_name=model_name,
            prompt=prompt,
            system_prompt=system_prompt,
            start_time=start_time,
            note="Safe mock fallback (GROQ_API_KEY not configured)",
        )

    # Prepare chat completion messages
    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = groq_client.chat.completions.create(
            model=model_name,
            messages=messages,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        content = ""
        if response.choices and len(response.choices) > 0:
            content = response.choices[0].message.content or ""

        input_tokens = (
            response.usage.prompt_tokens
            if response.usage and response.usage.prompt_tokens is not None
            else max(1, len((f"{system_prompt} {prompt}").split()))
        )
        output_tokens = (
            response.usage.completion_tokens
            if response.usage and response.usage.completion_tokens is not None
            else max(1, len(content.split()))
        )

        return {
            "text": content,
            "latency_ms": round(latency_ms, 2),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model": model_name,
        }

    except Exception as exc:
        logger.warning(
            "Encountered error while calling Groq API (%s: %s). Falling back to mock response.",
            exc.__class__.__name__,
            exc,
        )
        return _mock_generate(
            model_name=model_name,
            prompt=prompt,
            system_prompt=system_prompt,
            start_time=start_time,
            note=f"Fallback due to {exc.__class__.__name__}",
        )


class ModelClient:
    """Convenience class wrapper for model client invocations."""

    def __init__(self, api_key: Optional[str] = None):
        if api_key:
            os.environ["GROQ_API_KEY"] = api_key
        self.client = get_groq_client()

    def generate(
        self,
        model_name: str,
        prompt: str,
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        return generate(
            model_name=model_name,
            prompt=prompt,
            system_prompt=system_prompt,
        )
