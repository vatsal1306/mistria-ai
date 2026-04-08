"""Websocket client used by Streamlit to consume the FastAPI backend."""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

from websocket import WebSocketException, WebSocketTimeoutException, create_connection

from src.Logging import logger
from src.config import Api, Chat, Secrets


class ChatClientError(RuntimeError):
    """Raised when the websocket chat backend cannot satisfy a request."""


class StreamingChatClient:
    """Maintain a persistent websocket session and yield streamed text chunks."""

    def __init__(self, api_config: Api, chat_config: Chat, secrets_config: Secrets):
        self.api_config = api_config
        self.chat_config = chat_config
        self.secrets_config = secrets_config
        self._websocket: Any | None = None
        self._backend_name: str | None = None
        self._model_name: str | None = None

    @property
    def is_connected(self) -> bool:
        return bool(self._websocket is not None and getattr(self._websocket, "connected", False))

    @property
    def backend_name(self) -> str | None:
        return self._backend_name

    @property
    def model_name(self) -> str | None:
        return self._model_name

    def connect(self) -> None:
        if self.is_connected:
            return

        websocket_url = self._build_websocket_url()
        timeout = self.api_config.read_timeout_seconds
        logger.info("Opening websocket chat stream to %s", websocket_url)

        try:
            self._websocket = create_connection(websocket_url, timeout=timeout)
            self._consume_ready_event()
        except WebSocketTimeoutException as exc:
            self.disconnect()
            raise ChatClientError("The websocket chat backend timed out during connection setup.") from exc
        except WebSocketException as exc:
            self.disconnect()
            raise ChatClientError(
                "Could not connect to the websocket chat backend. Start main.py and verify the configured host and port."
            ) from exc
        except OSError as exc:
            self.disconnect()
            raise ChatClientError(
                "Could not reach the websocket chat backend. Start main.py before using the Streamlit UI."
            ) from exc

    def disconnect(self) -> None:
        if self._websocket is not None:
            try:
                self._websocket.close()
            finally:
                self._websocket = None
                self._backend_name = None
                self._model_name = None

    def stream_reply(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
    ) -> Generator[str, None, None]:
        if not self.is_connected:
            raise ChatClientError("No active websocket session. Click 'Start chat' before sending messages.")

        request_payload = {
            "action": "chat",
            "request_id": uuid4().hex,
            "system_prompt": system_prompt or self.chat_config.system_prompt,
            "messages": self._trim_messages(messages),
        }

        try:
            self._websocket.send(json.dumps(request_payload))
            yield from self._consume_stream()
        except WebSocketTimeoutException as exc:
            self.disconnect()
            raise ChatClientError("The websocket chat backend timed out while streaming a response.") from exc
        except WebSocketException as exc:
            self.disconnect()
            raise ChatClientError(
                "The websocket chat backend connection was interrupted. Reconnect and try again."
            ) from exc
        except OSError as exc:
            self.disconnect()
            raise ChatClientError(
                "The websocket chat backend became unreachable. Reconnect after the backend is available."
            ) from exc

    def _build_websocket_url(self) -> str:
        if not self.api_config.require_api_key:
            return self.api_config.websocket_url

        query_string = urlencode({"api_key": self.secrets_config.api_key})
        return f"{self.api_config.websocket_url}?{query_string}"

    def _consume_ready_event(self) -> None:
        frame = self._receive_frame()
        event_type = frame.get("type")
        if event_type != "ready":
            self.disconnect()
            raise ChatClientError("The websocket backend did not return a ready event during connection setup.")

        self._backend_name = frame.get("backend")
        self._model_name = frame.get("model_name")

    def _consume_stream(self) -> Generator[str, None, None]:
        while True:
            frame = self._receive_frame()
            event_type = frame.get("type")
            if event_type == "start":
                continue
            if event_type == "delta":
                delta = frame.get("delta", "")
                if delta:
                    yield delta
                continue
            if event_type == "done":
                break
            if event_type == "error":
                raise ChatClientError(frame.get("detail", "Unknown websocket backend error."))

            logger.warning("Ignoring unknown websocket event type=%s", event_type)

    def _receive_frame(self) -> dict[str, Any]:
        if not self.is_connected:
            raise ChatClientError("No active websocket session.")

        raw_frame = self._websocket.recv()
        if not raw_frame:
            raise ChatClientError("The websocket backend returned an empty frame.")

        try:
            return json.loads(raw_frame)
        except json.JSONDecodeError as exc:
            raise ChatClientError("The websocket backend returned malformed JSON.") from exc

    def _trim_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        return messages[-self.chat_config.history_message_limit:]
