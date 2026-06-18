"""Utilities for parsing engagement score responses from the LLM."""

from __future__ import annotations

import re

_SCORE_PATTERN = re.compile(r"\b(\d{1,3})\b")


def parse_engagement_score(raw_output: str) -> int | None:
    """Parse a 1-100 engagement score from raw LLM output.

    Args:
        raw_output: The raw text returned by the inference runtime.

    Returns:
        A validated score between 1 and 100, or ``None`` when parsing fails.
    """
    stripped = raw_output.strip()
    if not stripped:
        return None

    try:
        value = int(stripped)
        if 1 <= value <= 100:
            return value
    except ValueError:
        pass

    for match in _SCORE_PATTERN.finditer(stripped):
        value = int(match.group(1))
        if 1 <= value <= 100:
            return value

    return None
