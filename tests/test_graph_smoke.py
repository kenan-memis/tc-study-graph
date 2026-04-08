from pathlib import Path

from studygraph.graph import build_evaluation_graph, build_prepare_graph, build_quiz_graph
from studygraph.memory import MemoryStore
from studygraph.models import StudentProfile


def test_prepare_and_evaluation_graph_smoke(tmp_path: Path) -> None:
    store = MemoryStore(base_dir=tmp_path / "memory")
    profile_id = store.create_profile_id("Demo Student")
    store.save_profile(
        profile_id,
        StudentProfile(
            learner_name="Demo Student",
            education_level="high",
            preferred_language="English",
            preferred_difficulty="medium",
            preferred_pace="balanced",
        ),
    )

    prepare_graph = build_prepare_graph(store)
    prepare_out = prepare_graph.invoke(
        {
            "profile_id": profile_id,
            "session_input": {"course": "Math", "topic": "Algebra", "study_goal": "practice"},
        }
    )
    assert prepare_out.get("study_plan")
    assert prepare_out.get("study_material")

    quiz_graph = build_quiz_graph(store)
    quiz_out = quiz_graph.invoke(
        {
            "profile_id": profile_id,
            "session_input": {"course": "Math", "topic": "Algebra", "study_goal": "practice"},
        }
    )
    quiz = quiz_out.get("quiz_questions")
    assert isinstance(quiz, list) and len(quiz) == 5

    # Use correct answers to force a high score path.
    answers = [q["correct_answer"] for q in quiz]
    eval_graph = build_evaluation_graph(store)
    eval_out = eval_graph.invoke(
        {
            "profile_id": profile_id,
            "session_input": {"course": "Math", "topic": "Algebra", "study_goal": "practice"},
            "quiz_questions": quiz,
            "answers": answers,
        }
    )
    assert eval_out.get("score_percent", 0) >= 99
    assert "recommendation" in eval_out
    assert len(store.load_session_history(profile_id)) == 1
