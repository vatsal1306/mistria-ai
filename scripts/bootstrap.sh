#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
REPO_URL="${REPO_URL:-https://github.com/vatsal1306/mistria-ai.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
REPO_DIR="${REPO_DIR:-${WORKSPACE_DIR}/mistria-ai}"
ENV_FILE="${ENV_FILE:-${REPO_DIR}/.env}"
DATA_DIR="${DATA_DIR:-${REPO_DIR}/data/db}"
LOG_DIR="${LOG_DIR:-${REPO_DIR}/Logs}"
HF_HOME_DIR="${HF_HOME_DIR:-${WORKSPACE_DIR}/hf-cache}"

BACKEND_SESSION="${BACKEND_SESSION:-mistria-backend}"
FRONTEND_SESSION="${FRONTEND_SESSION:-mistria-frontend}"
BACKEND_PORT="${BACKEND_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-8501}"

MISTRIA_MODEL_NAME="${MISTRIA_MODEL_NAME:-dphn/Dolphin3.0-Llama3.1-8B}"
OVERWRITE_ENV="${OVERWRITE_ENV:-0}"

if [[ -t 1 ]]; then
  COLOR_RED=$'\033[0;31m'
  COLOR_GREEN=$'\033[0;32m'
  COLOR_YELLOW=$'\033[0;33m'
  COLOR_BLUE=$'\033[0;34m'
  COLOR_BOLD=$'\033[1m'
  COLOR_RESET=$'\033[0m'
else
  COLOR_RED=""
  COLOR_GREEN=""
  COLOR_YELLOW=""
  COLOR_BLUE=""
  COLOR_BOLD=""
  COLOR_RESET=""
fi

CURRENT_STEP="bootstrap"

log_line() {
  local color="$1"
  local label="$2"
  local message="$3"
  printf '%s[%s]%s %s\n' "$color" "$label" "$COLOR_RESET" "$message"
}

info() {
  log_line "$COLOR_BLUE" "INFO" "$1"
}

success() {
  log_line "$COLOR_GREEN" "OK" "$1"
}

warn() {
  log_line "$COLOR_YELLOW" "WARN" "$1"
}

fail() {
  log_line "$COLOR_RED" "FAIL" "$1" >&2
  exit 1
}

step() {
  CURRENT_STEP="$1"
  printf '\n%s==>%s %s%s%s\n' "$COLOR_BOLD" "$COLOR_RESET" "$COLOR_BOLD" "$1" "$COLOR_RESET"
}

on_error() {
  local exit_code="$1"
  fail "Step failed: ${CURRENT_STEP} (exit ${exit_code})"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Missing required command: $1"
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
    fail "Value required for ${var_name}"
  fi

  export "$var_name=$current_value"
}

write_env_file() {
  if [[ -f "$ENV_FILE" && "$OVERWRITE_ENV" != "1" ]]; then
    warn "Keeping existing .env at ${ENV_FILE}"
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

  success "Wrote ${ENV_FILE}"
}

install_system_packages() {
  local prefix
  prefix="$(apt_prefix)"

  if ! command -v byobu >/dev/null 2>&1; then
    info "Installing byobu, git, curl, nano and ca-certificates"
    ${prefix}apt-get update
    ${prefix}apt-get install -y byobu git curl nano ca-certificates
    success "Installed system packages"
  else
    success "byobu already installed"
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
  # Make it permanent for the user
  echo 'export PATH="${HOME}/.local/bin:${PATH}"' >> "${HOME}/.bashrc"
  require_cmd uv
  success "Installed uv"
}

sync_repo() {
  mkdir -p "$WORKSPACE_DIR"

  if [[ -d "${REPO_DIR}/.git" ]]; then
    info "Updating existing repo in ${REPO_DIR}"
    git -C "$REPO_DIR" fetch origin
    git -C "$REPO_DIR" checkout "$REPO_BRANCH"
    git -C "$REPO_DIR" pull --ff-only origin "$REPO_BRANCH"
    success "Repo updated"
    return
  fi

  info "Cloning repo into ${REPO_DIR}"
  git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR"
  success "Repo cloned"
}

install_dependencies() {
  info "Installing Python dependencies with vLLM extra"
  (
    cd "$REPO_DIR"
    export PATH="${HOME}/.local/bin:${PATH}"
    # Force copy mode to avoid hardlink issues on RunPod volumes
    export UV_LINK_MODE=copy
    uv sync --frozen --extra inference
  )
  success "Python dependencies installed"
}

kill_session_if_exists() {
  local session_name="$1"
  if byobu has-session -t "$session_name" 2>/dev/null; then
    warn "Restarting byobu session ${session_name}"
    byobu kill-session -t "$session_name"
  fi
}

verify_session() {
  local session_name="$1"
  sleep 2

  if ! byobu has-session -t "$session_name" 2>/dev/null; then
    fail "Byobu session did not stay alive: ${session_name}"
  fi

  success "Byobu session running: ${session_name}"
}

start_backend() {
  local cmd
  cmd="cd ${REPO_DIR} && export PATH=${HOME}/.local/bin:\$PATH && export HF_HOME=${HF_HOME_DIR} && export PYTHONUNBUFFERED=1 && export MISTRIA_API_HOST=0.0.0.0 && export MISTRIA_API_PORT=${BACKEND_PORT} && export MISTRIA_API_RELOAD=false && export MISTRIA_LOG_DIR=${LOG_DIR} && uv run python main.py"
  kill_session_if_exists "$BACKEND_SESSION"
  byobu new-session -d -s "$BACKEND_SESSION" "bash -lc '$cmd'"
  verify_session "$BACKEND_SESSION"
}

start_frontend() {
  local cmd
  cmd="cd ${REPO_DIR} && export PATH=${HOME}/.local/bin:\$PATH && export HF_HOME=${HF_HOME_DIR} && export PYTHONUNBUFFERED=1 && export MISTRIA_API_HOST=127.0.0.1 && export MISTRIA_API_PORT=${BACKEND_PORT} && export MISTRIA_LOG_DIR=${LOG_DIR} && uv run streamlit run streamlit_app.py --server.address=0.0.0.0 --server.port=${FRONTEND_PORT} --server.enableCORS=false --server.enableXsrfProtection=false --server.enableWebsocketCompression=false"
  kill_session_if_exists "$FRONTEND_SESSION"
  byobu new-session -d -s "$FRONTEND_SESSION" "bash -lc '$cmd'"
  verify_session "$FRONTEND_SESSION"
}

verify_health() {
  local health_url="http://127.0.0.1:${BACKEND_PORT}/health"
  local frontend_url="http://127.0.0.1:${FRONTEND_PORT}/"
  local tries=30

  info "Waiting for backend health endpoint"
  for _ in $(seq 1 "$tries"); do
    if curl -fsS "$health_url" >/dev/null 2>&1; then
      success "Backend is healthy"
      break
    fi
    sleep 2
  done
  if ! curl -fsS "$health_url" >/dev/null 2>&1; then
    fail "Backend health check failed at ${health_url}"
  fi

  info "Waiting for Streamlit frontend"
  for _ in $(seq 1 "$tries"); do
    if curl -fsS "$frontend_url" >/dev/null 2>&1; then
      success "Frontend is reachable"
      return
    fi
    sleep 2
  done
  fail "Frontend check failed at ${frontend_url}"
}

print_summary() {
  cat <<EOF

${COLOR_GREEN}${COLOR_BOLD}Setup complete.${COLOR_RESET}

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
  trap 'on_error $?' ERR

  step "Install system packages"
  install_system_packages
  step "Install uv"
  install_uv
  step "Sync repository"
  sync_repo

  mkdir -p "$DATA_DIR" "$LOG_DIR" "$HF_HOME_DIR"
  success "Workspace directories ready"

  step "Write environment file"
  write_env_file
  step "Install Python dependencies"
  install_dependencies
  step "Start backend"
  start_backend
  step "Start frontend"
  start_frontend
  step "Verify services"
  verify_health
  print_summary
}

main "$@"
