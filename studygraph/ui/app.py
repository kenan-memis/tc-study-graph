from __future__ import annotations

from pathlib import Path
import os
from typing import Generator

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from studygraph.graph import build_evaluation_graph, build_prepare_graph
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
        education_level = st.selectbox(
            "Education level",
            options=["primary", "middle", "high", "university_exam_prep"],
            index=2,
        )
        preferred_language = st.selectbox("Preferred language", options=["English"], index=0)
        preferred_difficulty = st.selectbox("Preferred difficulty", options=["easy", "medium", "hard"], index=1)
        preferred_pace = st.selectbox("Preferred pace", options=["slow", "balanced", "fast"], index=1)

        if st.button("Save as new profile"):
            try:
                profile = StudentProfile(
                    learner_name=learner_name,
                    education_level=education_level,
                    preferred_language=preferred_language,
                    preferred_difficulty=preferred_difficulty,
                    preferred_pace=preferred_pace,
                )
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
                    education_level=education_level,
                    preferred_language=preferred_language,
                    preferred_difficulty=preferred_difficulty,
                    preferred_pace=preferred_pace,
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

    st.divider()
    st.subheader("Start Study Session")
    course = st.text_input("Course", value="Math")
    topic = st.text_input("Topic", value="Algebra basics")
    study_goal = st.text_input("Study goal", value="quick revision")

    if st.button("Generate plan and quiz", type="primary"):
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
                st.session_state["current_quiz"] = result.get("quiz_questions", [])
                fallback_plan = result.get("study_plan", "")
                weak_summary = store.weak_topics_summary(active_profile_id, top_n=3)
                stream_prompt = _build_study_plan_stream_prompt(profile, session_input, weak_summary)
                st.markdown("### Study plan")
                streamed_plan = st.write_stream(
                    _stream_text_from_openai(stream_prompt, fallback_plan)
                )
                st.session_state["current_study_plan"] = streamed_plan or fallback_plan
                st.session_state["just_streamed_study_plan"] = True
                st.success("Study plan and quiz ready.")
        except Exception as exc:
            st.error(f"Failed to prepare study session: {exc}")

    if st.session_state.get("current_study_plan") and not st.session_state.get(
        "just_streamed_study_plan", False
    ):
        st.markdown("### Study plan")
        st.write(st.session_state["current_study_plan"])
    st.session_state["just_streamed_study_plan"] = False

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
            except Exception as exc:
                st.error(f"Failed to evaluate quiz: {exc}")

    st.divider()
    st.subheader("Profile Memory Snapshot")
    history = store.load_session_history(active_profile_id)
    st.caption(f"Total sessions: {len(history)}")
    weak_summary = store.weak_topics_summary(active_profile_id, top_n=5)
    if weak_summary:
        st.write("Top weak concepts:")
        for concept, count in weak_summary:
            st.write(f"- {concept} ({count})")
    else:
        st.write("No weak concepts recorded yet.")

    _render_footer()


if __name__ == "__main__":
    main()

