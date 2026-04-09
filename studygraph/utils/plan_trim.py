"""Strip study-material-style sections accidentally included in streamed study plans."""

from __future__ import annotations

import re
import unicodedata

# First line of a "study material" block (headings), not timed plan bullets.
_MATERIAL_SECTION_LINE = re.compile(
    r"^[\s\u00a0\u200b\ufeff]*(?:#{1,3}\s+)?(?:[-*•\u2013\u2014]+\s*)?(?:\*{1,2})?\s*"
    r"(?:topic\s+summary\s+for|core\s+concept|key\s+points?|worked\s+mini[\s-]*example|worked\s+example|common\s+mistakes)\b",
    re.IGNORECASE | re.UNICODE,
)

_TAIL_MARKERS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)(?:^|\n)\s*(?:\*\*)?\s*core\s+concept\s*\(",
        re.MULTILINE,
    ),
    # No leading \\b: avoids rare boundary failures when the model glues lines oddly.
    re.compile(r"(?i)topic\s+summary\s+for\b"),
    re.compile(
        r"(?i)(?:^|\n)\s*(?:\*\*)?\s*reference\s*:",
        re.MULTILINE,
    ),
)

# Echoes of ``material_fallback_template`` bullet lines (deterministic cut).
_FALLBACK_TEMPLATE_BULLETS: tuple[str, ...] = (
    "core definition and why it matters",
    "2-3 key rules/formulas",
    "one short example with explanation",
    "common mistakes to avoid",
)


def _cut_at_substring_casefold(text: str, needles: tuple[str, ...]) -> str:
    """Truncate before earliest occurrence of any needle (case-insensitive)."""
    if not text or not needles:
        return text
    cf = text.casefold()
    earliest = len(text)
    for needle in needles:
        n = needle.casefold()
        pos = cf.find(n)
        if pos != -1 and pos < earliest:
            earliest = pos
    if earliest < len(text):
        return text[:earliest].rstrip()
    return text


def trim_material_sections_from_study_plan(plan: str) -> str:
    """Remove duplicate material block: keep timed plan, drop echoed study material."""
    raw = plan or ""
    text = unicodedata.normalize("NFKC", raw.strip())
    if not text:
        return raw.strip()

    # 1) Deterministic: material_fallback_template title + generic bullets (substring — cannot
    #    fail on \\b or line breaks the way pure-regex passes sometimes do).
    text = _cut_at_substring_casefold(
        text,
        ("topic summary for",),
    )
    # If the model pasted fallback bullets without the title line, cut before first bullet line.
    cf = text.casefold()
    if (" min" in cf or "min:" in cf or "min：" in cf) and len(text) > 40:
        text = _cut_at_substring_casefold(text, _FALLBACK_TEMPLATE_BULLETS)

    kept: list[str] = []
    for line in text.splitlines():
        if _MATERIAL_SECTION_LINE.match(line):
            break
        kept.append(line)
    trimmed = "\n".join(kept).rstrip()

    cut_at: int | None = None
    for pat in _TAIL_MARKERS:
        match = pat.search(trimmed)
        if match:
            cut_at = match.start() if cut_at is None else min(cut_at, match.start())
    if cut_at is not None:
        trimmed = trimmed[:cut_at].rstrip()

    m_inline = re.search(r"(?i)\bcore\s+concept\s*\(", trimmed)
    if m_inline is not None and m_inline.start() > 40:
        trimmed = trimmed[: m_inline.start()].rstrip()

    trimmed = _nuclear_strip_appended_material(trimmed)

    return trimmed if trimmed else text


def _nuclear_strip_appended_material(text: str) -> str:
    """If a timed plan is followed by ``Core concept (…`` material, drop the tail."""
    if len(text) < 60:
        return text
    low = text.casefold()
    if " min" not in low and "min:" not in low and "min：" not in low:
        return text
    needle = "core concept ("
    pos = low.find(needle)
    if pos > 25:
        return text[:pos].rstrip()
    return text
