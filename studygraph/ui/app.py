from __future__ import annotations

from pathlib import Path
import os
import json
from collections import defaultdict
from typing import Generator
from datetime import datetime, timezone
from urllib import request

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from studygraph.graph import build_evaluation_graph, build_prepare_graph, build_quiz_graph
from studygraph.memory import MemoryStore
from studygraph.models import FeedbackRecord, StudySessionInput, StudentProfile
from studygraph.prompts import render_prompt
from studygraph.usage import (
    build_usage_record,
    summarize_usage,
)
from studygraph.utils import call_with_retry, trim_material_sections_from_study_plan


load_dotenv()

STANDARD_COURSES = [
    "Math",
    "Biology",
    "Chemistry",
    "Physics",
    "History",
    "Geography",
    "English",
    "Computer science",
]
SELECT_PLACEHOLDER = "Select..."
FEEDBACK_REASON_OPTIONS = [
    "too long",
    "too short",
    "too hard",
    "too easy",
    "not enough examples",
    "too much theory",
    "unclear structure",
]


def _store() -> MemoryStore:
    root = Path(__file__).resolve().parents[2]
    return MemoryStore(base_dir=root / "data" / "memory")


def _settings_file_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    path = root / "data" / "memory" / "app_settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_app_settings() -> dict[str, float | str]:
    default = {"llm_provider": "openai", "temperature": 0.4, "top_p": 1.0}
    path = _settings_file_path()
    if not path.exists():
        return default
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return default
        provider = str(raw.get("llm_provider", "openai")).strip().lower()
        if provider not in {"openai", "gemini"}:
            provider = "openai"
        temperature = float(raw.get("temperature", 0.4))
        top_p = float(raw.get("top_p", 1.0))
        temperature = min(2.0, max(0.0, temperature))
        top_p = min(1.0, max(0.0, top_p))
        return {"llm_provider": provider, "temperature": temperature, "top_p": top_p}
    except Exception:
        return default


def _save_app_settings(*, llm_provider: str, temperature: float, top_p: float) -> None:
    path = _settings_file_path()
    payload = {
        "llm_provider": llm_provider,
        "temperature": float(temperature),
        "top_p": float(top_p),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _provider_key_available(provider: str) -> bool:
    if provider == "gemini":
        return bool((os.getenv("GEMINI_API_KEY") or "").strip())
    return bool((os.getenv("OPENAI_API_KEY") or "").strip())


def _safe_ui_error(context: str) -> str:
    return f"{context}. Please try again."


def _append_usage_record(record: dict | None) -> None:
    if not record:
        return
    if "usage_records" not in st.session_state:
        st.session_state["usage_records"] = []
    st.session_state["usage_records"].append(record)


def _approx_token_count(text: str) -> int:
    # Lightweight approximation for providers/paths that do not return usage.
    cleaned = (text or "").strip()
    if not cleaned:
        return 0
    return max(1, round(len(cleaned) / 4))


def _append_estimated_stream_usage(
    *,
    provider: str,
    call_type: str,
    prompt_text: str,
    completion_text: str,
) -> None:
    model = "gemini-2.5-flash" if provider == "gemini" else "gpt-5.2"
    _append_usage_record(
        build_usage_record(
            provider=provider,
            model=model,
            call_type=call_type,
            prompt_tokens=_approx_token_count(prompt_text),
            completion_tokens=_approx_token_count(completion_text),
            note="Estimated from streamed text length.",
        )
    )


def _stream_text_from_openai(
    prompt: str,
    fallback_text: str,
    *,
    temperature: float = 0.4,
    top_p: float = 1.0,
    call_type: str = "stream_text",
) -> Generator[str, None, None]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        yield fallback_text
        return

    try:
        client = OpenAI(api_key=api_key, timeout=20.0)
        system_prompt = render_prompt("streaming.system_coach")
        stream = call_with_retry(
            lambda: client.chat.completions.create(
                model="gpt-5.2",
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                top_p=top_p,
                stream=True,
            )
        )
        emitted = False
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                emitted = True
                yield token
        if not emitted:
            yield fallback_text
    except Exception:
        yield fallback_text


def _stream_text_from_gemini(
    prompt: str,
    fallback_text: str,
    *,
    temperature: float = 0.4,
    top_p: float = 1.0,
    call_type: str = "stream_text",
) -> Generator[str, None, None]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        yield fallback_text
        return
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "topP": top_p},
    }
    try:
        def _request_body() -> dict:
            req = request.Request(
                url=url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))

        body = call_with_retry(_request_body)
        parts = body["candidates"][0]["content"]["parts"]
        text = "".join([p.get("text", "") for p in parts if isinstance(p, dict)]).strip()
        yield text or fallback_text
    except Exception:
        yield fallback_text


def _collect_stream_text(
    prompt: str,
    fallback_text: str,
    *,
    provider: str,
    temperature: float,
    top_p: float,
    call_type: str,
) -> str:
    """Consume the stream in memory (no ``st.write_stream``).

    Streamlit's ``write_stream`` nests an inner ``empty()`` and flushes the full
    untrimmed string there; a follow-up ``markdown`` on the parent slot does not
    replace that inner node, so the UI could keep showing duplicate material.
    """
    return "".join(
        _stream_text_with_provider(
            prompt,
            fallback_text,
            provider=provider,
            temperature=temperature,
            top_p=top_p,
            call_type=call_type,
        )
    )


def _stream_text_with_provider(
    prompt: str,
    fallback_text: str,
    *,
    provider: str,
    temperature: float,
    top_p: float,
    call_type: str,
) -> Generator[str, None, None]:
    if provider == "gemini":
        return _stream_text_from_gemini(
            prompt,
            fallback_text,
            temperature=temperature,
            top_p=top_p,
            call_type=call_type,
        )
    return _stream_text_from_openai(
        prompt,
        fallback_text,
        temperature=temperature,
        top_p=top_p,
        call_type=call_type,
    )


def _build_study_plan_stream_prompt(
    profile: StudentProfile,
    session_input: StudySessionInput,
    weak_summary: list[tuple[str, int]],
) -> str:
    weak_text = ", ".join([f"{name} ({count})" for name, count in weak_summary]) or "none yet"
    return render_prompt(
        "streaming.study_plan_user_template",
        learner_name=profile.learner_name,
        education_level=profile.education_level,
        preferred_language=profile.preferred_language,
        course=session_input.course,
        topic=session_input.topic,
        study_goal=session_input.study_goal,
        style_hint=session_input.response_style,
        weak_text=weak_text,
    )


def _build_recommendation_stream_prompt(
    profile: StudentProfile,
    session_input: StudySessionInput,
    score_percent: float,
    feedback: list[str],
) -> str:
    feedback_text = " | ".join(feedback[:3]) if feedback else "No major mistakes."
    return render_prompt(
        "streaming.recommendation_user_template",
        learner_name=profile.learner_name,
        education_level=profile.education_level,
        course=session_input.course,
        topic=session_input.topic,
        style_hint=session_input.response_style,
        score_percent=score_percent,
        feedback_text=feedback_text,
    )


def _render_footer() -> None:
    footer_line_1 = render_prompt("ui.fixed_footer_line_1")
    footer_line_2 = render_prompt("ui.fixed_footer_line_2")
    footer_html = """
        <style>
          .sg-fixed-footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            border-top: 1px solid #e9ecef;
            color: #6c757d;
            font-size: 0.9em;
            text-align: center;
            line-height: 1.4;
            padding: 0.55rem 0.75rem;
            background: rgba(255, 255, 255, 0.96);
            z-index: 99999;
            backdrop-filter: blur(3px);
          }
          .sg-footer-spacer {
            height: 56px;
          }
        </style>
        <div class="sg-footer-spacer"></div>
        <div class="sg-fixed-footer">
          <div>__FOOTER_LINE_1__</div>
          <div>__FOOTER_LINE_2__</div>
        </div>
        """
    footer_html = footer_html.replace("__FOOTER_LINE_1__", footer_line_1).replace(
        "__FOOTER_LINE_2__", footer_line_2
    )
    st.markdown(
        footer_html,
        unsafe_allow_html=True,
    )


def _inject_button_styles() -> None:
    st.markdown(
        """
        <style>
          /* Main CTA: avoid warning-like red tone */
          div[data-testid="stButton"] > button[kind="primary"] {
            background-color: #4caf50 !important;
            border-color: #4caf50 !important;
            color: #ffffff !important;
          }
          div[data-testid="stButton"] > button[kind="primary"]:hover {
            background-color: #43a047 !important;
            border-color: #43a047 !important;
          }

          /* Sidebar primary buttons should be orange (e.g., update profile) */
          section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"] {
            background-color: #fb8c00 !important;
            border-color: #fb8c00 !important;
            color: #ffffff !important;
          }
          section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"]:hover {
            background-color: #f57c00 !important;
            border-color: #f57c00 !important;
          }

          /* Sidebar action buttons default to light blue */
          section[data-testid="stSidebar"] div[data-testid="stButton"] > button {
            background-color: #edf5ff !important;
            border-color: #b6d6ff !important;
            color: #24559a !important;
          }
          section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
            background-color: #deeeff !important;
            border-color: #9ec8ff !important;
          }

          /* Primary actions inside expanders (e.g. feedback submit) -> orange */
          div[data-testid="stExpander"] div[data-testid="stButton"] > button[kind="primary"] {
            background-color: #fb8c00 !important;
            border-color: #fb8c00 !important;
            color: #ffffff !important;
          }
          div[data-testid="stExpander"] div[data-testid="stButton"] > button[kind="primary"]:hover {
            background-color: #f57c00 !important;
            border-color: #f57c00 !important;
          }

          /* Download button visual separation -> light red */
          div[data-testid="stDownloadButton"] > button {
            background-color: #ffebee !important;
            border-color: #ef9a9a !important;
            color: #b71c1c !important;
          }
          div[data-testid="stDownloadButton"] > button:hover {
            background-color: #ffcdd2 !important;
            border-color: #e57373 !important;
          }

        </style>
        """,
        unsafe_allow_html=True,
    )


def _group_history_by_course(
    history: list,
) -> list[tuple[str, list]]:
    """Return [(course_label, sessions_newest_first), ...] sorted by course name."""
    buckets: dict[str, list] = defaultdict(list)
    display: dict[str, str] = {}

    def key_for(course: str) -> str:
        k = (course or "").strip().lower()
        return k if k else "(no course)"

    for rec in history:
        k = key_for(rec.course)
        buckets[k].append(rec)
        if k not in display:
            display[k] = (rec.course or "").strip() or "(no course)"

    out: list[tuple[str, list]] = []
    for k in sorted(buckets.keys(), key=lambda x: display[x].lower()):
        sessions = sorted(buckets[k], key=lambda r: r.created_at, reverse=True)
        out.append((display[k], sessions))
    return out


def _course_progress(history: list[dict]) -> list[tuple[str, float, int]]:
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for item in history:
        course = item.get("course", "").strip()
        score = float(item.get("score_percent", 0.0))
        if not course:
            continue
        sums[course] = sums.get(course, 0.0) + score
        counts[course] = counts.get(course, 0) + 1
    result = []
    for course, total in sums.items():
        cnt = counts[course]
        result.append((course, round(total / cnt, 1), cnt))
    return sorted(result, key=lambda x: x[0].lower())


def _history_rows(history: list) -> list[dict]:
    rows = []
    for record in reversed(history):
        ts = record.created_at
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            ts = dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            pass
        rows.append(
            {
                "When": ts,
                "Course": record.course,
                "Topic": record.topic,
                "Score (%)": record.score_percent,
                "Weak Concepts": ", ".join(record.weak_concepts[:3]) if record.weak_concepts else "-",
            }
        )
    return rows


def _sync_profile_form_state(
    form_mode: str, active_profile_id: str | None, profile: StudentProfile | None
) -> None:
    marker = f"{form_mode}:{active_profile_id or '__none__'}"
    if st.session_state.get("profile_form_loaded_for") == marker:
        return

    education_value_to_label = {
        "primary": "Primary",
        "middle": "Middle",
        "high": "High",
        "university_exam_prep": "University exam prep",
    }
    difficulty_value_to_label = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}
    pace_value_to_label = {"slow": "Slow", "balanced": "Balanced", "fast": "Fast"}

    if form_mode == "Edit selected profile" and profile is not None:
        st.session_state["pf_learner_name"] = profile.learner_name
        st.session_state["pf_education_level"] = education_value_to_label.get(
            profile.education_level, "High"
        )
        st.session_state["pf_preferred_language"] = profile.preferred_language
        st.session_state["pf_preferred_difficulty"] = difficulty_value_to_label.get(
            profile.preferred_difficulty, "Medium"
        )
        st.session_state["pf_preferred_pace"] = pace_value_to_label.get(
            profile.preferred_pace, "Balanced"
        )
    else:
        st.session_state["pf_learner_name"] = ""
        st.session_state["pf_education_level"] = SELECT_PLACEHOLDER
        st.session_state["pf_preferred_language"] = SELECT_PLACEHOLDER
        st.session_state["pf_preferred_difficulty"] = SELECT_PLACEHOLDER
        st.session_state["pf_preferred_pace"] = SELECT_PLACEHOLDER
    st.session_state["profile_form_loaded_for"] = marker


def main() -> None:
    st.set_page_config(page_title="StudyGraph", page_icon="📘", layout="wide")
    _inject_button_styles()
    st.title(render_prompt("ui.app_title"))
    st.caption(render_prompt("ui.app_subtitle"))
    store = _store()
    saved_settings = _load_app_settings()

    st.sidebar.header(render_prompt("ui.sidebar_profile_manager"))
    profile_ids = store.list_profile_ids()
    selected = st.sidebar.selectbox("Select profile", options=[SELECT_PLACEHOLDER] + profile_ids)
    active_profile_id = selected if selected != SELECT_PLACEHOLDER else None
    selected_profile = store.load_profile(active_profile_id) if active_profile_id else None
    if "profile_form_mode" not in st.session_state:
        st.session_state["profile_form_mode"] = (
            "Edit selected profile" if selected_profile else "Create new profile"
        )

    with st.sidebar.expander(render_prompt("ui.create_profile_section"), expanded=False):
        form_mode = st.radio(
            "Profile action",
            options=["Create new profile", "Edit selected profile"],
            key="profile_form_mode",
        )
        _sync_profile_form_state(form_mode, active_profile_id, selected_profile)
        learner_name = st.text_input("Learner name", key="pf_learner_name")
        education_options = {
            "Primary": "primary",
            "Middle": "middle",
            "High": "high",
            "University exam prep": "university_exam_prep",
        }
        education_level = st.selectbox(
            "Education level",
            options=[SELECT_PLACEHOLDER] + list(education_options.keys()),
            key="pf_education_level",
        )
        preferred_language = st.selectbox(
            "Preferred language",
            options=[SELECT_PLACEHOLDER, "English"],
            key="pf_preferred_language",
        )
        difficulty_options = {"Easy": "easy", "Medium": "medium", "Hard": "hard"}
        pace_options = {"Slow": "slow", "Balanced": "balanced", "Fast": "fast"}
        preferred_difficulty = st.selectbox(
            "Preferred difficulty",
            options=[SELECT_PLACEHOLDER] + list(difficulty_options.keys()),
            key="pf_preferred_difficulty",
        )
        preferred_pace = st.selectbox(
            "Preferred pace",
            options=[SELECT_PLACEHOLDER] + list(pace_options.keys()),
            key="pf_preferred_pace",
        )

        if form_mode == "Create new profile" and st.button("Save as new profile"):
            try:
                if not learner_name.strip():
                    st.error("Learner name is required.")
                    st.stop()
                if education_level == SELECT_PLACEHOLDER:
                    st.error("Please select an education level.")
                    st.stop()
                if preferred_language == SELECT_PLACEHOLDER:
                    st.error("Please select a preferred language.")
                    st.stop()
                if preferred_difficulty == SELECT_PLACEHOLDER:
                    st.error("Please select a preferred difficulty.")
                    st.stop()
                if preferred_pace == SELECT_PLACEHOLDER:
                    st.error("Please select a preferred pace.")
                    st.stop()
                profile = StudentProfile(
                    learner_name=learner_name,
                    education_level=education_options[education_level],
                    preferred_language=preferred_language,
                    preferred_difficulty=difficulty_options[preferred_difficulty],
                    preferred_pace=pace_options[preferred_pace],
                )
                duplicate_id = store.find_duplicate_profile(profile)
                if duplicate_id is not None:
                    st.warning(render_prompt("ui.duplicate_profile_warning", profile_id=duplicate_id))
                    st.stop()
                new_id = store.create_profile_id(profile.learner_name)
                store.save_profile(new_id, profile)
                st.success(f"Created profile: {new_id}")
                st.rerun()
            except Exception:
                st.error(_safe_ui_error("Failed to create profile"))

        if form_mode == "Edit selected profile" and selected_profile and st.button(
            "Update selected profile", type="primary"
        ):
            try:
                if not learner_name.strip():
                    st.error("Learner name is required.")
                    st.stop()
                if education_level == SELECT_PLACEHOLDER:
                    st.error("Please select an education level.")
                    st.stop()
                if preferred_language == SELECT_PLACEHOLDER:
                    st.error("Please select a preferred language.")
                    st.stop()
                if preferred_difficulty == SELECT_PLACEHOLDER:
                    st.error("Please select a preferred difficulty.")
                    st.stop()
                if preferred_pace == SELECT_PLACEHOLDER:
                    st.error("Please select a preferred pace.")
                    st.stop()
                profile = StudentProfile(
                    learner_name=learner_name,
                    education_level=education_options[education_level],
                    preferred_language=preferred_language,
                    preferred_difficulty=difficulty_options[preferred_difficulty],
                    preferred_pace=pace_options[preferred_pace],
                )
                store.save_profile(active_profile_id, profile)
                st.success(f"Updated profile: {active_profile_id}")
            except Exception:
                st.error(_safe_ui_error("Failed to update profile"))
        if form_mode == "Edit selected profile" and not selected_profile:
            st.info("Select a profile first to edit it.")

    st.sidebar.divider()
    st.sidebar.header("General Settings")
    provider_label_options = {"OpenAI": "openai", "Gemini": "gemini"}
    provider_labels = list(provider_label_options.keys())
    default_provider_label = (
        "Gemini" if saved_settings["llm_provider"] == "gemini" else "OpenAI"
    )
    gs_provider = st.sidebar.selectbox(
        "LLM provider",
        options=provider_labels,
        index=provider_labels.index(default_provider_label),
        key="gs_provider_choice",
    )
    gs_temperature = st.sidebar.slider(
        "Temperature",
        min_value=0.0,
        max_value=2.0,
        value=float(saved_settings["temperature"]),
        step=0.1,
        key="gs_temperature_value",
        help="Lower = more deterministic, higher = more creative.",
    )
    gs_top_p = st.sidebar.slider(
        "Top-p",
        min_value=0.0,
        max_value=1.0,
        value=float(saved_settings["top_p"]),
        step=0.05,
        key="gs_top_p_value",
        help="Nucleus sampling. 1.0 means no truncation.",
    )
    if st.sidebar.button("Save settings"):
        try:
            _save_app_settings(
                llm_provider=provider_label_options[gs_provider],
                temperature=float(gs_temperature),
                top_p=float(gs_top_p),
            )
            st.sidebar.success("Settings saved.")
            st.rerun()
        except Exception:
            st.sidebar.error(_safe_ui_error("Failed to save settings"))
    active_provider_value = provider_label_options[gs_provider]
    if _provider_key_available(active_provider_value):
        st.sidebar.caption("API key status: ready")
    else:
        provider_name = "Gemini" if active_provider_value == "gemini" else "OpenAI"
        st.sidebar.warning(
            f"{provider_name} API key not found. The app will use built-in fallback outputs."
        )
    st.sidebar.caption(
        "These settings are saved and used for all requests until you change them."
    )

    if not active_profile_id:
        if profile_ids:
            st.info("Select a profile from the sidebar to start studying.")
        else:
            st.info(render_prompt("ui.create_profile_prompt"))
        _render_footer()
        return

    profile = selected_profile
    if profile is None:
        st.warning(render_prompt("ui.no_profile_loaded_warning"))
        return

    st.subheader(f"Active profile: `{active_profile_id}`")
    st.json(profile.model_dump())

    previous_active = st.session_state.get("active_profile_id")
    if previous_active != active_profile_id:
        # Clear stale per-profile session states when user switches profile.
        for key in [
            "current_session_input",
            "current_study_plan",
            "current_study_material",
            "current_external_knowledge",
            "current_quiz",
            "just_streamed_study_plan",
            "latest_recommendation",
            "usage_records",
        ]:
            st.session_state.pop(key, None)
        st.session_state["active_profile_id"] = active_profile_id

    st.divider()
    st.subheader("Start Study Session")

    if "course_choice" not in st.session_state:
        st.session_state["course_choice"] = SELECT_PLACEHOLDER
    if "course_other" not in st.session_state:
        st.session_state["course_other"] = ""
    if "topic_input" not in st.session_state:
        st.session_state["topic_input"] = ""
    if "study_goal_choice" not in st.session_state:
        st.session_state["study_goal_choice"] = SELECT_PLACEHOLDER
    if "response_style_choice" not in st.session_state:
        st.session_state["response_style_choice"] = SELECT_PLACEHOLDER

    with st.expander("Interactive help: build a good study request", expanded=False):
        st.markdown(
            "- Pick a course first, then enter your **topic/study request**.\n"
            "- This field can be short (`Division`) or detailed (a full paragraph with weak points).\n"
            "- Use **Quick revision** for short recap, **Exam preparation** for tougher practice.\n"
            "- You can click an example below to auto-fill session fields."
        )
        presets = [
            ("Math quick review", "Math", "", "Division", "Quick revision", "Friendly"),
            ("Biology exam prep", "Biology", "", "Cell structure", "Exam preparation", "Formal"),
            ("History deep study", "History", "", "French Revolution causes", "Deep understanding", "Concise"),
            ("Custom course example", "Other…", "Economics", "Supply and demand", "Practice only", "Friendly"),
        ]
        for label, c_choice, c_other, t, goal, style in presets:
            if st.button(label, key=f"preset_{label}"):
                st.session_state["course_choice"] = c_choice
                st.session_state["course_other"] = c_other
                st.session_state["topic_input"] = t
                st.session_state["study_goal_choice"] = goal
                st.session_state["response_style_choice"] = style
                st.rerun()

    course_choice = st.selectbox(
        "Course",
        options=[SELECT_PLACEHOLDER] + STANDARD_COURSES + ["Other…"],
        key="course_choice",
    )
    if course_choice == "Other…":
        course_other = st.text_input(
            "Course name",
            placeholder="e.g. Music, Economics",
            key="course_other",
        )
        course = (course_other or "").strip()
    else:
        course_other = st.session_state.get("course_other", "")
        course = course_choice
    topic = st.text_area(
        "Topic / study request",
        key="topic_input",
        height=120,
        placeholder=(
            "Examples: 'Division' OR "
            "'I struggle with long division and remainders, especially in word problems. "
            "I have a quiz tomorrow and want step-by-step practice.'"
        ),
    )
    study_goal = st.selectbox(
        "Study goal",
        options=[
            SELECT_PLACEHOLDER,
            "Quick revision",
            "Deep understanding",
            "Exam preparation",
            "Practice only",
            "Mistake correction",
        ],
        key="study_goal_choice",
    )
    response_style = st.selectbox(
        "Response style",
        options=[SELECT_PLACEHOLDER, "Friendly", "Formal", "Concise"],
        key="response_style_choice",
    )

    if st.button("Generate plan and study material", type="primary"):
        if course_choice == SELECT_PLACEHOLDER:
            st.error("Please select a course.")
            st.stop()
        if study_goal == SELECT_PLACEHOLDER:
            st.error("Please select a study goal.")
            st.stop()
        if response_style == SELECT_PLACEHOLDER:
            st.error("Please select a response style.")
            st.stop()
        if course_choice == "Other…" and not course:
            st.error("Please enter a course name when you choose “Other…”")
            st.stop()

        # Clear old outputs first, then rerun and generate in a fresh render cycle.
        for key in [
            "current_study_plan",
            "current_study_material",
            "current_external_knowledge",
            "current_quiz",
            "latest_recommendation",
            "usage_records",
            "fb_signal",
            "fb_section_open",
            "fb_reasons",
            "fb_note",
        ]:
            st.session_state.pop(key, None)
        st.session_state["pending_generation"] = {
            "course": course,
            "topic": topic,
            "study_goal": study_goal,
            "response_style": response_style,
        }
        st.session_state["is_generating"] = True
        st.rerun()

    pending_generation = st.session_state.get("pending_generation")
    if isinstance(pending_generation, dict):
        st.session_state.pop("pending_generation", None)
        try:
            st.markdown("### Study plan")
            plan_slot = st.empty()
            plan_slot.info("Generating a fresh study plan…")

            session_input = StudySessionInput(
                course=str(pending_generation.get("course", "")),
                topic=str(pending_generation.get("topic", "")),
                study_goal=str(pending_generation.get("study_goal", "")),
                response_style=str(pending_generation.get("response_style", "")),
                llm_provider=str(saved_settings["llm_provider"]),
                temperature=float(saved_settings["temperature"]),
                top_p=float(saved_settings["top_p"]),
            )
            prepare_graph = build_prepare_graph(store)
            result = prepare_graph.invoke(
                {"profile_id": active_profile_id, "session_input": session_input.model_dump()}
            )
            if result.get("error"):
                st.error(result["error"])
            else:
                st.session_state["current_session_input"] = session_input.model_dump()
                st.session_state["current_quiz"] = []
                st.session_state["usage_records"] = []
                fallback_plan = result.get("study_plan", "")
                fallback_material = result.get("study_material", "")
                _append_usage_record(result.get("study_material_usage"))
                weak_summary = store.weak_topics_summary_for_course(
                    active_profile_id, session_input.course, top_n=3
                )
                feedback_hint = store.feedback_preference_hint_for_course(
                    active_profile_id, session_input.course
                )
                st.session_state["applied_feedback_hint"] = feedback_hint
                stream_prompt = _build_study_plan_stream_prompt(
                    profile, session_input, weak_summary
                )
                raw_plan = _collect_stream_text(
                    stream_prompt,
                    fallback_plan,
                    provider=session_input.llm_provider,
                    temperature=session_input.temperature,
                    top_p=session_input.top_p,
                    call_type="study_plan_stream",
                )
                if not (raw_plan or "").strip():
                    raw_plan = str(fallback_plan)
                final_plan = trim_material_sections_from_study_plan(str(raw_plan))
                st.session_state["current_study_plan"] = final_plan
                plan_slot.markdown(final_plan)
                st.session_state["current_external_knowledge"] = result.get(
                    "external_knowledge", {}
                )
                _append_estimated_stream_usage(
                    provider=session_input.llm_provider,
                    call_type="study_plan_stream",
                    prompt_text=stream_prompt,
                    completion_text=str(final_plan),
                )
                st.session_state["current_study_material"] = fallback_material
                st.session_state["current_material_cache_hit"] = bool(
                    result.get("material_cache_hit", False)
                )
                st.session_state["just_streamed_study_plan"] = True
                st.success(render_prompt("ui.material_ready_success"))
        except Exception:
            st.error(_safe_ui_error("Failed to prepare study session"))
        finally:
            st.session_state["is_generating"] = False

    is_generating = bool(st.session_state.get("is_generating", False))

    if (
        not is_generating
        and st.session_state.get("current_study_plan")
        and not st.session_state.get(
        "just_streamed_study_plan", False
        )
    ):
        st.markdown("### Study plan")
        st.write(
            trim_material_sections_from_study_plan(
                str(st.session_state["current_study_plan"])
            )
        )
    st.session_state["just_streamed_study_plan"] = False

    if not is_generating and st.session_state.get("current_study_material"):
        st.markdown("### Study Material Summary")
        st.write(st.session_state["current_study_material"])
        applied_feedback_hint = str(st.session_state.get("applied_feedback_hint", "none")).strip()
        if applied_feedback_hint and applied_feedback_hint != "none":
            st.caption(f"Applied feedback preferences: {applied_feedback_hint}")
        ext = st.session_state.get("current_external_knowledge", {})
        ext_success = (
            isinstance(ext, dict)
            and (
                ext.get("success") is True
                or str(ext.get("success", "")).strip().lower() in {"true", "1", "yes"}
            )
        )
        if ext_success:
            source_url = str(ext.get("source_url", "")).strip()
            title = str(ext.get("title", "Wikipedia")).strip()
            if source_url:
                st.markdown(f"**External knowledge source:** [{title}]({source_url})")
            else:
                st.caption(f"External knowledge source used: {title}")
        else:
            st.caption("External knowledge enrichment unavailable for this run.")

        material_export = (
            "StudyGraph - Study Material\n\n"
            f"Course: {st.session_state.get('current_session_input', {}).get('course', '')}\n"
            f"Topic: {st.session_state.get('current_session_input', {}).get('topic', '')}\n"
            f"Goal: {st.session_state.get('current_session_input', {}).get('study_goal', '')}\n\n"
            f"Study Plan:\n{st.session_state.get('current_study_plan', '')}\n\n"
            f"Material:\n{st.session_state.get('current_study_material', '')}\n"
        )
        st.download_button(
            "Download study material (.txt)",
            data=material_export.encode("utf-8"),
            file_name="study_material.txt",
            mime="text/plain",
        )
        st.markdown("#### Feedback (optional)")
        st.toggle(
            "Show feedback options",
            key="fb_section_open",
            help="Optional ratings and notes; this panel stays open when you click 👍 / 👎 below.",
        )
        if st.session_state.get("fb_section_open"):
            col_up, col_down = st.columns(2)
            if col_up.button("👍 Helpful", key="fb_up"):
                st.session_state["fb_signal"] = "up"
            if col_down.button("👎 Needs improvement", key="fb_down"):
                st.session_state["fb_signal"] = "down"
            fb_signal = st.session_state.get("fb_signal", "")
            st.caption(f"Selected feedback: `{fb_signal or 'none'}`")
            fb_reasons = st.multiselect(
                "What should we improve next time?",
                options=FEEDBACK_REASON_OPTIONS,
                default=[],
                key="fb_reasons",
            )
            fb_note = st.text_input(
                "Optional note",
                key="fb_note",
                placeholder="e.g. More examples, less theory, simpler language",
            )
            if st.button("Save feedback", key="fb_save", type="primary"):
                try:
                    if fb_signal not in {"up", "down"}:
                        st.error("Select 👍 or 👎 before saving feedback.")
                        st.stop()
                    session = st.session_state.get("current_session_input", {})
                    record = FeedbackRecord(
                        course=str(session.get("course", "")).strip(),
                        topic=str(session.get("topic", "")).strip(),
                        signal=fb_signal,
                        reasons=fb_reasons,
                        note=fb_note,
                    )
                    store.append_feedback_record(active_profile_id, record)
                    st.success("Feedback saved. Next generations will adapt to it.")
                except Exception:
                    st.error(_safe_ui_error("Failed to save feedback"))

    if (
        not is_generating
        and st.session_state.get("current_session_input")
        and not st.session_state.get("current_quiz")
    ):
        if st.button("Start Quiz"):
            try:
                quiz_graph = build_quiz_graph(store)
                quiz_result = quiz_graph.invoke(
                    {
                        "profile_id": active_profile_id,
                        "session_input": st.session_state["current_session_input"],
                    }
                )
                if quiz_result.get("error"):
                    st.error(quiz_result["error"])
                else:
                    st.session_state["current_quiz"] = quiz_result.get("quiz_questions", [])
                    _append_usage_record(quiz_result.get("quiz_usage"))
                    st.session_state["current_quiz_cache_hit"] = bool(
                        quiz_result.get("quiz_cache_hit", False)
                    )
                    st.success(render_prompt("ui.quiz_ready_success"))
            except Exception:
                st.error(_safe_ui_error("Failed to generate quiz"))

    quiz_questions = st.session_state.get("current_quiz", []) if not is_generating else []
    if quiz_questions:
        st.markdown("### Quiz")
        answers: list[str] = []
        for i, q in enumerate(quiz_questions):
            answers.append(
                st.radio(
                    f"Q{i+1}. {q['question']}",
                    options=q["options"],
                    key=f"quiz_{i}",
                )
            )

        if st.button("Evaluate answers"):
            try:
                eval_graph = build_evaluation_graph(store)
                eval_result = eval_graph.invoke(
                    {
                        "profile_id": active_profile_id,
                        "session_input": st.session_state["current_session_input"],
                        "quiz_questions": quiz_questions,
                        "answers": answers,
                    }
                )
                if eval_result.get("error"):
                    st.error(eval_result["error"])
                else:
                    st.markdown("### Results")
                    score_percent = float(eval_result.get("score_percent", 0))
                    st.metric("Score", f"{score_percent}%")
                    feedback = eval_result.get("feedback", [])
                    if feedback:
                        st.markdown("**Feedback on mistakes**")
                        for line in feedback:
                            st.write(f"- {line}")
                    st.markdown("### Recommendation")
                    session_input = StudySessionInput.model_validate(
                        st.session_state["current_session_input"]
                    )
                    fallback_recommendation = eval_result.get(
                        "recommendation", "No recommendation available."
                    )
                    recommendation_prompt = _build_recommendation_stream_prompt(
                        profile=profile,
                        session_input=session_input,
                        score_percent=score_percent,
                        feedback=feedback,
                    )
                    streamed_recommendation = st.write_stream(
                        _stream_text_with_provider(
                            recommendation_prompt,
                            str(fallback_recommendation),
                            provider=session_input.llm_provider,
                            temperature=session_input.temperature,
                            top_p=session_input.top_p,
                            call_type="recommendation_stream",
                        )
                    )
                    final_recommendation = streamed_recommendation or fallback_recommendation
                    st.session_state["latest_recommendation"] = final_recommendation
                    _append_estimated_stream_usage(
                        provider=session_input.llm_provider,
                        call_type="recommendation_stream",
                        prompt_text=recommendation_prompt,
                        completion_text=str(final_recommendation),
                    )
                    weak_concepts = eval_result.get("weak_concepts", [])
                    st.markdown("### Knowledge Summary")
                    if score_percent >= 85:
                        st.success("Strong understanding for this topic. You are ready to progress.")
                    elif score_percent >= 60:
                        st.info("Moderate understanding. One more focused practice round is recommended.")
                    else:
                        st.warning("Foundational understanding needs improvement before moving on.")
                    st.write(
                        f"- Topic: {st.session_state['current_session_input']['topic']}\n"
                        f"- Score: {score_percent}%\n"
                        f"- Weak concepts detected: {len(weak_concepts)}"
                    )
            except Exception:
                st.error(_safe_ui_error("Failed to evaluate quiz"))

    if is_generating:
        st.caption("Generating new session output. History and analytics will appear after completion.")
    else:
        history = store.load_session_history(active_profile_id)
        st.divider()
        st.subheader("History")
        st.caption(f"Total sessions: {len(history)}")

        progress_rows = _course_progress([h.model_dump() for h in history])
        if progress_rows:
            st.markdown("### Progress by course")
            for course_name, avg_score, sessions in progress_rows:
                st.write(f"- **{course_name}:** {avg_score}% average across {sessions} session(s)")

        if not history:
            st.info("No sessions yet. Complete a quiz to see history grouped by course.")
        else:
            st.markdown("### Sessions and weak topics by course")
            st.caption("Open a course to see its weak-topic counts and session list.")
            for course_label, sessions_in_course in _group_history_by_course(history):
                n = len(sessions_in_course)
                avg = round(sum(s.score_percent for s in sessions_in_course) / n, 1)
                weak_here = store.weak_topics_summary_for_course(
                    active_profile_id, course_label, top_n=15
                )
                weak_preview = (
                    f"{len(weak_here)} tracked weak-topic entr{'y' if len(weak_here) == 1 else 'ies'}"
                    if weak_here
                    else "no weak topics yet"
                )
                with st.expander(f"{course_label} — {n} session(s), {avg}% avg · {weak_preview}"):
                    if weak_here:
                        st.markdown("**Weak topics (this course)**")
                        for concept, count in weak_here:
                            st.write(f"- {concept} ({count}×)")
                    else:
                        st.caption("No weak concepts recorded for this course yet.")
                    # Table: newest session first (sessions_in_course is newest-first)
                    rows = _history_rows(list(reversed(sessions_in_course)))
                    if rows:
                        st.dataframe(rows, use_container_width=True)

        usage_records = st.session_state.get("usage_records", [])
        if usage_records:
            usage_summary = summarize_usage(usage_records)
            st.divider()
            with st.expander("Token & Cost Summary (Current Session)", expanded=False):
                st.caption("Costs are estimates and may vary by provider pricing updates.")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Prompt tokens", str(usage_summary["prompt_tokens"]))
                c2.metric("Completion tokens", str(usage_summary["completion_tokens"]))
                c3.metric("Total tokens", str(usage_summary["total_tokens"]))
                c4.metric("Estimated cost (USD)", f"${usage_summary['estimated_cost_usd']:.6f}")
                if usage_summary["calls_without_usage"] > 0:
                    st.caption(
                        f"{usage_summary['calls_without_usage']} call(s) did not provide usage metadata."
                    )
                rows = []
                for rec in usage_records:
                    rows.append(
                        {
                            "Call": rec.get("call_type", ""),
                            "Provider": rec.get("provider", ""),
                            "Model": rec.get("model", ""),
                            "Prompt": rec.get("prompt_tokens", 0),
                            "Completion": rec.get("completion_tokens", 0),
                            "Total": rec.get("total_tokens", 0),
                            "Cost (USD est.)": rec.get("estimated_cost_usd"),
                            "Note": rec.get("note", ""),
                        }
                    )
                st.dataframe(rows, use_container_width=True)

    _render_footer()


if __name__ == "__main__":
    main()

