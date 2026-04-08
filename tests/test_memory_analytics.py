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
