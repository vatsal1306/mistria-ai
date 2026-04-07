"""Streamlit interface for a streaming Mistria chat demo."""

from __future__ import annotations

import streamlit as st

from src.chat.client import ChatClientError, StreamingChatClient
from src.config import settings

st.set_page_config(
    page_title=settings.app.title,
    page_icon="💬",
    layout="centered",
)


def _bootstrap_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "system_prompt" not in st.session_state:
        st.session_state.system_prompt = settings.chat.system_prompt


def _render_theme() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(255, 128, 96, 0.22), transparent 32%),
                    radial-gradient(circle at top right, rgba(255, 215, 140, 0.16), transparent 28%),
                    linear-gradient(180deg, #140f10 0%, #1f1719 40%, #0d0b0d 100%);
                color: #f6ead8;
            }
            [data-testid="stSidebar"] {
                background: rgba(16, 12, 13, 0.92);
                border-right: 1px solid rgba(255, 214, 165, 0.12);
            }
            .hero-shell {
                padding: 1.35rem 1.45rem;
                border: 1px solid rgba(255, 214, 165, 0.15);
                border-radius: 24px;
                background: linear-gradient(135deg, rgba(44, 28, 27, 0.92), rgba(25, 18, 18, 0.88));
                box-shadow: 0 22px 60px rgba(0, 0, 0, 0.24);
                margin-bottom: 1rem;
            }
            .hero-kicker {
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.18em;
                color: #ffbe88;
                margin-bottom: 0.45rem;
            }
            .hero-title {
                font-size: 2rem;
                line-height: 1.05;
                margin: 0;
                color: #fff4e1;
            }
            .hero-copy {
                margin: 0.65rem 0 0 0;
                color: #e9d4bc;
                font-size: 0.98rem;
            }
            .hero-meta {
                display: flex;
                gap: 0.65rem;
                flex-wrap: wrap;
                margin-top: 1rem;
            }
            .meta-pill {
                border-radius: 999px;
                padding: 0.36rem 0.72rem;
                background: rgba(255, 214, 165, 0.1);
                border: 1px solid rgba(255, 214, 165, 0.18);
                font-size: 0.84rem;
                color: #ffe4c4;
            }
            .empty-state {
                padding: 1rem 1.1rem;
                border-radius: 18px;
                background: rgba(255, 239, 221, 0.06);
                border: 1px dashed rgba(255, 214, 165, 0.18);
                color: #e5cfb5;
                margin: 1rem 0 1.25rem 0;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header() -> None:
    backend_label = "Mock Runtime" if settings.inference.backend == "mock" else "Embedded vLLM"
    st.markdown(
        f"""
        <div class="hero-shell">
            <div class="hero-kicker">Mistria Companion Chat</div>
            <h1 class="hero-title">{settings.chat.companion_name}</h1>
            <p class="hero-copy">
                Streaming text chat over a FastAPI websocket backend.
                The pulse signal is fixed at {settings.chat.fixed_pulse_bpm} BPM for this MVP.
            </p>
            <div class="hero-meta">
                <span class="meta-pill">{backend_label}</span>
                <span class="meta-pill">{settings.inference.model_name}</span>
                <span class="meta-pill">{settings.chat.fixed_pulse_bpm} BPM</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar() -> None:
    with st.sidebar:
        st.subheader("Session")
        st.write(f"**Model**  `{settings.inference.model_name}`")
        st.write(f"**WebSocket**  `{settings.api.websocket_url}`")
        st.write(f"**Backend**  `{settings.inference.backend}`")
        st.write(f"**Pulse**  `{settings.chat.fixed_pulse_bpm} BPM`")
        st.caption("The pulse value is appended to every system prompt as a fixed placeholder.")
        if st.button("Clear chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
        st.divider()
        st.subheader("Prompt")
        st.text_area(
            "System prompt",
            key="system_prompt",
            height=220,
            help="Edit the companion behavior without restarting the app.",
        )
        st.caption("Keep the tone aligned to your use case. Streamlit reruns will preserve this session value.")


def _render_messages() -> None:
    if not st.session_state.messages:
        st.markdown(
            """
            <div class="empty-state">
                Start the conversation. This MVP keeps session history in memory and streams every assistant response
                token-by-token from the configured websocket backend.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for message in st.session_state.messages:
        avatar = "A" if message["role"] == "assistant" else "U"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])


def _stream_assistant_reply(prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="U"):
        st.markdown(prompt)

    client = StreamingChatClient(settings.api, settings.chat, settings.secrets)
    with st.chat_message("assistant", avatar="A"):
        try:
            response_text = st.write_stream(
                client.stream_reply(
                    messages=st.session_state.messages,
                    system_prompt=st.session_state.system_prompt,
                )
            )
        except ChatClientError as exc:
            st.error(str(exc))
            return

    cleaned_response = response_text.strip() if isinstance(response_text, str) else ""
    if cleaned_response:
        st.session_state.messages.append({"role": "assistant", "content": cleaned_response})


def main() -> None:
    _bootstrap_state()
    _render_theme()
    _render_sidebar()
    _render_header()
    _render_messages()

    prompt = st.chat_input(f"Message {settings.chat.companion_name}...")
    if prompt:
        _stream_assistant_reply(prompt)


if __name__ == "__main__":
    main()
