# Mistria AI Streaming Chat MVP

Mistria AI ships a FastAPI backend, an embedded vLLM inference runtime, and a Streamlit chat UI. The production runtime is Docker Compose: one backend container for HTTP/WebSocket APIs and model inference, and one frontend container for Streamlit.

## What It Does

- Streams assistant responses over a FastAPI WebSocket endpoint.
- Exposes REST endpoints for user registration, companion preferences, and AI persona management.
- Persists users, companion data, conversations, and messages in SQLite.
- **Long-Term Memory System**: Asynchronously extracts facts/preferences and retrieves them using hybrid vector search (Qdrant).
- Starts vLLM from the Python backend process instead of a separate `vllm serve` process.
- Keeps Streamlit as the user-facing chat UI.
- Centralizes configuration in environment variables and `src/config.py`.

## API Documentation

Full API integration guide for frontend engineers:

- [API Integration Guide](docs/API%20Documentation.md) covers HTTP endpoints, WebSocket flow, schemas, and frontend integration notes.

## Production Requirements

- Ubuntu/Debian server with Docker Engine and the Docker Compose plugin.
- NVIDIA GPU drivers and NVIDIA Container Toolkit configured for `docker run --gpus all`.
- Enough disk space for the Docker images, SQLite data, logs, and Hugging Face model cache.
- Production secrets in `.env`.

Recommended model:

```text
dphn/Dolphin3.0-Llama3.1-8B
```

## Configure

Create a production env file from the example:

```bash
cp .env.example .env
chmod 600 .env
```

Update at least these values:

```bash
MISTRIA_AUTH_ENCRYPTION_KEY=replace-with-a-strong-secret
MISTRIA_API_KEY=replace-with-a-strong-secret
MISTRIA_INFERENCE_BACKEND=vllm
MISTRIA_INFERENCE_MODEL_NAME=dphn/Dolphin3.0-Llama3.1-8B
HF_TOKEN=optional-hugging-face-token
```

### Memory-Disabled Mode (Default)

To run the stack with only short-term conversation history (last 24 messages) and no vector storage, keep the default settings:
- `MISTRIA_MEMORY_ENABLED=False` (or unset)
- `MISTRIA_MEMORY_EXTRACTION_ENABLED=False` (or unset)
- `COMPOSE_PROFILES=` (do **not** include `memory`)

### Memory-Enabled Mode

To enable the long-term memory system (using Qdrant), update your `.env` with:

```bash
# Enable the core memory system and vector storage
MISTRIA_MEMORY_ENABLED=True
# Enable asynchronous background extraction of memories from chat
MISTRIA_MEMORY_EXTRACTION_ENABLED=True
# Qdrant connection settings
MISTRIA_MEMORY_QDRANT_URL=http://localhost:6333
MISTRIA_MEMORY_QDRANT_COLLECTION=mistria_memories
# Embedding model name (used by SentenceTransformers if provider is local)
MISTRIA_MEMORY_EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
# Enable the POST /debug/memory/retrieve endpoint
MISTRIA_MEMORY_DEBUG_ENDPOINT_ENABLED=True
# Required: activate the memory profile to start the Qdrant container
COMPOSE_PROFILES=memory
```

If a value contains `$`, escape it as `$$` because Docker Compose performs variable interpolation.

## Run With Docker

Build and start the production stack:

```bash
make build
make up
```

Check service status and readiness:

```bash
make ps
make health
```

Access the services:

- Streamlit: `http://127.0.0.1:8501`
- FastAPI health: `http://127.0.0.1:8080/health`
- FastAPI docs: `http://127.0.0.1:8080/docs`

Stop the stack:

```bash
make down
```

## Make Commands

- `make build`: build backend and frontend images.
- `make up`: start the Compose stack in the background.
- `make down`: stop containers and remove orphan containers.
- `make restart`: restart running containers.
- `make ps`: show Compose service status.
- `make logs`: follow all service logs.
- `make backend-logs`: follow backend logs.
- `make frontend-logs`: follow frontend logs.
- `make health`: verify backend model readiness and frontend reachability.
- `make smoke`: run the end-to-end HTTP/WebSocket smoke test against the running stack.
- `make clean`: stop the stack and remove named volumes.

Optional Make variables:

```bash
ENV_FILE=.env
COMPOSE_PROJECT_NAME=mistria-ai
IMAGE_TAG=latest
BACKEND_PORT=8080
FRONTEND_PORT=8501
```

Example:

```bash
make up ENV_FILE=/secure/path/mistria.env BACKEND_PORT=18080 FRONTEND_PORT=18501
```

## Bootstrap A Server

For a fresh Ubuntu/Debian server:

```bash
cd /workspace
curl -O https://raw.githubusercontent.com/vatsal1306/mistria-ai/main/scripts/bootstrap.sh
chmod +x bootstrap.sh
bash ./bootstrap.sh
```

Bootstrap will:

- Install base packages.
- Install Docker Engine and the Docker Compose plugin if missing.
- Sync or clone this repository.
- Write `.env` with production vLLM defaults.
- Verify Docker GPU access.
- Run `make build` and `make up`.
- Wait for backend vLLM readiness and Streamlit reachability.

Useful bootstrap variables:

```bash
REPO_BRANCH=main
REPO_DIR=/workspace/mistria-ai
BACKEND_PORT=8080
FRONTEND_PORT=8501
MISTRIA_MODEL_NAME=dphn/Dolphin3.0-Llama3.1-8B
OVERWRITE_ENV=0
SKIP_GPU_CHECK=0
RUN_SMOKE=0
```

## Persistence

Compose uses named volumes:

- `mistria_data`: SQLite database at `/app/data/db/app.db`.
- `mistria_logs`: application logs at `/app/Logs`.
- `mistria_hf_cache`: Hugging Face model cache at `/app/.cache/huggingface`.
- `mistria_qdrant_data`: Qdrant vector storage at `/qdrant/storage` (only used when `COMPOSE_PROFILES=memory` is set).
- `mistria_embeddings_cache`: Local embedding model cache (used when `MISTRIA_MEMORY_ENABLED=True`).

Container stdout/stderr is handled by Docker's `json-file` logging driver with rotation enabled.

## Development Notes

The backend entrypoint is `main.py`; the Streamlit entrypoint is `streamlit_app.py`. For non-Docker code checks:

```bash
uv sync --frozen
uv run python -m compileall main.py streamlit_app.py src scripts
```

The production Docker image installs the optional `inference` extra so the embedded vLLM runtime can import and initialize inside the backend container.
