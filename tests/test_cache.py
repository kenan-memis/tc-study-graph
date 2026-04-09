from pathlib import Path

from studygraph.cache import ResponseCache


def test_response_cache_set_get_roundtrip(tmp_path: Path) -> None:
    cache = ResponseCache(base_dir=tmp_path / "memory")
    key_payload = {"kind": "material", "topic": "Photosynthesis", "provider": "openai"}
    value = {"study_material": "cached material", "external_knowledge": {"success": True}}
    cache.set(key_payload, value)
    loaded = cache.get(key_payload)
    assert loaded is not None
    assert loaded["study_material"] == "cached material"


def test_response_cache_key_is_stable_for_key_order(tmp_path: Path) -> None:
    cache = ResponseCache(base_dir=tmp_path / "memory")
    a = {"kind": "quiz", "topic": "Algebra", "provider": "gemini", "temperature": 0.4}
    b = {"temperature": 0.4, "provider": "gemini", "topic": "Algebra", "kind": "quiz"}
    cache.set(a, {"quiz_questions": [{"question": "Q1"}]})
    loaded = cache.get(b)
    assert loaded is not None
    assert isinstance(loaded.get("quiz_questions"), list)


def test_response_cache_miss_when_temperature_differs(tmp_path: Path) -> None:
    """Prepare graph normalizes temperature; distinct values must not share cache."""
    cache = ResponseCache(base_dir=tmp_path / "memory")
    cold = {
        "kind": "material",
        "topic": "algebra",
        "course": "math",
        "temperature": 0.4,
        "top_p": 1.0,
    }
    hot = {**cold, "temperature": 0.9}
    cache.set(cold, {"study_material": "cold"})
    assert cache.get(hot) is None


def test_norm_text_like_payload_hits_same_cache(tmp_path: Path) -> None:
    cache = ResponseCache(base_dir=tmp_path / "memory")
    a = {"kind": "material", "topic": "photosynthesis", "course": "biology"}
    b = {"kind": "material", "topic": "photosynthesis", "course": "biology"}
    cache.set(a, {"study_material": "x"})
    assert cache.get(b) is not None
