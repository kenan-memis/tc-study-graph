"""Material generation falls back when the OpenAI client raises."""

from unittest.mock import MagicMock, patch

import pytest

from studygraph.graph.workflow import _build_material_with_openai_styled


@patch("studygraph.graph.workflow.call_with_retry")
@patch("studygraph.graph.workflow.OpenAI")
def test_openai_material_returns_fallback_on_api_error(
    mock_openai_cls: MagicMock,
    mock_retry: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    mock_retry.side_effect = RuntimeError("transient failure")
    mock_openai_cls.return_value = MagicMock()

    material, usage = _build_material_with_openai_styled(
        topic="Photosynthesis",
        course="Biology",
        level="high",
        language="English",
        style_hint="Friendly",
        feedback_hint="none",
        external_context="none",
        external_source_url="",
        temperature=0.4,
        top_p=1.0,
    )

    assert usage is None
    assert "Topic summary for Photosynthesis (Biology):" in material
    assert "Core definition and why it matters" in material
