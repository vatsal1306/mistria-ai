"""Central configuration registry for the application."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from src import ROOT_DIR, envs
from src.prompts import CHAT_SYSTEM_PROMPT


@dataclass(frozen=True, slots=True)
class App:
    title: str = "Mistria AI"


@dataclass(frozen=True, slots=True)
class Api:
    host: str = "127.0.0.1"
    port: int = 8080
    websocket_path: str = "/ws/chat"
    health_path: str = "/health"
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 900.0
    require_api_key: bool = False
    cors_origins: tuple[str, ...] = (
        "http://127.0.0.1:8501",
        "http://localhost:8501",
    )

    @property
    def http_base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def websocket_url(self) -> str:
        return f"ws://{self.host}:{self.port}{self.websocket_path}"


@dataclass(frozen=True, slots=True)
class Chat:
    companion_name: str = "Aria"
    fixed_pulse_bpm: int = 82
    history_message_limit: int = 24
    system_prompt: str = CHAT_SYSTEM_PROMPT

    @property
    def pulse_context(self) -> str:
        return f"Current pulse placeholder: {self.fixed_pulse_bpm} BPM. Treat it as a fixed demo signal."


@dataclass(frozen=True, slots=True)
class Auth:
    min_password_length: int = 6


@dataclass(frozen=True, slots=True)
class Inference:
    backend: str = "mock"  # ['mock', 'vllm']
    model_name: str = "dphn/Dolphin3.0-Llama3.1-8B"
    tokenizer_name: str | None = None
    temperature: float = 0.9
    top_p: float = 0.95
    max_tokens: int = 350
    max_model_len: int = 4096
    tensor_parallel_size: int = 1
    dtype: str = "auto"
    trust_remote_code: bool = False
    enforce_eager: bool = False
    engine_iteration_timeout_seconds: int = 900
    startup_heartbeat_interval_seconds: float = 10.0
    mock_response_delay_seconds: float = 0.03


@dataclass(frozen=True, slots=True)
class Storage:
    sqlite_path: str = os.path.join(ROOT_DIR, "data", "app.db")


@dataclass(frozen=True, slots=True)
class Secrets:
    api_key: str = field(default_factory=lambda: (envs.get("MISTRIA_API_KEY", "local-dev")).strip())
    hf_token: str = field(default_factory=lambda: (envs.get("HF_TOKEN", "")).strip())
    auth_encryption_key: str = field(default_factory=lambda: (envs.get("MISTRIA_AUTH_ENCRYPTION_KEY", "")).strip())


@dataclass(frozen=True, slots=True)
class Settings:
    root_dir: str = ROOT_DIR
    app: App = field(default_factory=App)
    api: Api = field(default_factory=Api)
    auth: Auth = field(default_factory=Auth)
    chat: Chat = field(default_factory=Chat)
    inference: Inference = field(default_factory=Inference)
    storage: Storage = field(default_factory=Storage)
    secrets: Secrets = field(default_factory=Secrets)


settings = Settings()
