"""Streamlit interface for auth-gated companion chat."""

from __future__ import annotations

import re
from dataclasses import dataclass

import streamlit as st

from src.auth.crypto import PasswordCipher
from src.auth.exceptions import AuthError, EncryptionConfigurationError, InvalidCredentialsError
from src.auth.service import AuthService
from src.chat.client import ChatClientError, StreamingChatClient
from src.config import settings
from src.storage.conversation_store import SQLiteConversationStore
from src.storage.database import SQLiteDatabase
from src.storage.exceptions import DatabaseInitializationError, StorageError
from src.storage.models import ConversationRecord, MessageRecord, UserRecord
from src.storage.repositories import SQLiteConversationRepository, SQLiteUserRepository
from src.storage.service import ChatHistoryService

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USER_AVATAR = ":material/person:"
ASSISTANT_AVATAR = ":material/auto_awesome:"


@dataclass(frozen=True, slots=True)
class StreamlitServices:
    auth_service: AuthService
    chat_history_service: ChatHistoryService


st.set_page_config(
    page_title=settings.app.title,
    page_icon="💬",
    layout="wide",
)


@st.cache_resource
def get_services() -> StreamlitServices:
    database = SQLiteDatabase(settings.storage.sqlite_path)
    database.initialize()

    user_repository = SQLiteUserRepository(database)
    conversation_repository = SQLiteConversationRepository(database)
    password_cipher = PasswordCipher(settings.secrets.auth_encryption_key)

    return StreamlitServices(
        auth_service=AuthService(user_repository=user_repository, password_cipher=password_cipher),
        chat_history_service=ChatHistoryService(
            conversation_store=SQLiteConversationStore(conversation_repository),
        ),
    )


def _bootstrap_state() -> None:
    defaults = {
        "auth_step": "email",
        "auth_email": "",
        "auth_name_hint": "",
        "email_lookup_input": "",
        "current_user": None,
        "current_conversation_id": None,
        "messages": [],
        "chat_client": StreamingChatClient(settings.api, settings.chat, settings.secrets),
        "connection_error": None,
        "auth_error": None,
        "welcome_message": None,
        "connection_pct": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_theme() -> None:
    st.markdown(
        """
        <style>
            .auth-shell, .chat-hero {
                background: var(--secondary-background-color);
                border: 1px solid color-mix(in srgb, var(--text-color) 10%, transparent);
                border-radius: 1rem;
                padding: 1.25rem 1.35rem;
                margin-bottom: 1rem;
            }
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
            .auth-kicker, .hero-kicker {
                color: var(--primary-color);
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin-bottom: 0.45rem;
            }
            .auth-title, .hero-title {
                color: var(--text-color);
                line-height: 1.05;
                margin: 0;
            }
            .auth-title {
                font-size: 2rem;
            }
            .hero-title {
                font-size: 2.15rem;
            }
            .auth-copy, .hero-copy {
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
            .sidebar-copy {
                color: color-mix(in srgb, var(--text-color) 76%, transparent);
                margin: 0;
                font-size: 0.92rem;
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


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _is_valid_email(value: str) -> bool:
    return bool(EMAIL_PATTERN.match(value))


def _is_authenticated() -> bool:
    return st.session_state.current_user is not None


def _set_authenticated_session(
    user: UserRecord,
    conversation: ConversationRecord,
    messages: list[MessageRecord],
    welcome_message: str,
) -> None:
    st.session_state.current_user = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
    }
    st.session_state.current_conversation_id = conversation.id
    st.session_state.messages = [{"role": message.role, "content": message.content} for message in messages]
    st.session_state.auth_step = "chat"
    st.session_state.auth_email = user.email
    st.session_state.auth_name_hint = user.name
    st.session_state.auth_error = None
    st.session_state.connection_error = None
    st.session_state.welcome_message = welcome_message


def _load_user_session(user: UserRecord, welcome_message: str, services: StreamlitServices) -> None:
    snapshot = services.chat_history_service.load_latest(user.id)
    _set_authenticated_session(
        user=user,
        conversation=snapshot.conversation,
        messages=snapshot.messages,
        welcome_message=welcome_message,
    )


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


def _clear_chat_history(services: StreamlitServices) -> None:
    current_user = st.session_state.current_user
    if current_user is None:
        return

    try:
        snapshot = services.chat_history_service.start_fresh(current_user["id"])
        st.session_state.current_conversation_id = snapshot.conversation.id
        st.session_state.messages = []
        st.session_state.connection_error = None
        st.rerun()
    except StorageError as exc:
        st.session_state.connection_error = f"Could not clear the chat: {exc}"
        st.rerun()


def _render_auth_intro(title: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="auth-shell">
            <div class="auth-kicker">Mistria Access</div>
            <h1 class="auth-title">{title}</h1>
            <p class="auth-copy">{copy}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_email_step(services: StreamlitServices) -> None:
    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        _render_auth_intro(
            title="Sign In",
            copy="Enter your email to continue.",
        )
        st.markdown("")
        with st.form("email_lookup_form", clear_on_submit=False):
            email = st.text_input("Email", placeholder="you@example.com", key="email_lookup_input")
            submitted = st.form_submit_button("Continue", use_container_width=True)

        if submitted:
            normalized_email = _normalize_email(email)
            if not _is_valid_email(normalized_email):
                st.session_state.auth_error = "Enter a valid email address."
                st.rerun()

            try:
                user = services.auth_service.find_user_by_email(normalized_email)
                st.session_state.auth_email = normalized_email
                st.session_state.auth_error = None
                if user is None:
                    st.session_state.auth_step = "signup"
                    st.session_state.auth_name_hint = ""
                else:
                    st.session_state.auth_step = "login"
                    st.session_state.auth_name_hint = user.name
                st.rerun()
            except StorageError as exc:
                st.session_state.auth_error = f"Could not look up that email: {exc}"
                st.rerun()

        if st.session_state.auth_error:
            st.error(st.session_state.auth_error)


def _render_signup_step(services: StreamlitServices) -> None:
    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        _render_auth_intro(
            title="Create Account",
            copy="Welcome to Mistria AI Backend. Add your name and password to create your account.",
        )
        st.markdown("")
        with st.form("signup_form", clear_on_submit=False):
            st.text_input("Email", value=st.session_state.auth_email, disabled=True)
            name = st.text_input("Name", placeholder="Your name")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create account", use_container_width=True)

        different_email = st.button("Use different email", use_container_width=True)

        if submitted:
            if not name.strip():
                st.session_state.auth_error = "Name is required."
                st.rerun()
            if len(password) < settings.auth.min_password_length:
                st.session_state.auth_error = (
                    f"Password must be at least {settings.auth.min_password_length} characters."
                )
                st.rerun()
            if password != confirm_password:
                st.session_state.auth_error = "Passwords do not match."
                st.rerun()

            try:
                user = services.auth_service.register_user(
                    email=st.session_state.auth_email,
                    name=name,
                    password=password,
                )
                snapshot = services.chat_history_service.start_fresh(user.id)
                _set_authenticated_session(
                    user=user,
                    conversation=snapshot.conversation,
                    messages=[],
                    welcome_message=f"Welcome, {user.name}.",
                )
                st.rerun()
            except AuthError as exc:
                st.session_state.auth_error = str(exc)
                st.rerun()
            except StorageError as exc:
                st.session_state.auth_error = f"Could not create your account: {exc}"
                st.rerun()

        if different_email:
            st.session_state.auth_step = "email"
            st.session_state.auth_email = ""
            st.session_state.auth_name_hint = ""
            st.session_state.auth_error = None
            st.session_state.email_lookup_input = ""
            st.rerun()

        if st.session_state.auth_error:
            st.error(st.session_state.auth_error)


def _render_login_step(services: StreamlitServices) -> None:
    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        _render_auth_intro(
            title=f"Welcome Back, {st.session_state.auth_name_hint}",
            copy="Enter your password to continue into your latest conversation.",
        )
        st.markdown("")
        with st.form("login_form", clear_on_submit=False):
            st.text_input("Email", value=st.session_state.auth_email, disabled=True)
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)

        different_email = st.button("Use different email", use_container_width=True)

        if submitted:
            try:
                user = services.auth_service.authenticate(
                    email=st.session_state.auth_email,
                    password=password,
                )
                _load_user_session(user, f"Welcome back, {user.name}.", services)
                st.rerun()
            except InvalidCredentialsError as exc:
                st.session_state.auth_error = str(exc)
                st.rerun()
            except StorageError as exc:
                st.session_state.auth_error = f"Could not sign you in: {exc}"
                st.rerun()

        if different_email:
            st.session_state.auth_step = "email"
            st.session_state.auth_email = ""
            st.session_state.auth_name_hint = ""
            st.session_state.auth_error = None
            st.session_state.email_lookup_input = ""
            st.rerun()

        if st.session_state.auth_error:
            st.error(st.session_state.auth_error)


def _render_auth_flow(services: StreamlitServices) -> None:
    step = st.session_state.auth_step
    if step == "signup":
        _render_signup_step(services)
        return
    if step == "login":
        _render_login_step(services)
        return
    _render_email_step(services)


def _render_sidebar(services: StreamlitServices) -> None:
    current_user = st.session_state.current_user
    client = _get_chat_client()

    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-card">
                <div class="sidebar-label">Current User</div>
                <div class="sidebar-title">{current_user['name']}</div>
                <p class="sidebar-copy">{current_user['email']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("")
        st.caption(f"Connection: {'connected' if client.is_connected else 'disconnected'}")
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
            _clear_chat_history(services)

        st.markdown("---")
        st.markdown(
            f"""
            <div class="sidebar-card">
                <div class="sidebar-label">Connection</div>
                <div class="sidebar-title" style="font-size:1.8rem;
                    background:linear-gradient(135deg,#e879a8,#a855f7);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
                    {st.session_state.connection_pct}%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "Private channel open. Stay in the moment, keep the signal live, and pick up exactly where the chemistry left off."
        )


def _render_chat_header() -> None:
    client = _get_chat_client()
    status_label = "Connected" if client.is_connected else "Disconnected"
    welcome_message = st.session_state.welcome_message or f"Hello, {st.session_state.current_user['name']}."

    st.markdown(
        f"""
        <div class="chat-hero">
            <div class="hero-kicker">Mistria Companion</div>
            <h1 class="hero-title">{settings.chat.companion_name}</h1>
            <p class="hero-copy">{welcome_message}</p>
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
                Your latest conversation is empty. Start the websocket session, send a message, and the app will
                persist the final user and assistant replies into SQLite.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for message in st.session_state.messages:
        avatar = ASSISTANT_AVATAR if message["role"] == "assistant" else USER_AVATAR
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])


def _ensure_conversation(services: StreamlitServices) -> int:
    conversation_id = st.session_state.current_conversation_id
    if conversation_id is not None:
        return conversation_id

    snapshot = services.chat_history_service.start_fresh(st.session_state.current_user["id"])
    st.session_state.current_conversation_id = snapshot.conversation.id
    return snapshot.conversation.id


def _handle_chat_submission(services: StreamlitServices, prompt: str) -> None:
    client = _get_chat_client()
    if not client.is_connected:
        st.session_state.connection_error = "No active websocket session. Click 'Start chat' before sending messages."
        st.rerun()

    try:
        conversation_id = _ensure_conversation(services)
        services.chat_history_service.save_message(conversation_id, "user", prompt)
    except StorageError as exc:
        st.error(f"Could not store your message: {exc}")
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        try:
            user_email = st.session_state.current_user.get("email", "") if st.session_state.current_user else ""
            response_text = st.write_stream(
                client.stream_reply(
                    messages=st.session_state.messages,
                    system_prompt=settings.chat.system_prompt,
                    user_id=user_email,
                )
            )
            st.session_state.connection_error = None
            if client.last_connection is not None:
                st.session_state.connection_pct = client.last_connection
            meta_parts = []
            if client.last_connection is not None:
                meta_parts.append(f"Connection: {client.last_connection}%")
            if client.last_latency is not None:
                meta_parts.append(f"{client.last_latency:.1f}s")
            if meta_parts:
                st.caption(" · ".join(meta_parts))
        except ChatClientError as exc:
            st.session_state.connection_error = str(exc)
            st.error(str(exc))
            return

    final_reply = response_text.strip() if isinstance(response_text, str) else ""
    if not final_reply:
        return

    try:
        services.chat_history_service.save_message(conversation_id, "assistant", final_reply)
    except StorageError as exc:
        st.error(f"Could not store the assistant reply: {exc}")
        return

    st.session_state.messages.append({"role": "assistant", "content": final_reply})


def _render_chat_interface(services: StreamlitServices) -> None:
    _render_sidebar(services)
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
        _handle_chat_submission(services, prompt)


def main() -> None:
    _bootstrap_state()
    _render_theme()

    try:
        services = get_services()
    except (DatabaseInitializationError, EncryptionConfigurationError) as exc:
        st.error(str(exc))
        st.stop()

    if _is_authenticated():
        _render_chat_interface(services)
        return

    _render_auth_flow(services)


if __name__ == "__main__":
    main()
