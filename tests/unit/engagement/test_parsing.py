"""Unit tests for engagement score parsing."""

from __future__ import annotations

import pytest

from src.engagement.parsing import parse_engagement_score


@pytest.mark.parametrize(
    ("raw_output", "expected"),
    [
        ("85", 85),
        (" 42 ", 42),
        ("The score is 85", 85),
        ("Score: 100", 100),
        ("1", 1),
    ],
)
def test_parse_engagement_score_accepts_valid_outputs(raw_output: str, expected: int) -> None:
    assert parse_engagement_score(raw_output) == expected


@pytest.mark.parametrize(
    "raw_output",
    [
        "",
        "no numbers here",
        "101",
        "0",
        "999",
    ],
)
def test_parse_engagement_score_rejects_invalid_outputs(raw_output: str) -> None:
    assert parse_engagement_score(raw_output) is None
