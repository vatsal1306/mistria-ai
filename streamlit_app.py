"""Streamlit chat interface."""

from __future__ import annotations

import streamlit as st

from src.chat.client import ChatClientError, StreamingChatClient
from src.config import settings

USER_AVATAR = ":material/person:"
ASSISTANT_AVATAR = ":material/auto_awesome:"


st.set_page_config(
    page_title=settings.app.title,
    page_icon="💬",
    layout="wide",
)


def _bootstrap_state() -> None:
    defaults = {
        "messages": [],
        "chat_client": StreamingChatClient(settings.api, settings.chat, settings.secrets),
        "connection_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_theme() -> None:
    st.markdown(
        """
        <style>
            .chat-hero {
                position: relative;
                overflow: hidden;
                background:
                    linear-gradient(
                        135deg,
                        color-mix(in srgb, var(--primary-color) 22%, var(--secondary-background-color) 78%) 0%,
                        color-mix(in srgb, var(--secondary-background-color) 88%, var(--background-color) 12%) 52%,
                        color-mix(in srgb, var(--primary-color) 12%, var(--background-color) 88%) 100%
                    );
                border: 1px solid color-mix(in srgb, var(--text-color) 10%, transparent);
                border-radius: 1rem;
                padding: 1.25rem 1.35rem;
                margin-bottom: 1rem;
                box-shadow: 0 18px 40px color-mix(in srgb, var(--primary-color) 18%, transparent);
            }
            .chat-hero::after {
                content: "";
                position: absolute;
                right: -2.5rem;
                bottom: -3.5rem;
                width: 9rem;
                height: 9rem;
                border-radius: 999px;
                background: color-mix(in srgb, var(--primary-color) 14%, transparent);
                filter: blur(10px);
            }
            .hero-kicker {
                color: var(--primary-color);
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin-bottom: 0.45rem;
            }
            .hero-title {
                color: var(--text-color);
                font-size: 2.15rem;
                line-height: 1.05;
                margin: 0;
            }
            .hero-copy {
                color: color-mix(in srgb, var(--text-color) 78%, transparent);
                margin: 0.75rem 0 0 0;
            }
            .chat-shell {
                background: linear-gradient(
                    180deg,
                    color-mix(in srgb, var(--background-color) 94%, var(--secondary-background-color) 6%) 0%,
                    color-mix(in srgb, var(--secondary-background-color) 72%, var(--background-color) 28%) 100%
                );
                border: 1px solid color-mix(in srgb, var(--primary-color) 16%, transparent);
                border-radius: 1.15rem;
                padding: 0.8rem 0.85rem 0.35rem 0.85rem;
                box-shadow: 0 12px 28px color-mix(in srgb, var(--primary-color) 10%, transparent);
                margin-bottom: 0.7rem;
            }
            .hero-meta {
                display: flex;
                gap: 0.5rem;
                flex-wrap: wrap;
                margin-top: 1rem;
            }
            .meta-pill {
                background: color-mix(in srgb, var(--background-color) 65%, var(--primary-color) 35%);
                color: var(--text-color);
                border: 1px solid color-mix(in srgb, var(--primary-color) 22%, transparent);
                border-radius: 999px;
                font-size: 0.82rem;
                padding: 0.32rem 0.7rem;
            }
            .empty-state {
                background: var(--secondary-background-color);
                border: 1px dashed color-mix(in srgb, var(--text-color) 14%, transparent);
                border-radius: 1rem;
                color: color-mix(in srgb, var(--text-color) 80%, transparent);
                padding: 0.95rem 1rem;
                margin: 0.75rem 0 1rem 0;
            }
            .sidebar-card {
                background: color-mix(in srgb, var(--secondary-background-color) 88%, transparent);
                border: 1px solid color-mix(in srgb, var(--text-color) 10%, transparent);
                border-radius: 1rem;
                padding: 1rem;
                margin-bottom: 0.5rem;
            }
            .sidebar-label {
                color: var(--primary-color);
                font-size: 0.75rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin-bottom: 0.35rem;
            }
            .sidebar-title {
                color: var(--text-color);
                font-size: 1.05rem;
                font-weight: 700;
                margin-bottom: 0.15rem;
            }
            div[data-testid="stChatMessage"] {
                background: color-mix(in srgb, var(--secondary-background-color) 84%, transparent) !important;
                border: 1px solid color-mix(in srgb, var(--primary-color) 12%, transparent) !important;
                border-radius: 1rem;
                padding: 0.2rem 0.25rem;
                margin-bottom: 0.7rem;
                box-shadow: 0 8px 18px color-mix(in srgb, var(--primary-color) 7%, transparent);
            }
            div[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {
                background: transparent !important;
            }
            div[data-testid="stChatInput"] {
                background: color-mix(in srgb, var(--secondary-background-color) 92%, var(--background-color) 8%);
                border: 1px solid color-mix(in srgb, var(--primary-color) 14%, transparent);
                border-radius: 1rem;
                box-shadow: 0 10px 24px color-mix(in srgb, var(--primary-color) 8%, transparent);
                padding: 0.15rem 0.15rem 0.15rem 0.35rem;
            }
            div[data-testid="stChatInput"] textarea {
                background: transparent !important;
            }
            .chat-input-note {
                color: color-mix(in srgb, var(--text-color) 64%, transparent);
                font-size: 0.84rem;
                margin: 0.15rem 0 0.5rem 0.2rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _get_chat_client() -> StreamingChatClient:
    return st.session_state.chat_client


def _start_chat_session() -> None:
    client = _get_chat_client()
    try:
        client.connect()
        st.session_state.connection_error = None
    except ChatClientError as exc:
        st.session_state.connection_error = str(exc)
    st.rerun()


def _stop_chat_session() -> None:
    _get_chat_client().disconnect()
    st.session_state.connection_error = None
    st.rerun()


def _clear_chat_history() -> None:
    st.session_state.messages = []
    st.session_state.connection_error = None
    st.rerun()


def _render_sidebar() -> None:
    client = _get_chat_client()

    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-card">
                <div class="sidebar-label">Status</div>
                <div class="sidebar-title">{'Connected' if client.is_connected else 'Disconnected'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("")
        if st.session_state.connection_error:
            st.error(st.session_state.connection_error)

        start_clicked = st.button("Start chat", use_container_width=True, disabled=client.is_connected)
        stop_clicked = st.button("Stop chat", use_container_width=True, disabled=not client.is_connected)
        clear_clicked = st.button("Clear chat", use_container_width=True)

        if start_clicked:
            _start_chat_session()
        if stop_clicked:
            _stop_chat_session()
        if clear_clicked:
            _clear_chat_history()


def _render_chat_header() -> None:
    client = _get_chat_client()
    status_label = "Connected" if client.is_connected else "Disconnected"

    st.markdown(
        f"""
        <div class="chat-hero">
            <div class="hero-kicker">Mistria Companion</div>
            <h1 class="hero-title">{settings.chat.companion_name}</h1>
            <p class="hero-copy">Start the websocket session and send a message to begin.</p>
            <div class="hero-meta">
                <span class="meta-pill">{status_label}</span>
                <span class="meta-pill">{settings.inference.backend}</span>
                <span class="meta-pill">{settings.inference.model_name}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_messages() -> None:
    if not st.session_state.messages:
        st.markdown(
            """
            <div class="empty-state">
                No messages yet. Start the websocket session and send a message to begin chatting.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for message in st.session_state.messages:
        avatar = ASSISTANT_AVATAR if message["role"] == "assistant" else USER_AVATAR
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])


def _handle_chat_submission(prompt: str) -> None:
    client = _get_chat_client()
    if not client.is_connected:
        st.session_state.connection_error = "No active websocket session. Click 'Start chat' before sending messages."
        st.rerun()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        try:
            response_text = st.write_stream(
                client.stream_reply(
                    messages=st.session_state.messages,
                    system_prompt=settings.chat.system_prompt,
                )
            )
            st.session_state.connection_error = None
        except ChatClientError as exc:
            st.session_state.connection_error = str(exc)
            st.error(str(exc))
            return

    final_reply = response_text.strip() if isinstance(response_text, str) else ""
    if final_reply:
        st.session_state.messages.append({"role": "assistant", "content": final_reply})


def main() -> None:
    _bootstrap_state()
    _render_theme()
    _render_sidebar()
    _render_chat_header()

    st.markdown('<div class="chat-shell">', unsafe_allow_html=True)
    _render_messages()
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="chat-input-note">Low-latency session flow is ready when the channel is connected.</div>',
        unsafe_allow_html=True,
    )

    prompt = st.chat_input(
        f"Message {settings.chat.companion_name}...",
        disabled=not _get_chat_client().is_connected,
    )
    if prompt:
        _handle_chat_submission(prompt)


if __name__ == "__main__":
    main()
