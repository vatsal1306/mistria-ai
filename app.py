"""Streamlit chat interface for Mistria."""

from __future__ import annotations

import streamlit as st

from src.chat import stream_chat_turn
from src.config import PULSE_DEFAULT, PULSE_MAX, PULSE_MIN
from src.persistence import load_user_data, save_user_session
from src.sessions import SESSIONS

st.set_page_config(page_title="Mistria Chat", page_icon="💬", layout="centered")

# ── Custom styling ──────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    .stApp { background-color: #0f0f0f; }

    [data-testid="stHeader"] { background-color: #0f0f0f; }

    [data-testid="stChatMessage"] {
        background-color: #1a1a2e;
        border: 1px solid #2a2a4a;
        border-radius: 12px;
        padding: 12px;
    }

    div[data-testid="stChatInput"] textarea {
        background-color: #0f0f1a !important;
        border: 1px solid #2a2a4a !important;
        color: #e0e0e0 !important;
    }

    .pulse-display {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border: 1px solid #2a2a4a;
        border-radius: 12px;
        padding: 10px 16px;
        text-align: center;
    }

    .pulse-number {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #e879a8, #a855f7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .pulse-label {
        font-size: 0.75rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state initialisation ────────────────────────────────────────────

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = ""
    st.session_state.messages = []
    st.session_state.current_pulse = PULSE_DEFAULT


def _get_pulse_label(pulse: int) -> str:
    if pulse >= PULSE_MAX:
        return "🔥 PEAK"
    if pulse >= 75:
        return "🔥 High Heat"
    if pulse >= 50:
        return "✨ Rising"
    return "💫 Soft"


# ── Login screen ────────────────────────────────────────────────────────────

if not st.session_state.logged_in:
    st.markdown(
        "<h1 style='text-align:center; background:linear-gradient(135deg,#e879a8,#a855f7);"
        "-webkit-background-clip:text;-webkit-text-fill-color:transparent;'>Mistria</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center;color:#888;'>Enter your user ID to start chatting</p>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        user_id = st.text_input("User ID", value="user_101", label_visibility="collapsed")
        if st.button("Start Chat", use_container_width=True, type="primary"):
            user_info = load_user_data(user_id)
            if user_info is None:
                st.error(f"Unknown user_id: {user_id}")
            else:
                st.session_state.logged_in = True
                st.session_state.user_id = user_id
                st.session_state.current_pulse = int(
                    user_info.get("last_pulse", PULSE_DEFAULT)
                )
                st.rerun()

    st.stop()

# ── Sidebar controls ───────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        "<h2 style='background:linear-gradient(135deg,#e879a8,#a855f7);"
        "-webkit-background-clip:text;-webkit-text-fill-color:transparent;'>Mistria</h2>",
        unsafe_allow_html=True,
    )
    st.caption(f"Chatting as **{st.session_state.user_id}**")

    st.markdown(
        f"""
        <div class="pulse-display">
            <div class="pulse-label">Pulse</div>
            <div class="pulse-number">{st.session_state.current_pulse}%</div>
            <div class="pulse-label">{_get_pulse_label(st.session_state.current_pulse)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    new_pulse = st.slider(
        "Set Pulse",
        min_value=PULSE_MIN,
        max_value=PULSE_MAX,
        value=st.session_state.current_pulse,
    )
    if st.button("Apply Pulse", use_container_width=True):
        SESSIONS.reset(st.session_state.user_id, initial_pulse=new_pulse)
        save_user_session(st.session_state.user_id, new_pulse)
        st.session_state.current_pulse = new_pulse
        st.rerun()

    st.divider()

    if st.button("Reset Session", use_container_width=True, type="secondary"):
        SESSIONS.reset(st.session_state.user_id, initial_pulse=PULSE_DEFAULT)
        save_user_session(st.session_state.user_id, PULSE_DEFAULT)
        st.session_state.current_pulse = PULSE_DEFAULT
        st.session_state.messages = []
        st.rerun()

    if st.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_id = ""
        st.session_state.messages = []
        st.rerun()

# ── Chat history ────────────────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("meta"):
            st.caption(msg["meta"])

# ── Chat input ──────────────────────────────────────────────────────────────

if prompt := st.chat_input("Type a message..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        reply_parts: list[str] = []
        placeholder = st.empty()
        pulse = st.session_state.current_pulse
        latency = 0.0

        for event_type, payload in stream_chat_turn(
            st.session_state.user_id, prompt, resume_pulse=True,
        ):
            if event_type == "token":
                reply_parts.append(payload["token"])
                placeholder.markdown("".join(reply_parts) + "▌")
            elif event_type == "done":
                pulse = payload["pulse"]
                latency = payload["latency_seconds"]
            elif event_type == "error":
                placeholder.error(payload["detail"])

        full_reply = "".join(reply_parts)
        placeholder.markdown(full_reply)
        st.caption(f"Pulse: {pulse}% · {latency:.1f}s")

    st.session_state.current_pulse = pulse
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_reply,
        "meta": f"Pulse: {pulse}% · {latency:.1f}s",
    })
    st.rerun()
