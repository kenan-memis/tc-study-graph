from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def is_transient_error(exc: Exception) -> bool:
    """Best-effort transient error detection for provider/network calls."""
    code = getattr(exc, "status", None)
    if code is None:
        code = getattr(exc, "code", None)
    if isinstance(code, int) and (code == 429 or 500 <= code < 600):
        return True
    if isinstance(exc, (TimeoutError, OSError)):
        return True

    text = str(exc).lower()
    transient_markers = [
        "timeout",
        "timed out",
        "connection",
        "temporarily unavailable",
        "service unavailable",
        "rate limit",
        "try again",
        "overloaded",
        "reset by peer",
    ]
    return any(marker in text for marker in transient_markers)


def call_with_retry(
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.5,
    jitter_seconds: float = 0.15,
    should_retry: Callable[[Exception], bool] | None = None,
) -> T:
    """Call function with exponential backoff retries on transient errors."""
    should_retry_fn = should_retry or is_transient_error
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except Exception as exc:
            if attempt >= max_attempts or not should_retry_fn(exc):
                raise
            delay = (base_delay_seconds * (2 ** (attempt - 1))) + random.uniform(
                0.0, jitter_seconds
            )
            time.sleep(delay)
