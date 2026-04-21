"""Websocket request handling for chat streaming."""

from __future__ import annotations

from fastapi import WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from src.Logging import logger
from src.backend.exceptions import AuthenticationError, ServiceError
from src.backend.schemas import ChatSocketEvent, ChatSocketRequest
from src.backend.service import ChatService
from src.config import Api, Secrets
from src.storage.repositories import (
    SQLiteAICompanionRepository,
    SQLiteUserCompanionRepository,
    UserRepository,
)


class WebSocketChatHandler:
    """One handler instance shared across websocket connections."""

    def __init__(self, api_config: Api, secrets_config: Secrets, service: ChatService,
                 user_repo: UserRepository, user_companion_repo: SQLiteUserCompanionRepository,
                 ai_companion_repo: SQLiteAICompanionRepository):
        self.api_config = api_config
        self.secrets_config = secrets_config
        self.service = service
        self.user_repo = user_repo
        self.user_companion_repo = user_companion_repo
        self.ai_companion_repo = ai_companion_repo

    async def handle(self, websocket: WebSocket) -> None:
        """Own the full lifecycle of a websocket chat session."""
        await websocket.accept()

        try:
            self._authorize(websocket)
            await self._send_event(websocket,
                                   ChatSocketEvent(type="ready", backend=self.service.runtime.backend_name))

            while True:
                raw_payload = await websocket.receive_text()
                await self._handle_request_message(websocket, raw_payload)
        except AuthenticationError as exc:
            await self._send_event(
                websocket,
                ChatSocketEvent(type="error", backend=self.service.runtime.backend_name, detail=str(exc)),
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        except WebSocketDisconnect:
            logger.info("Websocket client disconnected")
        except Exception:
            logger.exception("Unhandled websocket session failure")
            await self._safe_close(websocket)

    def _authorize(self, websocket: WebSocket) -> None:
        if not self.api_config.require_api_key:
            return

        provided_key = websocket.query_params.get("api_key", "").strip()
        if provided_key != self.secrets_config.api_key:
            raise AuthenticationError("Missing or invalid websocket API key.")

    async def _handle_request_message(self, websocket: WebSocket, raw_payload: str) -> None:
        try:
            request = ChatSocketRequest.model_validate_json(raw_payload)
            
            user = self.user_repo.find_by_email(request.user_id)
            if not user:
                raise ServiceError(f"User not found in DB: {request.user_id}")
                
            user_companion = self.user_companion_repo.find_by_user_id(user.id)
            if not user_companion:
                raise ServiceError("User companion preferences are missing in DB.")
                
            ai_companion = self.ai_companion_repo.find_by_id(request.ai_companion_id)
            if not ai_companion or ai_companion.user_id != user.id:
                raise ServiceError("AI companion is missing, invalid, or not owned by the user.")

            async for token in self.service.stream_response(request, user.id):
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
        except ValidationError as exc:
            await self._send_event(
                websocket,
                ChatSocketEvent(
                    type="error",
                    backend=self.service.runtime.backend_name,
                    detail=str(exc.errors(include_url=False)),
                ),
            )
        except ServiceError as exc:
            await self._send_event(
                websocket,
                ChatSocketEvent(type="error", backend=self.service.runtime.backend_name, detail=str(exc)),
            )
        except Exception as exc:
            logger.exception("Unhandled request failure on websocket")
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
