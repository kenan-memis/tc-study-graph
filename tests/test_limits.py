"""Ensure ``studygraph.limits`` matches Pydantic ``maxLength`` in models."""

from __future__ import annotations

from studygraph.limits import (
    MAX_COURSE,
    MAX_FEEDBACK_NOTE,
    MAX_LEARNER_NAME,
    MAX_TOPIC,
)
from studygraph.models import FeedbackRecord, StudentProfile, StudySessionInput


def test_limits_match_json_schema_max_length() -> None:
    assert (
        StudentProfile.model_json_schema()["properties"]["learner_name"]["maxLength"]
        == MAX_LEARNER_NAME
    )
    assert (
        StudySessionInput.model_json_schema()["properties"]["course"]["maxLength"]
        == MAX_COURSE
    )
    assert (
        StudySessionInput.model_json_schema()["properties"]["topic"]["maxLength"]
        == MAX_TOPIC
    )
    assert (
        FeedbackRecord.model_json_schema()["properties"]["note"]["maxLength"]
        == MAX_FEEDBACK_NOTE
    )
