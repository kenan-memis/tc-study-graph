"""User-facing error helpers (no raw exception strings to UI)."""

from studygraph.utils.ui_errors import sanitize_graph_error_message, user_facing_message


def test_sanitize_allows_short_graph_message() -> None:
    msg = "Profile 'demo' was not found."
    assert (
        sanitize_graph_error_message(msg, fallback="fallback")
        == msg
    )


def test_sanitize_rejects_oversized_message() -> None:
    blob = "x" * 400
    assert sanitize_graph_error_message(blob, fallback="safe") == "safe"


def test_sanitize_rejects_traceback_like() -> None:
    assert (
        sanitize_graph_error_message(
            'Error\n  File "app.py", line 1\nTraceback',
            fallback="safe",
        )
        == "safe"
    )


def test_user_facing_generic_exception_uses_default() -> None:
    assert (
        user_facing_message(
            ValueError("internal secret detail"),
            default="Please try again.",
        )
        == "Please try again."
    )


def test_user_facing_timeout_error_readable() -> None:
    out = user_facing_message(TimeoutError(), default="default")
    assert "timed out" in out.lower()
    assert "default" not in out.lower()
