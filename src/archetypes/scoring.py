"""Deterministic archetype scoring via cosine similarity."""

from __future__ import annotations

import math
from typing import Final

from src.archetypes.contracts import (
    ARCHETYPE_IDS,
    ARCHETYPE_TARGET_VECTORS,
    TIE_BREAK_ORDER,
    TIEBREAK_TRAIT_PRIORITY,
    TRAIT_KEYS,
    ArchetypeId,
    TraitKey,
)
from src.archetypes.exceptions import InvalidTraitVectorError, ZeroVectorError

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

BLEND_THRESHOLD: Final[float] = 0.10
"""Activate secondary archetype when its similarity is within 10% of primary."""

NEUTRAL_MIN_SIMILARITY: Final[float] = 0.60
"""Below this primary similarity the match is considered low-confidence."""

TIEBREAK_SIMILARITY_TOLERANCE: Final[float] = 0.02
"""Similarity gap below which trait-priority tiebreaking is applied."""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

class ScoringResult:
    """Immutable scoring outcome returned by :func:`score_trait_vector`."""

    __slots__ = (
        "primary_archetype",
        "primary_similarity",
        "secondary_archetype",
        "secondary_similarity",
        "blend_active",
        "trait_scores",
        "all_scores",
        "low_confidence",
    )

    def __init__(
        self,
        *,
        primary_archetype: ArchetypeId,
        primary_similarity: float,
        secondary_archetype: ArchetypeId | None,
        secondary_similarity: float | None,
        blend_active: bool,
        trait_scores: dict[TraitKey, float],
        all_scores: dict[ArchetypeId, float],
        low_confidence: bool,
    ) -> None:
        self.primary_archetype = primary_archetype
        self.primary_similarity = primary_similarity
        self.secondary_archetype = secondary_archetype
        self.secondary_similarity = secondary_similarity
        self.blend_active = blend_active
        self.trait_scores = trait_scores
        self.all_scores = all_scores
        self.low_confidence = low_confidence

    def to_dict(self) -> dict:
        """Serialize to the recommended JSON-friendly shape."""
        return {
            "primary_archetype": self.primary_archetype,
            "primary_similarity": round(self.primary_similarity, 4),
            "secondary_archetype": self.secondary_archetype,
            "secondary_similarity": (
                round(self.secondary_similarity, 4)
                if self.secondary_similarity is not None
                else None
            ),
            "blend_active": self.blend_active,
            "trait_scores": self.trait_scores,
            "low_confidence": self.low_confidence,
        }


# ---------------------------------------------------------------------------
# Pure scoring functions
# ---------------------------------------------------------------------------

def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Compute cosine similarity between two trait-keyed vectors."""
    dot = sum(a[k] * b[k] for k in TRAIT_KEYS)
    mag_a = math.sqrt(sum(a[k] ** 2 for k in TRAIT_KEYS))
    mag_b = math.sqrt(sum(b[k] ** 2 for k in TRAIT_KEYS))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def _validate_input(trait_vector: dict[str, float]) -> None:
    """Validate a raw trait vector dict before scoring."""
    if not isinstance(trait_vector, dict):
        raise InvalidTraitVectorError("trait vector must be a dict")

    keys = set(trait_vector.keys())
    expected = set(TRAIT_KEYS)

    missing = expected - keys
    if missing:
        raise InvalidTraitVectorError(
            f"missing trait keys: {sorted(missing)}"
        )

    extra = keys - expected
    if extra:
        raise InvalidTraitVectorError(
            f"unexpected trait keys: {sorted(extra)}"
        )

    for key, val in trait_vector.items():
        if not isinstance(val, (int, float)):
            raise InvalidTraitVectorError(
                f"trait {key!r} must be numeric, got {type(val).__name__}"
            )
        if not math.isfinite(val):
            raise InvalidTraitVectorError(
                f"trait {key!r} must be finite, got {val}"
            )

    if all(trait_vector[k] == 0.0 for k in TRAIT_KEYS):
        raise ZeroVectorError(
            "all-zero trait vector has no direction and cannot be scored"
        )


def _resolve_tiebreak(
    candidates: list[tuple[ArchetypeId, float]],
) -> list[tuple[ArchetypeId, float]]:
    """Apply deterministic tie-break when top candidates are within tolerance.

    1. Compare the archetype's target-vector score on the highest-priority
       trait dimension (TIEBREAK_TRAIT_PRIORITY order).
    2. If still tied, fall back to TIE_BREAK_ORDER position.
    """
    if len(candidates) < 2:
        return candidates

    best_sim = candidates[0][1]
    tied = [c for c in candidates if best_sim - c[1] < TIEBREAK_SIMILARITY_TOLERANCE]

    if len(tied) <= 1:
        return candidates

    def _sort_key(item: tuple[ArchetypeId, float]) -> tuple:
        aid, sim = item
        target = ARCHETYPE_TARGET_VECTORS[aid]
        trait_scores = tuple(
            -abs(target[t]) for t in TIEBREAK_TRAIT_PRIORITY
        )
        fallback = TIE_BREAK_ORDER.index(aid)
        return (-sim, trait_scores, fallback)

    candidates.sort(key=_sort_key)
    return candidates


def score_trait_vector(trait_vector: dict[str, float]) -> ScoringResult:
    """Score a submitted trait vector and return the best matching archetype.

    Accepts the seven canonical trait keys with numeric values.  Returns a
    deterministic :class:`ScoringResult` containing the primary archetype,
    optional secondary archetype, blend metadata, and all similarity scores.
    """
    _validate_input(trait_vector)

    # --- Compute cosine similarity against every archetype target ---
    similarities: list[tuple[ArchetypeId, float]] = [
        (aid, _cosine_similarity(trait_vector, ARCHETYPE_TARGET_VECTORS[aid]))
        for aid in ARCHETYPE_IDS
    ]

    # --- Sort descending by similarity, then apply tiebreak ---
    similarities.sort(key=lambda x: -x[1])
    similarities = _resolve_tiebreak(similarities)

    primary_id, primary_sim = similarities[0]
    runner_id, runner_sim = similarities[1]

    # --- Blend rule: secondary activates within 10% of primary ---
    blend_active = False
    secondary_archetype: ArchetypeId | None = None
    secondary_similarity: float | None = None

    if primary_sim > 0.0:
        gap_ratio = (primary_sim - runner_sim) / primary_sim
        if gap_ratio < BLEND_THRESHOLD:
            blend_active = True
            secondary_archetype = runner_id
            secondary_similarity = runner_sim

    return ScoringResult(
        primary_archetype=primary_id,
        primary_similarity=primary_sim,
        secondary_archetype=secondary_archetype,
        secondary_similarity=secondary_similarity,
        blend_active=blend_active,
        trait_scores={k: trait_vector[k] for k in TRAIT_KEYS},
        all_scores={aid: sim for aid, sim in similarities},
        low_confidence=primary_sim < NEUTRAL_MIN_SIMILARITY,
    )
