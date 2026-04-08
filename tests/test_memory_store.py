from pathlib import Path

from studygraph.memory import MemoryStore
from studygraph.models import SessionRecord, StudentProfile


def test_profile_save_and_load_roundtrip(tmp_path: Path) -> None:
    store = MemoryStore(base_dir=tmp_path / "memory")
    profile_id = store.create_profile_id("Kenan")
    profile = StudentProfile(
        learner_name="Kenan",
        education_level="high",
        preferred_language="English",
        preferred_difficulty="medium",
        preferred_pace="balanced",
    )

    store.save_profile(profile_id, profile)
    loaded = store.load_profile(profile_id)

    assert loaded is not None
    assert loaded.learner_name == "Kenan"
    assert loaded.education_level == "high"


def test_append_and_load_session_history(tmp_path: Path) -> None:
    store = MemoryStore(base_dir=tmp_path / "memory")
    profile_id = store.create_profile_id("Kenan")
    first = SessionRecord(
        course="Math",
        topic="Algebra",
        score_percent=60.0,
        weak_concepts=["Linear equations", "Factoring"],
    )
    second = SessionRecord(
        course="Math",
        topic="Geometry",
        score_percent=80.0,
        weak_concepts=["Triangles"],
    )

    store.append_session_record(profile_id, first)
    store.append_session_record(profile_id, second)

    history = store.load_session_history(profile_id)
    assert len(history) == 2
    assert history[0].topic == "Algebra"
    assert history[1].topic == "Geometry"


def test_profiles_are_isolated(tmp_path: Path) -> None:
    store = MemoryStore(base_dir=tmp_path / "memory")
    p1 = store.create_profile_id("Alice")
    p2 = store.create_profile_id("Bob")

    store.append_session_record(
        p1, SessionRecord(course="Math", topic="Algebra", score_percent=50, weak_concepts=["equations"])
    )
    store.append_session_record(
        p2, SessionRecord(course="History", topic="Rome", score_percent=90, weak_concepts=["dates"])
    )

    h1 = store.load_session_history(p1)
    h2 = store.load_session_history(p2)
    assert len(h1) == 1 and h1[0].course == "Math"
    assert len(h2) == 1 and h2[0].course == "History"
