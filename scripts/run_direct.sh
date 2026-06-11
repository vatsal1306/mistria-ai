#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_DIR}/.env}"
RUN_DIR="${RUN_DIR:-${REPO_DIR}/run}"
LOG_DIR="${LOG_DIR:-${RUN_DIR}/logs}"
BACKEND_PID_FILE="${RUN_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUN_DIR}/frontend.pid"
BACKEND_PORT="${BACKEND_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-8501}"

load_env() {
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi

  BACKEND_PORT="${MISTRIA_API_PORT:-${MISTRIA_BACKEND_PORT:-$BACKEND_PORT}}"
  FRONTEND_PORT="${MISTRIA_FRONTEND_PORT:-$FRONTEND_PORT}"
  mkdir -p "$RUN_DIR" "$LOG_DIR" "${REPO_DIR}/data/db" "${REPO_DIR}/Logs"
}

python_bin() {
  if [[ -x "${REPO_DIR}/.venv/bin/python" ]]; then
    printf '%s\n' "${REPO_DIR}/.venv/bin/python"
    return
  fi
  command -v python3 || command -v python
}

streamlit_bin() {
  if [[ -x "${REPO_DIR}/.venv/bin/streamlit" ]]; then
    printf '%s\n' "${REPO_DIR}/.venv/bin/streamlit"
    return
  fi
  command -v streamlit
}

is_running() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file")"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

start_backend() {
  if is_running "$BACKEND_PID_FILE"; then
    printf '[OK] Backend already running pid=%s\n' "$(cat "$BACKEND_PID_FILE")"
    return
  fi

  local py
  py="$(python_bin)"
  printf '[INFO] Starting backend on 0.0.0.0:%s\n' "$BACKEND_PORT"
  cd "$REPO_DIR"
  env MISTRIA_API_HOST=0.0.0.0 MISTRIA_API_PORT="$BACKEND_PORT" \
    "$py" main.py >"${LOG_DIR}/backend.log" 2>&1 &
  printf '%s\n' "$!" >"$BACKEND_PID_FILE"
}

start_frontend() {
  if is_running "$FRONTEND_PID_FILE"; then
    printf '[OK] Frontend already running pid=%s\n' "$(cat "$FRONTEND_PID_FILE")"
    return
  fi

  local streamlit
  streamlit="$(streamlit_bin)"
  printf '[INFO] Starting Streamlit on 0.0.0.0:%s\n' "$FRONTEND_PORT"
  cd "$REPO_DIR"
  env MISTRIA_API_HOST=127.0.0.1 MISTRIA_API_PORT="$BACKEND_PORT" \
    "$streamlit" run streamlit_app.py \
      --server.address=0.0.0.0 \
      --server.port="$FRONTEND_PORT" \
      --server.headless=true \
      >"${LOG_DIR}/frontend.log" 2>&1 &
  printf '%s\n' "$!" >"$FRONTEND_PID_FILE"
}

stop_process() {
  local name="$1"
  local pid_file="$2"
  if ! is_running "$pid_file"; then
    printf '[OK] %s is not running\n' "$name"
    rm -f "$pid_file"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  printf '[INFO] Stopping %s pid=%s\n' "$name" "$pid"
  kill "$pid"
  for _ in $(seq 1 20); do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      rm -f "$pid_file"
      return
    fi
    sleep 0.5
  done

  printf '[WARN] %s did not exit cleanly; sending SIGKILL\n' "$name"
  kill -9 "$pid" >/dev/null 2>&1 || true
  rm -f "$pid_file"
}

status_process() {
  local name="$1"
  local pid_file="$2"
  if is_running "$pid_file"; then
    printf '[OK] %s running pid=%s\n' "$name" "$(cat "$pid_file")"
  else
    printf '[FAIL] %s not running\n' "$name"
  fi
}

health() {
  local py
  py="$(python_bin)"
  "$py" scripts/http_probe.py --url "http://127.0.0.1:${BACKEND_PORT}/health" --expect-json status=ok
  "$py" scripts/http_probe.py --url "http://127.0.0.1:${FRONTEND_PORT}/" --expected-status 200
}

logs() {
  touch "${LOG_DIR}/backend.log" "${LOG_DIR}/frontend.log"
  tail -n 80 -f "${LOG_DIR}/backend.log" "${LOG_DIR}/frontend.log"
}

usage() {
  cat <<EOF
Usage: bash scripts/run_direct.sh <command>

Commands:
  start     Start backend and Streamlit
  stop      Stop backend and Streamlit
  restart   Restart backend and Streamlit
  status    Show process status
  health    Probe backend and frontend
  logs      Follow backend and frontend logs
EOF
}

main() {
  load_env
  case "${1:-}" in
    start)
      start_backend
      start_frontend
      ;;
    stop)
      stop_process "frontend" "$FRONTEND_PID_FILE"
      stop_process "backend" "$BACKEND_PID_FILE"
      ;;
    restart)
      "$0" stop
      "$0" start
      ;;
    status)
      status_process "backend" "$BACKEND_PID_FILE"
      status_process "frontend" "$FRONTEND_PID_FILE"
      ;;
    health)
      health
      ;;
    logs)
      logs
      ;;
    *)
      usage
      exit 2
      ;;
  esac
}

main "$@"
