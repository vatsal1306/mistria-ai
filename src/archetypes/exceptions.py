"""Archetype-domain exception hierarchy."""


class ArchetypeError(RuntimeError):
    """Base archetype-domain failure."""


class InvalidTraitVectorError(ArchetypeError):
    """Raised when a submitted trait vector fails validation."""


class ZeroVectorError(InvalidTraitVectorError):
    """Raised when the trait vector is all zeros (no direction to score)."""
