from __future__ import annotations

from pathlib import Path
import os
from collections import defaultdict
from typing import Generator
from datetime import datetime, timezone

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from studygraph.graph import build_evaluation_graph, build_prepare_graph, build_quiz_graph
from studygraph.memory import MemoryStore
from studygraph.models import StudySessionInput, StudentProfile
from studygraph.prompts import render_prompt


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


def _store() -> MemoryStore:
    root = Path(__file__).resolve().parents[2]
    return MemoryStore(base_dir=root / "data" / "memory")


def _stream_text_from_openai(prompt: str, fallback_text: str) -> Generator[str, None, None]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        yield fallback_text
        return

    try:
        client = OpenAI(api_key=api_key, timeout=20.0)
        system_prompt = render_prompt("streaming.system_coach")
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            stream=True,
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


def main() -> None:
    st.set_page_config(page_title="StudyGraph", page_icon="📘", layout="wide")
    st.title(render_prompt("ui.app_title"))
    st.caption(render_prompt("ui.app_subtitle"))
    store = _store()

    st.sidebar.header(render_prompt("ui.sidebar_profile_manager"))
    profile_ids = store.list_profile_ids()
    no_profile_label = render_prompt("ui.no_profile_yet")
    selected = st.sidebar.selectbox("Select profile", options=profile_ids or [no_profile_label])
    active_profile_id = selected if selected != no_profile_label else None

    with st.sidebar.expander(render_prompt("ui.create_profile_section"), expanded=True):
        learner_name = st.text_input("Learner name", value="Student One")
        education_options = {
            "Primary": "primary",
            "Middle": "middle",
            "High": "high",
            "University exam prep": "university_exam_prep",
        }
        education_level = st.selectbox(
            "Education level",
            options=list(education_options.keys()),
            index=2,
        )
        preferred_language = st.selectbox("Preferred language", options=["English"], index=0)
        difficulty_options = {"Easy": "easy", "Medium": "medium", "Hard": "hard"}
        pace_options = {"Slow": "slow", "Balanced": "balanced", "Fast": "fast"}
        preferred_difficulty = st.selectbox(
            "Preferred difficulty", options=list(difficulty_options.keys()), index=1
        )
        preferred_pace = st.selectbox("Preferred pace", options=list(pace_options.keys()), index=1)

        if st.button("Save as new profile"):
            try:
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
            except Exception as exc:
                st.error(f"Failed to create profile: {exc}")

        if active_profile_id and st.button("Update selected profile"):
            try:
                profile = StudentProfile(
                    learner_name=learner_name,
                    education_level=education_options[education_level],
                    preferred_language=preferred_language,
                    preferred_difficulty=difficulty_options[preferred_difficulty],
                    preferred_pace=pace_options[preferred_pace],
                )
                store.save_profile(active_profile_id, profile)
                st.success(f"Updated profile: {active_profile_id}")
            except Exception as exc:
                st.error(f"Failed to update profile: {exc}")

    if not active_profile_id:
        st.info(render_prompt("ui.create_profile_prompt"))
        _render_footer()
        return

    profile = store.load_profile(active_profile_id)
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
            "current_quiz",
            "just_streamed_study_plan",
            "latest_recommendation",
        ]:
            st.session_state.pop(key, None)
        st.session_state["active_profile_id"] = active_profile_id

    st.divider()
    st.subheader("Start Study Session")

    if "course_choice" not in st.session_state:
        st.session_state["course_choice"] = "Math"
    if "course_other" not in st.session_state:
        st.session_state["course_other"] = ""
    if "topic_input" not in st.session_state:
        st.session_state["topic_input"] = "Algebra basics"
    if "study_goal_choice" not in st.session_state:
        st.session_state["study_goal_choice"] = "Quick revision"

    with st.expander("Interactive help: build a good study request", expanded=False):
        st.markdown(
            "- Pick a course first, then a narrow topic (e.g., `Division with remainders`).\n"
            "- Use **Quick revision** for short recap, **Exam preparation** for tougher practice.\n"
            "- You can click an example below to auto-fill session fields."
        )
        presets = [
            ("Math quick review", "Math", "", "Division", "Quick revision"),
            ("Biology exam prep", "Biology", "", "Cell structure", "Exam preparation"),
            ("History deep study", "History", "", "French Revolution causes", "Deep understanding"),
            ("Custom course example", "Other…", "Economics", "Supply and demand", "Practice only"),
        ]
        for label, c_choice, c_other, t, goal in presets:
            if st.button(label, key=f"preset_{label}"):
                st.session_state["course_choice"] = c_choice
                st.session_state["course_other"] = c_other
                st.session_state["topic_input"] = t
                st.session_state["study_goal_choice"] = goal
                st.rerun()

    course_choice = st.selectbox(
        "Course",
        options=STANDARD_COURSES + ["Other…"],
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
    topic = st.text_input("Topic", key="topic_input")
    study_goal = st.selectbox(
        "Study goal",
        options=[
            "Quick revision",
            "Deep understanding",
            "Exam preparation",
            "Practice only",
            "Mistake correction",
        ],
        key="study_goal_choice",
    )

    if st.button("Generate plan and study material", type="primary"):
        try:
            if course_choice == "Other…" and not course:
                st.error("Please enter a course name when you choose “Other…”")
                st.stop()
            session_input = StudySessionInput(course=course, topic=topic, study_goal=study_goal)
            prepare_graph = build_prepare_graph(store)
            result = prepare_graph.invoke(
                {"profile_id": active_profile_id, "session_input": session_input.model_dump()}
            )
            if result.get("error"):
                st.error(result["error"])
            else:
                st.session_state["current_session_input"] = session_input.model_dump()
                st.session_state["current_quiz"] = []
                fallback_plan = result.get("study_plan", "")
                fallback_material = result.get("study_material", "")
                weak_summary = store.weak_topics_summary_for_course(
                    active_profile_id, session_input.course, top_n=3
                )
                stream_prompt = _build_study_plan_stream_prompt(profile, session_input, weak_summary)
                st.markdown("### Study plan")
                streamed_plan = st.write_stream(
                    _stream_text_from_openai(stream_prompt, fallback_plan)
                )
                st.session_state["current_study_plan"] = streamed_plan or fallback_plan
                st.session_state["current_study_material"] = fallback_material
                st.session_state["just_streamed_study_plan"] = True
                st.success(render_prompt("ui.material_ready_success"))
        except Exception as exc:
            st.error(f"Failed to prepare study session: {exc}")

    if st.session_state.get("current_study_plan") and not st.session_state.get(
        "just_streamed_study_plan", False
    ):
        st.markdown("### Study plan")
        st.write(st.session_state["current_study_plan"])
    st.session_state["just_streamed_study_plan"] = False

    if st.session_state.get("current_study_material"):
        st.markdown("### Study Material Summary")
        st.write(st.session_state["current_study_material"])

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

    if st.session_state.get("current_session_input") and not st.session_state.get("current_quiz"):
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
                    st.success(render_prompt("ui.quiz_ready_success"))
            except Exception as exc:
                st.error(f"Failed to generate quiz: {exc}")

    quiz_questions = st.session_state.get("current_quiz", [])
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
                        _stream_text_from_openai(
                            recommendation_prompt, str(fallback_recommendation)
                        )
                    )
                    st.session_state["latest_recommendation"] = (
                        streamed_recommendation or fallback_recommendation
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
            except Exception as exc:
                st.error(f"Failed to evaluate quiz: {exc}")

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

    _render_footer()


if __name__ == "__main__":
    main()

