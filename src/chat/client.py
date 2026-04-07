"""Websocket client used by Streamlit to consume the FastAPI backend."""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any, List, Dict
from urllib.parse import urlencode
from uuid import uuid4

from websocket import WebSocketException, WebSocketTimeoutException, create_connection

from src.Logging import logger
from src.config import Api, Chat, Secrets


class ChatClientError(RuntimeError):
    """Raised when the websocket chat backend cannot satisfy a request."""


class StreamingChatClient:
    """Connect to the backend websocket and yield streamed text chunks."""

    def __init__(self, api_config: Api, chat_config: Chat, secrets_config: Secrets):
        self.api_config = api_config
        self.chat_config = chat_config
        self.secrets_config = secrets_config

    def stream_reply(self, messages: List[Dict[str, str]], system_prompt: str | None = None) -> \
            Generator[str, None, None]:
        request_payload = {
            "action": "chat",
            "request_id": uuid4().hex,
            "system_prompt": system_prompt or self.chat_config.system_prompt,
            "messages": self._trim_messages(messages),
        }

        websocket_url = self._build_websocket_url()
        timeout = self.api_config.read_timeout_seconds
        logger.info("Opening websocket chat stream to %s", websocket_url)
        websocket = None

        try:
            websocket = create_connection(websocket_url, timeout=timeout)
            websocket.send(json.dumps(request_payload))
            yield from self._consume_stream(websocket)
        except WebSocketTimeoutException as exc:
            raise ChatClientError("The websocket chat backend timed out while streaming a response.") from exc
        except WebSocketException as exc:
            raise ChatClientError(
                "Could not connect to the websocket chat backend. Start main.py and verify the configured host and port."
            ) from exc
        except OSError as exc:
            raise ChatClientError(
                "Could not reach the websocket chat backend. Start main.py before using the Streamlit UI."
            ) from exc
        finally:
            if websocket is not None:
                websocket.close()

    def _build_websocket_url(self) -> str:
        if not self.api_config.require_api_key:
            return self.api_config.websocket_url

        query_string = urlencode({"api_key": self.secrets_config.api_key})
        return f"{self.api_config.websocket_url}?{query_string}"

    def _consume_stream(self, websocket: Any) -> Generator[str, None, None]:
        while True:
            raw_frame = websocket.recv()
            if not raw_frame:
                continue

            try:
                frame = json.loads(raw_frame)
            except json.JSONDecodeError as exc:
                raise ChatClientError("The websocket backend returned malformed JSON.") from exc

            event_type = frame.get("type")
            if event_type in {"ready", "start"}:
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

    def _trim_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        return messages[-self.chat_config.history_message_limit:]
