#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
REPO_URL="${REPO_URL:-https://github.com/vatsal1306/mistria-ai.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
REPO_DIR="${REPO_DIR:-${WORKSPACE_DIR}/mistria-ai}"
ENV_FILE="${ENV_FILE:-${REPO_DIR}/.env}"
DATA_DIR="${DATA_DIR:-${WORKSPACE_DIR}/data}"
LOG_DIR="${LOG_DIR:-${WORKSPACE_DIR}/logs}"
HF_HOME_DIR="${HF_HOME_DIR:-${WORKSPACE_DIR}/hf-cache}"

BACKEND_SESSION="${BACKEND_SESSION:-mistria-backend}"
FRONTEND_SESSION="${FRONTEND_SESSION:-mistria-frontend}"
BACKEND_PORT="${BACKEND_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-8501}"

MISTRIA_MODEL_NAME="${MISTRIA_MODEL_NAME:-dphn/Dolphin3.0-Llama3.1-8B}"
OVERWRITE_ENV="${OVERWRITE_ENV:-0}"

info() {
  printf '[runpod-bootstrap] %s\n' "$1"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  fi
}

apt_prefix() {
  if command -v sudo >/dev/null 2>&1; then
    printf 'sudo '
  fi
}

prompt_env() {
  local var_name="$1"
  local prompt_text="$2"
  local secret="${3:-0}"
  local current_value="${!var_name:-}"

  if [[ -n "$current_value" ]]; then
    return
  fi

  if [[ "$secret" == "1" ]]; then
    read -r -s -p "${prompt_text}: " current_value
    printf '\n'
  else
    read -r -p "${prompt_text}: " current_value
  fi

  if [[ -z "$current_value" ]]; then
    printf 'Value required for %s\n' "$var_name" >&2
    exit 1
  fi

  export "$var_name=$current_value"
}

write_env_file() {
  if [[ -f "$ENV_FILE" && "$OVERWRITE_ENV" != "1" ]]; then
    info "Keeping existing .env at ${ENV_FILE}"
    return
  fi

  prompt_env "MISTRIA_AUTH_ENCRYPTION_KEY" "Enter MISTRIA_AUTH_ENCRYPTION_KEY" 1
  prompt_env "MISTRIA_API_KEY" "Enter MISTRIA_API_KEY" 1

  mkdir -p "$(dirname "$ENV_FILE")"
  : >"$ENV_FILE"
  printf 'MISTRIA_AUTH_ENCRYPTION_KEY=%s\n' "$MISTRIA_AUTH_ENCRYPTION_KEY" >>"$ENV_FILE"
  printf 'MISTRIA_API_KEY=%s\n' "$MISTRIA_API_KEY" >>"$ENV_FILE"
  printf 'MISTRIA_INFERENCE_BACKEND=vllm\n' >>"$ENV_FILE"
  printf 'MISTRIA_INFERENCE_MODEL_NAME=%s\n' "$MISTRIA_MODEL_NAME" >>"$ENV_FILE"
  printf 'MISTRIA_STORAGE_SQLITE_PATH=%s/app.db\n' "$DATA_DIR" >>"$ENV_FILE"

  if [[ -n "${HF_TOKEN:-}" ]]; then
    printf 'HF_TOKEN=%s\n' "$HF_TOKEN" >>"$ENV_FILE"
  fi

  info "Wrote ${ENV_FILE}"
}

install_system_packages() {
  local prefix
  prefix="$(apt_prefix)"

  if ! command -v byobu >/dev/null 2>&1; then
    info "Installing byobu, git, curl, and ca-certificates"
    ${prefix}apt-get update
    ${prefix}apt-get install -y byobu git curl ca-certificates
  else
    info "byobu already installed"
  fi
}

install_uv() {
  if command -v uv >/dev/null 2>&1; then
    info "uv already installed"
    return
  fi

  require_cmd curl
  info "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
  require_cmd uv
}

sync_repo() {
  mkdir -p "$WORKSPACE_DIR"

  if [[ -d "${REPO_DIR}/.git" ]]; then
    info "Updating existing repo in ${REPO_DIR}"
    git -C "$REPO_DIR" fetch origin
    git -C "$REPO_DIR" checkout "$REPO_BRANCH"
    git -C "$REPO_DIR" pull --ff-only origin "$REPO_BRANCH"
    return
  fi

  info "Cloning repo into ${REPO_DIR}"
  git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR"
}

install_dependencies() {
  info "Installing Python dependencies with vLLM extra"
  (
    cd "$REPO_DIR"
    export PATH="${HOME}/.local/bin:${PATH}"
    uv sync --frozen --extra inference
  )
}

kill_session_if_exists() {
  local session_name="$1"
  if byobu has-session -t "$session_name" 2>/dev/null; then
    info "Restarting byobu session ${session_name}"
    byobu kill-session -t "$session_name"
  fi
}

start_backend() {
  local cmd
  cmd="cd ${REPO_DIR} && export PATH=${HOME}/.local/bin:\$PATH && export HF_HOME=${HF_HOME_DIR} && export PYTHONUNBUFFERED=1 && export MISTRIA_API_HOST=0.0.0.0 && export MISTRIA_API_PORT=${BACKEND_PORT} && export MISTRIA_API_RELOAD=false && export MISTRIA_LOG_DIR=${LOG_DIR} && uv run python main.py"
  kill_session_if_exists "$BACKEND_SESSION"
  byobu new-session -d -s "$BACKEND_SESSION" "bash -lc '$cmd'"
}

start_frontend() {
  local cmd
  cmd="cd ${REPO_DIR} && export PATH=${HOME}/.local/bin:\$PATH && export HF_HOME=${HF_HOME_DIR} && export PYTHONUNBUFFERED=1 && export MISTRIA_API_HOST=127.0.0.1 && export MISTRIA_API_PORT=${BACKEND_PORT} && export MISTRIA_LOG_DIR=${LOG_DIR} && uv run streamlit run streamlit_app.py --server.address=0.0.0.0 --server.port=${FRONTEND_PORT}"
  kill_session_if_exists "$FRONTEND_SESSION"
  byobu new-session -d -s "$FRONTEND_SESSION" "bash -lc '$cmd'"
}

print_summary() {
  cat <<EOF

Setup complete.

Repo: ${REPO_DIR}
Env: ${ENV_FILE}
SQLite: ${DATA_DIR}/app.db
HF cache: ${HF_HOME_DIR}

Byobu sessions:
  - ${BACKEND_SESSION}
  - ${FRONTEND_SESSION}

Useful commands:
  byobu ls
  byobu attach -t ${BACKEND_SESSION}
  byobu attach -t ${FRONTEND_SESSION}
  curl http://127.0.0.1:${BACKEND_PORT}/health
  ss -tulpn | grep ${BACKEND_PORT}
  ss -tulpn | grep ${FRONTEND_PORT}

Runpod exposure:
  - Expose TCP ${BACKEND_PORT} for FastAPI/websocket
  - Expose HTTP ${FRONTEND_PORT} for Streamlit
EOF
}

main() {
  install_system_packages
  install_uv
  sync_repo

  mkdir -p "$DATA_DIR" "$LOG_DIR" "$HF_HOME_DIR"

  write_env_file
  install_dependencies
  start_backend
  start_frontend
  print_summary
}

main "$@"
