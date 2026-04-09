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
from studygraph.tools import fetch_wikipedia_summary
from studygraph.usage import build_usage_record
from studygraph.utils import call_with_retry


class PrepareState(TypedDict, total=False):
    profile_id: str
    session_input: dict[str, Any]
    profile: dict[str, Any]
    study_plan: str
    study_material: str
    quiz_questions: list[dict[str, Any]]
    study_material_usage: dict[str, Any]
    external_knowledge: dict[str, Any]
    error: str


class QuizState(TypedDict, total=False):
    profile_id: str
    session_input: dict[str, Any]
    profile: dict[str, Any]
    quiz_questions: list[dict[str, Any]]
    quiz_usage: dict[str, Any]
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


def _material_fallback_with_external(
    *,
    topic: str,
    course: str,
    external_context: str,
    external_source_url: str,
) -> str:
    if external_context and external_context != "none":
        return (
            f"Core concept ({course} / {topic}):\n"
            f"{external_context}\n\n"
            "Key points:\n"
            "- Identify the main definition and explain it in your own words.\n"
            "- Extract 3 key facts/rules and connect each one to a practical example.\n"
            "- Compare this concept with a similar concept to avoid confusion.\n\n"
            "Worked mini-example:\n"
            "- Build one short scenario and solve/explain it step by step.\n"
            "- Verify your answer by checking units, assumptions, or definitions.\n\n"
            "Common mistakes:\n"
            "- Memorizing terms without understanding relationships.\n"
            "- Skipping why/how explanations and focusing only on final answers.\n\n"
            f"Reference: {external_source_url or 'Wikipedia'}"
        )
    return (
        f"Topic summary for {topic} ({course}):\n"
        "- Core definition and why it matters.\n"
        "- 2-3 key rules/formulas.\n"
        "- One short example with explanation.\n"
        "- Common mistakes to avoid."
    )


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
) -> tuple[list[QuizQuestion], dict[str, Any] | None]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _fallback_quiz(topic), None

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
                model="gpt-5.2",
                temperature=temperature,
                top_p=top_p,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=1400,
            )
        )
        content = resp.choices[0].message.content or ""
        data = json.loads(content)
        usage_data = getattr(resp, "usage", None)
        usage_record = (
            build_usage_record(
                provider="openai",
                model="gpt-5.2",
                call_type="quiz_generation",
                prompt_tokens=getattr(usage_data, "prompt_tokens", None),
                completion_tokens=getattr(usage_data, "completion_tokens", None),
                total_tokens=getattr(usage_data, "total_tokens", None),
            )
            if usage_data is not None
            else None
        )
        raw_items = data.get("questions") if isinstance(data, dict) else data
        if not isinstance(raw_items, list):
            return _fallback_quiz(topic), usage_record
        parsed: list[QuizQuestion] = []
        for item in raw_items[:5]:
            parsed.append(QuizQuestion.model_validate(item))
        return (parsed if len(parsed) == 5 else _fallback_quiz(topic)), usage_record
    except Exception:
        return _fallback_quiz(topic), None


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
) -> tuple[list[QuizQuestion], dict[str, Any] | None]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback_quiz(topic), None

    prompt = render_prompt(
        "generation.quiz_user_prompt_template",
        topic=topic,
        course=course,
        level=level,
        language=language,
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
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
        usage_meta = body.get("usageMetadata", {}) if isinstance(body, dict) else {}
        usage_record = (
            build_usage_record(
                provider="gemini",
                model="gemini-2.5-flash",
                call_type="quiz_generation",
                prompt_tokens=usage_meta.get("promptTokenCount"),
                completion_tokens=usage_meta.get("candidatesTokenCount"),
                total_tokens=usage_meta.get("totalTokenCount"),
            )
            if usage_meta
            else None
        )
        parts = body["candidates"][0]["content"]["parts"]
        text = "".join([p.get("text", "") for p in parts if isinstance(p, dict)])
        data = json.loads(_extract_json_block(text))
        raw_items = data.get("questions") if isinstance(data, dict) else data
        if not isinstance(raw_items, list):
            return _fallback_quiz(topic), usage_record
        parsed: list[QuizQuestion] = []
        for item in raw_items[:5]:
            parsed.append(QuizQuestion.model_validate(item))
        return (parsed if len(parsed) == 5 else _fallback_quiz(topic)), usage_record
    except Exception:
        return _fallback_quiz(topic), None


def _build_material_with_openai(topic: str, course: str, level: str, language: str) -> str:
    material, _usage = _build_material_with_openai_styled(
        topic=topic,
        course=course,
        level=level,
        language=language,
        style_hint="Friendly",
        external_context="none",
        external_source_url="",
    )
    return material


def _build_material_with_openai_styled(
    topic: str,
    course: str,
    level: str,
    language: str,
    style_hint: str,
    external_context: str,
    external_source_url: str,
    *,
    temperature: float = 0.4,
    top_p: float = 1.0,
) -> tuple[str, dict[str, Any] | None]:
    api_key = os.getenv("OPENAI_API_KEY")
    fallback_material = _material_fallback_with_external(
        topic=topic,
        course=course,
        external_context=external_context,
        external_source_url=external_source_url,
    )
    if not api_key:
        return fallback_material, None

    client = OpenAI(api_key=api_key, timeout=10.0)
    prompt = render_prompt(
        "generation.material_user_prompt_template",
        course=course,
        topic=topic,
        level=level,
        language=language,
        style_hint=style_hint,
        external_context=external_context,
    )
    try:
        resp = call_with_retry(
            lambda: client.chat.completions.create(
                model="gpt-5.2",
                temperature=temperature,
                top_p=top_p,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=420,
            )
        )
        content = (resp.choices[0].message.content or "").strip()
        usage_data = getattr(resp, "usage", None)
        usage_record = (
            build_usage_record(
                provider="openai",
                model="gpt-5.2",
                call_type="material_generation",
                prompt_tokens=getattr(usage_data, "prompt_tokens", None),
                completion_tokens=getattr(usage_data, "completion_tokens", None),
                total_tokens=getattr(usage_data, "total_tokens", None),
            )
            if usage_data is not None
            else None
        )
        return (
            content
            or render_prompt(
                "generation.material_generation_failure_template",
                topic=topic,
            ),
            usage_record,
        )
    except Exception:
        return fallback_material, None


def _build_material_with_gemini_styled(
    topic: str,
    course: str,
    level: str,
    language: str,
    style_hint: str,
    external_context: str,
    external_source_url: str,
    *,
    temperature: float = 0.4,
    top_p: float = 1.0,
) -> tuple[str, dict[str, Any] | None]:
    api_key = os.getenv("GEMINI_API_KEY")
    fallback_material = _material_fallback_with_external(
        topic=topic,
        course=course,
        external_context=external_context,
        external_source_url=external_source_url,
    )
    if not api_key:
        return fallback_material, None

    prompt = render_prompt(
        "generation.material_user_prompt_template",
        course=course,
        topic=topic,
        level=level,
        language=language,
        style_hint=style_hint,
        external_context=external_context,
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
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
        usage_meta = body.get("usageMetadata", {}) if isinstance(body, dict) else {}
        usage_record = (
            build_usage_record(
                provider="gemini",
                model="gemini-2.5-flash",
                call_type="material_generation",
                prompt_tokens=usage_meta.get("promptTokenCount"),
                completion_tokens=usage_meta.get("candidatesTokenCount"),
                total_tokens=usage_meta.get("totalTokenCount"),
            )
            if usage_meta
            else None
        )
        parts = body["candidates"][0]["content"]["parts"]
        content = "".join([p.get("text", "") for p in parts if isinstance(p, dict)]).strip()
        return (
            content
            or render_prompt(
                "generation.material_generation_failure_template",
                topic=topic,
            ),
            usage_record,
        )
    except Exception:
        return fallback_material, None


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
        usage: dict[str, Any] | None = None
        ext = fetch_wikipedia_summary(session.topic)
        external_context = (
            f"{ext.get('title', session.topic)}: {ext.get('summary', '')}"
            if ext.get("success")
            else "none"
        )
        external_source_url = str(ext.get("source_url", "")).strip()
        if session.llm_provider == "gemini":
            material, usage = _build_material_with_gemini_styled(
                topic=session.topic,
                course=session.course,
                level=profile.education_level,
                language=profile.preferred_language,
                style_hint=session.response_style,
                external_context=external_context,
                external_source_url=external_source_url,
                temperature=session.temperature,
                top_p=session.top_p,
            )
        else:
            material, usage = _build_material_with_openai_styled(
                topic=session.topic,
                course=session.course,
                level=profile.education_level,
                language=profile.preferred_language,
                style_hint=session.response_style,
                external_context=external_context,
                external_source_url=external_source_url,
                temperature=session.temperature,
                top_p=session.top_p,
            )
        return {
            "study_material": material,
            "study_material_usage": usage or {},
            "external_knowledge": ext,
        }

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
        usage: dict[str, Any] | None = None
        if session.llm_provider == "gemini":
            questions, usage = _generate_quiz_with_gemini(
                topic=session.topic,
                course=session.course,
                level=profile.education_level,
                language=profile.preferred_language,
                temperature=session.temperature,
                top_p=session.top_p,
            )
        else:
            questions, usage = _generate_quiz_with_openai(
                topic=session.topic,
                course=session.course,
                level=profile.education_level,
                language=profile.preferred_language,
                temperature=session.temperature,
                top_p=session.top_p,
            )
        return {"quiz_questions": [q.model_dump() for q in questions], "quiz_usage": usage or {}}

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
