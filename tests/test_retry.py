from __future__ import annotations

import studygraph.utils.retry as retry_mod
from studygraph.utils import call_with_retry


def test_call_with_retry_succeeds_after_transient_failure(monkeypatch) -> None:
    attempts = {"n": 0}
    monkeypatch.setattr(retry_mod.time, "sleep", lambda _: None)

    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise TimeoutError("temporary timeout")
        return "ok"

    result = call_with_retry(flaky, max_attempts=3)
    assert result == "ok"
    assert attempts["n"] == 2


def test_call_with_retry_does_not_retry_non_transient(monkeypatch) -> None:
    attempts = {"n": 0}
    monkeypatch.setattr(retry_mod.time, "sleep", lambda _: None)

    def non_transient() -> str:
        attempts["n"] += 1
        raise ValueError("invalid payload format")

    try:
        call_with_retry(non_transient, max_attempts=3)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")
    assert attempts["n"] == 1


def test_call_with_retry_stops_after_max_attempts(monkeypatch) -> None:
    attempts = {"n": 0}
    monkeypatch.setattr(retry_mod.time, "sleep", lambda _: None)

    def always_timeout() -> str:
        attempts["n"] += 1
        raise TimeoutError("still failing")

    try:
        call_with_retry(always_timeout, max_attempts=3)
    except TimeoutError:
        pass
    else:
        raise AssertionError("Expected TimeoutError")
    assert attempts["n"] == 3
