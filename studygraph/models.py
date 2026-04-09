from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


EducationLevel = Literal["primary", "middle", "high", "university_exam_prep"]
DifficultyLevel = Literal["easy", "medium", "hard"]
PaceLevel = Literal["slow", "balanced", "fast"]
ResponseStyle = Literal["Friendly", "Formal", "Concise"]
LlmProvider = Literal["openai", "gemini"]


class StudentProfile(BaseModel):
    learner_name: str = Field(min_length=1, max_length=80)
    education_level: EducationLevel = "high"
    preferred_language: str = Field(default="English", min_length=1, max_length=40)
    preferred_difficulty: DifficultyLevel = "medium"
    preferred_pace: PaceLevel = "balanced"

    @field_validator("learner_name", "preferred_language")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()


class StudySessionInput(BaseModel):
    course: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=1, max_length=800)
    study_goal: str = Field(default="quick revision", min_length=1, max_length=200)
    response_style: ResponseStyle = "Friendly"
    llm_provider: LlmProvider = "openai"
    temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("course", "topic", "study_goal", "response_style", "llm_provider")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()


class SessionRecord(BaseModel):
    course: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=1, max_length=800)
    score_percent: float = Field(ge=0.0, le=100.0)
    weak_concepts: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator("course", "topic")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("weak_concepts")
    @classmethod
    def _normalize_weak_concepts(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in values:
            text = item.strip()
            if text:
                cleaned.append(text.lower())
        return cleaned


class QuizQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    options: list[str] = Field(min_length=2, max_length=6)
    correct_answer: str = Field(min_length=1, max_length=120)
    explanation: str = Field(min_length=1, max_length=400)

    @field_validator("question", "correct_answer", "explanation")
    @classmethod
    def _strip_fields(cls, value: str) -> str:
        return value.strip()

    @field_validator("options")
    @classmethod
    def _strip_options(cls, values: list[str]) -> list[str]:
        cleaned = [item.strip() for item in values if item.strip()]
        if len(cleaned) < 2:
            raise ValueError("Each question must include at least 2 options.")
        return cleaned

