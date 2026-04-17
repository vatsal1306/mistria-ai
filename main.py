"""FastAPI entrypoint for chat transport and companion management APIs."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Query, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.auth.exceptions import UserAlreadyExistsError
from src.backend.exceptions import ConfigurationError
from src.backend.runtime import InferenceRuntimeFactory
from src.backend.schemas import HealthResponse, UserCreateRequest, UserResponse
from src.backend.service import ChatService
from src.backend.websocket_handler import WebSocketChatHandler
from src.companion.exceptions import CompanionNotFoundError
from src.companion.schemas import (
    AICompanionCreateRequest,
    AICompanionIdentifierResponse,
    AICompanionResponse,
    UserCompanionResponse,
    UserCompanionUpsertRequest,
)
from src.companion.service import CompanionService
from src.config import settings
from src.storage.database import SQLiteDatabase
from src.storage.repositories import SQLiteAICompanionRepository, SQLiteUserCompanionRepository, SQLiteUserRepository

runtime = InferenceRuntimeFactory.create(settings.chat, settings.inference, settings.secrets)
chat_service = ChatService(settings.chat, runtime)
websocket_handler = WebSocketChatHandler(settings.api, settings.secrets, chat_service)
database = SQLiteDatabase(settings.storage.sqlite_path)
user_repository = SQLiteUserRepository(database)
user_companion_repository = SQLiteUserCompanionRepository(database)
ai_companion_repository = SQLiteAICompanionRepository(database)
companion_service = CompanionService(user_repository, user_companion_repository, ai_companion_repository)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize shared resources at startup and release them on shutdown."""
    database.initialize()
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
    """Translate backend configuration failures into a standard JSON response."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


@app.exception_handler(CompanionNotFoundError)
async def companion_not_found_handler(_: object, exc: CompanionNotFoundError) -> JSONResponse:
    """Translate companion-domain lookup failures into `404` responses."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(UserAlreadyExistsError)
async def user_already_exists_handler(_: object, exc: UserAlreadyExistsError) -> JSONResponse:
    """Translate duplicate-user failures into `409` responses."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


@app.get("/info", response_model=dict[str, str])
async def info() -> dict[str, str]:
    """Return a minimal description of the running API surface."""
    return {
        "app": settings.app.title,
        "backend": runtime.backend_name,
        "websocket": settings.api.websocket_path,
        "health": settings.api.health_path,
    }


@app.get(settings.api.health_path, response_model=HealthResponse)
async def health() -> HealthResponse:
    """Expose runtime readiness and startup diagnostics for probes."""
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


@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreateRequest) -> UserResponse:
    """Create a new user row for frontend-managed identities."""
    if user_repository.find_by_email(payload.email) is not None:
        raise UserAlreadyExistsError("An account with this email already exists.")

    user = user_repository.create_user(
        email=payload.email,
        name=payload.name,
        encrypted_password="",
    )
    return UserResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
    )


@app.websocket(settings.api.websocket_path)
async def chat_socket(websocket: WebSocket) -> None:
    """Handle websocket chat traffic for the active inference backend."""
    await websocket_handler.handle(websocket)


@app.post("/user-companion", response_model=UserCompanionResponse)
def upsert_user_companion(payload: UserCompanionUpsertRequest) -> UserCompanionResponse:
    """Create or replace the saved user-companion preferences for a registered user."""
    return companion_service.upsert_user_companion(payload)


@app.get("/user-companion/{user_mail_id}", response_model=UserCompanionResponse)
def get_user_companion(user_mail_id: str) -> UserCompanionResponse:
    """Fetch the saved user-companion preferences for the given email address."""
    return companion_service.get_user_companion(user_mail_id)


@app.post("/ai-companion", response_model=AICompanionIdentifierResponse, status_code=status.HTTP_201_CREATED)
def create_ai_companion(payload: AICompanionCreateRequest) -> AICompanionIdentifierResponse:
    """Create a new AI companion persona for the given registered user."""
    return companion_service.create_ai_companion(payload)


@app.get("/ai-companion", response_model=list[AICompanionResponse])
def list_ai_companions(user_mail_id: str = Query(..., min_length=3, max_length=320)) -> list[AICompanionResponse]:
    """List every AI companion persona created by the given user."""
    return companion_service.list_ai_companions(user_mail_id)


@app.get("/ai-companion/{ai_companion_id}", response_model=AICompanionResponse)
def get_ai_companion(ai_companion_id: int) -> AICompanionResponse:
    """Fetch one AI companion persona by its internal identifier."""
    return companion_service.get_ai_companion(ai_companion_id)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        # log_level="info",
    )
