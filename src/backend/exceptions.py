"""Backend service exception hierarchy."""


class ServiceError(RuntimeError):
    """Base class for application-level failures."""


class ConfigurationError(ServiceError):
    """Raised when a runtime cannot be configured correctly."""


class AuthenticationError(ServiceError):
    """Raised when a request is not authorized."""


class InferenceNotReadyError(ServiceError):
    """Raised when the inference backend is not available."""


class InferenceExecutionError(ServiceError):
    """Raised when token generation fails mid-request."""
