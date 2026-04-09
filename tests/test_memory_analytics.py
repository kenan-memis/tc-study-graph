from pathlib import Path

from studygraph.memory import MemoryStore
from studygraph.models import SessionRecord


def test_weak_topics_summary_returns_top_items(tmp_path: Path) -> None:
    store = MemoryStore(base_dir=tmp_path / "memory")
    profile_id = store.create_profile_id("Kenan")
    store.append_session_record(
        profile_id,
        SessionRecord(
            course="Biology",
            topic="Cells",
            score_percent=50.0,
            weak_concepts=["Mitosis", "Mitosis", "Cell membrane"],
        )
    )
    store.append_session_record(
        profile_id,
        SessionRecord(
            course="Biology",
            topic="Genetics",
            score_percent=55.0,
            weak_concepts=["Mitosis", "DNA replication"],
        )
    )

    summary = store.weak_topics_summary(profile_id, top_n=3)
    assert summary[0] == ("mitosis", 3)
    assert len(summary) <= 3


def test_weak_topics_summary_for_course_isolates_courses(tmp_path: Path) -> None:
    store = MemoryStore(base_dir=tmp_path / "memory")
    pid = store.create_profile_id("Learner")
    store.append_session_record(
        pid,
        SessionRecord(
            course="Math",
            topic="Division",
            score_percent=50.0,
            weak_concepts=["division facts", "long division"],
        ),
    )
    store.append_session_record(
        pid,
        SessionRecord(
            course="Geography",
            topic="Austria",
            score_percent=80.0,
            weak_concepts=["capital cities"],
        ),
    )
    math_only = store.weak_topics_summary_for_course(pid, "Math", top_n=5)
    geo_only = store.weak_topics_summary_for_course(pid, "Geography", top_n=5)
    assert {c for c, _ in math_only} == {"division facts", "long division"}
    assert geo_only == [("capital cities", 1)]

    chem_only = store.weak_topics_summary_for_course(pid, "Chemistry", top_n=5)
    assert chem_only == []
