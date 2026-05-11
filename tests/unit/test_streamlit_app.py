"""Unit tests for Streamlit UI helper functions using a fake Streamlit module."""

from __future__ import annotations

import importlib
import sys

import pytest


class _SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self):
        self.session_state = _SessionState()
        self.sidebar = _Context()
        self.messages = []
        self.next_chat_input = None

    def set_page_config(self, **kwargs):
        self.page_config = kwargs

    def header(self, value):
        self.messages.append(("header", value))

    def text_input(self, *args, **kwargs):
        return None

    def number_input(self, *args, **kwargs):
        return None

    def checkbox(self, *args, **kwargs):
        return None

    def text_area(self, *args, **kwargs):
        return None

    def divider(self):
        return None

    def caption(self, value):
        self.messages.append(("caption", value))

    def write(self, value):
        self.messages.append(("write", value))

    def button(self, *args, **kwargs):
        return False

    def chat_message(self, role):
        self.messages.append(("chat_message", role))
        return _Context()

    def markdown(self, value):
        self.messages.append(("markdown", value))

    def error(self, value):
        self.messages.append(("error", value))

    def title(self, value):
        self.messages.append(("title", value))

    def chat_input(self, *args, **kwargs):
        return self.next_chat_input

    def write_stream(self, generator):
        return "".join(generator)


class _Client:
    def __init__(self, *args, **kwargs):
        self.connected = False
        self.is_connected = False
        self.backend_name = "mock"
        self.connect_calls = []
        self.disconnected = False

    def connect(self, user_id, ai_companion_id):
        self.connect_calls.append((user_id, ai_companion_id))
        self.connected = True
        self.is_connected = True

    def disconnect(self):
        self.disconnected = True
        self.connected = False
        self.is_connected = False

    def stream_reply(self, **kwargs):
        yield "hello"
        yield " world"


def _load_app(monkeypatch):
    fake_st = _FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    sys.modules.pop("streamlit_app", None)
    module = importlib.import_module("streamlit_app")
    return module, fake_st


def test_bootstrap_state_and_url_helpers(monkeypatch):
    app, st = _load_app(monkeypatch)

    app._bootstrap_state()
    st.session_state.ws_path = "ws/custom"
    st.session_state.ws_host = "localhost"
    st.session_state.ws_port = 9000

    assert st.session_state.messages == []
    assert app._normalize_path("") == "/ws/chat"
    assert app._normalize_path("abc") == "/abc"
    assert app._current_websocket_url() == "ws://localhost:9000/ws/custom"
    assert app._get_client() is None
    assert app._is_connected() is False


def test_build_chat_client_uses_session_overrides(monkeypatch):
    app, st = _load_app(monkeypatch)
    app._bootstrap_state()
    st.session_state.ws_host = "example.com"
    st.session_state.ws_port = 7777
    st.session_state.ws_path = "chat"
    st.session_state.ws_require_api_key = True
    st.session_state.ws_api_key = " secret "

    client = app._build_chat_client()

    assert client.api_config.websocket_url == "ws://example.com:7777/chat"
    assert client.api_config.require_api_key is True
    assert client.secrets_config.api_key == "secret"


def test_connect_disconnect_and_clear_messages(monkeypatch):
    app, st = _load_app(monkeypatch)
    monkeypatch.setattr(app, "StreamingChatClient", _Client)
    app._bootstrap_state()

    app._connect()
    assert st.session_state.connection_error == "User ID / email is required."

    st.session_state.user_id = "user@example.com"
    app._connect()
    assert st.session_state.chat_client.is_connected is True
    assert st.session_state.connection_error is None

    app._disconnect()
    assert st.session_state.chat_client is None

    st.session_state.messages = [{"role": "user", "content": "x"}]
    st.session_state.connection_error = "bad"
    app._clear_messages()
    assert st.session_state.messages == []
    assert st.session_state.connection_error is None


def test_connect_reports_client_errors(monkeypatch):
    app, st = _load_app(monkeypatch)

    class _FailingClient(_Client):
        def connect(self, user_id, ai_companion_id):
            raise app.ChatClientError("backend down")

    monkeypatch.setattr(app, "StreamingChatClient", _FailingClient)
    app._bootstrap_state()
    st.session_state.user_id = "user@example.com"

    app._connect()

    assert st.session_state.chat_client is None
    assert st.session_state.connection_error == "backend down"


def test_render_helpers_and_handle_prompt(monkeypatch):
    app, st = _load_app(monkeypatch)
    monkeypatch.setattr(app, "StreamingChatClient", _Client)
    app._bootstrap_state()
    client = _Client()
    client.is_connected = True
    st.session_state.chat_client = client
    st.session_state.user_id = "user@example.com"
    st.session_state.ai_companion_id = 3
    st.session_state.system_prompt = ""

    app._render_sidebar()
    app._render_messages()
    app._handle_prompt("Hi")

    assert st.session_state.messages == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "hello world"},
    ]
    assert st.session_state.connection_error is None


def test_handle_prompt_requires_connection_and_reports_stream_errors(monkeypatch):
    app, st = _load_app(monkeypatch)
    monkeypatch.setattr(app, "StreamingChatClient", _Client)
    app._bootstrap_state()
    app._handle_prompt("Hi")
    assert st.session_state.connection_error == "Connect to the websocket before sending messages."

    class _FailingStreamClient(_Client):
        def stream_reply(self, **kwargs):
            raise app.ChatClientError("stream failed")
            yield  # pragma: no cover

    failing_client = _FailingStreamClient()
    failing_client.is_connected = True
    st.session_state.chat_client = failing_client
    st.session_state.user_id = "user@example.com"
    st.session_state.ai_companion_id = 3
    st.session_state.system_prompt = ""

    app._handle_prompt("Hi")

    assert st.session_state.connection_error == "stream failed"


def test_main_renders_and_handles_chat_input(monkeypatch):
    app, st = _load_app(monkeypatch)
    monkeypatch.setattr(app, "StreamingChatClient", _Client)
    app._bootstrap_state()
    client = _Client()
    client.is_connected = True
    st.session_state.chat_client = client
    st.session_state.user_id = "user@example.com"
    st.session_state.ai_companion_id = 3
    st.next_chat_input = "Hello"

    app.main()

    assert ("title", "WebSocket Chat") in st.messages
    assert st.session_state.messages[-1]["content"] == "hello world"
