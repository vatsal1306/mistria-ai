"""Streamlit interface for companion chat via the FastAPI backend."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import streamlit as st

from src.chat_client.client import ChatClientError, StreamingChatClient
from src.config import settings

USER_AVATAR = ":material/person:"
ASSISTANT_AVATAR = ":material/auto_awesome:"

st.set_page_config(
    page_title=settings.app.title,
    page_icon="💬",
    layout="centered",
)


def _bootstrap_state() -> None:
    defaults = {
        "logged_in": False,
        "user_id": "",
        "messages": [],
        "connection_pct": 0,
        "chat_client": StreamingChatClient(
            settings.api, settings.chat, settings.secrets,
        ),
        "connection_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp { background-color: #0f0f0f; }
        [data-testid="stHeader"] { background-color: #0f0f0f; }
        [data-testid="stChatMessage"] {
            background-color: #1a1a2e; border: 1px solid #2a2a4a;
            border-radius: 12px; padding: 12px;
        }
        div[data-testid="stChatInput"] textarea {
            background-color: #0f0f1a !important;
            border: 1px solid #2a2a4a !important;
            color: #e0e0e0 !important;
        }
        .conn-display {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border: 1px solid #2a2a4a; border-radius: 12px;
            padding: 10px 16px; text-align: center;
        }
        .conn-number {
            font-size: 2rem; font-weight: 700;
            background: linear-gradient(135deg, #e879a8, #a855f7);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .conn-label {
            font-size: 0.75rem; color: #888;
            text-transform: uppercase; letter-spacing: 1px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _get_client() -> StreamingChatClient:
    return st.session_state.chat_client


def _call_rest(endpoint: str, payload: dict) -> dict | None:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{settings.api.http_base_url}{endpoint}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError) as exc:
        st.error(f"Backend unreachable: {exc}")
        return None


def _start_chat() -> None:
    try:
        _get_client().connect()
        st.session_state.connection_error = None
    except ChatClientError as exc:
        st.session_state.connection_error = str(exc)


def _stop_chat() -> None:
    _get_client().disconnect()
    st.session_state.connection_error = None


def _render_login() -> None:
    st.markdown(
        "<h1 style='text-align:center; background:linear-gradient(135deg,#e879a8,#a855f7);"
        "-webkit-background-clip:text;-webkit-text-fill-color:transparent;'>Mistria</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center;color:#888;'>Enter your user ID to start chatting</p>",
        unsafe_allow_html=True,
    )
    _, center, _ = st.columns([1, 2, 1])
    with center:
        user_id = st.text_input("User ID", value="user_101", label_visibility="collapsed")
        if st.button("Start Chat", use_container_width=True, type="primary"):
            st.session_state.logged_in = True
            st.session_state.user_id = user_id
            st.rerun()


def _render_sidebar() -> None:
    client = _get_client()
    with st.sidebar:
        st.markdown(
            "<h2 style='background:linear-gradient(135deg,#e879a8,#a855f7);"
            "-webkit-background-clip:text;-webkit-text-fill-color:transparent;'>Mistria</h2>",
            unsafe_allow_html=True,
        )
        st.caption(f"Chatting as **{st.session_state.user_id}**")
        st.caption(f"Connection: **{'connected' if client.is_connected else 'disconnected'}**")

        if st.session_state.connection_error:
            st.error(st.session_state.connection_error)

        if st.button("Start chat", use_container_width=True, disabled=client.is_connected):
            _start_chat()
            st.rerun()
        if st.button("Stop chat", use_container_width=True, disabled=not client.is_connected):
            _stop_chat()
            st.rerun()

        st.divider()

        st.markdown(
            f"""
            <div class="conn-display">
                <div class="conn-label">Connection</div>
                <div class="conn-number">{st.session_state.connection_pct}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        if st.button("Reset Session", use_container_width=True, type="secondary"):
            result = _call_rest("/reset", {"user_id": st.session_state.user_id})
            if result:
                st.session_state.connection_pct = result["connection"]
                st.session_state.messages = []
                st.rerun()

        if st.button("Logout", use_container_width=True):
            _stop_chat()
            st.session_state.logged_in = False
            st.session_state.user_id = ""
            st.session_state.messages = []
            st.rerun()


def _render_messages() -> None:
    for msg in st.session_state.messages:
        avatar = ASSISTANT_AVATAR if msg["role"] == "assistant" else USER_AVATAR
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])
            if msg.get("meta"):
                st.caption(msg["meta"])


def _handle_chat_input() -> None:
    client = _get_client()
    prompt = st.chat_input(
        f"Message {settings.chat.companion_name}...",
        disabled=not client.is_connected,
    )
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        try:
            response_text = st.write_stream(
                client.stream_reply(
                    messages=st.session_state.messages,
                    system_prompt=settings.chat.system_prompt,
                    user_id=st.session_state.user_id,
                    resume_pulse=True,
                ),
            )
            st.session_state.connection_error = None

            connection = client.last_pulse
            latency = client.last_latency
            if connection is not None:
                st.session_state.connection_pct = connection
            meta = ""
            if connection is not None:
                meta += f"Connection: {connection}%"
            if latency is not None:
                meta += f" · {latency:.1f}s"
            if meta:
                st.caption(meta)
        except ChatClientError as exc:
            st.session_state.connection_error = str(exc)
            st.error(str(exc))
            return

    final_reply = response_text.strip() if isinstance(response_text, str) else ""
    if final_reply:
        meta_str = ""
        if client.last_pulse is not None:
            meta_str = f"Connection: {client.last_pulse}%"
        if client.last_latency is not None:
            meta_str += f" · {client.last_latency:.1f}s"
        st.session_state.messages.append({
            "role": "assistant",
            "content": final_reply,
            "meta": meta_str,
        })


def main() -> None:
    _bootstrap_state()
    _render_theme()
    if not st.session_state.logged_in:
        _render_login()
        return
    _render_sidebar()
    _render_messages()
    _handle_chat_input()


if __name__ == "__main__":
    main()
