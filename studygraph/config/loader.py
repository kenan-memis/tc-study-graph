"""Load ``settings.yaml`` and ``constants.yaml`` for the Streamlit UI."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


_CONFIG_DIR = Path(__file__).resolve().parent


def _read_yaml(name: str) -> dict[str, Any]:
    path = _CONFIG_DIR / name
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass(frozen=True)
class SessionPreset:
    label: str
    course: str
    course_other: str
    topic: str
    study_goal: str
    response_style: str


@dataclass(frozen=True)
class UIConstants:
    select_placeholder: str
    other_course_label: str
    topic_area_placeholder: str
    standard_courses: tuple[str, ...]
    study_goal_labels: tuple[str, ...]
    response_style_labels: tuple[str, ...]
    feedback_reason_options: tuple[str, ...]
    session_presets: tuple[SessionPreset, ...]
    education_value_to_label: dict[str, str]
    education_options: dict[str, str]
    difficulty_value_to_label: dict[str, str]
    difficulty_options: dict[str, str]
    pace_value_to_label: dict[str, str]
    pace_options: dict[str, str]
    preferred_language_extra_labels: tuple[str, ...]
    regenerate_clear_keys: tuple[str, ...]
    reset_extra_keys: tuple[str, ...]
    quiz_answer_key_pattern: re.Pattern[str]
    rate_limit_state_actions: tuple[str, ...]


@dataclass(frozen=True)
class AppSettings:
    rate_limits_seconds: dict[str, float]
    model_openai_chat: str
    model_gemini_generate: str
    gemini_generate_content_url_template: str

    def rate_limit_seconds(self, action_id: str) -> float:
        return float(self.rate_limits_seconds[action_id])

    def gemini_generate_url(self, api_key: str) -> str:
        return self.gemini_generate_content_url_template.format(
            model=self.model_gemini_generate,
            api_key=api_key,
        )


_DEFAULT_SETTINGS: dict[str, Any] = {
    "rate_limits_seconds": {
        "generate_plan_material": 8.0,
        "start_quiz": 6.0,
        "evaluate_quiz": 6.0,
    },
    "models": {
        "openai_chat": "gpt-5.2",
        "gemini_generate": "gemini-2.5-flash",
    },
    "gemini": {
        "generate_content_url_template": (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "{model}:generateContent?key={api_key}"
        ),
    },
}


def _build_ui_constants(data: dict[str, Any]) -> UIConstants:
    ui = data.get("ui") or {}
    pf = data.get("profile_form") or {}
    ss = data.get("session_state") or {}
    presets_raw = data.get("session_presets") or []
    presets: list[SessionPreset] = []
    for row in presets_raw:
        if not isinstance(row, dict):
            continue
        presets.append(
            SessionPreset(
                label=str(row["label"]),
                course=str(row["course"]),
                course_other=str(row.get("course_other", "")),
                topic=str(row["topic"]),
                study_goal=str(row["study_goal"]),
                response_style=str(row["response_style"]),
            )
        )
    pat = str(data.get("quiz_answer_key_pattern") or r"^quiz_\d+$")
    return UIConstants(
        select_placeholder=str(ui.get("select_placeholder", "Select...")),
        other_course_label=str(ui.get("other_course_label", "Other…")),
        topic_area_placeholder=str(
            ui.get(
                "topic_area_placeholder",
                "Describe what you want to study.",
            )
        ),
        standard_courses=tuple(data.get("standard_courses") or ()),
        study_goal_labels=tuple(data.get("study_goal_labels") or ()),
        response_style_labels=tuple(data.get("response_style_labels") or ()),
        feedback_reason_options=tuple(data.get("feedback_reason_options") or ()),
        session_presets=tuple(presets),
        education_value_to_label=dict(pf.get("education_value_to_label") or {}),
        education_options=dict(pf.get("education_options") or {}),
        difficulty_value_to_label=dict(pf.get("difficulty_value_to_label") or {}),
        difficulty_options=dict(pf.get("difficulty_options") or {}),
        pace_value_to_label=dict(pf.get("pace_value_to_label") or {}),
        pace_options=dict(pf.get("pace_options") or {}),
        preferred_language_extra_labels=tuple(
            pf.get("preferred_language_extra_labels") or ()
        ),
        regenerate_clear_keys=tuple(ss.get("regenerate_clear_keys") or ()),
        reset_extra_keys=tuple(ss.get("reset_extra_keys") or ()),
        quiz_answer_key_pattern=re.compile(pat),
        rate_limit_state_actions=tuple(data.get("rate_limit_state_actions") or ()),
    )


def _build_app_settings(data: dict[str, Any]) -> AppSettings:
    models = data.get("models") or {}
    gem = data.get("gemini") or {}
    return AppSettings(
        rate_limits_seconds={
            k: float(v) for k, v in (data.get("rate_limits_seconds") or {}).items()
        },
        model_openai_chat=str(models.get("openai_chat", "gpt-5.2")),
        model_gemini_generate=str(models.get("gemini_generate", "gemini-2.5-flash")),
        gemini_generate_content_url_template=str(
            gem.get(
                "generate_content_url_template",
                _DEFAULT_SETTINGS["gemini"]["generate_content_url_template"],
            )
        ),
    )


@lru_cache(maxsize=1)
def get_ui_constants() -> UIConstants:
    merged = _read_yaml("constants.yaml")
    return _build_ui_constants(merged)


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    merged = _merge(_DEFAULT_SETTINGS, _read_yaml("settings.yaml"))
    return _build_app_settings(merged)


def read_button_styles_css() -> str:
    path = _CONFIG_DIR / "button_styles.css"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def read_footer_snippet_html() -> str:
    path = _CONFIG_DIR / "footer_snippet.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return (
        '<div class="sg-footer-spacer"></div>'
        '<div class="sg-fixed-footer"><div>__FOOTER_LINE_1__</div>'
        '<div>__FOOTER_LINE_2__</div></div>'
    )
