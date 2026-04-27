from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backend.runtime import VLLMInferenceRuntime


class _GuidedParams:
    def __init__(self, json):
        self.json = json


class _StructuredParams:
    def __init__(self, json):
        self.json = json


def _make_runtime() -> VLLMInferenceRuntime:
    chat_config = SimpleNamespace(system_prompt="system", pulse_context="context")
    inference_config = SimpleNamespace(backend="vllm", model_name="test-model")
    secrets_config = SimpleNamespace(hf_token=None)
    return VLLMInferenceRuntime(chat_config, inference_config, secrets_config)


def test_prefers_structured_outputs_when_supported():
    runtime = _make_runtime()

    class SamplingParams:
        def __init__(self, structured_outputs=None, **kwargs):
            self.structured_outputs = structured_outputs
            self.kwargs = kwargs

    runtime._configure_structured_output_support(
        sampling_params_cls=SamplingParams,
        guided_decoding_params_cls=_GuidedParams,
        structured_outputs_params_cls=_StructuredParams,
    )

    schema = {"type": "object"}
    kwargs = runtime._build_structured_output_kwargs(schema)

    assert set(kwargs) == {"structured_outputs"}
    assert isinstance(kwargs["structured_outputs"], _StructuredParams)
    assert kwargs["structured_outputs"].json == schema


def test_uses_guided_decoding_when_guided_json_is_unavailable():
    runtime = _make_runtime()

    class SamplingParams:
        def __init__(self, guided_decoding=None, **kwargs):
            self.guided_decoding = guided_decoding
            self.kwargs = kwargs

    runtime._configure_structured_output_support(
        sampling_params_cls=SamplingParams,
        guided_decoding_params_cls=_GuidedParams,
        structured_outputs_params_cls=None,
    )

    schema = {"type": "object"}
    kwargs = runtime._build_structured_output_kwargs(schema)

    assert set(kwargs) == {"guided_decoding"}
    assert isinstance(kwargs["guided_decoding"], _GuidedParams)
    assert kwargs["guided_decoding"].json == schema


def test_falls_back_to_legacy_guided_json_when_available():
    runtime = _make_runtime()

    class SamplingParams:
        def __init__(self, guided_json=None, **kwargs):
            self.guided_json = guided_json
            self.kwargs = kwargs

    runtime._configure_structured_output_support(
        sampling_params_cls=SamplingParams,
        guided_decoding_params_cls=None,
        structured_outputs_params_cls=None,
    )

    schema = {"type": "object"}
    kwargs = runtime._build_structured_output_kwargs(schema)

    assert kwargs == {"guided_json": schema}


def test_returns_empty_kwargs_when_structured_output_is_unsupported():
    runtime = _make_runtime()

    class SamplingParams:
        def __init__(self, temperature=None, **kwargs):
            self.temperature = temperature
            self.kwargs = kwargs

    runtime._configure_structured_output_support(
        sampling_params_cls=SamplingParams,
        guided_decoding_params_cls=None,
        structured_outputs_params_cls=None,
    )

    assert runtime._build_structured_output_kwargs({"type": "object"}) == {}
