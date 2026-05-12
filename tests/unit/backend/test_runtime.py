"""Unit tests for inference runtime helpers and factory behavior."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest import mock

import pytest

from src.backend.exceptions import ConfigurationError, InferenceExecutionError, InferenceNotReadyError
from src.backend.runtime import InferenceRuntimeFactory, MockInferenceRuntime, OllamaInferenceRuntime, VLLMInferenceRuntime
from src.backend.schemas import ChatMessage, InferencePromptRequest
from src.config import Chat, Inference, Secrets


def _chat_config() -> Chat:
    return Chat(system_prompt="system prompt", fixed_pulse_bpm=72)


def _inference_config(backend: str = "mock", **overrides) -> Inference:
    values = {"backend": backend, "model_name": "test-model", "mock_response_delay_seconds": 0.0}
    values.update(overrides)
    return Inference(**values)


def _secrets_config() -> Secrets:
    return Secrets(api_key="api", hf_token="", auth_encryption_key="secret")


def _request(json_schema: dict | None = None) -> InferencePromptRequest:
    return InferencePromptRequest(
        system_prompt=None,
        messages=[ChatMessage(role="user", content="Hello")],
        json_schema=json_schema,
    )


@pytest.mark.anyio
async def test_base_runtime_generate_text_accumulates_stream_and_tracks_startup_stage():
    runtime = MockInferenceRuntime(_chat_config(), _inference_config(), _secrets_config())

    assert runtime.backend_name == "mock"
    assert runtime.model_name == "test-model"
    assert runtime.startup_stage == "not_started"
    assert runtime.startup_elapsed_seconds is None

    await runtime.startup()
    text = await runtime.generate_text(_request())
    await runtime.shutdown()

    assert "Mock backend active" in text
    assert runtime.startup_stage == "stopped"
    assert runtime.startup_elapsed_seconds is not None


@pytest.mark.anyio
async def test_mock_runtime_returns_structured_json_for_schema_requests():
    runtime = MockInferenceRuntime(_chat_config(), _inference_config(), _secrets_config())

    text = await runtime.generate_text(_request(json_schema={"type": "object"}))

    assert '"title": "Mock Companion"' in text


def test_runtime_factory_creates_supported_backends():
    chat_config = _chat_config()
    secrets_config = _secrets_config()

    assert isinstance(InferenceRuntimeFactory.create(chat_config, _inference_config("mock"), secrets_config), MockInferenceRuntime)
    assert isinstance(InferenceRuntimeFactory.create(chat_config, _inference_config("vllm"), secrets_config), VLLMInferenceRuntime)
    assert isinstance(InferenceRuntimeFactory.create(chat_config, _inference_config("ollama"), secrets_config), OllamaInferenceRuntime)

    with pytest.raises(ConfigurationError, match="Unsupported inference backend"):
        InferenceRuntimeFactory.create(chat_config, _inference_config("bogus"), secrets_config)


def test_vllm_prompt_building_uses_tokenizer_template_and_pulse_context():
    runtime = VLLMInferenceRuntime(_chat_config(), _inference_config("vllm"), _secrets_config())
    runtime._tokenizer = mock.Mock()
    runtime._tokenizer.apply_chat_template.return_value = "rendered prompt"

    prompt = runtime._build_prompt(_request())

    assert prompt == "rendered prompt"
    messages = runtime._tokenizer.apply_chat_template.call_args.args[0]
    assert messages[0]["role"] == "system"
    assert "Current pulse placeholder: 72 BPM" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "Hello"}


def test_vllm_prompt_building_wraps_tokenizer_failures():
    runtime = VLLMInferenceRuntime(_chat_config(), _inference_config("vllm"), _secrets_config())
    runtime._tokenizer = mock.Mock()
    runtime._tokenizer.apply_chat_template.side_effect = RuntimeError("template failed")

    with pytest.raises(InferenceExecutionError, match="Tokenizer chat templating failed"):
        runtime._build_prompt(_request())


@pytest.mark.anyio
async def test_vllm_stream_text_rejects_unready_runtime():
    runtime = VLLMInferenceRuntime(_chat_config(), _inference_config("vllm"), _secrets_config())

    with pytest.raises(InferenceNotReadyError):
        async for _ in runtime.stream_text(_request()):
            pass


@pytest.mark.anyio
async def test_vllm_stream_text_yields_completion_deltas():
    class _Output:
        def __init__(self, text: str, finished: bool):
            self.outputs = [SimpleNamespace(text=text)]
            self.finished = finished

    class _Engine:
        async def generate(self, **kwargs):
            self.kwargs = kwargs
            yield _Output("hello", False)
            yield _Output(" world", True)

    class _SamplingParams:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    runtime = VLLMInferenceRuntime(_chat_config(), _inference_config("vllm", max_tokens=8), _secrets_config())
    runtime._engine = _Engine()
    runtime._tokenizer = mock.Mock()
    runtime._tokenizer.apply_chat_template.return_value = "prompt"
    runtime._sampling_params_cls = _SamplingParams
    runtime._request_output_kind = SimpleNamespace(DELTA="delta")

    chunks = []
    async for chunk in runtime.stream_text(_request(json_schema={"type": "object"})):
        chunks.append(chunk)

    assert chunks == ["hello", " world"]


@pytest.mark.anyio
async def test_vllm_stream_text_wraps_generation_failures():
    class _Engine:
        async def generate(self, **kwargs):
            raise RuntimeError("boom")
            yield  # pragma: no cover

    runtime = VLLMInferenceRuntime(_chat_config(), _inference_config("vllm"), _secrets_config())
    runtime._engine = _Engine()
    runtime._tokenizer = mock.Mock()
    runtime._tokenizer.apply_chat_template.return_value = "prompt"
    runtime._sampling_params_cls = lambda **kwargs: kwargs
    runtime._request_output_kind = SimpleNamespace(DELTA="delta")

    with pytest.raises(InferenceExecutionError, match="RuntimeError"):
        async for _ in runtime.stream_text(_request()):
            pass


@pytest.mark.anyio
async def test_vllm_shutdown_uses_available_engine_shutdown_method():
    runtime = VLLMInferenceRuntime(_chat_config(), _inference_config("vllm"), _secrets_config())
    runtime._engine = mock.Mock()
    await runtime.shutdown()
    runtime._engine = mock.Mock(spec=["shutdown_background_loop"])
    await runtime.shutdown()

    assert runtime.startup_stage == "stopped"


def test_vllm_get_param_names_falls_back_to_init_signature():
    class CallableWithoutSignature:
        __signature__ = None

        def __init__(self, alpha=None):
            self.alpha = alpha

    assert "alpha" in VLLMInferenceRuntime._get_param_names(CallableWithoutSignature)


@pytest.mark.anyio
async def test_vllm_startup_handles_import_failure(monkeypatch):
    runtime = VLLMInferenceRuntime(_chat_config(), _inference_config("vllm"), _secrets_config())

    original_import = __import__

    def failing_import(name, *args, **kwargs):
        if name == "transformers":
            raise ImportError("missing transformers")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", failing_import)

    await runtime.startup()

    assert runtime.startup_stage == "failed"
    assert "vLLM runtime import failed" in runtime.startup_error


@pytest.mark.anyio
async def test_ollama_runtime_startup_success_pull_and_stream(monkeypatch):
    class _Client:
        def __init__(self):
            self.pulled: list[str] = []

        async def list(self):
            return {"models": []}

        async def pull(self, model_name: str):
            self.pulled.append(model_name)

        async def chat(self, **kwargs):
            async def _chunks():
                yield {"message": {"content": "hi"}}
                yield {"message": {"content": ""}}
            return _chunks()

    client = _Client()
    monkeypatch.setattr("src.backend.runtime.ollama.AsyncClient", mock.Mock(return_value=client))
    runtime = OllamaInferenceRuntime(_chat_config(), _inference_config("ollama"), _secrets_config())

    await runtime.startup()
    chunks = []
    async for chunk in runtime.stream_text(_request(json_schema={"type": "object"})):
        chunks.append(chunk)
    await runtime.shutdown()

    assert client.pulled == ["test-model"]
    assert chunks == ["hi"]
    assert runtime.startup_stage == "stopped"


@pytest.mark.anyio
async def test_ollama_runtime_reports_startup_and_unready_errors(monkeypatch):
    class _FailingClient:
        async def list(self):
            raise OSError("ollama down")

    monkeypatch.setattr("src.backend.runtime.ollama.AsyncClient", mock.Mock(return_value=_FailingClient()))
    runtime = OllamaInferenceRuntime(_chat_config(), _inference_config("ollama"), _secrets_config())

    await runtime.startup()

    assert runtime.is_ready is False
    assert runtime.startup_stage == "failed"
    with pytest.raises(InferenceNotReadyError):
        async for _ in runtime.stream_text(_request()):
            pass


@pytest.mark.anyio
async def test_runtime_startup_monitor_exits_when_cancelled():
    runtime = MockInferenceRuntime(
        _chat_config(),
        _inference_config(startup_heartbeat_interval_seconds=60.0),
        _secrets_config(),
    )
    task = asyncio.create_task(runtime._startup_monitor()) if hasattr(runtime, "_startup_monitor") else None
    if task is not None:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
