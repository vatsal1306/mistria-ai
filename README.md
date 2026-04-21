# Mistria AI Streaming Chat MVP

This repo currently ships a Python-only AI MVP with:

- `main.py`: FastAPI backend entrypoint (HTTP + WebSocket)
- `streamlit_app.py`: Streamlit UI entrypoint
- `src/backend`: websocket transport and inference runtime orchestration
- `src/companion`: companion persona creation and user preference management
- `src/auth`: signup, login, and password encryption
- `src/storage`: SQLite-backed user, conversation, and message persistence

## What it does

- Streams assistant responses over a FastAPI websocket endpoint
- Exposes REST endpoints for user registration, companion preferences, and AI persona management
- Persists user auth and chat history in SQLite
- Starts the inference runtime from Python code instead of a separate `vllm serve` process
- Keeps Streamlit as the user-facing companion UI
- Centralizes non-secret config in `src/config.py`
- Centralizes prompts in `src/prompts.py`

## API Documentation

Full API integration guide for frontend engineers:

📄 **[API Integration Guide](docs/api_integration_guide.md)** — covers all HTTP endpoints, WebSocket chat flow, request/response schemas, allowed values, and frontend integration notes.

## Recommended model

Use `dphn/Dolphin3.0-Llama3.1-8B` for the first pass. It is lightweight enough for an MVP and its model card explicitly positions it around owner-controlled alignment and system-prompt steerability, which fits your self-hosted adult-chat requirement.

## Run it

1. Sync dependencies:

   ```bash
   uv sync --frozen
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
  uv sync --frozen --extra inference
  ```

- The current default backend is `mock` so the app remains runnable without GPU inference on this machine.

## Docker Compose

The repo includes a single `docker-compose.yaml` that works for local development and a simple Ubuntu server deployment.

1. Update the secrets in `.env`.
   If a secret contains `$`, escape it as `$$` so Docker Compose treats it literally.

2. Build and start the stack:

   ```bash
   docker compose up -d --build
   ```

3. Access:

   - Streamlit: `http://127.0.0.1:8501`
   - FastAPI health: `http://127.0.0.1:8080/health`

The stack mounts a named volume for `data/app.db`, so SQLite state survives container restarts. Container logs stay on standard Docker stdout/stderr.

## CI

GitHub Actions now runs three checks on every push and pull request:

- Python compilation and dependency install
- Security checks with Bandit and `pip-audit`
- Full Docker Compose smoke test that builds both images, starts both containers, probes the app, and performs a websocket round-trip against the `mock` backend

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

## How to use Pod

```shell
cd /workspace
curl -O https://raw.githubusercontent.com/vatsal1306/mistria-ai/main/scripts/bootstrap.sh
chmod +x bootstrap.sh
bash ./bootstrap.sh
```
