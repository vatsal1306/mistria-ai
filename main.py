"""
FastAPI only: app, models, routes, logging, server.

Business logic lives under ``src/``.
"""

from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from src.chat import run_chat_turn

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

# --- Request / response models ---


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    resume_pulse: bool = Field(
        True,
        description="After >30 min away: keep stored pulse if True, else reset to baseline.",
    )


class ChatResponse(BaseModel):
    reply: str
    pulse: int = Field(..., ge=0, le=100)
    latency_seconds: float = Field(..., ge=0)


class HealthResponse(BaseModel):
    status: str = "ok"


# --- Application ---

app = FastAPI(title="Mistria API", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    result = run_chat_turn(body.user_id, body.message, body.resume_pulse)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown user_id: {body.user_id}",
        )
    return ChatResponse(
        reply=result.reply,
        pulse=result.pulse,
        latency_seconds=result.latency_seconds,
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
