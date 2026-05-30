"""Archetype domain contracts: canonical IDs, trait keys, target vectors, and result metadata."""

from __future__ import annotations

import math
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

# ---------------------------------------------------------------------------
# Onboarding pathway
# ---------------------------------------------------------------------------

OnboardingPathway = Literal["intense_heat", "slow_burn"]

# ---------------------------------------------------------------------------
# Archetype IDs (canonical, alphabetical)
# ---------------------------------------------------------------------------

ArchetypeId = Literal["devotee", "muse", "protector", "rebel", "soulmate"]

ARCHETYPE_IDS: Final[tuple[ArchetypeId, ...]] = (
    "devotee",
    "muse",
    "protector",
    "rebel",
    "soulmate",
)

# ---------------------------------------------------------------------------
# Trait keys (canonical, alphabetical)
# ---------------------------------------------------------------------------

TraitKey = Literal["depth", "freedom", "intensity", "pace", "power", "sharp", "soft"]

TRAIT_KEYS: Final[tuple[TraitKey, ...]] = (
    "depth",
    "freedom",
    "intensity",
    "pace",
    "power",
    "sharp",
    "soft",
)

# ---------------------------------------------------------------------------
# Trait vector — validated seven-dimension mapping
#
# When used as a Pydantic model field the validator enforces that exactly
# the seven canonical trait keys are present and values are within bounds.
# ---------------------------------------------------------------------------

_TRAIT_VALUE_MIN: Final[float] = -20.0
_TRAIT_VALUE_MAX: Final[float] = 20.0


def _validate_trait_vector(value: Any) -> dict[str, float]:
    """Require exactly the canonical trait keys with bounded, finite values."""
    if not isinstance(value, dict):
        raise ValueError("trait vector must be a dict")

    keys = set(value.keys())
    expected = set(TRAIT_KEYS)

    missing = expected - keys
    if missing:
        raise ValueError(f"missing trait keys: {sorted(missing)}")

    extra = keys - expected
    if extra:
        raise ValueError(f"unexpected trait keys: {sorted(extra)}")

    for key, val in value.items():
        if not isinstance(val, (int, float)):
            raise ValueError(
                f"trait {key!r} must be numeric, got {type(val).__name__}"
            )
        if not math.isfinite(val):
            raise ValueError(f"trait {key!r} must be finite, got {val}")
        if not (_TRAIT_VALUE_MIN <= val <= _TRAIT_VALUE_MAX):
            raise ValueError(
                f"trait {key!r} value {val} out of range "
                f"[{_TRAIT_VALUE_MIN}, {_TRAIT_VALUE_MAX}]"
            )

    return {k: float(v) for k, v in value.items()}


TraitVector = Annotated[
    dict[str, float], BeforeValidator(_validate_trait_vector)
]

# ---------------------------------------------------------------------------
# Target archetype vectors
#
# Each archetype has a canonical seven-dimension profile that incoming
# trait vectors are compared against during scoring.
# ---------------------------------------------------------------------------

ARCHETYPE_TARGET_VECTORS: Final[dict[ArchetypeId, TraitVector]] = {
    "soulmate": {
        "power": -1.0,
        "pace": -2.0,
        "intensity": 1.0,
        "depth": 3.0,
        "soft": 3.0,
        "freedom": 0.0,
        "sharp": 0.0,
    },
    "protector": {
        "power": 2.0,
        "pace": -1.0,
        "intensity": 1.0,
        "depth": 1.0,
        "soft": 2.0,
        "freedom": 0.0,
        "sharp": 0.0,
    },
    "devotee": {
        "power": -1.0,
        "pace": 1.0,
        "intensity": 3.0,
        "depth": 3.0,
        "soft": 1.0,
        "freedom": 0.0,
        "sharp": 1.0,
    },
    "muse": {
        "power": 0.0,
        "pace": 1.0,
        "intensity": 2.0,
        "depth": 1.0,
        "soft": 1.0,
        "freedom": 3.0,
        "sharp": 1.0,
    },
    "rebel": {
        "power": 3.0,
        "pace": 2.0,
        "intensity": 3.0,
        "depth": 0.0,
        "soft": -3.0,
        "freedom": 1.0,
        "sharp": 4.0,
    },
}

# ---------------------------------------------------------------------------
# Tie-break priority order
#
# If similarity scores match closely, ties are resolved using the archetype's
# score on its strongest trait dimensions in this order.
# ---------------------------------------------------------------------------

TIEBREAK_TRAIT_PRIORITY: Final[tuple[TraitKey, ...]] = (
    "depth",
    "intensity",
    "sharp",
    "soft",
    "freedom",
    "power",
    "pace",
)

# ---------------------------------------------------------------------------
# Tie-break order
#
# Fallback deterministic order when trait comparisons are also tied.
# ---------------------------------------------------------------------------

TIE_BREAK_ORDER: Final[tuple[ArchetypeId, ...]] = (
    "soulmate",
    "protector",
    "devotee",
    "muse",
    "rebel",
)

# ---------------------------------------------------------------------------
# Result metadata schema
# ---------------------------------------------------------------------------


class ArchetypeScoreResult(BaseModel):
    """Scoring result for a single archetype candidate."""

    model_config = ConfigDict(extra="forbid")

    archetype_id: ArchetypeId
    score: float = Field(ge=-1.0, le=1.0)


class ArchetypeResult(BaseModel):
    """Final archetype determination returned by the scoring layer."""

    model_config = ConfigDict(extra="forbid")

    matched_archetype: ArchetypeId
    scores: list[ArchetypeScoreResult]
    trait_vector: TraitVector
    onboarding_pathway: OnboardingPathway
