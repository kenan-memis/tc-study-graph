"""Pydantic validation for session and profile inputs."""

import pytest
from pydantic import ValidationError

from studygraph.models import StudySessionInput


def test_study_session_input_accepts_valid_defaults() -> None:
    s = StudySessionInput(course="Math", topic="Division")
    assert s.course == "Math"
    assert s.topic == "Division"
    assert s.temperature == 0.4
    assert s.top_p == 1.0
    assert s.llm_provider == "openai"


def test_study_session_input_strips_whitespace() -> None:
    s = StudySessionInput(course="  Biology  ", topic="  Cells  ")
    assert s.course == "Biology"
    assert s.topic == "Cells"


def test_study_session_input_rejects_empty_course() -> None:
    with pytest.raises(ValidationError):
        StudySessionInput(course="", topic="x")


def test_study_session_input_rejects_empty_topic() -> None:
    with pytest.raises(ValidationError):
        StudySessionInput(course="Math", topic="")


def test_study_session_input_temperature_bounds() -> None:
    with pytest.raises(ValidationError):
        StudySessionInput(course="Math", topic="x", temperature=3.0)
    with pytest.raises(ValidationError):
        StudySessionInput(course="Math", topic="x", temperature=-0.1)


def test_study_session_input_top_p_bounds() -> None:
    with pytest.raises(ValidationError):
        StudySessionInput(course="Math", topic="x", top_p=1.1)
