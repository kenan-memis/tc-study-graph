from __future__ import annotations

from pathlib import Path
import os
from typing import Generator
from datetime import datetime, timezone

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from studygraph.graph import build_evaluation_graph, build_prepare_graph, build_quiz_graph
from studygraph.memory import MemoryStore
from studygraph.models import StudySessionInput, StudentProfile


load_dotenv()


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
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise and encouraging study coach. "
                        "Return plain text only."
                    ),
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
    return (
        f"Create a concise study plan for {profile.learner_name}. "
        f"Education level: {profile.education_level}. Language: {profile.preferred_language}. "
        f"Course: {session_input.course}. Topic: {session_input.topic}. Goal: {session_input.study_goal}. "
        f"Historical weak concepts: {weak_text}. "
        "Provide a practical plan in 4-6 bullet points."
    )


def _build_recommendation_stream_prompt(
    profile: StudentProfile,
    session_input: StudySessionInput,
    score_percent: float,
    feedback: list[str],
) -> str:
    feedback_text = " | ".join(feedback[:3]) if feedback else "No major mistakes."
    return (
        f"Write a short next-step recommendation for a student. "
        f"Name: {profile.learner_name}. Level: {profile.education_level}. "
        f"Course: {session_input.course}. Topic: {session_input.topic}. "
        f"Score: {score_percent}%. Key mistakes: {feedback_text}. "
        "Return 3-5 concise bullet points."
    )


def _render_footer() -> None:
    st.markdown(
        """
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
          <div>Sprint 3 – Building with AI Agents</div>
          <div>Turing College 2026</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
    st.title("StudyGraph")
    st.caption("LangGraph-based student study and exam preparation assistant")
    store = _store()

    st.sidebar.header("Profile Manager")
    profile_ids = store.list_profile_ids()
    selected = st.sidebar.selectbox("Select profile", options=profile_ids or ["No profile yet"])
    active_profile_id = selected if selected != "No profile yet" else None

    with st.sidebar.expander("Create or update profile", expanded=True):
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
                    st.warning(
                        f"An identical profile already exists: `{duplicate_id}`. "
                        "Please select it from the profile list or update that profile."
                    )
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
        st.info("Create at least one profile from the sidebar to start studying.")
        _render_footer()
        return

    profile = store.load_profile(active_profile_id)
    if profile is None:
        st.warning("Selected profile could not be loaded.")
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
    course = st.text_input("Course", value="Math")
    topic = st.text_input("Topic", value="Algebra basics")
    study_goal = st.selectbox(
        "Study goal",
        options=[
            "Quick revision",
            "Deep understanding",
            "Exam preparation",
            "Practice only",
            "Mistake correction",
        ],
        index=0,
    )

    if st.button("Generate plan and study material", type="primary"):
        try:
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
                weak_summary = store.weak_topics_summary(active_profile_id, top_n=3)
                stream_prompt = _build_study_plan_stream_prompt(profile, session_input, weak_summary)
                st.markdown("### Study plan")
                streamed_plan = st.write_stream(
                    _stream_text_from_openai(stream_prompt, fallback_plan)
                )
                st.session_state["current_study_plan"] = streamed_plan or fallback_plan
                st.session_state["current_study_material"] = fallback_material
                st.session_state["just_streamed_study_plan"] = True
                st.success("Study plan and material ready.")
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
                    st.success("Quiz generated. Continue with exercises below.")
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

    st.divider()
    st.subheader("Progress and Suggestions")
    history = store.load_session_history(active_profile_id)
    if st.button("Do you have suggestions for me?"):
        if not history:
            st.info("No study sessions yet. Complete one session first to get personalized suggestions.")
        else:
            overall = round(sum(h.score_percent for h in history) / len(history), 1)
            weak_summary_for_suggestion = store.weak_topics_summary(active_profile_id, top_n=3)
            weak_text = ", ".join([w for w, _ in weak_summary_for_suggestion]) or "none"
            st.info(
                f"Overall progress: {overall}%. Next recommendation: focus on weak areas ({weak_text}) "
                "and then retry the same topic with exam_preparation goal."
            )

    st.divider()
    st.subheader("History")
    st.caption(f"Total sessions: {len(history)}")
    weak_summary = store.weak_topics_summary(active_profile_id, top_n=5)
    if weak_summary:
        st.write("Top weak concepts:")
        for concept, count in weak_summary:
            st.write(f"- {concept} ({count})")
    else:
        st.write("No weak concepts recorded yet.")

    progress_rows = _course_progress([h.model_dump() for h in history])
    if progress_rows:
        st.markdown("### Progress by Course")
        for course_name, avg_score, sessions in progress_rows:
            st.write(f"- {course_name}: {avg_score}% average across {sessions} session(s)")

    history_rows = _history_rows(history)
    if history_rows:
        st.markdown("### Session History")
        st.dataframe(history_rows, use_container_width=True)

    _render_footer()


if __name__ == "__main__":
    main()

