"""Websocket request handling for chat streaming."""

from __future__ import annotations

from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from src.Logging import logger
from src.backend.exceptions import AuthenticationError, ServiceError
from src.backend.schemas import ChatSocketEvent, ChatSocketRequest
from src.backend.service import ChatService, StreamMetadata
from src.config import Api, Secrets


class WebSocketChatHandler:
    """One handler instance shared across websocket connections."""

    def __init__(self, api_config: Api, secrets_config: Secrets, service: ChatService):
        self.api_config = api_config
        self.secrets_config = secrets_config
        self.service = service

    async def handle(self, websocket: WebSocket) -> None:
        await websocket.accept()

        try:
            self._authorize(websocket)
            await self._send_event(websocket,
                                   ChatSocketEvent(type="ready", backend=self.service.runtime.backend_name,
                                                   model_name=self.service.runtime.model_name))

            while True:
                raw_payload = await websocket.receive_text()
                await self._handle_request_message(websocket, raw_payload)
        except AuthenticationError as exc:
            await self._send_event(websocket, ChatSocketEvent(type="error", detail=str(exc)))
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
        request_id = uuid4().hex
        try:
            request = ChatSocketRequest.model_validate_json(raw_payload)
            request_id = request.request_id or request_id
            request = request.model_copy(update={"request_id": request_id})
            await self._send_event(websocket,
                                   ChatSocketEvent(type="start", request_id=request_id,
                                                   backend=self.service.runtime.backend_name,
                                                   model_name=self.service.runtime.model_name))

            chunks: list[str] = []
            latency: float | None = None

            async for item in self.service.stream_response(request):
                if isinstance(item, StreamMetadata):
                    latency = item.latency_seconds
                else:
                    chunks.append(item)
                    await self._send_event(
                        websocket,
                        ChatSocketEvent(type="delta", request_id=request_id, delta=item),
                    )

            await self._send_event(
                websocket,
                ChatSocketEvent(
                    type="done",
                    request_id=request_id,
                    text="".join(chunks).strip(),
                    latency_seconds=latency,
                ),
            )
        except ValidationError as exc:
            await self._send_event(
                websocket,
                ChatSocketEvent(type="error", request_id=request_id, detail=str(exc.errors(include_url=False))),
            )
        except ServiceError as exc:
            await self._send_event(
                websocket,
                ChatSocketEvent(type="error", request_id=request_id, detail=str(exc)),
            )
        except Exception as exc:
            logger.exception("Unhandled request failure on websocket")
            await self._send_event(
                websocket,
                ChatSocketEvent(
                    type="error",
                    request_id=request_id,
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
