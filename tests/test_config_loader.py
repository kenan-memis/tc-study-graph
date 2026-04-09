"""YAML config loaders for UI constants and tunable settings."""

from __future__ import annotations

from studygraph.config.loader import get_app_settings, get_ui_constants


def test_ui_constants_load_and_match_courses_count() -> None:
    ui = get_ui_constants()
    assert ui.select_placeholder
    assert len(ui.standard_courses) == 8
    assert ui.other_course_label not in ui.standard_courses


def test_app_settings_rate_limits_and_models() -> None:
    s = get_app_settings()
    assert s.rate_limit_seconds("generate_plan_material") >= 1.0
    assert s.rate_limit_seconds("start_quiz") >= 1.0
    assert "gpt" in s.model_openai_chat.lower() or s.model_openai_chat
    assert "gemini" in s.model_gemini_generate.lower() or s.model_gemini_generate


def test_session_presets_align_with_goal_and_style_labels() -> None:
    ui = get_ui_constants()
    goals = set(ui.study_goal_labels)
    styles = set(ui.response_style_labels)
    for p in ui.session_presets:
        assert p.study_goal in goals, p.label
        assert p.response_style in styles, p.label
