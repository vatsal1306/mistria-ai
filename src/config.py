"""Central configuration registry for the application."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from src import ROOT_DIR, envs
from src.prompts import CHAT_SYSTEM_PROMPT


def _get_str(name: str, default: str) -> str:
    """Read a string setting from the environment with a fallback."""
    value = envs.get(name)
    if value is None:
        return default
    return str(value).strip()


def _get_int(name: str, default: int) -> int:
    """Read an integer setting from the environment with a fallback."""
    value = envs.get(name)
    if value is None or str(value).strip() == "":
        return default
    return int(str(value).strip())


def _get_float(name: str, default: float) -> float:
    """Read a floating-point setting from the environment with a fallback."""
    value = envs.get(name)
    if value is None or str(value).strip() == "":
        return default
    return float(str(value).strip())


def _get_bool(name: str, default: bool) -> bool:
    """Read a boolean setting from the environment with strict parsing."""
    value = envs.get(name)
    if value is None:
        return default

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value for {name}: {value!r}")


def _get_tuple(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Read a comma-delimited tuple setting from the environment."""
    value = envs.get(name)
    if value is None:
        return default

    parsed = tuple(item.strip() for item in str(value).split(",") if item.strip())
    return parsed or default


def _get_log_level(name: str, default: str) -> str:
    """Read and validate a standard Python logging level name."""
    value = _get_str(name, default).upper()
    valid_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
    if value not in valid_levels:
        raise ValueError(f"Invalid log level for {name}: {value!r}. Expected one of {sorted(valid_levels)}.")
    return value


@dataclass(frozen=True, slots=True)
class App:
    """Top-level application branding settings."""
    title: str = _get_str("MISTRIA_APP_TITLE", "Mistria AI")


@dataclass(frozen=True, slots=True)
class Api:
    """HTTP and websocket transport settings."""
    host: str = _get_str("MISTRIA_API_HOST", "127.0.0.1")
    port: int = _get_int("MISTRIA_API_PORT", 8080)
    websocket_path: str = _get_str("MISTRIA_API_WEBSOCKET_PATH", "/ws/chat")
    health_path: str = _get_str("MISTRIA_API_HEALTH_PATH", "/health")
    connect_timeout_seconds: float = _get_float("MISTRIA_API_CONNECT_TIMEOUT_SECONDS", 10.0)
    read_timeout_seconds: float = _get_float("MISTRIA_API_READ_TIMEOUT_SECONDS", 900.0)
    require_api_key: bool = _get_bool("MISTRIA_API_REQUIRE_API_KEY", False)
    reload: bool = _get_bool("MISTRIA_API_RELOAD", False)
    cors_origins: tuple[str, ...] = _get_tuple("MISTRIA_API_CORS_ORIGINS",
                                               ("http://127.0.0.1:8501", "http://localhost:8501"))

    @property
    def http_base_url(self) -> str:
        """Return the configured HTTP base URL."""
        return f"http://{self.host}:{self.port}"

    @property
    def websocket_url(self) -> str:
        """Return the configured websocket endpoint URL."""
        return f"ws://{self.host}:{self.port}{self.websocket_path}"


@dataclass(frozen=True, slots=True)
class Chat:
    """Chat-session defaults and prompt context settings."""
    companion_name: str = _get_str("MISTRIA_CHAT_COMPANION_NAME", "Aria")
    fixed_pulse_bpm: int = _get_int("MISTRIA_CHAT_FIXED_PULSE_BPM", 82)
    history_message_limit: int = _get_int("MISTRIA_CHAT_HISTORY_MESSAGE_LIMIT", 24)
    system_prompt: str = CHAT_SYSTEM_PROMPT

    @property
    def pulse_context(self) -> str:
        """Return the fixed pulse context appended to the active system prompt."""
        return f"Current pulse placeholder: {self.fixed_pulse_bpm} BPM. Treat it as a fixed demo signal."


@dataclass(frozen=True, slots=True)
class Auth:
    """Authentication policy settings."""
    min_password_length: int = _get_int("MISTRIA_AUTH_MIN_PASSWORD_LENGTH", 6)


@dataclass(frozen=True, slots=True)
class Inference:
    """Inference backend, model, and generation settings."""
    backend: str = _get_str("MISTRIA_INFERENCE_BACKEND", "mock")  # ['mock', 'vllm', 'ollama']
    model_name: str = _get_str("MISTRIA_INFERENCE_MODEL_NAME", "dphn/Dolphin3.0-Llama3.1-8B")  # ['dolphin-llama3']
    model_revision: str | None = _get_str("MISTRIA_INFERENCE_MODEL_REVISION", "") or None
    tokenizer_name: str | None = _get_str("MISTRIA_INFERENCE_TOKENIZER_NAME", "") or None
    tokenizer_revision: str | None = _get_str("MISTRIA_INFERENCE_TOKENIZER_REVISION", "") or None
    temperature: float = _get_float("MISTRIA_INFERENCE_TEMPERATURE", 0.9)
    top_p: float = _get_float("MISTRIA_INFERENCE_TOP_P", 0.95)
    max_tokens: int = _get_int("MISTRIA_INFERENCE_MAX_TOKENS", 350)
    max_model_len: int = _get_int("MISTRIA_INFERENCE_MAX_MODEL_LEN", 4096)
    tensor_parallel_size: int = _get_int("MISTRIA_INFERENCE_TENSOR_PARALLEL_SIZE", 1)
    dtype: str = _get_str("MISTRIA_INFERENCE_DTYPE", "auto")
    trust_remote_code: bool = _get_bool("MISTRIA_INFERENCE_TRUST_REMOTE_CODE", False)
    enforce_eager: bool = _get_bool("MISTRIA_INFERENCE_ENFORCE_EAGER", False)
    engine_iteration_timeout_seconds: int = _get_int("MISTRIA_INFERENCE_ENGINE_TIMEOUT_SECONDS", 900)
    startup_heartbeat_interval_seconds: float = _get_float("MISTRIA_INFERENCE_STARTUP_HEARTBEAT_SECONDS", 10.0)
    mock_response_delay_seconds: float = _get_float("MISTRIA_INFERENCE_MOCK_RESPONSE_DELAY_SECONDS", 0.03)


@dataclass(frozen=True, slots=True)
class Storage:
    """Persistent storage settings."""
    sqlite_path: str = _get_str("MISTRIA_STORAGE_SQLITE_PATH", os.path.join(ROOT_DIR, "data", "db", "app.db"))


@dataclass(frozen=True, slots=True)
class AppLogging:
    """Application logging settings."""
    level: str = _get_log_level("MISTRIA_LOG_LEVEL", "INFO")
    directory: str = os.path.join(ROOT_DIR, "Logs")
    filename: str = "app.log"
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5

    @property
    def file_path(self) -> str:
        """Return the absolute path to the rotating application log file."""
        return os.path.join(self.directory, self.filename)


@dataclass(frozen=True, slots=True)
class Secrets:
    """Secret configuration loaded from the environment."""
    api_key: str = field(default_factory=lambda: _get_str("MISTRIA_API_KEY", "local-dev-api-key"))
    hf_token: str = field(default_factory=lambda: _get_str("HF_TOKEN", ""))
    auth_encryption_key: str = field(default_factory=lambda: _get_str("MISTRIA_AUTH_ENCRYPTION_KEY", ""))


@dataclass(frozen=True, slots=True)
class Settings:
    """Aggregated application settings object."""
    root_dir: str = ROOT_DIR
    app: App = field(default_factory=App)
    api: Api = field(default_factory=Api)
    auth: Auth = field(default_factory=Auth)
    chat: Chat = field(default_factory=Chat)
    inference: Inference = field(default_factory=Inference)
    logging: AppLogging = field(default_factory=AppLogging)
    storage: Storage = field(default_factory=Storage)
    secrets: Secrets = field(default_factory=Secrets)


settings = Settings()
