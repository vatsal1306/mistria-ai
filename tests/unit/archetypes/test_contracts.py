"""Unit tests for archetype domain contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.archetypes.contracts import (
    ARCHETYPE_IDS,
    ARCHETYPE_TARGET_VECTORS,
    ArchetypeResult,
    ArchetypeScoreResult,
    TIE_BREAK_ORDER,
    TIEBREAK_TRAIT_PRIORITY,
    TRAIT_KEYS,
)


class TestCanonicalConstants:
    """Verify canonical ID and key tuples are consistent."""

    def test_archetype_ids_match_target_vectors(self):
        """Every archetype ID must have a corresponding target vector."""
        assert set(ARCHETYPE_IDS) == set(ARCHETYPE_TARGET_VECTORS.keys())

    def test_target_vectors_use_canonical_trait_keys(self):
        """Every target vector must use exactly the canonical trait keys."""
        for archetype_id, vector in ARCHETYPE_TARGET_VECTORS.items():
            assert set(vector.keys()) == set(TRAIT_KEYS), (
                f"Target vector for {archetype_id!r} uses non-canonical trait keys"
            )

    def test_target_vector_values_in_range(self):
        """All target vector values must be in [-3.0, 4.0]."""
        for archetype_id, vector in ARCHETYPE_TARGET_VECTORS.items():
            for key, value in vector.items():
                assert -3.0 <= value <= 4.0, (
                    f"{archetype_id}.{key} = {value} is out of range"
                )

    def test_tie_break_order_covers_all_archetypes(self):
        """Tie-break order must be a permutation of the archetype IDs."""
        assert set(TIE_BREAK_ORDER) == set(ARCHETYPE_IDS)
        assert len(TIE_BREAK_ORDER) == len(ARCHETYPE_IDS)

    def test_tiebreak_trait_priority_covers_all_traits(self):
        """Tiebreak trait priority must be a permutation of canonical trait keys."""
        assert set(TIEBREAK_TRAIT_PRIORITY) == set(TRAIT_KEYS)
        assert len(TIEBREAK_TRAIT_PRIORITY) == len(TRAIT_KEYS)

    def test_no_duplicate_archetype_ids(self):
        """No duplicate entries in the canonical tuples."""
        assert len(ARCHETYPE_IDS) == len(set(ARCHETYPE_IDS))
        assert len(TRAIT_KEYS) == len(set(TRAIT_KEYS))

    def test_naming_conventions(self):
        """Verify latest client naming (rebel not possessive, protector not caring)."""
        assert "rebel" in ARCHETYPE_IDS
        assert "protector" in ARCHETYPE_IDS
        assert "possessive" not in ARCHETYPE_IDS
        assert "caring" not in ARCHETYPE_IDS


class TestArchetypeScoreResult:
    """Verify ArchetypeScoreResult validation."""

    def test_valid_score(self):
        """Accept a score in [-1.0, 1.0]."""
        result = ArchetypeScoreResult(archetype_id="rebel", score=-0.75)
        assert result.archetype_id == "rebel"
        assert result.score == -0.75

    def test_rejects_score_above_one(self):
        """Reject scores above 1.0."""
        with pytest.raises(ValidationError):
            ArchetypeScoreResult(archetype_id="muse", score=1.5)

    def test_rejects_score_below_minus_one(self):
        """Reject scores below -1.0."""
        with pytest.raises(ValidationError):
            ArchetypeScoreResult(archetype_id="muse", score=-1.5)

    def test_rejects_invalid_archetype_id(self):
        """Reject unknown archetype IDs."""
        with pytest.raises(ValidationError):
            ArchetypeScoreResult(archetype_id="possessive", score=0.5)

    def test_rejects_extra_fields(self):
        """Extra fields are forbidden."""
        with pytest.raises(ValidationError):
            ArchetypeScoreResult(archetype_id="rebel", score=0.5, bonus=True)


class TestArchetypeResult:
    """Verify ArchetypeResult validation."""

    def _make_scores(self) -> list[ArchetypeScoreResult]:
        return [
            ArchetypeScoreResult(archetype_id=aid, score=round(i * 0.2, 1))
            for i, aid in enumerate(ARCHETYPE_IDS)
        ]

    def test_valid_result(self):
        """Accept a well-formed archetype result."""
        result = ArchetypeResult(
            matched_archetype="soulmate",
            scores=self._make_scores(),
            trait_vector={k: 0.5 for k in TRAIT_KEYS},
            onboarding_pathway="slow_burn",
        )
        assert result.matched_archetype == "soulmate"
        assert result.onboarding_pathway == "slow_burn"
        assert len(result.scores) == len(ARCHETYPE_IDS)

    def test_rejects_invalid_pathway(self):
        """Reject unknown onboarding pathways."""
        with pytest.raises(ValidationError):
            ArchetypeResult(
                matched_archetype="soulmate",
                scores=self._make_scores(),
                trait_vector={k: 0.5 for k in TRAIT_KEYS},
                onboarding_pathway="turbo",
            )

    def test_rejects_extra_fields(self):
        """Extra fields are forbidden."""
        with pytest.raises(ValidationError):
            ArchetypeResult(
                matched_archetype="soulmate",
                scores=self._make_scores(),
                trait_vector={k: 0.5 for k in TRAIT_KEYS},
                onboarding_pathway="slow_burn",
                extra_field="nope",
            )


class TestTraitVectorValidation:
    """Verify TraitVector enforcement on ArchetypeResult.trait_vector."""

    def _make_scores(self) -> list[ArchetypeScoreResult]:
        return [
            ArchetypeScoreResult(archetype_id=aid, score=round(i * 0.2, 1))
            for i, aid in enumerate(ARCHETYPE_IDS)
        ]

    def _build(self, trait_vector: dict) -> ArchetypeResult:
        """Helper to construct an ArchetypeResult with the given trait vector."""
        return ArchetypeResult(
            matched_archetype="soulmate",
            scores=self._make_scores(),
            trait_vector=trait_vector,
            onboarding_pathway="slow_burn",
        )

    def test_accepts_complete_valid_vector(self):
        """Accept a trait vector with all seven canonical keys and valid values."""
        result = self._build({k: 1.5 for k in TRAIT_KEYS})
        assert set(result.trait_vector.keys()) == set(TRAIT_KEYS)

    def test_accepts_negative_values(self):
        """Accept negative values within bounds."""
        result = self._build({k: -5.0 for k in TRAIT_KEYS})
        assert result.trait_vector["power"] == -5.0

    def test_rejects_missing_keys(self):
        """Reject a trait vector that omits canonical keys."""
        with pytest.raises(ValidationError, match="missing trait keys"):
            self._build({"power": 1.0})

    def test_rejects_extra_keys(self):
        """Reject a trait vector with non-canonical keys."""
        vector = {k: 0.5 for k in TRAIT_KEYS}
        vector["charisma"] = 1.0
        with pytest.raises(ValidationError, match="unexpected trait keys"):
            self._build(vector)

    def test_rejects_out_of_range_high(self):
        """Reject trait values above the upper bound."""
        vector = {k: 0.5 for k in TRAIT_KEYS}
        vector["power"] = 99.0
        with pytest.raises(ValidationError, match="out of range"):
            self._build(vector)

    def test_rejects_out_of_range_low(self):
        """Reject trait values below the lower bound."""
        vector = {k: 0.5 for k in TRAIT_KEYS}
        vector["soft"] = -50.0
        with pytest.raises(ValidationError, match="out of range"):
            self._build(vector)

    def test_rejects_infinity(self):
        """Reject non-finite trait values."""
        vector = {k: 0.5 for k in TRAIT_KEYS}
        vector["depth"] = float("inf")
        with pytest.raises(ValidationError, match="must be finite"):
            self._build(vector)

    def test_rejects_nan(self):
        """Reject NaN trait values."""
        vector = {k: 0.5 for k in TRAIT_KEYS}
        vector["depth"] = float("nan")
        with pytest.raises(ValidationError, match="must be finite"):
            self._build(vector)
