"""Archetype domain contracts: canonical IDs, trait keys, target vectors, and result metadata."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

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
# Trait vector — typed alias for the seven-dimension mapping
# ---------------------------------------------------------------------------

TraitVector = dict[TraitKey, float]

# ---------------------------------------------------------------------------
# Target archetype vectors
#
# Each archetype has a canonical seven-dimension profile that incoming
# trait vectors are compared against during scoring.
# ---------------------------------------------------------------------------

ARCHETYPE_TARGET_VECTORS: Final[dict[ArchetypeId, TraitVector]] = {
    "soulmate": {
        "power": 0.3,
        "pace": 0.3,
        "intensity": 0.3,
        "depth": 0.9,
        "soft": 0.9,
        "freedom": 0.3,
        "sharp": 0.1,
    },
    "protector": {
        "power": 0.8,
        "pace": 0.4,
        "intensity": 0.6,
        "depth": 0.7,
        "soft": 0.6,
        "freedom": 0.2,
        "sharp": 0.4,
    },
    "devotee": {
        "power": 0.2,
        "pace": 0.3,
        "intensity": 0.7,
        "depth": 0.8,
        "soft": 0.8,
        "freedom": 0.2,
        "sharp": 0.2,
    },
    "muse": {
        "power": 0.5,
        "pace": 0.7,
        "intensity": 0.5,
        "depth": 0.4,
        "soft": 0.5,
        "freedom": 0.8,
        "sharp": 0.6,
    },
    "rebel": {
        "power": 0.9,
        "pace": 0.8,
        "intensity": 0.9,
        "depth": 0.3,
        "soft": 0.1,
        "freedom": 0.9,
        "sharp": 0.9,
    },
}

# ---------------------------------------------------------------------------
# Tie-break order
#
# When two or more archetypes produce the same score, the one appearing
# earlier in this tuple wins.  This keeps results fully deterministic.
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
    score: float = Field(ge=0.0, le=1.0)


class ArchetypeResult(BaseModel):
    """Final archetype determination returned by the scoring layer."""

    model_config = ConfigDict(extra="forbid")

    matched_archetype: ArchetypeId
    scores: list[ArchetypeScoreResult]
    trait_vector: TraitVector
    onboarding_pathway: OnboardingPathway
