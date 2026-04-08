"""Pydantic schemas for backend transport and health responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChatMessage(BaseModel):
    """Normalized chat message payload."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatSocketRequest(BaseModel):
    """Incoming websocket request for a streamed chat completion."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: Literal["chat"] = "chat"
    request_id: str | None = Field(default=None, max_length=128)
    user_id: str | None = Field(default=None, max_length=128)
    system_prompt: str | None = Field(default=None, max_length=20_000)
    messages: list[ChatMessage] = Field(min_length=1, max_length=200)
    resume_pulse: bool = True

    @model_validator(mode="after")
    def validate_message_sequence(self) -> "ChatSocketRequest":
        if self.messages[-1].role != "user":
            raise ValueError("The last message in the request must be from the user.")
        return self


class ChatSocketEvent(BaseModel):
    """Outgoing websocket event frame."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["ready", "start", "delta", "done", "error"]
    request_id: str | None = None
    backend: str | None = None
    model_name: str | None = None
    delta: str | None = None
    text: str | None = None
    detail: str | None = None
    connection: int | None = None
    latency_seconds: float | None = None


class HealthResponse(BaseModel):
    """Runtime health payload for HTTP probes."""

    status: Literal["ok", "degraded"]
    app: str
    backend: str
    model_name: str
    engine_ready: bool
    websocket_path: str
    startup_stage: str
    startup_detail: str | None = None
    startup_elapsed_seconds: float | None = None
    startup_error: str | None = None


class ResetRequest(BaseModel):
    """Request to reset a user's session."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: str = Field(..., min_length=1)


class SetEngagementRequest(BaseModel):
    """Request to manually set a user's engagement score (dev/admin only)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: str = Field(..., min_length=1)
    score: int = Field(..., ge=0, le=100)


class EngagementResponse(BaseModel):
    """Response for engagement/reset operations."""

    connection: int
    message: str
