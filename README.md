# Mistria AI Streaming Chat MVP

This repo now includes:

- `main.py`: a single-file FastAPI backend with websocket streaming chat
- `streamlit_app.py`: a Streamlit interface that connects to that websocket backend
- embedded runtime wiring for `mock` and `vllm` inference backends

## What it does

- Streams assistant responses over a FastAPI websocket endpoint
- Keeps backend logic inside `main.py` as requested
- Starts the inference runtime from Python code instead of a separate `vllm serve` process
- Keeps Streamlit as a simple websocket consumer for the future frontend contract
- Centralizes non-secret config in `src/config.py`
- Centralizes prompts in `src/prompts.py`

## Recommended model

Use `dphn/Dolphin3.0-Llama3.1-8B` for the first pass. It is lightweight enough for an MVP and its model card explicitly positions it around owner-controlled alignment and system-prompt steerability, which fits your self-hosted adult-chat requirement.

## Run it

1. Sync dependencies:

   ```bash
   uv sync
   ```

2. Adjust non-secret configuration in `src/config.py` and prompts in `src/prompts.py` if needed.
   For local smoke tests on unsupported hosts, leave `Inference.backend = "mock"`.
   For embedded model inference, switch `Inference.backend = "vllm"`.

3. Start the FastAPI backend:

   ```bash
   uv run python main.py
   ```

4. Launch the app:

   ```bash
   uv run streamlit run streamlit_app.py
   ```

## Embedded vLLM notes

- `main.py` initializes the inference runtime during FastAPI startup and shuts it down on app exit.
- To install the optional vLLM dependency on supported Linux hosts:

  ```bash
  uv sync --extra inference
  ```

- The current default backend is `mock` so the app remains runnable without GPU inference on this machine.

## Configuration layout

- `.env`
  - Secrets only. Right now that includes `MISTRIA_API_KEY` and optional `HF_TOKEN`.
- `src/config.py`
  - Non-secret application config grouped by classes such as `App`, `Api`, `Chat`, and `Inference`.
- `src/prompts.py`
  - Prompt text used by the app, starting with the chat system prompt.

## Environment variables

- `MISTRIA_API_KEY`
- `MISTRIA_AUTH_ENCRYPTION_KEY`
- `HF_TOKEN`
