"""Readable, non-leaking error messages for Streamlit + server-side exception logging."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def log_exception(context: str, exc: BaseException) -> None:
    """Log full traceback for operators; never pass this string to end users."""
    logger.exception("%s", context, exc_info=exc)


def user_facing_message(exc: BaseException, *, default: str) -> str:
    """Map known failures to short copy. Never returns raw ``str(exc)`` (may leak internals)."""
    try:
        from openai import APIConnectionError, APITimeoutError, RateLimitError

        if isinstance(exc, APITimeoutError):
            return "The AI request timed out. Please try again in a moment."
        if isinstance(exc, RateLimitError):
            return "The AI service is rate-limiting requests. Wait briefly and try again."
        if isinstance(exc, APIConnectionError):
            return "Could not reach the AI service. Check your network and try again."
    except ImportError:
        pass

    if isinstance(exc, TimeoutError):
        return "The operation timed out. Please try again."
    if isinstance(exc, (ConnectionError, OSError)):
        return "A network problem occurred. Please try again."
    if isinstance(exc, MemoryError):
        return "The app ran out of memory for this action. Try a smaller topic or restart."

    return default


def sanitize_graph_error_message(message: Any, *, fallback: str) -> str:
    """Allow short in-app graph errors; block traceback-like or oversized blobs."""
    if message is None:
        return fallback
    text = str(message).strip()
    if not text:
        return fallback
    if len(text) > 280:
        return fallback
    if "\n" in text or "Traceback" in text or "File \"" in text:
        return fallback
    return text
