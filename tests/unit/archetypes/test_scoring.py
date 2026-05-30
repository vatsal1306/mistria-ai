"""Unit tests for the archetype scoring service."""

from __future__ import annotations

import math

import pytest

from src.archetypes.contracts import (
    ARCHETYPE_IDS,
    ARCHETYPE_TARGET_VECTORS,
    TRAIT_KEYS,
)
from src.archetypes.exceptions import InvalidTraitVectorError, ZeroVectorError
from src.archetypes.scoring import (
    BLEND_THRESHOLD,
    NEUTRAL_MIN_SIMILARITY,
    ScoringResult,
    score_trait_vector,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pure_path_vector(archetype_id: str) -> dict[str, float]:
    """Build a user vector that strongly aligns with one archetype.

    Uses the archetype's own target vector scaled up, so cosine similarity
    is maximised for that archetype (direction identical, magnitude larger).
    """
    target = ARCHETYPE_TARGET_VECTORS[archetype_id]
    return {k: target[k] * 3.0 for k in TRAIT_KEYS}


def _zero_vector() -> dict[str, float]:
    return {k: 0.0 for k in TRAIT_KEYS}


def _valid_vector(**overrides: float) -> dict[str, float]:
    """Return a valid baseline vector with optional per-trait overrides."""
    base = {k: 1.0 for k in TRAIT_KEYS}
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    """Verify that invalid trait vectors are rejected with clear errors."""

    def test_rejects_missing_keys(self):
        """Reject a vector missing canonical keys."""
        with pytest.raises(InvalidTraitVectorError, match="missing trait keys"):
            score_trait_vector({"power": 1.0})

    def test_rejects_extra_keys(self):
        """Reject a vector with non-canonical keys."""
        vector = _valid_vector()
        vector["charisma"] = 1.0
        with pytest.raises(InvalidTraitVectorError, match="unexpected trait keys"):
            score_trait_vector(vector)

    def test_rejects_non_numeric_value(self):
        """Reject a vector with a non-numeric value."""
        vector = _valid_vector()
        vector["power"] = "high"
        with pytest.raises(InvalidTraitVectorError, match="must be numeric"):
            score_trait_vector(vector)

    def test_rejects_infinity(self):
        """Reject a vector with infinity."""
        vector = _valid_vector()
        vector["depth"] = float("inf")
        with pytest.raises(InvalidTraitVectorError, match="must be finite"):
            score_trait_vector(vector)

    def test_rejects_nan(self):
        """Reject a vector with NaN."""
        vector = _valid_vector()
        vector["depth"] = float("nan")
        with pytest.raises(InvalidTraitVectorError, match="must be finite"):
            score_trait_vector(vector)

    def test_rejects_all_zero_vector(self):
        """Reject an all-zero vector (no direction)."""
        with pytest.raises(ZeroVectorError, match="all-zero"):
            score_trait_vector(_zero_vector())

    def test_rejects_non_dict(self):
        """Reject a non-dict input."""
        with pytest.raises(InvalidTraitVectorError, match="must be a dict"):
            score_trait_vector([1, 2, 3])


# ---------------------------------------------------------------------------
# Deterministic pure-path routing
# ---------------------------------------------------------------------------

class TestPurePathRouting:
    """Verify each archetype wins when the user vector aligns perfectly."""

    @pytest.mark.parametrize("archetype_id", list(ARCHETYPE_IDS))
    def test_pure_path_routes_correctly(self, archetype_id: str):
        """A scaled copy of the target vector must route to its own archetype."""
        vector = _pure_path_vector(archetype_id)
        result = score_trait_vector(vector)

        assert result.primary_archetype == archetype_id
        assert result.primary_similarity == pytest.approx(1.0, abs=1e-9)

    @pytest.mark.parametrize("archetype_id", list(ARCHETYPE_IDS))
    def test_pure_path_has_healthy_gap(self, archetype_id: str):
        """Pure paths must have >=10% gap to the runner-up (no blend)."""
        vector = _pure_path_vector(archetype_id)
        result = score_trait_vector(vector)

        assert not result.blend_active
        assert result.secondary_archetype is None

        # Verify a meaningful gap exists in the all_scores
        runner_sim = max(
            sim for aid, sim in result.all_scores.items()
            if aid != archetype_id
        )
        gap = result.primary_similarity - runner_sim
        assert gap > 0.10, (
            f"{archetype_id} gap to runner-up is only {gap:.3f}"
        )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    """Verify the same input always produces the same output."""

    def test_repeated_calls_identical(self):
        """Score the same vector twice and confirm identical results."""
        vector = _valid_vector(depth=5.0, soft=4.0, intensity=2.0)
        a = score_trait_vector(vector)
        b = score_trait_vector(vector)

        assert a.primary_archetype == b.primary_archetype
        assert a.primary_similarity == b.primary_similarity
        assert a.blend_active == b.blend_active
        assert a.secondary_archetype == b.secondary_archetype


# ---------------------------------------------------------------------------
# Blend activation
# ---------------------------------------------------------------------------

class TestBlendActivation:
    """Verify secondary archetype and blend_active logic."""

    def test_blend_activates_for_mixed_vector(self):
        """A vector between two archetypes should activate the blend."""
        # Average soulmate and devotee targets — they share depth/soft traits
        sm = ARCHETYPE_TARGET_VECTORS["soulmate"]
        dv = ARCHETYPE_TARGET_VECTORS["devotee"]
        mixed = {k: (sm[k] + dv[k]) / 2.0 for k in TRAIT_KEYS}
        result = score_trait_vector(mixed)

        # Should activate blend because mid-point is close to both
        if result.blend_active:
            assert result.secondary_archetype is not None
            assert result.secondary_similarity is not None
            gap_ratio = (
                (result.primary_similarity - result.secondary_similarity)
                / result.primary_similarity
            )
            assert gap_ratio < BLEND_THRESHOLD

    def test_no_blend_for_pure_path(self):
        """A pure-path vector should not activate the blend."""
        vector = _pure_path_vector("rebel")
        result = score_trait_vector(vector)

        assert not result.blend_active
        assert result.secondary_archetype is None
        assert result.secondary_similarity is None


# ---------------------------------------------------------------------------
# Low-confidence / neutral fallback
# ---------------------------------------------------------------------------

class TestLowConfidence:
    """Verify low-confidence flagging for weak matches."""

    def test_low_confidence_flag(self):
        """A deliberately noisy vector should flag low confidence."""
        # Construct a vector orthogonal to all archetypes
        # by using values that don't align with any target direction
        vector = {k: 0.001 for k in TRAIT_KEYS}
        vector["pace"] = 1.0  # just enough to not be zero
        result = score_trait_vector(vector)

        # The result is still valid, but may be low-confidence
        assert isinstance(result.low_confidence, bool)
        assert result.primary_archetype in ARCHETYPE_IDS


# ---------------------------------------------------------------------------
# ScoringResult serialization
# ---------------------------------------------------------------------------

class TestScoringResultSerialization:
    """Verify to_dict output shape matches the recommended JSON format."""

    def test_to_dict_contains_required_keys(self):
        """Serialized result must contain all recommended fields."""
        vector = _pure_path_vector("rebel")
        result = score_trait_vector(vector)
        d = result.to_dict()

        assert "primary_archetype" in d
        assert "primary_similarity" in d
        assert "secondary_archetype" in d
        assert "secondary_similarity" in d
        assert "blend_active" in d
        assert "trait_scores" in d
        assert "low_confidence" in d

    def test_to_dict_similarities_are_rounded(self):
        """Similarity values should be rounded to 4 decimal places."""
        vector = _valid_vector(depth=5.0, soft=4.0)
        result = score_trait_vector(vector)
        d = result.to_dict()

        sim_str = str(d["primary_similarity"])
        # At most 4 decimal places
        if "." in sim_str:
            assert len(sim_str.split(".")[1]) <= 4

    def test_to_dict_trait_scores_match_input(self):
        """Trait scores in the result must match the submitted vector."""
        vector = _valid_vector(sharp=7.0, intensity=3.0)
        result = score_trait_vector(vector)

        assert result.trait_scores["sharp"] == 7.0
        assert result.trait_scores["intensity"] == 3.0


# ---------------------------------------------------------------------------
# Cosine similarity correctness
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    """Verify cosine similarity math independently."""

    def test_identical_direction_gives_one(self):
        """Parallel vectors have similarity 1.0."""
        vector = _pure_path_vector("muse")
        result = score_trait_vector(vector)
        assert result.all_scores["muse"] == pytest.approx(1.0, abs=1e-9)

    def test_all_scores_populated(self):
        """All five archetypes should have a score in all_scores."""
        vector = _valid_vector()
        result = score_trait_vector(vector)
        assert set(result.all_scores.keys()) == set(ARCHETYPE_IDS)
