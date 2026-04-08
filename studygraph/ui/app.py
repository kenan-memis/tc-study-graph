from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from studygraph.graph import build_evaluation_graph, build_prepare_graph
from studygraph.memory import MemoryStore
from studygraph.models import StudySessionInput, StudentProfile


load_dotenv()


def _store() -> MemoryStore:
    root = Path(__file__).resolve().parents[2]
    return MemoryStore(base_dir=root / "data" / "memory")

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
                st.session_state["current_study_plan"] = result.get("study_plan", "")
                st.success("Study plan and quiz ready.")
        except Exception as exc:
            st.error(f"Failed to prepare study session: {exc}")

    if st.session_state.get("current_study_plan"):
        st.markdown("### Study plan")
        st.write(st.session_state["current_study_plan"])

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
                    st.metric("Score", f"{eval_result.get('score_percent', 0)}%")
                    feedback = eval_result.get("feedback", [])
                    if feedback:
                        st.markdown("**Feedback on mistakes**")
                        for line in feedback:
                            st.write(f"- {line}")
                    st.markdown("### Recommendation")
                    st.info(eval_result.get("recommendation", "No recommendation available."))
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

