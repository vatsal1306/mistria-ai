"""Websocket request handling for chat streaming."""

from __future__ import annotations

from fastapi import WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from src.Logging import get_logger
from src.backend.exceptions import AuthenticationError, ServiceError
from src.backend.schemas import ChatSocketEvent, ChatSocketRequest
from src.backend.service import ChatService
from src.config import Api, Secrets
from src.storage.repositories import (
    SQLiteAICompanionRepository,
    SQLiteUserCompanionRepository,
    UserRepository,
)
import asyncio
from src.storage.service import ChatHistoryService
from src.storage.conversation_store import ConversationSnapshot

logger = get_logger(__name__)


class WebSocketChatHandler:
    """One handler instance shared across websocket connections."""

    def __init__(self, api_config: Api, secrets_config: Secrets, service: ChatService,
                 history_service: ChatHistoryService,
                 user_repo: UserRepository, user_companion_repo: SQLiteUserCompanionRepository,
                 ai_companion_repo: SQLiteAICompanionRepository):
        self.api_config = api_config
        self.secrets_config = secrets_config
        self.service = service
        self.history_service = history_service
        self.user_repo = user_repo
        self.user_companion_repo = user_companion_repo
        self.ai_companion_repo = ai_companion_repo
        self._history_tasks: dict[str, asyncio.Task[ConversationSnapshot]] = {}

    async def handle(self, websocket: WebSocket) -> None:
        """Own the full lifecycle of a websocket chat session."""
        await websocket.accept()
        client_label = self._client_label(websocket)
        logger.info("Accepted websocket connection client=%s", client_label)

        try:
            self._authorize(websocket)
            
            # Extract User and Companion IDs from query parameters for pre-fetching
            user_id = websocket.query_params.get("user_id")
            ai_companion_id_str = websocket.query_params.get("ai_companion_id")
            
            history_task = None
            if user_id and ai_companion_id_str:
                try:
                    ai_companion_id = int(ai_companion_id_str)
                    # Pre-validate user/companion existence before starting pre-fetch
                    user = self.user_repo.find_by_email(user_id)
                    if user:
                        logger.info("Initiating history pre-fetch for client=%s user_id=%s", client_label, user_id)
                        history_task = asyncio.create_task(
                            asyncio.to_thread(self.history_service.load_latest, user.id, ai_companion_id)
                        )
                except (ValueError, TypeError):
                    logger.warning("Invalid IDs in query parameters for client=%s", client_label)

            await self._send_event(
                websocket,
                ChatSocketEvent(type="ready", backend=self.service.runtime.backend_name),
            )
            logger.debug(
                "Sent websocket ready event client=%s backend=%s",
                client_label,
                self.service.runtime.backend_name,
            )

            while True:
                raw_payload = await websocket.receive_text()
                logger.debug("Received websocket request payload client=%s payload_bytes=%s", client_label, len(raw_payload))
                await self._handle_request_message(websocket, raw_payload, history_task)
                # After the first message, we don't need the pre-fetch task anymore
                history_task = None 
        except AuthenticationError as exc:
            logger.warning("Rejected websocket connection client=%s reason=%s", client_label, exc)
            await self._send_event(
                websocket,
                ChatSocketEvent(type="error", backend=self.service.runtime.backend_name, detail=str(exc)),
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        except WebSocketDisconnect:
            logger.info("Websocket client disconnected client=%s", client_label)
        except Exception:
            logger.exception("Unhandled websocket session failure client=%s", client_label)
            await self._safe_close(websocket)
        finally:
            if history_task and not history_task.done():
                history_task.cancel()

    def _authorize(self, websocket: WebSocket) -> None:
        if not self.api_config.require_api_key:
            logger.debug("Websocket API key authentication disabled")
            return

        provided_key = websocket.query_params.get("api_key", "").strip()
        if provided_key != self.secrets_config.api_key:
            raise AuthenticationError("Missing or invalid websocket API key.")
        logger.debug("Websocket API key authentication succeeded client=%s", self._client_label(websocket))

    async def _handle_request_message(
        self, 
        websocket: WebSocket, 
        raw_payload: str, 
        history_task: asyncio.Task[ConversationSnapshot] | None = None
    ) -> None:
        client_label = self._client_label(websocket)
        try:
            request = ChatSocketRequest.model_validate_json(raw_payload)
            logger.info(
                "Validated websocket chat request client=%s user_id=%s ai_companion_id=%s",
                client_label,
                request.user_id,
                request.ai_companion_id,
            )

            user = self.user_repo.find_by_email(request.user_id)
            if not user:
                logger.warning("Rejected websocket chat request for unknown user client=%s user_id=%s", client_label, request.user_id)
                raise ServiceError(f"User not found in DB: {request.user_id}")

            user_companion = self.user_companion_repo.find_by_user_id(user.id)
            if not user_companion:
                logger.warning(
                    "Rejected websocket chat request with missing user companion client=%s user_id=%s internal_user_id=%s",
                    client_label,
                    request.user_id,
                    user.id,
                )
                raise ServiceError("User companion preferences are missing in DB.")

            ai_companion = self.ai_companion_repo.find_by_id(request.ai_companion_id)
            if not ai_companion or ai_companion.user_id != user.id:
                logger.warning(
                    "Rejected websocket chat request with invalid AI companion client=%s user_id=%s ai_companion_id=%s",
                    client_label,
                    request.user_id,
                    request.ai_companion_id,
                )
                raise ServiceError("AI companion is missing, invalid, or not owned by the user.")

            # Resolve pre-fetched history if available
            snapshot = None
            if history_task:
                try:
                    snapshot = await history_task
                    logger.debug("Resolved pre-fetched history snapshot for client=%s", client_label)
                except Exception:
                    logger.exception("Pre-fetch history task failed for client=%s", client_label)

            async for token in self.service.stream_response(
                    request,
                    user.id,
                    user.name,
                    user_companion,
                    ai_companion,
                    snapshot,
            ):
                await self._send_event(
                    websocket,
                    ChatSocketEvent(type="delta", backend=self.service.runtime.backend_name, delta=token),
                )

            await self._send_event(
                websocket,
                ChatSocketEvent(
                    type="done",
                    backend=self.service.runtime.backend_name,
                ),
            )
            logger.info(
                "Completed websocket chat request client=%s user_id=%s ai_companion_id=%s",
                client_label,
                request.user_id,
                request.ai_companion_id,
            )
        except ValidationError as exc:
            logger.warning(
                "Rejected invalid websocket payload client=%s validation_errors=%s",
                client_label,
                len(exc.errors()),
            )
            await self._send_event(
                websocket,
                ChatSocketEvent(
                    type="error",
                    backend=self.service.runtime.backend_name,
                    detail=str(exc.errors(include_url=False)),
                ),
            )
        except ServiceError as exc:
            logger.warning("Websocket request failed client=%s detail=%s", client_label, exc)
            await self._send_event(
                websocket,
                ChatSocketEvent(type="error", backend=self.service.runtime.backend_name, detail=str(exc)),
            )
        except Exception:
            logger.exception("Unhandled request failure on websocket client=%s", client_label)
            await self._send_event(
                websocket,
                ChatSocketEvent(
                    type="error",
                    backend=self.service.runtime.backend_name,
                    detail=f"Unhandled server error: {type(exc).__name__}",
                ),
            )

    @staticmethod
    async def _send_event(websocket: WebSocket, event: ChatSocketEvent) -> None:
        await websocket.send_text(event.model_dump_json())

    @staticmethod
    async def _safe_close(websocket: WebSocket) -> None:
        try:
            await websocket.close()
        except RuntimeError:
            pass

    @staticmethod
    def _client_label(websocket: WebSocket) -> str:
        client = websocket.client
        if client is None:
            return "unknown"
        return f"{client.host}:{client.port}"
