"""FastAPI entrypoint for chat transport and companion management APIs."""

from contextlib import asynccontextmanager
from typing import Literal


import uvicorn
from fastapi import FastAPI, Query, WebSocket, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.Logging import get_logger
from src.auth.exceptions import UserAlreadyExistsError
from src.backend.exceptions import ConfigurationError
from src.backend.runtime import InferenceRuntimeFactory
from src.backend.schemas import HealthResponse, UserCreateRequest, UserResponse
from src.backend.service import ChatService
from src.backend.websocket_handler import WebSocketChatHandler
from src.companion.exceptions import CompanionNotFoundError
from src.companion.schemas import (
    AICompanionCreateRequest,
    AICompanionCreateResponse,
    AICompanionGenerateRequest,
    AICompanionGenerateResponse,
    AICompanionResponse,
)
from src.companion.service import CompanionService
from src.config import settings
from src.engagement.worker import EngagementScoringWorker
from src.memory.background import MemoryExtractionWorker
from src.memory.embeddings import LocalEmbeddingProvider
from src.memory.events import LoggingMemoryEventSink
from src.memory.extraction import MemoryExtractionService
from src.memory.schemas import (
    DebugMemoryRetrieveRequest,
    DebugMemoryRetrieveResponse,
    DebugMemoryListResponse,
)
from src.memory.service import MemoryService
from src.memory.vector_store import QdrantVectorStore
from src.storage.database import SQLiteDatabase
from src.archetypes import (
    ArchetypeResultResponse,
    InvalidTraitVectorError,
    SlowBurnScoreRequest,
    score_trait_vector,
)
from src.storage.archetype_repository import SQLiteArchetypeResultRepository
from src.storage.memory_repository import SQLiteMemoryRepository
from src.storage.repositories import (
    SQLiteAICompanionRepository,
    SQLiteConversationRepository,
    SQLiteUserRepository,
)
from src.storage.conversation_store import SQLiteConversationStore
from src.storage.service import ChatHistoryService

logger = get_logger(__name__)

database = SQLiteDatabase(settings.storage.sqlite_path)
user_repository = SQLiteUserRepository(database)
ai_companion_repository = SQLiteAICompanionRepository(database)
conversation_repository = SQLiteConversationRepository(database)
archetype_repository = SQLiteArchetypeResultRepository(database)
conversation_store = SQLiteConversationStore(conversation_repository)
chat_history_service = ChatHistoryService(conversation_store)

runtime = InferenceRuntimeFactory.create(settings.chat, settings.inference, settings.secrets)
companion_service = CompanionService(user_repository, ai_companion_repository, runtime)

# Initialize memory sub-system if enabled
memory_service = None
extraction_worker = None
memory_vector_store = None
memory_embedding_provider = None
if settings.memory.enabled:
    logger.info("Memory system is enabled. Initializing components.")
    memory_repository = SQLiteMemoryRepository(database)
    memory_vector_store = QdrantVectorStore(
        url=settings.memory.qdrant_url,
        path=settings.memory.qdrant_path,
        collection_name=settings.memory.qdrant_collection,
        enabled=settings.memory.enabled,
    )
    memory_embedding_provider = LocalEmbeddingProvider(settings.memory.embedding_model_name)
    memory_service = MemoryService(
        settings.memory,
        memory_repository,
        memory_vector_store,
        memory_embedding_provider,
        event_sink=LoggingMemoryEventSink(),
    )
    extraction_service = MemoryExtractionService(runtime)
    extraction_worker = MemoryExtractionWorker(extraction_service, memory_service)
else:
    logger.info("Memory system is disabled via configuration.")

engagement_worker = None
if settings.engagement.external_backend_webhook_url:
    logger.info("Engagement scoring is enabled.")
    engagement_worker = EngagementScoringWorker(runtime, chat_history_service, settings.engagement)
else:
    logger.info("Engagement scoring is disabled (webhook URL not configured).")

chat_service = ChatService(
    settings.chat, runtime, chat_history_service, memory_service, extraction_worker, engagement_worker
)

websocket_handler = WebSocketChatHandler(
    settings.api,
    settings.secrets,
    chat_service,
    chat_history_service,
    user_repository,
    ai_companion_repository,
    archetype_repository,
)

logger.debug(
    "Initialized application services backend=%s model=%s sqlite_path=%s websocket_path=%s log_level=%s",
    runtime.backend_name,
    runtime.model_name,
    settings.storage.sqlite_path,
    settings.api.websocket_path,
    settings.logging.level,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize shared resources at startup and release them on shutdown."""
    logger.info(
        "Application startup initiated backend=%s model=%s host=%s port=%s log_level=%s",
        runtime.backend_name,
        runtime.model_name,
        settings.api.host,
        settings.api.port,
        settings.logging.level,
    )
    database.initialize()
    await runtime.startup()
    
    try:
        if settings.memory.enabled and memory_vector_store and memory_embedding_provider:
            dimension = memory_embedding_provider.get_dimension()
            memory_vector_store.bootstrap_collection(dimension)

        logger.info(
            "Application startup complete backend=%s ready=%s startup_stage=%s",
            runtime.backend_name,
            runtime.is_ready,
            runtime.startup_stage,
        )
        yield
    finally:
        logger.info("Application shutdown initiated backend=%s", runtime.backend_name)
        if extraction_worker:
            await extraction_worker.shutdown()
        if engagement_worker:
            await engagement_worker.shutdown()
        await runtime.shutdown()
        logger.info("Application shutdown complete backend=%s", runtime.backend_name)


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
    logger.error("Returning configuration error response detail=%s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


@app.exception_handler(CompanionNotFoundError)
async def companion_not_found_handler(_: object, exc: CompanionNotFoundError) -> JSONResponse:
    """Translate companion-domain lookup failures into `404` responses."""
    logger.warning("Returning companion not found response detail=%s", exc)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(UserAlreadyExistsError)
async def user_already_exists_handler(_: object, exc: UserAlreadyExistsError) -> JSONResponse:
    """Translate duplicate-user failures into `409` responses."""
    logger.warning("Returning duplicate user response detail=%s", exc)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


@app.exception_handler(InvalidTraitVectorError)
async def invalid_trait_vector_handler(_: object, exc: InvalidTraitVectorError) -> JSONResponse:
    """Translate archetype trait validation failures into `422` responses."""
    logger.warning("Returning invalid trait vector response detail=%s", exc)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
        logger.warning("Rejected duplicate user creation attempt email=%s", payload.email)
        raise UserAlreadyExistsError("An account with this email already exists.")

    user = user_repository.create_user(
        email=payload.email,
        name=payload.name,
        encrypted_password=None,
    )
    logger.info("Created user via API user_id=%s email=%s", user.id, user.email)
    return UserResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
    )


@app.post("/archetype/slow-burn/score", response_model=ArchetypeResultResponse)
def score_slow_burn_archetype(payload: SlowBurnScoreRequest) -> ArchetypeResultResponse:
    """Score a Slow Burn archetype quiz and persist the result."""
    user = user_repository.find_by_email(payload.user_mail_id)
    if not user:
        raise CompanionNotFoundError("User not found.")

    scoring_result = score_trait_vector(payload.trait_scores)

    record = archetype_repository.create_from_scoring(
        user_id=user.id,
        onboarding_pathway="slow_burn",
        scoring_result=scoring_result,
    )

    logger.info("Created archetype result user_id=%s primary_archetype=%s", user.id, record.primary_archetype)

    return ArchetypeResultResponse(
        user_mail_id=user.email,
        onboarding_pathway=record.onboarding_pathway,
        primary_archetype=record.primary_archetype,
        primary_similarity=record.primary_similarity,
        secondary_archetype=record.secondary_archetype,
        secondary_similarity=record.secondary_similarity,
        blend_active=record.blend_active,
        trait_scores=scoring_result.trait_scores,
        created_at=record.created_at,
    )


@app.get("/archetype/latest/{user_mail_id}", response_model=ArchetypeResultResponse)
def get_latest_archetype_result(user_mail_id: str) -> ArchetypeResultResponse:
    """Fetch the most recent Slow Burn archetype result for a user."""
    user = user_repository.find_by_email(user_mail_id)
    if not user:
        raise CompanionNotFoundError("User not found.")

    record = archetype_repository.find_latest_by_user_id(user.id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No archetype result found for user.",
        )

    return ArchetypeResultResponse(
        user_mail_id=user.email,
        onboarding_pathway=record.onboarding_pathway,
        primary_archetype=record.primary_archetype,
        primary_similarity=record.primary_similarity,
        secondary_archetype=record.secondary_archetype,
        secondary_similarity=record.secondary_similarity,
        blend_active=record.blend_active,
        trait_scores=archetype_repository.parse_trait_scores(record),
        created_at=record.created_at,
    )


@app.websocket(settings.api.websocket_path)
async def chat_socket(websocket: WebSocket) -> None:
    """Handle websocket chat traffic for the active inference backend."""
    await websocket_handler.handle(websocket)


@app.post("/ai-companion", response_model=AICompanionCreateResponse)
async def create_ai_companion(payload: AICompanionCreateRequest) -> AICompanionCreateResponse:
    """Persist a new AI companion persona."""
    logger.info("Creating AI companion via API email=%s title=%s", payload.user_mail_id, payload.title or "auto")
    response = await companion_service.create_ai_companion(payload)
    logger.info("Created AI companion via API email=%s ai_companion_id=%s", payload.user_mail_id, response.ai_companion_id)
    return response


@app.post("/ai-companion/generate", response_model=AICompanionGenerateResponse)
async def generate_ai_companion(payload: AICompanionGenerateRequest) -> AICompanionGenerateResponse:
    """Generate AI companion metadata directly from the LLM without saving it."""
    logger.info(
        "Generating AI companion via API visual_style=%s personality=%s intention=%s",
        payload.visual_style,
        payload.companion_personality,
        payload.intention,
    )
    return await companion_service.generate_ai_companion(payload)


@app.get("/ai-companion", response_model=list[AICompanionResponse])
def list_ai_companions(user_mail_id: str = Query(..., min_length=3, max_length=320)) -> list[AICompanionResponse]:
    """List every AI companion persona created by the given user."""
    logger.debug("Listing AI companions via API email=%s", user_mail_id)
    return companion_service.list_ai_companions(user_mail_id)


@app.get("/ai-companion/{ai_companion_id}", response_model=AICompanionResponse)
def get_ai_companion(ai_companion_id: int) -> AICompanionResponse:
    """Fetch one AI companion persona by its internal identifier."""
    logger.debug("Fetching AI companion via API ai_companion_id=%s", ai_companion_id)
    return companion_service.get_ai_companion(ai_companion_id)


@app.post("/debug/memory/retrieve", response_model=DebugMemoryRetrieveResponse)
async def debug_memory_retrieve(payload: DebugMemoryRetrieveRequest) -> DebugMemoryRetrieveResponse:
    """Internal debug endpoint for memory retrieval."""
    if not settings.memory.debug_endpoint_enabled or not memory_service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint disabled or memory system not configured"
        )

    user = user_repository.find_by_email(payload.user_mail_id)
    if not user:
        raise CompanionNotFoundError("User not found.")

    companion = ai_companion_repository.find_by_id(payload.ai_companion_id)
    if not companion or companion.user_id != user.id:
        raise CompanionNotFoundError(f"Companion {payload.ai_companion_id} not found or not owned by user.")

    memories = await memory_service.retrieve_memories(
        user_id=user.id,
        ai_companion_id=companion.id,
        query=payload.user_message,
    )

    return DebugMemoryRetrieveResponse(
        user_mail_id=payload.user_mail_id,
        ai_companion_id=payload.ai_companion_id,
        memories=memories,
    )


@app.get("/debug/memory/{user_mail_id}/{ai_companion_id}", response_model=DebugMemoryListResponse)
async def debug_memory_list(
    user_mail_id: str,
    ai_companion_id: int,
    status_filter: Literal["active", "superseded", "archived", "all"] = Query("active", alias="status"),
    memory_type: Literal["fact", "preference", "pattern", "emotional"] | None = Query(None, alias="memory_type"),
    limit: int = Query(50, ge=1, le=100),
) -> DebugMemoryListResponse:
    """Internal debug endpoint to list stored memories for a specific user and companion."""
    if not settings.memory.debug_endpoint_enabled or not memory_service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint disabled or memory system not configured"
        )

    user = user_repository.find_by_email(user_mail_id)
    if not user:
        raise CompanionNotFoundError("User not found.")

    companion = ai_companion_repository.find_by_id(ai_companion_id)
    if not companion or companion.user_id != user.id:
        raise CompanionNotFoundError(f"Companion {ai_companion_id} not found or not owned by user.")

    memories = await memory_service.list_memories(
        user_id=user.id,
        ai_companion_id=companion.id,
        status=status_filter,
        memory_type=memory_type,
        limit=limit,
    )

    return DebugMemoryListResponse(
        user_mail_id=user_mail_id,
        ai_companion_id=ai_companion_id,
        memories=memories,
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        # log_level="info",
    )
