"""Storage-domain exception hierarchy."""


class StorageError(RuntimeError):
    """Base class for persistence failures."""


class DatabaseInitializationError(StorageError):
    """Raised when the SQLite schema cannot be initialized."""


class RepositoryError(StorageError):
    """Raised when a repository operation fails."""
