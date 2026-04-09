from studygraph.usage import build_usage_record, estimate_cost_usd, summarize_usage


def test_estimate_cost_openai_gpt4o_mini() -> None:
    cost = estimate_cost_usd("openai", "gpt-5.2", 1000, 500)
    assert cost is not None
    assert cost > 0


def test_summarize_usage_aggregates_tokens_and_cost() -> None:
    rows = [
        build_usage_record(
            provider="openai",
            model="gpt-5.2",
            call_type="material_generation",
            prompt_tokens=100,
            completion_tokens=50,
        ),
        build_usage_record(
            provider="gemini",
            model="gemini-2.5-flash",
            call_type="quiz_generation",
            prompt_tokens=200,
            completion_tokens=80,
        ),
    ]
    summary = summarize_usage(rows)
    assert summary["prompt_tokens"] == 300
    assert summary["completion_tokens"] == 130
    assert summary["total_tokens"] == 430
    assert summary["estimated_cost_usd"] > 0
