from __future__ import annotations

import json
import os
from urllib import request
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from openai import OpenAI

from studygraph.memory import MemoryStore
from studygraph.models import QuizQuestion, SessionRecord, StudySessionInput, StudentProfile
from studygraph.prompts import render_prompt
from studygraph.utils import call_with_retry


class PrepareState(TypedDict, total=False):
    profile_id: str
    session_input: dict[str, Any]
    profile: dict[str, Any]
    study_plan: str
    study_material: str
    quiz_questions: list[dict[str, Any]]
    error: str


class QuizState(TypedDict, total=False):
    profile_id: str
    session_input: dict[str, Any]
    profile: dict[str, Any]
    quiz_questions: list[dict[str, Any]]
    error: str


class EvaluateState(TypedDict, total=False):
    profile_id: str
    session_input: dict[str, Any]
    profile: dict[str, Any]
    quiz_questions: list[dict[str, Any]]
    answers: list[str]
    score_percent: float
    weak_concepts: list[str]
    feedback: list[str]
    recommendation: str
    error: str


def _fallback_quiz(topic: str) -> list[QuizQuestion]:
    return [
        QuizQuestion(
            question=f"What is the best summary of {topic}?",
            options=["A core concept", "An unrelated topic", "A sports rule", "A random city"],
            correct_answer="A core concept",
            explanation=f"{topic} should be understood through its core concepts and definitions.",
        ),
        QuizQuestion(
            question=f"Which approach helps learn {topic} best?",
            options=["Active recall", "Never practicing", "Ignoring mistakes", "Skipping feedback"],
            correct_answer="Active recall",
            explanation="Active recall and spaced practice are reliable study methods.",
        ),
        QuizQuestion(
            question="What should you do after a wrong answer?",
            options=["Review the mistake", "Ignore it", "Memorize blindly", "Stop practicing"],
            correct_answer="Review the mistake",
            explanation="Mistake review is the fastest way to improve weak concepts.",
        ),
        QuizQuestion(
            question="What is a good exam strategy?",
            options=["Practice regularly", "Cram once", "Skip hard topics", "Avoid testing"],
            correct_answer="Practice regularly",
            explanation="Frequent short practice sessions improve retention.",
        ),
        QuizQuestion(
            question="What data is useful for personalized study?",
            options=["Past weak topics", "Random guesses", "None", "Only study date"],
            correct_answer="Past weak topics",
            explanation="Weak-topic history helps adapt future study recommendations.",
        ),
    ]


def _generate_quiz_with_openai(
    topic: str,
    course: str,
    level: str,
    language: str,
    *,
    temperature: float = 0.4,
    top_p: float = 1.0,
) -> list[QuizQuestion]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _fallback_quiz(topic)

    client = OpenAI(api_key=api_key, timeout=10.0)
    prompt = render_prompt(
        "generation.quiz_user_prompt_template",
        topic=topic,
        course=course,
        level=level,
        language=language,
    )

    try:
        resp = call_with_retry(
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=temperature,
                top_p=top_p,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=1400,
            )
        )
        content = resp.choices[0].message.content or ""
        data = json.loads(content)
        raw_items = data.get("questions") if isinstance(data, dict) else data
        if not isinstance(raw_items, list):
            return _fallback_quiz(topic)
        parsed: list[QuizQuestion] = []
        for item in raw_items[:5]:
            parsed.append(QuizQuestion.model_validate(item))
        return parsed if len(parsed) == 5 else _fallback_quiz(topic)
    except Exception:
        return _fallback_quiz(topic)


def _extract_json_block(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    return raw


def _generate_quiz_with_gemini(
    topic: str,
    course: str,
    level: str,
    language: str,
    *,
    temperature: float = 0.4,
    top_p: float = 1.0,
) -> list[QuizQuestion]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback_quiz(topic)

    prompt = render_prompt(
        "generation.quiz_user_prompt_template",
        topic=topic,
        course=course,
        level=level,
        language=language,
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "topP": top_p,
            "responseMimeType": "application/json",
        },
    }
    try:
        def _request_body() -> dict:
            req = request.Request(
                url=url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))

        body = call_with_retry(_request_body)
        parts = body["candidates"][0]["content"]["parts"]
        text = "".join([p.get("text", "") for p in parts if isinstance(p, dict)])
        data = json.loads(_extract_json_block(text))
        raw_items = data.get("questions") if isinstance(data, dict) else data
        if not isinstance(raw_items, list):
            return _fallback_quiz(topic)
        parsed: list[QuizQuestion] = []
        for item in raw_items[:5]:
            parsed.append(QuizQuestion.model_validate(item))
        return parsed if len(parsed) == 5 else _fallback_quiz(topic)
    except Exception:
        return _fallback_quiz(topic)


def _build_material_with_openai(topic: str, course: str, level: str, language: str) -> str:
    return _build_material_with_openai_styled(
        topic=topic,
        course=course,
        level=level,
        language=language,
        style_hint="Friendly",
    )


def _build_material_with_openai_styled(
    topic: str,
    course: str,
    level: str,
    language: str,
    style_hint: str,
    *,
    temperature: float = 0.4,
    top_p: float = 1.0,
) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    fallback_material = render_prompt(
        "generation.material_fallback_template",
        topic=topic,
        course=course,
    )
    if not api_key:
        return fallback_material

    client = OpenAI(api_key=api_key, timeout=10.0)
    prompt = render_prompt(
        "generation.material_user_prompt_template",
        course=course,
        topic=topic,
        level=level,
        language=language,
        style_hint=style_hint,
    )
    try:
        resp = call_with_retry(
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=temperature,
                top_p=top_p,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=420,
            )
        )
        content = (resp.choices[0].message.content or "").strip()
        return content or render_prompt(
            "generation.material_generation_failure_template",
            topic=topic,
        )
    except Exception:
        return fallback_material


def _build_material_with_gemini_styled(
    topic: str,
    course: str,
    level: str,
    language: str,
    style_hint: str,
    *,
    temperature: float = 0.4,
    top_p: float = 1.0,
) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    fallback_material = render_prompt(
        "generation.material_fallback_template",
        topic=topic,
        course=course,
    )
    if not api_key:
        return fallback_material

    prompt = render_prompt(
        "generation.material_user_prompt_template",
        course=course,
        topic=topic,
        level=level,
        language=language,
        style_hint=style_hint,
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "topP": top_p,
        },
    }
    try:
        def _request_body() -> dict:
            req = request.Request(
                url=url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))

        body = call_with_retry(_request_body)
        parts = body["candidates"][0]["content"]["parts"]
        content = "".join([p.get("text", "") for p in parts if isinstance(p, dict)]).strip()
        return content or render_prompt(
            "generation.material_generation_failure_template",
            topic=topic,
        )
    except Exception:
        return fallback_material


def build_prepare_graph(store: MemoryStore):
    def load_profile_node(state: PrepareState) -> PrepareState:
        profile_id = state["profile_id"]
        profile = store.load_profile(profile_id)
        if profile is None:
            return {"error": f"Profile '{profile_id}' was not found."}
        return {"profile": profile.model_dump()}

    def build_study_plan_node(state: PrepareState) -> PrepareState:
        profile = StudentProfile.model_validate(state["profile"])
        session = StudySessionInput.model_validate(state["session_input"])
        weak_topics = store.weak_topics_summary_for_course(
            state["profile_id"], session.course, top_n=3
        )
        weak_text = ", ".join([f"{t} ({n})" for t, n in weak_topics]) if weak_topics else "no prior weak topics yet"
        plan = (
            f"Study plan for {profile.learner_name}: "
            f"1) 10 min recap of {session.topic}; "
            f"2) 15 min focused practice ({session.study_goal}); "
            f"3) 10 min review of mistakes and notes. "
            f"Historical weak areas: {weak_text}."
        )
        return {"study_plan": plan}

    def build_material_node(state: PrepareState) -> PrepareState:
        profile = StudentProfile.model_validate(state["profile"])
        session = StudySessionInput.model_validate(state["session_input"])
        if session.llm_provider == "gemini":
            material = _build_material_with_gemini_styled(
                topic=session.topic,
                course=session.course,
                level=profile.education_level,
                language=profile.preferred_language,
                style_hint=session.response_style,
                temperature=session.temperature,
                top_p=session.top_p,
            )
        else:
            material = _build_material_with_openai_styled(
                topic=session.topic,
                course=session.course,
                level=profile.education_level,
                language=profile.preferred_language,
                style_hint=session.response_style,
                temperature=session.temperature,
                top_p=session.top_p,
            )
        return {"study_material": material}

    graph = StateGraph(PrepareState)
    graph.add_node("load_profile", load_profile_node)
    graph.add_node("build_study_plan", build_study_plan_node)
    graph.add_node("build_material", build_material_node)
    graph.add_edge(START, "load_profile")
    graph.add_edge("load_profile", "build_study_plan")
    graph.add_edge("build_study_plan", "build_material")
    graph.add_edge("build_material", END)
    return graph.compile()


def build_quiz_graph(store: MemoryStore):
    def load_profile_node(state: QuizState) -> QuizState:
        profile = store.load_profile(state["profile_id"])
        if profile is None:
            return {"error": f"Profile '{state['profile_id']}' was not found."}
        return {"profile": profile.model_dump()}

    def generate_quiz_node(state: QuizState) -> QuizState:
        profile = StudentProfile.model_validate(state["profile"])
        session = StudySessionInput.model_validate(state["session_input"])
        if session.llm_provider == "gemini":
            questions = _generate_quiz_with_gemini(
                topic=session.topic,
                course=session.course,
                level=profile.education_level,
                language=profile.preferred_language,
                temperature=session.temperature,
                top_p=session.top_p,
            )
        else:
            questions = _generate_quiz_with_openai(
                topic=session.topic,
                course=session.course,
                level=profile.education_level,
                language=profile.preferred_language,
                temperature=session.temperature,
                top_p=session.top_p,
            )
        return {"quiz_questions": [q.model_dump() for q in questions]}

    graph = StateGraph(QuizState)
    graph.add_node("load_profile", load_profile_node)
    graph.add_node("generate_quiz", generate_quiz_node)
    graph.add_edge(START, "load_profile")
    graph.add_edge("load_profile", "generate_quiz")
    graph.add_edge("generate_quiz", END)
    return graph.compile()


def build_evaluation_graph(store: MemoryStore):
    def load_profile_node(state: EvaluateState) -> EvaluateState:
        profile = store.load_profile(state["profile_id"])
        if profile is None:
            return {"error": f"Profile '{state['profile_id']}' was not found."}
        return {"profile": profile.model_dump()}

    def evaluate_answers_node(state: EvaluateState) -> EvaluateState:
        questions = [QuizQuestion.model_validate(item) for item in state.get("quiz_questions", [])]
        answers = state.get("answers", [])
        correct = 0
        weak: list[str] = []
        feedback: list[str] = []
        for i, q in enumerate(questions):
            answer = answers[i].strip() if i < len(answers) else ""
            if answer == q.correct_answer:
                correct += 1
            else:
                weak.append(q.question)
                feedback.append(f"Q{i+1}: {q.explanation}")
        total = len(questions) or 1
        score_percent = round((correct / total) * 100, 1)
        return {"score_percent": score_percent, "weak_concepts": weak, "feedback": feedback}

    def update_memory_node(state: EvaluateState) -> EvaluateState:
        session = StudySessionInput.model_validate(state["session_input"])
        record = SessionRecord(
            course=session.course,
            topic=session.topic,
            score_percent=float(state.get("score_percent", 0.0)),
            weak_concepts=state.get("weak_concepts", []),
        )
        store.append_session_record(state["profile_id"], record)
        return {}

    def recommend_next_step_node(state: EvaluateState) -> EvaluateState:
        score = float(state.get("score_percent", 0.0))
        session = StudySessionInput.model_validate(state["session_input"])
        if score < 60:
            rec = render_prompt(
                "evaluation.recommendation_low_template",
                score=score,
                topic=session.topic,
            )
        elif score < 85:
            rec = render_prompt(
                "evaluation.recommendation_mid_template",
                score=score,
                topic=session.topic,
            )
        else:
            rec = render_prompt(
                "evaluation.recommendation_high_template",
                score=score,
                course=session.course,
            )
        return {"recommendation": rec}

    graph = StateGraph(EvaluateState)
    graph.add_node("load_profile", load_profile_node)
    graph.add_node("evaluate_answers", evaluate_answers_node)
    graph.add_node("update_memory", update_memory_node)
    graph.add_node("recommend_next_step", recommend_next_step_node)
    graph.add_edge(START, "load_profile")
    graph.add_edge("load_profile", "evaluate_answers")
    graph.add_edge("evaluate_answers", "update_memory")
    graph.add_edge("update_memory", "recommend_next_step")
    graph.add_edge("recommend_next_step", END)
    return graph.compile()
