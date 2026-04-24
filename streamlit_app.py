"""Minimal Streamlit websocket chat tester."""

from __future__ import annotations

from dataclasses import replace

import streamlit as st

from src.chat.client import ChatClientError, StreamingChatClient
from src.config import settings


st.set_page_config(
    page_title=settings.app.title,
    page_icon="💬",
    layout="wide",
)


def _bootstrap_state() -> None:
    defaults = {
        "messages": [],
        "chat_client": None,
        "connection_error": None,
        "ws_host": settings.api.host,
        "ws_port": settings.api.port,
        "ws_path": settings.api.websocket_path,
        "ws_require_api_key": settings.api.require_api_key,
        "ws_api_key": settings.secrets.api_key if settings.api.require_api_key else "",
        "user_id": "",
        "ai_companion_id": 1,
        "system_prompt": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _get_client() -> StreamingChatClient | None:
    client = st.session_state.chat_client
    if isinstance(client, StreamingChatClient):
        return client
    return None


def _is_connected() -> bool:
    client = _get_client()
    return bool(client and client.is_connected)


def _normalize_path(path: str) -> str:
    cleaned = path.strip() or "/ws/chat"
    if not cleaned.startswith("/"):
        return f"/{cleaned}"
    return cleaned


def _current_websocket_url() -> str:
    path = _normalize_path(st.session_state.ws_path)
    return f"ws://{st.session_state.ws_host.strip()}:{int(st.session_state.ws_port)}{path}"


def _build_chat_client() -> StreamingChatClient:
    api_config = replace(
        settings.api,
        host=st.session_state.ws_host.strip(),
        port=int(st.session_state.ws_port),
        websocket_path=_normalize_path(st.session_state.ws_path),
        require_api_key=bool(st.session_state.ws_require_api_key),
    )
    secrets_config = replace(
        settings.secrets,
        api_key=st.session_state.ws_api_key.strip(),
    )
    return StreamingChatClient(api_config, settings.chat, secrets_config)


def _connect() -> None:
    user_id = st.session_state.user_id.strip()
    if not user_id:
        st.session_state.connection_error = "User ID / email is required."
        return

    existing_client = _get_client()
    if existing_client:
        existing_client.disconnect()

    client = _build_chat_client()
    try:
        client.connect(
            user_id=user_id,
            ai_companion_id=int(st.session_state.ai_companion_id),
        )
    except ChatClientError as exc:
        st.session_state.chat_client = None
        st.session_state.connection_error = str(exc)
        return

    st.session_state.chat_client = client
    st.session_state.connection_error = None


def _disconnect() -> None:
    client = _get_client()
    if client:
        client.disconnect()
    st.session_state.chat_client = None
    st.session_state.connection_error = None


def _clear_messages() -> None:
    st.session_state.messages = []
    st.session_state.connection_error = None


def _render_sidebar() -> None:
    connected = _is_connected()
    client = _get_client()

    with st.sidebar:
        st.header("Connection")
        st.text_input("Host", key="ws_host", disabled=connected)
        st.number_input("Port", min_value=1, max_value=65535, step=1, key="ws_port", disabled=connected)
        st.text_input("Path", key="ws_path", disabled=connected)
        st.checkbox("Use API key", key="ws_require_api_key", disabled=connected)
        st.text_input(
            "API key",
            key="ws_api_key",
            type="password",
            disabled=connected or not st.session_state.ws_require_api_key,
        )

        st.divider()
        st.header("Payload")
        st.text_input("User ID / email", key="user_id", disabled=connected, placeholder="user@example.com")
        st.number_input("AI Companion ID", min_value=1, step=1, key="ai_companion_id", disabled=connected)
        st.text_area(
            "System prompt (optional)",
            key="system_prompt",
            height=140,
            placeholder="Leave empty to use the backend default.",
        )

        st.caption(f"WebSocket URL: `{_current_websocket_url()}`")
        st.caption("This backend expects `user_id` to be a registered user email.")

        st.divider()
        st.write(f"Status: {'Connected' if connected else 'Disconnected'}")
        if connected and client and client.backend_name:
            st.write(f"Backend: {client.backend_name}")

        st.button("Connect", use_container_width=True, on_click=_connect, disabled=connected)
        st.button("Disconnect", use_container_width=True, on_click=_disconnect, disabled=not connected)
        st.button("Clear chat", use_container_width=True, on_click=_clear_messages)


def _render_messages() -> None:
    if not st.session_state.messages:
        st.caption("No messages yet.")
        return

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def _handle_prompt(prompt: str) -> None:
    client = _get_client()
    if client is None or not client.is_connected:
        st.session_state.connection_error = "Connect to the websocket before sending messages."
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            response_text = st.write_stream(
                client.stream_reply(
                    user_message=prompt,
                    user_id=st.session_state.user_id.strip(),
                    ai_companion_id=int(st.session_state.ai_companion_id),
                    system_prompt=st.session_state.system_prompt.strip() or None,
                )
            )
        except ChatClientError as exc:
            st.session_state.connection_error = str(exc)
            st.error(str(exc))
            return

    final_reply = response_text if isinstance(response_text, str) else ""
    if final_reply:
        st.session_state.messages.append({"role": "assistant", "content": final_reply})
    st.session_state.connection_error = None


def main() -> None:
    _bootstrap_state()
    _render_sidebar()

    st.title("WebSocket Chat")

    if _is_connected():
        client = _get_client()
        backend_name = client.backend_name if client else None
        if backend_name:
            st.caption(f"Connected to `{_current_websocket_url()}` using backend `{backend_name}`.")
        else:
            st.caption(f"Connected to `{_current_websocket_url()}`.")
    else:
        st.caption("Configure the sidebar, connect to the websocket, then send messages.")

    if st.session_state.connection_error:
        st.error(st.session_state.connection_error)

    _render_messages()

    prompt = st.chat_input("Send a message", disabled=not _is_connected())
    if prompt:
        _handle_prompt(prompt)


if __name__ == "__main__":
    main()
