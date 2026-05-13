#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
REPO_URL="${REPO_URL:-https://github.com/vatsal1306/mistria-ai.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
REPO_DIR="${REPO_DIR:-${WORKSPACE_DIR}/mistria-ai}"
ENV_FILE="${ENV_FILE:-${REPO_DIR}/.env}"

BACKEND_PORT="${BACKEND_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-8501}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-mistria-ai}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
MISTRIA_MODEL_NAME="${MISTRIA_MODEL_NAME:-dphn/Dolphin3.0-Llama3.1-8B}"

OVERWRITE_ENV="${OVERWRITE_ENV:-0}"
SKIP_DOCKER_INSTALL="${SKIP_DOCKER_INSTALL:-0}"
SKIP_GPU_CHECK="${SKIP_GPU_CHECK:-0}"
RUN_SMOKE="${RUN_SMOKE:-0}"
MISTRIA_MEMORY_ENABLED="${MISTRIA_MEMORY_ENABLED:-}"

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

sudo_prefix() {
  if [[ "$(id -u)" -ne 0 ]]; then
    if ! command -v sudo >/dev/null 2>&1; then
      fail "This step needs root privileges. Install sudo or run bootstrap as root."
    fi
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

install_base_packages() {
  require_cmd apt-get
  local prefix
  prefix="$(sudo_prefix)"

  info "Installing base packages"
  ${prefix}apt-get update
  ${prefix}apt-get install -y ca-certificates curl git gnupg make
  success "Base packages are installed"
}

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    success "Docker Engine and Compose plugin are already installed"
    return
  fi

  if [[ "$SKIP_DOCKER_INSTALL" == "1" ]]; then
    fail "Docker Engine or Compose plugin is missing and SKIP_DOCKER_INSTALL=1"
  fi

  require_cmd apt-get
  local prefix
  prefix="$(sudo_prefix)"

  info "Installing Docker Engine and Compose plugin from Docker's apt repository"
  ${prefix}install -m 0755 -d /etc/apt/keyrings

  local distro_id
  local codename
  distro_id="$(. /etc/os-release && printf '%s' "${ID}")"
  codename="$(. /etc/os-release && printf '%s' "${VERSION_CODENAME}")"
  case "$distro_id" in
    ubuntu|debian) ;;
    *) fail "Automatic Docker install supports Ubuntu/Debian only. Install Docker manually or set SKIP_DOCKER_INSTALL=1." ;;
  esac

  curl -fsSL "https://download.docker.com/linux/${distro_id}/gpg" | ${prefix}gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
  ${prefix}chmod a+r /etc/apt/keyrings/docker.gpg

  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu %s stable\n' \
    "$(dpkg --print-architecture)" "$codename" \
    | sed "s#linux/ubuntu#linux/${distro_id}#" \
    | ${prefix}tee /etc/apt/sources.list.d/docker.list >/dev/null

  ${prefix}apt-get update
  ${prefix}apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  success "Docker Engine and Compose plugin are installed"
}

ensure_docker_access() {
  if docker info >/dev/null 2>&1; then
    success "Current user can access Docker"
    return
  fi

  local prefix
  prefix="$(sudo_prefix)"
  if ${prefix}docker info >/dev/null 2>&1; then
    warn "Docker is available through sudo. Adding current user to the docker group for future sessions."
    ${prefix}usermod -aG docker "$USER" || true
    fail "Docker is not available to the current shell without sudo. Log out/in or run bootstrap as root, then rerun."
  fi

  fail "Docker daemon is not reachable. Start Docker and rerun bootstrap."
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

write_env_file() {
  if [[ -f "$ENV_FILE" && "$OVERWRITE_ENV" != "1" ]]; then
    warn "Keeping existing env file at ${ENV_FILE}"
    return
  fi

  prompt_env "MISTRIA_AUTH_ENCRYPTION_KEY" "Enter MISTRIA_AUTH_ENCRYPTION_KEY" 1
  prompt_env "MISTRIA_API_KEY" "Enter MISTRIA_API_KEY" 1

  if [[ -z "${MISTRIA_MEMORY_ENABLED:-}" ]]; then
    read -r -p "Enable memory subsystem and Qdrant? (y/N): " mem_input
    case "${mem_input,,}" in
      y|yes) MISTRIA_MEMORY_ENABLED="1" ;;
      *) MISTRIA_MEMORY_ENABLED="0" ;;
    esac
  fi

  mkdir -p "$(dirname "$ENV_FILE")"
  {
    printf 'MISTRIA_AUTH_ENCRYPTION_KEY=%s\n' "$MISTRIA_AUTH_ENCRYPTION_KEY"
    printf 'MISTRIA_API_KEY=%s\n' "$MISTRIA_API_KEY"
    printf 'MISTRIA_INFERENCE_BACKEND=vllm\n'
    printf 'MISTRIA_INFERENCE_MODEL_NAME=%s\n' "$MISTRIA_MODEL_NAME"
    printf 'MISTRIA_LOG_LEVEL=INFO\n'
    printf 'MISTRIA_BACKEND_PORT=%s\n' "$BACKEND_PORT"
    printf 'MISTRIA_FRONTEND_PORT=%s\n' "$FRONTEND_PORT"
    printf 'COMPOSE_PROJECT_NAME=%s\n' "$COMPOSE_PROJECT_NAME"
    printf 'IMAGE_TAG=%s\n' "$IMAGE_TAG"
    if [[ "$MISTRIA_MEMORY_ENABLED" == "1" || "$MISTRIA_MEMORY_ENABLED" == "true" ]]; then
      printf 'MISTRIA_MEMORY_ENABLED=True\n'
      printf 'COMPOSE_PROFILES=memory\n'
      printf 'MISTRIA_MEMORY_QDRANT_URL=http://qdrant:6333\n'
    fi
    if [[ -n "${HF_TOKEN:-}" ]]; then
      printf 'HF_TOKEN=%s\n' "$HF_TOKEN"
    fi
  } >"$ENV_FILE"

  chmod 600 "$ENV_FILE"
  success "Wrote ${ENV_FILE}"
}

verify_gpu_runtime() {
  if [[ "$SKIP_GPU_CHECK" == "1" ]]; then
    warn "Skipping Docker GPU verification because SKIP_GPU_CHECK=1"
    return
  fi

  require_cmd nvidia-smi
  info "Verifying Docker GPU access"
  docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi >/dev/null
  success "Docker can access the NVIDIA GPU"
}

make_stack() {
  local target="$1"
  (
    cd "$REPO_DIR"
    ENV_FILE="$ENV_FILE" \
    COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" \
    IMAGE_TAG="$IMAGE_TAG" \
    BACKEND_PORT="$BACKEND_PORT" \
    FRONTEND_PORT="$FRONTEND_PORT" \
    make "$target"
  )
}

verify_health() {
  local health_url="http://127.0.0.1:${BACKEND_PORT}/health"
  local frontend_url="http://127.0.0.1:${FRONTEND_PORT}/"
  local tries=90

  info "Waiting for backend vLLM readiness"
  for _ in $(seq 1 "$tries"); do
    if (
      cd "$REPO_DIR"
      ENV_FILE="$ENV_FILE" COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" IMAGE_TAG="$IMAGE_TAG" MISTRIA_BACKEND_PORT="$BACKEND_PORT" MISTRIA_FRONTEND_PORT="$FRONTEND_PORT" \
        docker compose --env-file "$ENV_FILE" exec -T backend \
      python scripts/http_probe.py \
        --url "http://127.0.0.1:8080/health" \
        --expect-json status=ok \
        --expect-json engine_ready=true
    ) >/dev/null 2>&1; then
      success "Backend is ready at ${health_url}"
      break
    fi
    sleep 10
  done

  if ! (
    cd "$REPO_DIR"
    ENV_FILE="$ENV_FILE" COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" IMAGE_TAG="$IMAGE_TAG" MISTRIA_BACKEND_PORT="$BACKEND_PORT" MISTRIA_FRONTEND_PORT="$FRONTEND_PORT" \
      docker compose --env-file "$ENV_FILE" exec -T backend \
        python scripts/http_probe.py \
          --url "http://127.0.0.1:8080/health" \
          --expect-json status=ok \
          --expect-json engine_ready=true
  ) >/dev/null 2>&1; then
    fail "Backend readiness check failed at ${health_url}. Run 'make logs' in ${REPO_DIR} for details."
  fi

  info "Waiting for Streamlit frontend"
  for _ in $(seq 1 30); do
    if curl -fsS "$frontend_url" >/dev/null 2>&1; then
      success "Frontend is reachable at ${frontend_url}"
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
Backend health: http://127.0.0.1:${BACKEND_PORT}/health
Streamlit: http://127.0.0.1:${FRONTEND_PORT}

Useful commands:
  cd ${REPO_DIR}
  make ps
  make logs
  make restart
  make down
EOF
}

main() {
  trap 'on_error $?' ERR

  step "Install base packages"
  install_base_packages
  step "Install Docker"
  install_docker
  step "Verify Docker access"
  ensure_docker_access
  step "Sync repository"
  sync_repo
  step "Write environment file"
  write_env_file
  step "Verify GPU runtime"
  verify_gpu_runtime
  step "Build Docker images"
  make_stack build
  step "Start Docker stack"
  make_stack up
  step "Verify services"
  verify_health

  if [[ "$RUN_SMOKE" == "1" ]]; then
    step "Run smoke test"
    make_stack smoke
  fi

  print_summary
}

main "$@"
