"""FastAPI entrypoint for the chat backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from src.backend.exceptions import ConfigurationError
from src.backend.runtime import InferenceRuntimeFactory
from src.backend.schemas import (
    ChatRestRequest,
    ChatRestResponse,
    EngagementResponse,
    HealthResponse,
    ResetRequest,
    SetEngagementRequest,
)
from src.backend.service import ChatService
from src.backend.websocket_handler import WebSocketChatHandler
from src.config import settings
from src.persistence import load_user_data

STATIC_DIR = Path(__file__).resolve().parent / "static"

runtime = InferenceRuntimeFactory.create(settings.chat, settings.inference, settings.secrets)
chat_service = ChatService(settings.chat, runtime, settings.engagement)
websocket_handler = WebSocketChatHandler(settings.api, settings.secrets, chat_service)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await runtime.startup()
    yield
    await runtime.shutdown()


app = FastAPI(title=settings.app.title, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.api.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ConfigurationError)
async def configuration_error_handler(_: object, exc: ConfigurationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


@app.get("/")
async def root() -> HTMLResponse:
    html_path = STATIC_DIR / "chat.html"
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        return HTMLResponse(content=html)
    return HTMLResponse(
        content="<h1>Mistria AI</h1><p>Chat UI not found. Use /health or /ws/chat.</p>",
    )


@app.get("/info", response_model=dict[str, str])
async def info() -> dict[str, str]:
    return {
        "app": settings.app.title,
        "backend": runtime.backend_name,
        "websocket": settings.api.websocket_path,
        "health": settings.api.health_path,
    }


@app.get(settings.api.health_path, response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok" if runtime.is_ready else "degraded",
        app=settings.app.title,
        backend=runtime.backend_name,
        model_name=runtime.model_name,
        engine_ready=runtime.is_ready,
        websocket_path=settings.api.websocket_path,
        startup_stage=runtime.startup_stage,
        startup_detail=runtime.startup_detail,
        startup_elapsed_seconds=runtime.startup_elapsed_seconds,
        startup_error=runtime.startup_error,
    )


@app.post("/chat", response_model=ChatRestResponse)
async def chat(body: ChatRestRequest) -> ChatRestResponse:
    result = await chat_service.run_chat_turn(body.user_id, body.message)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown user_id: {body.user_id}",
        )
    return ChatRestResponse(
        reply=result.reply,
        connection=result.connection,
        latency_seconds=result.latency_seconds,
    )


@app.post("/reset", response_model=EngagementResponse)
async def reset_session(body: ResetRequest) -> EngagementResponse:
    user_info = load_user_data(body.user_id)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown user_id: {body.user_id}",
        )
    connection = chat_service.reset_session(body.user_id)
    return EngagementResponse(connection=connection, message="Session reset")


@app.post("/set-engagement", response_model=EngagementResponse)
async def set_engagement(body: SetEngagementRequest) -> EngagementResponse:
    user_info = load_user_data(body.user_id)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown user_id: {body.user_id}",
        )
    connection = chat_service.set_engagement(body.user_id, body.score)
    return EngagementResponse(
        connection=connection,
        message=f"Engagement set to {body.score}",
    )


@app.websocket(settings.api.websocket_path)
async def chat_socket(websocket: WebSocket) -> None:
    await websocket_handler.handle(websocket)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=True,
    )
