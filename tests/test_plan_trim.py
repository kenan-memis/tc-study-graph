"""Tests for stripping duplicate material headings from streamed study plans."""

from studygraph.utils.plan_trim import trim_material_sections_from_study_plan


def test_trim_keeps_plan_when_no_material_headings() -> None:
    plan = "- 5 min: warm-up\n- 10 min: practice division facts"
    assert trim_material_sections_from_study_plan(plan) == plan


def test_trim_removes_tail_starting_at_core_concept() -> None:
    plan = """- Warm-up (3 min): facts
- Core idea (5 min): division as sharing

Core concept (Math / Division): Division may refer to:
- Key points:
  - one
"""
    out = trim_material_sections_from_study_plan(plan)
    assert "Core concept" not in out
    assert "Warm-up" in out
    assert "Core idea" in out


def test_trim_matches_key_points_heading() -> None:
    plan = "Bullet one\n\nKey points:\n- a\n- b"
    assert trim_material_sections_from_study_plan(plan).strip() == "Bullet one"


def test_trim_strips_markdown_bold_core_concept_line() -> None:
    plan = (
        "- 3 min: Warm-up\n\n"
        "**Core concept (Math / Division):** Division may refer to:\n"
        "- Key points:\n"
    )
    out = trim_material_sections_from_study_plan(plan)
    assert "Core concept" not in out
    assert "Warm-up" in out


def test_trim_strips_markdown_heading_core_concept() -> None:
    plan = "- 4 min: drill\n\n### Core concept\nSome text"
    out = trim_material_sections_from_study_plan(plan)
    assert "Core concept" not in out
    assert "drill" in out


def test_inline_core_concept_after_min_same_line() -> None:
    """Same-line glue after timed bullet: nuclear / inline cut removes material tail."""
    plan = "- 5 min: warmup practice " + "x" * 20 + " Core concept (Math / Division): tail"
    out = trim_material_sections_from_study_plan(plan)
    assert "tail" not in out
    assert "warmup" in out


def test_trim_removes_topic_summary_fallback_block() -> None:
    plan = """- 5 min: warm-up

Topic summary for French Revolution causes (History):
- Core definition and why it matters.
- 2-3 key rules/formulas.
"""
    out = trim_material_sections_from_study_plan(plan).strip()
    assert "Topic summary" not in out
    assert "warm-up" in out


def test_topic_summary_cut_runs_before_line_parser() -> None:
    """Substring cut must run first so glued or odd line breaks still drop the template block."""
    plan = (
        "- 5 min: focus\n- 10 min: read\nTopic summary for French Revolution causes (History):\n"
        "- Core definition and why it matters.\n"
    )
    out = trim_material_sections_from_study_plan(plan)
    assert "Topic summary" not in out
    assert "focus" in out
    assert "Core definition" not in out
