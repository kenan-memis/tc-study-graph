"""Pure math for session rate-limit cooldowns (mirrors studygraph.ui.app._rate_limit_allow)."""

import time


def remaining_block_seconds(prev_monotonic: float | None, now: float, cooldown: float) -> float:
    if prev_monotonic is None:
        return 0.0
    return max(0.0, cooldown - (now - float(prev_monotonic)))


def test_no_previous_allows_immediately() -> None:
    assert remaining_block_seconds(None, 100.0, 8.0) == 0.0


def test_within_cooldown_returns_positive_remainder() -> None:
    t0 = 1000.0
    assert remaining_block_seconds(t0, t0 + 3.0, 8.0) == 5.0


def test_after_cooldown_zero() -> None:
    t0 = 1000.0
    assert remaining_block_seconds(t0, t0 + 8.0, 8.0) == 0.0


def test_real_monotonic_smoke() -> None:
    a = time.monotonic()
    b = time.monotonic()
    assert remaining_block_seconds(a, b, 60.0) > 59.0
