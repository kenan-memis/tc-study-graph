from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


DEFAULT_PROMPTS: dict[str, Any] = {
    "streaming": {
        "system_coach": (
            "You are a concise and encouraging study coach.\n"
            "Return plain text only.\n"
            "When the user asks for a study plan, output only timed activity bullets — never add "
            "Core concept, Key points, worked examples, or common-mistakes sections "
            "(those are a different deliverable)."
        ),
        "study_plan_user_template": (
            "Create a concise study plan for {learner_name}. "
            "Education level: {education_level}. Language: {preferred_language}. "
            "Course: {course}. Topic: {topic}. Goal: {study_goal}. "
            "Response style preference: {style_hint}. "
            "Historical weak concepts in this course only: {weak_text}. "
            "Do not include study advice for other subjects. "
            "Output ONLY a practical timed study plan as 4-6 bullet points "
            "(short activities; you may prefix a time hint like \"5 min:\"). "
            "Stop after those bullets. No paragraphs, no tutorial, no definitions. "
            "Do NOT add separate sections or headings such as: Core concept, Key points, "
            "Worked mini-example, Worked example, Common mistakes, definitions lists, or "
            "reference/Wikipedia links — that detailed content is produced elsewhere as study material. "
            "Do not duplicate or preview the study material layout. "
            "Never output a block titled \"Topic summary for ...\" or the generic placeholder bullets "
            "(e.g. \"Core definition and why it matters\", \"2-3 key rules/formulas\") — those belong "
            "only in study material, not in the timed plan."
        ),
        "recommendation_user_template": (
            "Write a short next-step recommendation for a student. "
            "Name: {learner_name}. Level: {education_level}. "
            "Course: {course}. Topic: {topic}. "
            "Response style preference: {style_hint}. "
            "Score: {score_percent}%. Key mistakes: {feedback_text}. "
            "Return 3-5 concise bullet points."
        ),
    },
    "generation": {
        "quiz_user_prompt_template": (
            "Generate exactly 5 multiple-choice questions in JSON array format. "
            "Each item must have keys: question, options, correct_answer, explanation. "
            "Topic: {topic}. Course: {course}. Student level: {level}. Language: {language}. "
            "Options should include 4 choices and correct_answer must match one option exactly. "
            "Return JSON only."
        ),
        "material_user_prompt_template": (
            "Create concise study material in plain text with bullets. "
            "Course: {course}. Topic: {topic}. Student level: {level}. Language: {language}. "
            "Response style preference: {style_hint}. "
            "Feedback preferences from past sessions in this course: {feedback_hint}. "
            "External context (if available): {external_context}. "
            "If external context is present, use it for factual grounding and keep it concise. "
            "Sections: core concept, key points, worked mini-example, common mistakes. "
            "Keep it under 220 words."
        ),
        "material_fallback_template": (
            "Topic summary for {topic} ({course}):\n"
            "- Core definition and why it matters.\n"
            "- 2-3 key rules/formulas.\n"
            "- One short example with explanation.\n"
            "- Common mistakes to avoid.\n"
        ),
        "material_generation_failure_template": "Study material could not be generated for {topic}.",
    },
    "evaluation": {
        "recommendation_low_template": (
            "Score {score}%. Focus on fundamentals in {topic} next session with easier questions."
        ),
        "recommendation_mid_template": (
            "Score {score}%. Keep practicing {topic} and review the mistakes once more."
        ),
        "recommendation_high_template": (
            "Score {score}%. Great progress. Move to the next advanced topic in {course}."
        ),
    },
    "ui": {
        "app_title": "StudyGraph",
        "app_subtitle": "LangGraph-based student study and exam preparation assistant",
        "sidebar_profile_manager": "Profile Manager",
        "no_profile_yet": "No profile yet",
        "create_profile_section": "Create or update profile",
        "fixed_footer_line_1": "Sprint 3 – Building with AI Agents",
        "fixed_footer_line_2": "Turing College 2026",
        "create_profile_prompt": "Create at least one profile from the sidebar to start studying.",
        "duplicate_profile_warning": (
            "An identical profile already exists: `{profile_id}`. "
            "Please select it from the profile list or update that profile."
        ),
        "no_profile_loaded_warning": "Selected profile could not be loaded.",
        "material_ready_success": "Study plan and material ready.",
        "quiz_ready_success": "Quiz generated. Continue with exercises below.",
        "rate_limit_wait": (
            "Please wait {seconds}s before using this action again (protects API usage)."
        ),
        "error_profile_create": (
            "We couldn't create the profile. Please check your inputs and try again."
        ),
        "error_profile_update": (
            "We couldn't update the profile. Please check your inputs and try again."
        ),
        "error_save_settings": "We couldn't save settings. Please try again.",
        "error_prepare_session": "We couldn't prepare your study session. Please try again.",
        "error_save_feedback": "We couldn't save your feedback. Please try again.",
        "error_generate_quiz": "We couldn't generate the quiz. Please try again.",
        "error_evaluate_quiz": "We couldn't evaluate your answers. Please try again.",
        "error_graph_generic": "Something went wrong. Please try again.",
    },
}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


@lru_cache(maxsize=1)
def get_prompts() -> dict[str, Any]:
    prompt_file = Path(__file__).with_name("prompts.yaml")
    if not prompt_file.exists():
        return deepcopy(DEFAULT_PROMPTS)
    raw = yaml.safe_load(prompt_file.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return deepcopy(DEFAULT_PROMPTS)
    return _merge(DEFAULT_PROMPTS, raw)


def render_prompt(path: str, **kwargs: Any) -> str:
    data: Any = get_prompts()
    for part in path.split("."):
        if not isinstance(data, dict) or part not in data:
            raise KeyError(f"Prompt key not found: {path}")
        data = data[part]
    if not isinstance(data, str):
        raise TypeError(f"Prompt value is not a string: {path}")
    return data.format(**kwargs)
