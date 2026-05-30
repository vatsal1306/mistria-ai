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
# Explicit trait-vector fixtures
#
# Each fixture is a stable, hand-crafted vector that clearly aligns with
# one archetype.  Values are chosen to mirror realistic quiz accumulations
# rather than directly scaling the target coordinates.
# ---------------------------------------------------------------------------

SOULMATE_VECTOR: dict[str, float] = {
    "power": -1.0,
    "pace": -3.0,
    "intensity": 1.0,
    "depth": 8.0,
    "soft": 9.0,
    "freedom": 0.0,
    "sharp": 0.0,
}
"""High depth + soft, negative pace — textbook Soulmate accumulation."""

PROTECTOR_VECTOR: dict[str, float] = {
    "power": 6.0,
    "pace": -2.0,
    "intensity": 2.0,
    "depth": 3.0,
    "soft": 5.0,
    "freedom": 0.0,
    "sharp": 0.0,
}
"""High power + soft, low pace — textbook Protector accumulation."""

DEVOTEE_VECTOR: dict[str, float] = {
    "power": -2.0,
    "pace": 2.0,
    "intensity": 9.0,
    "depth": 8.0,
    "soft": 2.0,
    "freedom": 0.0,
    "sharp": 2.0,
}
"""Extreme intensity + depth, negative power — textbook Devotee accumulation."""

MUSE_VECTOR: dict[str, float] = {
    "power": 0.0,
    "pace": 3.0,
    "intensity": 3.0,
    "depth": 1.0,
    "soft": 1.0,
    "freedom": 9.0,
    "sharp": 2.0,
}
"""Dominant freedom, moderate pace/sharp — textbook Muse accumulation."""

REBEL_VECTOR: dict[str, float] = {
    "power": 8.0,
    "pace": 5.0,
    "intensity": 8.0,
    "depth": 0.0,
    "soft": -4.0,
    "freedom": 2.0,
    "sharp": 12.0,
}
"""Extreme sharp + power, negative soft — textbook Rebel accumulation."""

NEAR_BOUNDARY_VECTOR: dict[str, float] = {
    "power": -1.0,
    "pace": -0.5,
    "intensity": 2.0,
    "depth": 3.0,
    "soft": 2.0,
    "freedom": 0.0,
    "sharp": 0.5,
}
"""Midpoint between Soulmate and Devotee — should produce blend metadata."""

FIXTURE_MAP: dict[str, dict[str, float]] = {
    "soulmate": SOULMATE_VECTOR,
    "protector": PROTECTOR_VECTOR,
    "devotee": DEVOTEE_VECTOR,
    "muse": MUSE_VECTOR,
    "rebel": REBEL_VECTOR,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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

    def test_accepts_negative_trait_values(self):
        """Negative values are valid (quiz answers can subtract from traits)."""
        vector = _valid_vector(soft=-2.0, pace=-3.0)
        result = score_trait_vector(vector)
        assert result.primary_archetype in ARCHETYPE_IDS
        assert result.trait_scores["soft"] == -2.0
        assert result.trait_scores["pace"] == -3.0


# ---------------------------------------------------------------------------
# Fixture-based routing — explicit vectors per archetype
# ---------------------------------------------------------------------------

class TestFixtureRouting:
    """Verify each hand-crafted fixture routes to its intended archetype."""

    @pytest.mark.parametrize("archetype_id", list(FIXTURE_MAP.keys()))
    def test_fixture_routes_to_expected_archetype(self, archetype_id: str):
        """Explicit fixture vector must route to the expected archetype."""
        vector = FIXTURE_MAP[archetype_id]
        result = score_trait_vector(vector)
        assert result.primary_archetype == archetype_id

    @pytest.mark.parametrize("archetype_id", list(FIXTURE_MAP.keys()))
    def test_fixture_has_healthy_gap_to_runner_up(self, archetype_id: str):
        """Fixture vectors should clear the blend threshold (no blend)."""
        vector = FIXTURE_MAP[archetype_id]
        result = score_trait_vector(vector)

        assert not result.blend_active, (
            f"{archetype_id} fixture unexpectedly activated blend"
        )

        runner_sim = max(
            sim for aid, sim in result.all_scores.items()
            if aid != archetype_id
        )
        gap = result.primary_similarity - runner_sim
        assert gap > 0.10, (
            f"{archetype_id} fixture gap to runner-up is only {gap:.3f}"
        )

    @pytest.mark.parametrize("archetype_id", list(FIXTURE_MAP.keys()))
    def test_fixture_not_low_confidence(self, archetype_id: str):
        """Clear fixture vectors should never be low-confidence."""
        vector = FIXTURE_MAP[archetype_id]
        result = score_trait_vector(vector)
        assert not result.low_confidence


# ---------------------------------------------------------------------------
# Scaled target-vector routing (pure-path confirmation)
# ---------------------------------------------------------------------------

class TestPurePathRouting:
    """Verify cosine similarity is 1.0 when the input is a scaled target."""

    @pytest.mark.parametrize("archetype_id", list(ARCHETYPE_IDS))
    def test_scaled_target_gives_perfect_similarity(self, archetype_id: str):
        """A scaled copy of the target vector must produce similarity 1.0."""
        target = ARCHETYPE_TARGET_VECTORS[archetype_id]
        vector = {k: target[k] * 3.0 for k in TRAIT_KEYS}
        result = score_trait_vector(vector)

        assert result.primary_archetype == archetype_id
        assert result.primary_similarity == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    """Verify the same input always produces the same output."""

    def test_repeated_calls_identical(self):
        """Score the same vector twice and confirm identical results."""
        vector = SOULMATE_VECTOR.copy()
        a = score_trait_vector(vector)
        b = score_trait_vector(vector)

        assert a.primary_archetype == b.primary_archetype
        assert a.primary_similarity == b.primary_similarity
        assert a.blend_active == b.blend_active
        assert a.secondary_archetype == b.secondary_archetype
        assert a.all_scores == b.all_scores

    def test_all_fixtures_deterministic(self):
        """Every fixture produces stable output across two calls."""
        for aid, vec in FIXTURE_MAP.items():
            a = score_trait_vector(vec)
            b = score_trait_vector(vec)
            assert a.primary_archetype == b.primary_archetype, (
                f"{aid} fixture produced non-deterministic primary"
            )


# ---------------------------------------------------------------------------
# Blend activation
# ---------------------------------------------------------------------------

class TestBlendActivation:
    """Verify secondary archetype and blend_active logic."""

    def test_near_boundary_activates_blend(self):
        """The near-boundary fixture should activate secondary/blend metadata."""
        result = score_trait_vector(NEAR_BOUNDARY_VECTOR)

        assert result.blend_active
        assert result.secondary_archetype is not None
        assert result.secondary_similarity is not None
        assert result.secondary_archetype != result.primary_archetype

        gap_ratio = (
            (result.primary_similarity - result.secondary_similarity)
            / result.primary_similarity
        )
        assert gap_ratio < BLEND_THRESHOLD

    def test_blend_does_not_replace_primary(self):
        """Blend metadata must not change the primary archetype assignment."""
        result = score_trait_vector(NEAR_BOUNDARY_VECTOR)

        # Primary is still the top scorer regardless of blend
        all_sorted = sorted(
            result.all_scores.items(), key=lambda x: -x[1]
        )
        assert result.primary_archetype == all_sorted[0][0]

    def test_blend_metadata_is_metadata_only(self):
        """secondary_archetype and blend_active are metadata — not a routing override."""
        result = score_trait_vector(NEAR_BOUNDARY_VECTOR)

        # The secondary must be the runner-up, not the primary
        assert result.secondary_archetype != result.primary_archetype
        # blend_active is a boolean flag, not a routing instruction
        assert isinstance(result.blend_active, bool)

    def test_no_blend_for_clear_fixture(self):
        """A clear fixture vector should not activate the blend."""
        result = score_trait_vector(REBEL_VECTOR)

        assert not result.blend_active
        assert result.secondary_archetype is None
        assert result.secondary_similarity is None


# ---------------------------------------------------------------------------
# Low-confidence / neutral fallback
# ---------------------------------------------------------------------------

class TestLowConfidence:
    """Verify low-confidence flagging for weak matches."""

    def test_low_confidence_flag_type(self):
        """Result always carries a boolean low_confidence field."""
        vector = {k: 0.001 for k in TRAIT_KEYS}
        vector["pace"] = 1.0  # just enough to not be zero
        result = score_trait_vector(vector)

        assert isinstance(result.low_confidence, bool)
        assert result.primary_archetype in ARCHETYPE_IDS

    def test_clear_fixtures_are_not_low_confidence(self):
        """All clear fixture vectors should be high-confidence."""
        for aid, vec in FIXTURE_MAP.items():
            result = score_trait_vector(vec)
            assert not result.low_confidence, (
                f"{aid} fixture was unexpectedly low-confidence "
                f"(sim={result.primary_similarity:.3f})"
            )


# ---------------------------------------------------------------------------
# ScoringResult serialization
# ---------------------------------------------------------------------------

class TestScoringResultSerialization:
    """Verify to_dict output shape matches the recommended JSON format."""

    def test_to_dict_contains_required_keys(self):
        """Serialized result must contain all recommended fields."""
        result = score_trait_vector(REBEL_VECTOR)
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
        result = score_trait_vector(SOULMATE_VECTOR)
        d = result.to_dict()

        sim_str = str(d["primary_similarity"])
        if "." in sim_str:
            assert len(sim_str.split(".")[1]) <= 4

    def test_to_dict_trait_scores_match_input(self):
        """Trait scores in the result must match the submitted vector."""
        result = score_trait_vector(REBEL_VECTOR)

        assert result.trait_scores["sharp"] == 12.0
        assert result.trait_scores["soft"] == -4.0
        assert result.trait_scores["power"] == 8.0


# ---------------------------------------------------------------------------
# Cosine similarity correctness
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    """Verify cosine similarity math independently."""

    def test_identical_direction_gives_one(self):
        """Parallel vectors have similarity 1.0."""
        target = ARCHETYPE_TARGET_VECTORS["muse"]
        vector = {k: target[k] * 5.0 for k in TRAIT_KEYS}
        result = score_trait_vector(vector)
        assert result.all_scores["muse"] == pytest.approx(1.0, abs=1e-9)

    def test_all_scores_populated(self):
        """All five archetypes should have a score in all_scores."""
        result = score_trait_vector(DEVOTEE_VECTOR)
        assert set(result.all_scores.keys()) == set(ARCHETYPE_IDS)

    def test_similarity_range(self):
        """All cosine similarity values should be in [-1.0, 1.0]."""
        for vec in FIXTURE_MAP.values():
            result = score_trait_vector(vec)
            for aid, sim in result.all_scores.items():
                assert -1.0 <= sim <= 1.0, (
                    f"similarity for {aid} is {sim}, out of range"
                )


# ---------------------------------------------------------------------------
# Tie-breaking logic
# ---------------------------------------------------------------------------

class TestTieBreaking:
    """Verify deterministic tie-breaking logic for closely matched similarities."""

    def _get_unit_vector(self, archetype_id: str) -> dict[str, float]:
        target = ARCHETYPE_TARGET_VECTORS[archetype_id]
        mag = math.sqrt(sum(v**2 for v in target.values()))
        return {k: target[k] / mag for k in TRAIT_KEYS}

    def test_tiebreak_soulmate_vs_devotee(self):
        """Devotee wins tiebreak over Soulmate due to higher intensity score."""
        sm_u = self._get_unit_vector("soulmate")
        dv_u = self._get_unit_vector("devotee")
        # Equidistant vector
        vector = {k: sm_u[k] + dv_u[k] for k in TRAIT_KEYS}
        result = score_trait_vector(vector)

        # Both have depth=3, but Devotee has intensity=3, Soulmate has intensity=1
        assert result.primary_archetype == "devotee"
        assert result.all_scores["devotee"] == pytest.approx(result.all_scores["soulmate"], abs=1e-9)

    def test_tiebreak_soulmate_vs_muse(self):
        """Soulmate wins tiebreak over Muse due to higher depth score."""
        sm_u = self._get_unit_vector("soulmate")
        mu_u = self._get_unit_vector("muse")
        # Equidistant vector
        vector = {k: sm_u[k] + mu_u[k] for k in TRAIT_KEYS}
        result = score_trait_vector(vector)

        # Soulmate depth=3, Muse depth=1
        assert result.primary_archetype == "soulmate"
        assert result.all_scores["soulmate"] == pytest.approx(result.all_scores["muse"], abs=1e-9)

