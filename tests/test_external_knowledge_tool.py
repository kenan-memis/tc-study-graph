from __future__ import annotations

import json

import studygraph.tools.external_knowledge as ek


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_fetch_wikipedia_summary_success(monkeypatch) -> None:
    payload = {
        "title": "Algebra",
        "extract": "Algebra is one of the broad areas of mathematics.",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Algebra"}},
    }
    monkeypatch.setattr(
        ek.request, "urlopen", lambda req, timeout=8: _FakeResponse(payload)
    )
    result = ek.fetch_wikipedia_summary("Algebra")
    assert result["success"] is True
    assert "Algebra" in str(result.get("title"))
    assert "mathematics" in str(result.get("summary", "")).lower()


def test_fetch_wikipedia_summary_failure(monkeypatch) -> None:
    def _raise(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr(ek.request, "urlopen", _raise)
    result = ek.fetch_wikipedia_summary("Algebra")
    assert result["success"] is False
