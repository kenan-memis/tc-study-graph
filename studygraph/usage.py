from __future__ import annotations

from typing import Any

# Estimated USD per 1M tokens (can be updated anytime).
MODEL_PRICING_PER_1M: dict[tuple[str, str], tuple[float, float]] = {
    ("openai", "gpt-5.2"): (0.15, 0.60),
    ("gemini", "gemini-2.5-flash"): (0.075, 0.30),
}


def estimate_cost_usd(
    provider: str, model: str, prompt_tokens: int, completion_tokens: int
) -> float | None:
    pricing = MODEL_PRICING_PER_1M.get((provider, model))
    if pricing is None:
        return None
    in_per_m, out_per_m = pricing
    cost = ((prompt_tokens / 1_000_000) * in_per_m) + (
        (completion_tokens / 1_000_000) * out_per_m
    )
    return round(cost, 8)


def build_usage_record(
    *,
    provider: str,
    model: str,
    call_type: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    pt = int(prompt_tokens or 0)
    ct = int(completion_tokens or 0)
    tt = int(total_tokens if total_tokens is not None else pt + ct)
    cost = estimate_cost_usd(provider, model, pt, ct)
    return {
        "provider": provider,
        "model": model,
        "call_type": call_type,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": tt,
        "estimated_cost_usd": cost,
        "usage_available": True,
        "note": note or "",
    }


def build_unavailable_usage_record(
    *, provider: str, model: str, call_type: str, note: str
) -> dict[str, Any]:
    return {
        "provider": provider,
        "model": model,
        "call_type": call_type,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": None,
        "usage_available": False,
        "note": note,
    }


def summarize_usage(records: list[dict[str, Any]]) -> dict[str, Any]:
    prompt = sum(int(r.get("prompt_tokens", 0) or 0) for r in records)
    completion = sum(int(r.get("completion_tokens", 0) or 0) for r in records)
    total = sum(int(r.get("total_tokens", 0) or 0) for r in records)
    known_cost = [
        float(r["estimated_cost_usd"])
        for r in records
        if r.get("estimated_cost_usd") is not None
    ]
    unavailable = sum(1 for r in records if not r.get("usage_available", False))
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "estimated_cost_usd": round(sum(known_cost), 8) if known_cost else 0.0,
        "calls_count": len(records),
        "calls_without_usage": unavailable,
    }
