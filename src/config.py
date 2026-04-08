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
    port: int = 8000
    websocket_path: str = "/ws/chat"
    health_path: str = "/health"
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 900.0
    require_api_key: bool = False
    cors_origins: tuple[str, ...] = (
        "http://127.0.0.1:8501",
        "http://localhost:8501",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    )

    @property
    def http_base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def websocket_url(self) -> str:
        return f"ws://{self.host}:{self.port}{self.websocket_path}"


@dataclass(frozen=True, slots=True)
class Chat:
    companion_name: str = "Mistria"
    default_companion_id: str = "mistria"
    history_message_limit: int = 24
    system_prompt: str = CHAT_SYSTEM_PROMPT


@dataclass(frozen=True, slots=True)
class Engagement:
    """Engagement scoring aligned with the Escalation & Engagement Spec."""

    max_score: int = 100
    default_score: int = 0
    per_message_score: int = 1
    session_bonus_threshold: int = 5
    session_bonus_score: int = 2
    emotional_score: int = 3
    voice_score: int = 5
    decay_12h: int = 5
    decay_24h: int = 15


@dataclass(frozen=True, slots=True)
class Inference:
    backend: str = "ollama"
    model_name: str = "dolphin-llama3"
    temperature: float = 0.88
    top_p: float = 0.9
    max_tokens: int = 150
    ollama_host: str = field(
        default_factory=lambda: envs.get("OLLAMA_HOST", "http://localhost:11434").strip(),
    )


@dataclass(frozen=True, slots=True)
class Storage:
    db_path: str = os.path.join(ROOT_DIR, "database.json")
    companions_path: str = os.path.join(ROOT_DIR, "companions.json")


@dataclass(frozen=True, slots=True)
class Secrets:
    api_key: str = field(
        default_factory=lambda: envs.get("MISTRIA_API_KEY", "local-dev").strip(),
    )


@dataclass(frozen=True, slots=True)
class Settings:
    root_dir: str = ROOT_DIR
    app: App = field(default_factory=App)
    api: Api = field(default_factory=Api)
    chat: Chat = field(default_factory=Chat)
    engagement: Engagement = field(default_factory=Engagement)
    inference: Inference = field(default_factory=Inference)
    storage: Storage = field(default_factory=Storage)
    secrets: Secrets = field(default_factory=Secrets)


settings = Settings()
