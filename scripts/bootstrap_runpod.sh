#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
REPO_URL="${REPO_URL:-https://github.com/vatsal1306/mistria-ai.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
REPO_DIR="${REPO_DIR:-${WORKSPACE_DIR}/mistria-ai}"
ENV_FILE="${ENV_FILE:-${REPO_DIR}/.env}"

BACKEND_PORT="${BACKEND_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-8501}"
MISTRIA_MODEL_NAME="${MISTRIA_MODEL_NAME:-dphn/Dolphin3.0-Llama3.1-8B}"
MISTRIA_INFERENCE_BACKEND="${MISTRIA_INFERENCE_BACKEND:-vllm}"
MISTRIA_MEMORY_ENABLED="${MISTRIA_MEMORY_ENABLED:-True}"
MISTRIA_MEMORY_EXTRACTION_ENABLED="${MISTRIA_MEMORY_EXTRACTION_ENABLED:-True}"
OVERWRITE_ENV="${OVERWRITE_ENV:-0}"
INSTALL_SYSTEM_PACKAGES="${INSTALL_SYSTEM_PACKAGES:-1}"

log() {
  printf '[%s] %s\n' "$1" "$2"
}

fail() {
  log "FAIL" "$1" >&2
  exit 1
}

sudo_prefix() {
  if [[ "$(id -u)" -ne 0 ]]; then
    if ! command -v sudo >/dev/null 2>&1; then
      fail "This step needs root privileges. Install sudo, run as root, or set INSTALL_SYSTEM_PACKAGES=0."
    fi
    printf 'sudo '
  fi
}

install_system_packages() {
  if [[ "$INSTALL_SYSTEM_PACKAGES" != "1" ]]; then
    log "INFO" "Skipping system package installation"
    return
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    log "WARN" "apt-get not found; skipping system package installation"
    return
  fi

  local prefix
  prefix="$(sudo_prefix)"
  log "INFO" "Installing base system packages"
  ${prefix}apt-get update
  ${prefix}apt-get install -y ca-certificates curl git libgomp1 libnuma1
}

install_uv() {
  if command -v uv >/dev/null 2>&1; then
    log "OK" "uv is already installed"
    return
  fi

  log "INFO" "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
  command -v uv >/dev/null 2>&1 || fail "uv install completed, but uv is not on PATH"
}

sync_repo() {
  mkdir -p "$WORKSPACE_DIR"
  if [[ -d "${REPO_DIR}/.git" ]]; then
    log "INFO" "Updating existing repo in ${REPO_DIR}"
    git -C "$REPO_DIR" fetch origin
    git -C "$REPO_DIR" checkout "$REPO_BRANCH"
    git -C "$REPO_DIR" pull --ff-only origin "$REPO_BRANCH"
    return
  fi

  log "INFO" "Cloning ${REPO_URL} into ${REPO_DIR}"
  git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR"
}

write_env_file() {
  if [[ -f "$ENV_FILE" && "$OVERWRITE_ENV" != "1" ]]; then
    log "OK" "Keeping existing env file at ${ENV_FILE}"
    return
  fi

  mkdir -p "$(dirname "$ENV_FILE")" "${REPO_DIR}/data/db" "${REPO_DIR}/Logs" "${WORKSPACE_DIR}/.cache/huggingface" "${WORKSPACE_DIR}/.cache/embeddings" "${WORKSPACE_DIR}/qdrant"

  local api_key
  local auth_key
  api_key="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  auth_key="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

  log "INFO" "Writing direct runtime env file to ${ENV_FILE}"
  cat >"$ENV_FILE" <<EOF
MISTRIA_APP_TITLE="Mistria AI"
MISTRIA_BACKEND_PORT=${BACKEND_PORT}
MISTRIA_FRONTEND_PORT=${FRONTEND_PORT}
MISTRIA_API_PORT=${BACKEND_PORT}
MISTRIA_API_RELOAD=False
MISTRIA_API_REQUIRE_API_KEY=False
MISTRIA_API_CORS_ORIGINS=http://127.0.0.1:${FRONTEND_PORT},http://localhost:${FRONTEND_PORT}
MISTRIA_API_KEY=${api_key}
MISTRIA_AUTH_ENCRYPTION_KEY=${auth_key}

MISTRIA_INFERENCE_BACKEND=${MISTRIA_INFERENCE_BACKEND}
MISTRIA_INFERENCE_MODEL_NAME=${MISTRIA_MODEL_NAME}
MISTRIA_INFERENCE_MAX_MODEL_LEN=4096
MISTRIA_INFERENCE_TENSOR_PARALLEL_SIZE=1
MISTRIA_INFERENCE_DTYPE=auto
MISTRIA_INFERENCE_TRUST_REMOTE_CODE=False
MISTRIA_INFERENCE_ENFORCE_EAGER=False

MISTRIA_STORAGE_SQLITE_PATH=${REPO_DIR}/data/db/app.db
MISTRIA_LOG_LEVEL=INFO

MISTRIA_MEMORY_ENABLED=${MISTRIA_MEMORY_ENABLED}
MISTRIA_MEMORY_EXTRACTION_ENABLED=${MISTRIA_MEMORY_EXTRACTION_ENABLED}
MISTRIA_MEMORY_QDRANT_URL=http://localhost:6333
MISTRIA_MEMORY_QDRANT_PATH=${WORKSPACE_DIR}/qdrant
MISTRIA_MEMORY_QDRANT_COLLECTION=mistria_memories
MISTRIA_MEMORY_EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2

HF_HOME=${WORKSPACE_DIR}/.cache/huggingface
XDG_CACHE_HOME=${WORKSPACE_DIR}/.cache
SENTENCE_TRANSFORMERS_HOME=${WORKSPACE_DIR}/.cache/embeddings
EOF
  chmod 600 "$ENV_FILE"
}

install_python_dependencies() {
  cd "$REPO_DIR"
  log "INFO" "Installing Python dependencies into ${REPO_DIR}/.venv"
  uv sync --frozen --extra inference --no-dev
}

print_summary() {
  cat <<EOF

[OK] Runpod direct setup complete.

Start services:
  cd ${REPO_DIR}
  bash scripts/run_direct.sh start

Check status and logs:
  bash scripts/run_direct.sh status
  bash scripts/run_direct.sh logs

Expose these Runpod HTTP ports:
  Streamlit: ${FRONTEND_PORT}
  FastAPI:   ${BACKEND_PORT}
EOF
}

install_system_packages
install_uv
sync_repo
write_env_file
install_python_dependencies
print_summary
