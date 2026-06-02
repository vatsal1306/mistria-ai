"""Expose the supported archetypes package API."""

from src.archetypes.contracts import (
    ARCHETYPE_IDS,
    ARCHETYPE_TARGET_VECTORS,
    ArchetypeId,
    ArchetypeResult,
    ArchetypeScoreResult,
    OnboardingPathway,
    TIE_BREAK_ORDER,
    TIEBREAK_TRAIT_PRIORITY,
    TRAIT_KEYS,
    TraitKey,
    TraitVector,
)
from src.archetypes.exceptions import (
    ArchetypeError,
    InvalidTraitVectorError,
    ZeroVectorError,
)
from src.archetypes.scoring import (
    BLEND_THRESHOLD,
    NEUTRAL_MIN_SIMILARITY,
    ScoringResult,
    score_trait_vector,
)
from src.archetypes.schemas import ArchetypeResultResponse, SlowBurnScoreRequest

__all__ = [
    "ARCHETYPE_IDS",
    "ARCHETYPE_TARGET_VECTORS",
    "ArchetypeError",
    "ArchetypeId",
    "ArchetypeResult",
    "ArchetypeResultResponse",
    "ArchetypeScoreResult",
    "BLEND_THRESHOLD",
    "InvalidTraitVectorError",
    "NEUTRAL_MIN_SIMILARITY",
    "OnboardingPathway",
    "ScoringResult",
    "SlowBurnScoreRequest",
    "TIE_BREAK_ORDER",
    "TIEBREAK_TRAIT_PRIORITY",
    "TRAIT_KEYS",
    "TraitKey",
    "TraitVector",
    "ZeroVectorError",
    "score_trait_vector",
]
