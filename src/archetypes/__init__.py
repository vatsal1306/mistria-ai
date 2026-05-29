"""Expose the supported archetypes package API."""

from src.archetypes.contracts import (
    ARCHETYPE_IDS,
    ARCHETYPE_TARGET_VECTORS,
    ArchetypeId,
    ArchetypeResult,
    ArchetypeScoreResult,
    OnboardingPathway,
    TIE_BREAK_ORDER,
    TRAIT_KEYS,
    TraitKey,
    TraitVector,
)

__all__ = [
    "ARCHETYPE_IDS",
    "ARCHETYPE_TARGET_VECTORS",
    "ArchetypeId",
    "ArchetypeResult",
    "ArchetypeScoreResult",
    "OnboardingPathway",
    "TIE_BREAK_ORDER",
    "TRAIT_KEYS",
    "TraitKey",
    "TraitVector",
]
