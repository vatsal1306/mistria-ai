"""
FastAPI only: app, models, routes, logging, server.

Business logic lives under ``src/``.
"""

from __future__ import annotations

import logging

from pathlib import Path

import json

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

STATIC_DIR = Path(__file__).resolve().parent / "static"

from src.chat import run_chat_turn, stream_chat_turn
from src.sessions import SESSIONS
from src.persistence import load_user_data, save_user_session
from src.config import PULSE_DEFAULT

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


@app.get("/")
def chat_ui():
    html = (STATIC_DIR / "chat.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


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


class ResetRequest(BaseModel):
    user_id: str = Field(..., min_length=1)


class ResetResponse(BaseModel):
    pulse: int
    message: str


@app.post("/reset", response_model=ResetResponse)
def reset_session(body: ResetRequest):
    user_info = load_user_data(body.user_id)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown user_id: {body.user_id}",
        )
    SESSIONS.reset(body.user_id, initial_pulse=PULSE_DEFAULT)
    save_user_session(body.user_id, PULSE_DEFAULT)
    return ResetResponse(pulse=PULSE_DEFAULT, message="Session reset")


class SetPulseRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    pulse: int = Field(..., ge=0, le=100)


@app.post("/set-pulse", response_model=ResetResponse)
def set_pulse(body: SetPulseRequest):
    user_info = load_user_data(body.user_id)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown user_id: {body.user_id}",
        )
    SESSIONS.reset(body.user_id, initial_pulse=body.pulse)
    save_user_session(body.user_id, body.pulse)
    return ResetResponse(pulse=body.pulse, message=f"Pulse set to {body.pulse}")


@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "detail": "Invalid JSON"})
                continue

            user_id = data.get("user_id", "")
            message = data.get("message", "")
            resume_pulse = data.get("resume_pulse", True)

            if not user_id or not message:
                await ws.send_json({"type": "error", "detail": "user_id and message required"})
                continue

            for event_type, payload in stream_chat_turn(user_id, message, resume_pulse):
                await ws.send_json({"type": event_type, **payload})
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
