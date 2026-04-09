from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
import re

from studygraph.models import SessionRecord, StudentProfile


class MemoryStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[2]
        self.base_dir = base_dir or (root / "data" / "memory")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir = self.base_dir / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slugify(raw: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
        return slug or "profile"

    def list_profile_ids(self) -> list[str]:
        ids = []
        for item in self.profiles_dir.glob("*/profile.json"):
            ids.append(item.parent.name)
        return sorted(ids)

    def create_profile_id(self, learner_name: str) -> str:
        base = self._slugify(learner_name)
        existing = set(self.list_profile_ids())
        if base not in existing:
            return base
        i = 2
        while f"{base}-{i}" in existing:
            i += 1
        return f"{base}-{i}"

    def find_duplicate_profile(self, profile: StudentProfile) -> str | None:
        target = profile.model_dump()
        for profile_id in self.list_profile_ids():
            loaded = self.load_profile(profile_id)
            if loaded and loaded.model_dump() == target:
                return profile_id
        return None

    def _profile_dir(self, profile_id: str) -> Path:
        p = self.profiles_dir / profile_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def save_profile(self, profile_id: str, profile: StudentProfile) -> None:
        profile_path = self._profile_dir(profile_id) / "profile.json"
        profile_path.write_text(
            json.dumps(profile.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_profile(self, profile_id: str) -> StudentProfile | None:
        profile_path = self._profile_dir(profile_id) / "profile.json"
        if not profile_path.exists():
            return None
        raw = json.loads(profile_path.read_text(encoding="utf-8"))
        return StudentProfile.model_validate(raw)

    def append_session_record(self, profile_id: str, record: SessionRecord) -> None:
        sessions_path = self._profile_dir(profile_id) / "sessions.json"
        history = self.load_session_history(profile_id)
        history.append(record)
        payload = [item.model_dump() for item in history]
        sessions_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_session_history(self, profile_id: str) -> list[SessionRecord]:
        sessions_path = self._profile_dir(profile_id) / "sessions.json"
        if not sessions_path.exists():
            return []
        raw = json.loads(sessions_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        return [SessionRecord.model_validate(item) for item in raw]

    @staticmethod
    def _normalize_course(course: str) -> str:
        return (course or "").strip().lower()

    def weak_topics_summary(self, profile_id: str, *, top_n: int = 5) -> list[tuple[str, int]]:
        counter: Counter[str] = Counter()
        for record in self.load_session_history(profile_id):
            counter.update(record.weak_concepts)
        return counter.most_common(top_n)

    def weak_topics_summary_for_course(
        self, profile_id: str, course: str, *, top_n: int = 5
    ) -> list[tuple[str, int]]:
        """Weak concepts only from sessions for this course (cross-course isolation)."""
        target = self._normalize_course(course)
        if not target:
            return []
        counter: Counter[str] = Counter()
        for record in self.load_session_history(profile_id):
            if self._normalize_course(record.course) != target:
                continue
            counter.update(record.weak_concepts)
        return counter.most_common(top_n)

