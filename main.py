"""FastAPI entrypoint for the chat backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.backend.exceptions import ConfigurationError
from src.backend.runtime import InferenceRuntimeFactory
from src.backend.schemas import HealthResponse
from src.backend.service import ChatService
from src.backend.websocket_handler import WebSocketChatHandler
from src.config import settings

runtime = InferenceRuntimeFactory.create(settings.chat, settings.inference, settings.secrets)
chat_service = ChatService(settings.chat, runtime)
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


@app.get("/", response_model=dict[str, str])
async def root() -> dict[str, str]:
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
        startup_error=runtime.startup_error,
    )


@app.websocket(settings.api.websocket_path)
async def chat_socket(websocket: WebSocket) -> None:
    await websocket_handler.handle(websocket)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.api.host,
        port=settings.api.port,
        reload=False,
        log_level="info",
    )
