#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
UVICORN_BIN="${VENV_DIR}/bin/uvicorn"
PYTHON_BIN="${VENV_DIR}/bin/python"
CONFIG_FILE="${ROOT_DIR}/config/config.yaml"
SECRETS_ENV_FILE="${ROOT_DIR}/config/secrets.env"
LOG_DIR="${ROOT_DIR}/data/logs"
LOG_FILE="${LOG_DIR}/uvicorn.log"
PID_FILE="${LOG_DIR}/aria.pid"
LOCK_DIR="${LOG_DIR}/aria.lock"
CRON_MARKER_START="# ARIA_AUTOSTART_START"
CRON_MARKER_END="# ARIA_AUTOSTART_END"

mkdir -p "${LOG_DIR}"

if [[ -f "${SECRETS_ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "${SECRETS_ENV_FILE}"
  set +a
fi

if [[ ! -x "${UVICORN_BIN}" ]]; then
  echo "Fehler: ${UVICORN_BIN} nicht gefunden oder nicht ausfuehrbar."
  exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Fehler: ${PYTHON_BIN} nicht gefunden oder nicht ausfuehrbar."
  exit 1
fi

read_config_value() {
  local key="$1"
  "${PYTHON_BIN}" - "${CONFIG_FILE}" "${key}" <<'PY'
import sys
from pathlib import Path
import yaml

config_path = Path(sys.argv[1])
key = sys.argv[2]

data = {}
if config_path.exists():
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

value = data
for part in key.split("."):
    if not isinstance(value, dict):
        value = ""
        break
    value = value.get(part, "")

if value is None:
    value = ""

print(value)
PY
}

HOST="${ARIA_ARIA_HOST:-$(read_config_value "aria.host")}"
PORT="${ARIA_ARIA_PORT:-$(read_config_value "aria.port")}"

if [[ -z "${HOST}" ]]; then
  HOST="0.0.0.0"
fi

if [[ -z "${PORT}" ]]; then
  PORT="8800"
fi

resolve_public_host() {
  "${PYTHON_BIN}" - <<'PY'
import socket

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(("8.8.8.8", 80))
    print(sock.getsockname()[0])
    sock.close()
except OSError:
    print("127.0.0.1")
PY
}

health_url() {
  echo "http://127.0.0.1:${PORT}/health"
}

app_url() {
  local public_host="${HOST}"
  if [[ "${public_host}" == "0.0.0.0" || "${public_host}" == "127.0.0.1" || "${public_host}" == "localhost" ]]; then
    public_host="$(resolve_public_host)"
  fi
  echo "http://${public_host}:${PORT}"
}

process_pid() {
  if [[ -f "${PID_FILE}" ]]; then
    local pid
    pid="$(cat "${PID_FILE}")"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      if pid_matches_aria "${pid}"; then
        echo "${pid}"
        return 0
      fi
      rm -f "${PID_FILE}"
    fi
  fi

  local detected
  detected="$(list_process_pids | head -n 1)"
  if [[ -n "${detected}" ]]; then
    echo "${detected}" > "${PID_FILE}"
    if [[ -r "/proc/${detected}/cmdline" ]] && tr '\0' ' ' < "/proc/${detected}/cmdline" | grep -q "uvicorn aria.main:app"; then
      echo "${detected}"
      return 0
    fi
  fi

  return 1
}

list_process_pids() {
  if command -v pgrep >/dev/null 2>&1; then
    # Prefer pgrep because it is not affected by ps output width/truncation.
    pgrep -f '/uvicorn aria.main:app' 2>/dev/null | sort -u || true
    return 0
  fi
  ps -eo pid=,args=ww | awk '$0 ~ /\/uvicorn aria\.main:app/ {print $1}' | sort -u
}

pid_matches_aria() {
  local pid="$1"
  [[ -n "${pid}" ]] || return 1
  kill -0 "${pid}" 2>/dev/null || return 1

  # First choice: ps for portability and to avoid hard dependency on /proc.
  if ps -p "${pid}" -o args=ww 2>/dev/null | grep -q '/uvicorn aria.main:app'; then
    return 0
  fi

  # Fallback for environments where ps formatting is odd.
  if [[ -r "/proc/${pid}/cmdline" ]] && tr '\0' ' ' < "/proc/${pid}/cmdline" | grep -q 'uvicorn aria.main:app'; then
    return 0
  fi

  return 1
}

with_lock() {
  local max_wait_seconds=20
  local waited=0
  while ! mkdir "${LOCK_DIR}" 2>/dev/null; do
    sleep 1
    waited=$((waited + 1))
    if [[ "${waited}" -ge "${max_wait_seconds}" ]]; then
      echo "Fehler: Konnte Lock nicht erhalten (${LOCK_DIR})."
      return 1
    fi
  done
  trap 'rmdir "${LOCK_DIR}" >/dev/null 2>&1 || true' RETURN
  "$@"
}

is_running() {
  process_pid >/dev/null 2>&1
}

wait_for_health() {
  local tries=20
  local url
  url="$(health_url)"
  for _ in $(seq 1 "${tries}"); do
    if is_running && curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

start_background() {
  if is_running; then
    echo "ARIA laeuft bereits mit PID $(process_pid)."
    echo "URL: $(app_url)"
    return 0
  fi

  with_lock _start_background_locked || return 1

  if wait_for_health; then
    # Short settle window: avoid reporting "started" if process dies immediately after first health.
    sleep 1
    if ! is_running; then
      echo "ARIA wurde gestartet, ist aber direkt wieder beendet."
      echo "Log-Auszug:"
      tail -n 40 "${LOG_FILE}" 2>/dev/null || true
      exit 1
    fi
    echo "ARIA gestartet."
    echo "PID: $(process_pid)"
    echo "URL: $(app_url)"
    echo "Log: ${LOG_FILE}"
    return 0
  fi

  echo "ARIA konnte nicht gestartet werden."
  echo "Log-Auszug:"
  tail -n 40 "${LOG_FILE}" 2>/dev/null || true
  exit 1
}

_start_background_locked() {
  if is_running; then
    echo "ARIA laeuft bereits mit PID $(process_pid)."
    echo "URL: $(app_url)"
    return 0
  fi

  (
    cd "${ROOT_DIR}"
    if command -v setsid >/dev/null 2>&1; then
      nohup setsid "${UVICORN_BIN}" aria.main:app --host "${HOST}" --port "${PORT}" </dev/null > "${LOG_FILE}" 2>&1 &
    else
      nohup "${UVICORN_BIN}" aria.main:app --host "${HOST}" --port "${PORT}" </dev/null > "${LOG_FILE}" 2>&1 &
    fi
    echo $! > "${PID_FILE}"
  )
}

start_foreground() {
  if is_running; then
    echo "ARIA laeuft bereits mit PID $(process_pid)."
    echo "Stoppe den laufenden Prozess zuerst oder nutze './aria.sh restart'."
    exit 1
  fi

  cd "${ROOT_DIR}"
  exec "${UVICORN_BIN}" aria.main:app --host "${HOST}" --port "${PORT}"
}

stop_app() {
  with_lock _stop_app_locked
}

_stop_app_locked() {
  local pids pid
  pids="$(list_process_pids | tr '\n' ' ')"
  if [[ -z "${pids// }" ]]; then
    echo "ARIA laeuft nicht."
    rm -f "${PID_FILE}"
    return 0
  fi

  for pid in ${pids}; do
    kill "${pid}" 2>/dev/null || true
  done

  for _ in $(seq 1 12); do
    if [[ -z "$(list_process_pids | tr '\n' ' ' | xargs echo -n 2>/dev/null)" ]]; then
      rm -f "${PID_FILE}"
      echo "ARIA gestoppt."
      return 0
    fi
    sleep 1
  done

  for pid in ${pids}; do
    kill -9 "${pid}" 2>/dev/null || true
  done
  rm -f "${PID_FILE}"
  echo "ARIA hart gestoppt."
}

status_app() {
  if is_running; then
    echo "ARIA laeuft."
    echo "PID: $(process_pid)"
    echo "URL: $(app_url)"
    echo "Health: $(health_url)"
    return 0
  fi

  # Fallback: service can be reachable even if PID detection fails.
  if curl -fsS "$(health_url)" >/dev/null 2>&1; then
    echo "ARIA antwortet auf Health, aber PID konnte nicht eindeutig ermittelt werden."
    echo "URL: $(app_url)"
    echo "Health: $(health_url)"
    return 0
  fi

  echo "ARIA laeuft nicht."
  return 1
}

show_logs() {
  if [[ ! -f "${LOG_FILE}" ]]; then
    echo "Noch kein Log vorhanden: ${LOG_FILE}"
    exit 0
  fi

  if [[ "${1:-}" == "--follow" ]]; then
    tail -f "${LOG_FILE}"
  else
    tail -n 80 "${LOG_FILE}"
  fi
}

show_help() {
  cat <<EOF
ARIA Starter

Verwendung:
  ./aria.sh start
  ./aria.sh start --foreground
  ./aria.sh stop
  ./aria.sh restart
  ./aria.sh status
  ./aria.sh health
  ./aria.sh logs
  ./aria.sh logs --follow
  ./aria.sh url
  ./aria.sh maintenance
  ./aria.sh secure-migrate
  ./aria.sh user-admin <args>
  ./aria.sh autostart-status
  ./aria.sh autostart-install
  ./aria.sh autostart-remove

Konfiguration:
  Host und Port werden aus config/config.yaml gelesen.
  ENV-Overrides:
    ARIA_ARIA_HOST
    ARIA_ARIA_PORT
EOF
}

run_maintenance() {
  cd "${ROOT_DIR}"
  "${PYTHON_BIN}" -m aria.core.maintenance
}

run_secure_migrate() {
  cd "${ROOT_DIR}"
  "${PYTHON_BIN}" -m aria.core.secure_migrate
}

run_user_admin() {
  shift || true
  cd "${ROOT_DIR}"
  "${PYTHON_BIN}" -m aria.core.user_admin "$@"
}

_crontab_dump_without_aria_block() {
  local source_file="$1"
  awk -v start="${CRON_MARKER_START}" -v end="${CRON_MARKER_END}" '
    $0 == start {skip=1; next}
    $0 == end {skip=0; next}
    skip != 1 {print}
  ' "${source_file}"
}

_crontab_current_to_file() {
  local dest_file="$1"
  if crontab -l >/dev/null 2>&1; then
    crontab -l > "${dest_file}"
  else
    : > "${dest_file}"
  fi
}

autostart_status() {
  local tmp
  tmp="$(mktemp)"
  _crontab_current_to_file "${tmp}"
  if grep -q "^${CRON_MARKER_START}\$" "${tmp}" && grep -q "^${CRON_MARKER_END}\$" "${tmp}"; then
    echo "Autostart: aktiv"
    awk -v start="${CRON_MARKER_START}" -v end="${CRON_MARKER_END}" '
      $0 == start {print "Eintraege:"; show=1; next}
      $0 == end {show=0; next}
      show == 1 {print "  " $0}
    ' "${tmp}"
  else
    echo "Autostart: nicht aktiv"
  fi
  rm -f "${tmp}"
}

autostart_install() {
  local tmp_current tmp_clean tmp_new
  tmp_current="$(mktemp)"
  tmp_clean="$(mktemp)"
  tmp_new="$(mktemp)"

  _crontab_current_to_file "${tmp_current}"
  _crontab_dump_without_aria_block "${tmp_current}" > "${tmp_clean}"

  cat > "${tmp_new}" <<EOF
${CRON_MARKER_START}
@reboot cd ${ROOT_DIR} && ./aria.sh start >${LOG_DIR}/cron-start.log 2>&1
* * * * * cd ${ROOT_DIR} && ./aria.sh start >${LOG_DIR}/cron-ensure.log 2>&1
17 3 * * * cd ${ROOT_DIR} && ./aria.sh maintenance >${LOG_DIR}/cron-maintenance.log 2>&1
${CRON_MARKER_END}
EOF

  if [[ -s "${tmp_clean}" ]]; then
    cat "${tmp_clean}" >> "${tmp_new}"
  fi

  crontab "${tmp_new}"
  rm -f "${tmp_current}" "${tmp_clean}" "${tmp_new}"
  echo "Autostart installiert."
  autostart_status
}

autostart_remove() {
  local tmp_current tmp_clean
  tmp_current="$(mktemp)"
  tmp_clean="$(mktemp)"

  _crontab_current_to_file "${tmp_current}"
  _crontab_dump_without_aria_block "${tmp_current}" > "${tmp_clean}"

  if [[ -s "${tmp_clean}" ]]; then
    crontab "${tmp_clean}"
  else
    crontab -r 2>/dev/null || true
  fi

  rm -f "${tmp_current}" "${tmp_clean}"
  echo "Autostart entfernt."
  autostart_status
}

COMMAND="${1:-start}"
ARGUMENT="${2:-}"

case "${COMMAND}" in
  start)
    if [[ "${ARGUMENT}" == "--foreground" ]]; then
      start_foreground
    else
      start_background
    fi
    ;;
  stop)
    stop_app
    ;;
  restart)
    stop_app
    start_background
    ;;
  status)
    status_app
    ;;
  health)
    curl -fsS "$(health_url)" && echo
    ;;
  logs)
    show_logs "${ARGUMENT}"
    ;;
  url)
    app_url
    ;;
  maintenance)
    run_maintenance
    ;;
  secure-migrate)
    run_secure_migrate
    ;;
  user-admin)
    run_user_admin "$@"
    ;;
  autostart-status)
    autostart_status
    ;;
  autostart-install)
    autostart_install
    ;;
  autostart-remove)
    autostart_remove
    ;;
  help|-h|--help)
    show_help
    ;;
  *)
    echo "Unbekannter Befehl: ${COMMAND}"
    echo
    show_help
    exit 1
    ;;
esac
