#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_STACK_NAME="aria"
DEFAULT_HTTP_PORT="8800"
DEFAULT_IMAGE="fischermanch/aria:alpha"
DEFAULT_INSTALL_BASE="/opt/aria"

STACK_NAME="$DEFAULT_STACK_NAME"
HTTP_PORT="$DEFAULT_HTTP_PORT"
PUBLIC_URL=""
INSTALL_DIR=""
ARIA_IMAGE="$DEFAULT_IMAGE"
LLM_API_BASE="http://host.docker.internal:11434"
LLM_MODEL="ollama_chat/qwen3:8b"
EMBEDDINGS_API_BASE="http://host.docker.internal:11434"
EMBEDDINGS_MODEL="ollama/nomic-embed-text"
ARIA_QDRANT_API_KEY=""
SEARXNG_SECRET=""
ARIA_UPDATER_TOKEN=""
ARIA_COOKIE_NAMESPACE=""
START_STACK="true"
FORCE="false"
UPGRADE_EXISTING="false"

STACK_NAME_EXPLICIT="false"
HTTP_PORT_EXPLICIT="false"
PUBLIC_URL_EXPLICIT="false"
INSTALL_DIR_EXPLICIT="false"
ARIA_IMAGE_EXPLICIT="false"
LLM_API_BASE_EXPLICIT="false"
LLM_MODEL_EXPLICIT="false"
EMBEDDINGS_API_BASE_EXPLICIT="false"
EMBEDDINGS_MODEL_EXPLICIT="false"
ARIA_QDRANT_API_KEY_EXPLICIT="false"
SEARXNG_SECRET_EXPLICIT="false"
ARIA_UPDATER_TOKEN_EXPLICIT="false"
ARIA_COOKIE_NAMESPACE_EXPLICIT="false"

log() {
  printf '[aria-setup] %s\n' "$*"
}

die() {
  printf '[aria-setup] ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Usage:
  setup-compose-stack.sh [options]

What it does:
  - creates a managed ARIA docker-compose installation under one directory
  - keeps config, prompts, data, qdrant and searxng storage in visible bind mounts
  - writes a local helper ./aria-stack.sh for start/status/update operations
  - serves as the lower-level automation helper behind aria-setup

Options:
  --stack-name NAME           Compose stack name. Default: aria
  --install-dir PATH          Target directory. Default: /opt/aria/<stack-name>
  --http-port PORT            Host port for ARIA. Default: 8800
  --public-url URL            Public/browser URL. Default: http://localhost:<port>
  --aria-image IMAGE          ARIA image tag. Default: fischermanch/aria:alpha
  --llm-api-base URL          Default LLM base URL inside the container
  --llm-model MODEL           Default LLM model
  --embeddings-api-base URL   Default embeddings base URL inside the container
  --embeddings-model MODEL    Default embeddings model
  --qdrant-key VALUE          Explicit Qdrant API key. Default: generated
  --searxng-secret VALUE      Explicit SearXNG secret. Default: generated
  --updater-token VALUE       Explicit token for the managed GUI update helper. Default: generated
  --cookie-namespace VALUE    Explicit browser-cookie namespace. Default: managed:<stack-name>:<port>
  --upgrade-existing          Reuse an existing install dir and keep its current env values unless explicitly overridden
  --no-start                  Only write files, do not start docker compose
  --force                     Overwrite existing stack files in the target dir
  -h, --help                  Show this help

Examples:
  ./docker/setup-compose-stack.sh --stack-name aria-main --public-url http://aria.black.lan:8800
  ./docker/setup-compose-stack.sh --stack-name lab --http-port 8810 --no-start
USAGE
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Kommando fehlt: $1"
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
    docker-compose "$@"
    return 0
  fi
  die "Weder 'docker compose' noch 'docker-compose' ist verfuegbar"
}

generate_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import secrets; print(secrets.token_hex(32))'
    return 0
  fi
  die "Weder openssl noch python3 verfuegbar, kann keinen Secret-Wert erzeugen."
}

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)$port$"
    return $?
  fi
  return 1
}

backup_if_exists() {
  local path="$1"
  [[ -e "$path" ]] || return 0
  mv "$path" "${path}.bak.$(date +%Y%m%d%H%M%S)"
}

read_env_value() {
  local env_file="$1"
  local key="$2"
  sed -n "s/^${key}=//p" "$env_file" | head -n1
}

load_existing_env_defaults() {
  local env_file="$1"
  local value=""

  [[ -f "$env_file" ]] || die "Bestehende Env-Datei nicht gefunden: $env_file"

  if [[ "$STACK_NAME_EXPLICIT" != "true" ]]; then
    value="$(read_env_value "$env_file" "ARIA_STACK_NAME")"
    [[ -n "$value" ]] && STACK_NAME="$value"
  fi
  if [[ "$HTTP_PORT_EXPLICIT" != "true" ]]; then
    value="$(read_env_value "$env_file" "ARIA_HTTP_PORT")"
    [[ -n "$value" ]] && HTTP_PORT="$value"
  fi
  if [[ "$PUBLIC_URL_EXPLICIT" != "true" ]]; then
    value="$(read_env_value "$env_file" "ARIA_PUBLIC_URL")"
    [[ -n "$value" ]] && PUBLIC_URL="$value"
  fi
  if [[ "$ARIA_IMAGE_EXPLICIT" != "true" ]]; then
    value="$(read_env_value "$env_file" "ARIA_IMAGE")"
    [[ -n "$value" ]] && ARIA_IMAGE="$value"
  fi
  if [[ "$LLM_API_BASE_EXPLICIT" != "true" ]]; then
    value="$(read_env_value "$env_file" "ARIA_LLM_API_BASE")"
    [[ -n "$value" ]] && LLM_API_BASE="$value"
  fi
  if [[ "$LLM_MODEL_EXPLICIT" != "true" ]]; then
    value="$(read_env_value "$env_file" "ARIA_LLM_MODEL")"
    [[ -n "$value" ]] && LLM_MODEL="$value"
  fi
  if [[ "$EMBEDDINGS_API_BASE_EXPLICIT" != "true" ]]; then
    value="$(read_env_value "$env_file" "ARIA_EMBEDDINGS_API_BASE")"
    [[ -n "$value" ]] && EMBEDDINGS_API_BASE="$value"
  fi
  if [[ "$EMBEDDINGS_MODEL_EXPLICIT" != "true" ]]; then
    value="$(read_env_value "$env_file" "ARIA_EMBEDDINGS_MODEL")"
    [[ -n "$value" ]] && EMBEDDINGS_MODEL="$value"
  fi
  if [[ "$ARIA_QDRANT_API_KEY_EXPLICIT" != "true" ]]; then
    value="$(read_env_value "$env_file" "ARIA_QDRANT_API_KEY")"
    [[ -n "$value" ]] && ARIA_QDRANT_API_KEY="$value"
  fi
  if [[ "$SEARXNG_SECRET_EXPLICIT" != "true" ]]; then
    value="$(read_env_value "$env_file" "SEARXNG_SECRET")"
    [[ -n "$value" ]] && SEARXNG_SECRET="$value"
  fi
  if [[ "$ARIA_UPDATER_TOKEN_EXPLICIT" != "true" ]]; then
    value="$(read_env_value "$env_file" "ARIA_UPDATER_TOKEN")"
    [[ -n "$value" ]] && ARIA_UPDATER_TOKEN="$value"
  fi
  if [[ "$ARIA_COOKIE_NAMESPACE_EXPLICIT" != "true" ]]; then
    value="$(read_env_value "$env_file" "ARIA_COOKIE_NAMESPACE")"
    [[ -n "$value" ]] && ARIA_COOKIE_NAMESPACE="$value"
  fi
}

write_compose_file() {
  local target="$1"
  cat >"$target" <<'EOF'
name: ${ARIA_STACK_NAME:-aria}

services:
  qdrant:
    image: qdrant/qdrant:latest
    restart: unless-stopped
    environment:
      QDRANT__SERVICE__API_KEY: ${ARIA_QDRANT_API_KEY}
    volumes:
      - ./storage/qdrant-storage:/qdrant/storage

  searxng-valkey:
    image: valkey/valkey:8-alpine
    restart: unless-stopped
    volumes:
      - ./storage/searxng-valkey:/data

  searxng:
    image: searxng/searxng:latest
    restart: unless-stopped
    depends_on:
      - searxng-valkey
    environment:
      FORCE_OWNERSHIP: "false"
      SEARXNG_SECRET: ${SEARXNG_SECRET}
      SEARXNG_LIMITER: "false"
      SEARXNG_VALKEY_URL: "valkey://searxng-valkey:6379/0"
    entrypoint:
      - /bin/sh
      - -lc
      - |
        umask 077
        mkdir -p /etc/searxng
        python - <<'PY'
        import json
        import os
        from pathlib import Path

        secret = os.environ.get("SEARXNG_SECRET", "ultrasecretkey")
        valkey_url = os.environ.get("SEARXNG_VALKEY_URL", "valkey://searxng-valkey:6379/0")
        lines = [
            "use_default_settings: true",
            "",
            "general:",
            '  instance_name: "ARIA Search"',
            "",
            "search:",
            "  safe_search: 1",
            '  autocomplete: ""',
            "  formats:",
            "    - html",
            "    - json",
            "",
            "server:",
            f"  secret_key: {json.dumps(secret)}",
            "  limiter: false",
            "  image_proxy: true",
            "",
            "valkey:",
            f"  url: {json.dumps(valkey_url)}",
            "",
        ]
        Path("/etc/searxng/settings.yml").write_text("\n".join(lines), encoding="utf-8")
        PY
        exec /usr/local/searxng/entrypoint.sh
    volumes:
      - ./storage/searxng-cache:/var/cache/searxng

  aria:
    image: ${ARIA_IMAGE:-fischermanch/aria:alpha}
    restart: unless-stopped
    depends_on:
      - qdrant
      - searxng
    ports:
      - "${ARIA_HTTP_PORT:-8800}:8800"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      ARIA_ARIA_HOST: "0.0.0.0"
      ARIA_ARIA_PORT: "8800"
      ARIA_COOKIE_NAMESPACE: ${ARIA_COOKIE_NAMESPACE:-}
      ARIA_PUBLIC_URL: ${ARIA_PUBLIC_URL:-http://localhost:8800}
      ARIA_QDRANT_URL: http://qdrant:6333
      ARIA_QDRANT_API_KEY: ${ARIA_QDRANT_API_KEY}
      ARIA_UPDATE_MODE: ${ARIA_UPDATE_MODE:-managed-helper}
      ARIA_UPDATER_URL: ${ARIA_UPDATER_URL:-http://aria-updater:8094}
      ARIA_UPDATER_TOKEN: ${ARIA_UPDATER_TOKEN}
      ARIA_LLM_API_BASE: ${ARIA_LLM_API_BASE:-http://host.docker.internal:11434}
      ARIA_LLM_MODEL: ${ARIA_LLM_MODEL:-ollama_chat/qwen3:8b}
      ARIA_EMBEDDINGS_API_BASE: ${ARIA_EMBEDDINGS_API_BASE:-http://host.docker.internal:11434}
      ARIA_EMBEDDINGS_MODEL: ${ARIA_EMBEDDINGS_MODEL:-ollama/nomic-embed-text}
    volumes:
      - ./storage/aria-config:/app/config
      - ./storage/aria-prompts:/app/prompts
      - ./storage/aria-data:/app/data
      - ./storage/qdrant-storage:/qdrant/storage:ro

  aria-updater:
    image: ${ARIA_IMAGE:-fischermanch/aria:alpha}
    restart: unless-stopped
    depends_on:
      - aria
    environment:
      ARIA_UPDATE_TOKEN: ${ARIA_UPDATER_TOKEN}
      ARIA_UPDATE_INSTALL_DIR: /managed
      ARIA_UPDATE_HELPER_PORT: "8094"
      ARIA_UPDATE_HEALTH_URL: http://aria:8800/health
    volumes:
      - ./:/managed
      - /var/run/docker.sock:/var/run/docker.sock
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8094/health', timeout=5)"
      interval: 30s
      timeout: 5s
      start_period: 20s
      retries: 3
    command:
      - python
      - -m
      - aria.update_helper

EOF
}

write_env_file() {
  local target="$1"
  cat >"$target" <<EOF
ARIA_STACK_NAME=$STACK_NAME
ARIA_IMAGE=$ARIA_IMAGE
ARIA_QDRANT_API_KEY=$ARIA_QDRANT_API_KEY
SEARXNG_SECRET=$SEARXNG_SECRET
ARIA_UPDATE_MODE=managed-helper
ARIA_UPDATER_URL=http://aria-updater:8094
ARIA_UPDATER_TOKEN=$ARIA_UPDATER_TOKEN
ARIA_COOKIE_NAMESPACE=$ARIA_COOKIE_NAMESPACE

ARIA_HTTP_PORT=$HTTP_PORT
ARIA_PUBLIC_URL=$PUBLIC_URL

ARIA_LLM_API_BASE=$LLM_API_BASE
ARIA_LLM_MODEL=$LLM_MODEL
ARIA_EMBEDDINGS_API_BASE=$EMBEDDINGS_API_BASE
ARIA_EMBEDDINGS_MODEL=$EMBEDDINGS_MODEL
EOF
}

write_stack_helper() {
  local target="$1"
  cat >"$target" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

STACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$STACK_DIR/docker-compose.yml"
ENV_FILE="$STACK_DIR/.env"

log() {
  printf '[aria-stack] %s\n' "$*"
}

die() {
  printf '[aria-stack] ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Kommando fehlt: $1"
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
    docker-compose "$@"
    return 0
  fi
  die "Weder 'docker compose' noch 'docker-compose' ist verfuegbar"
}

run_compose() {
  compose_cmd --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

health_url() {
  local http_port
  local public_url
  http_port="$(sed -n 's/^ARIA_HTTP_PORT=//p' "$ENV_FILE" | head -n1)"
  if [[ -n "$http_port" ]]; then
    printf 'http://127.0.0.1:%s/health\n' "$http_port"
    return 0
  fi
  public_url="$(sed -n 's/^ARIA_PUBLIC_URL=//p' "$ENV_FILE" | head -n1)"
  if [[ -n "$public_url" ]]; then
    printf '%s/health\n' "${public_url%/}"
    return 0
  fi
  printf 'http://127.0.0.1:8800/health\n'
}

wait_for_health() {
  local url
  local idx
  url="$(health_url)"
  if ! command -v curl >/dev/null 2>&1; then
    log "curl nicht vorhanden, ueberspringe Healthcheck."
    return 0
  fi
  for idx in $(seq 1 45); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log "Health ok: $url"
      return 0
    fi
    sleep 2
  done
  die "Healthcheck nicht erfolgreich: $url"
}

runtime_update_services() {
  local services=("aria")
  local line=""
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    if [[ "$line" == "aria-updater" ]]; then
      services+=("aria-updater")
      break
    fi
  done < <(run_compose config --services 2>/dev/null || true)
  printf '%s\n' "${services[@]}"
}

usage() {
  cat <<'USAGE'
Usage:
  ./aria-stack.sh up
  ./aria-stack.sh down
  ./aria-stack.sh stop
  ./aria-stack.sh restart
  ./aria-stack.sh ps
  ./aria-stack.sh logs [service]
  ./aria-stack.sh config
  ./aria-stack.sh health
  ./aria-stack.sh pull
  ./aria-stack.sh pull-all
  ./aria-stack.sh update
  ./aria-stack.sh update-all
USAGE
}

main() {
  require_cmd docker
  compose_cmd version >/dev/null 2>&1
  [[ -f "$COMPOSE_FILE" ]] || die "Compose-Datei nicht gefunden: $COMPOSE_FILE"
  [[ -f "$ENV_FILE" ]] || die "Env-Datei nicht gefunden: $ENV_FILE"

  local command="${1:-ps}"
  local runtime_services=()
  shift || true

  readarray -t runtime_services < <(runtime_update_services)
  if [[ "${#runtime_services[@]}" -eq 0 ]]; then
    runtime_services=("aria")
  fi

  case "$command" in
    up|start)
      run_compose up -d
      wait_for_health
      ;;
    stop)
      run_compose stop
      ;;
    down)
      run_compose down
      ;;
    restart)
      run_compose up -d --no-deps --force-recreate "${runtime_services[@]}"
      wait_for_health
      ;;
    ps|status)
      run_compose ps
      ;;
    logs)
      run_compose logs -f "${1:-aria}"
      ;;
    config)
      run_compose config
      ;;
    health)
      wait_for_health
      ;;
    pull)
      run_compose pull "${runtime_services[@]}"
      ;;
    pull-all)
      run_compose pull
      ;;
    update)
      run_compose pull "${runtime_services[@]}"
      run_compose up -d --no-deps --force-recreate "${runtime_services[@]}"
      wait_for_health
      ;;
    update-all)
      run_compose pull
      run_compose up -d
      wait_for_health
      ;;
    -h|--help|help)
      usage
      ;;
    *)
      die "Unbekanntes Kommando: $command"
      ;;
  esac
}

main "$@"
EOF
}

write_install_readme() {
  local target="$1"
  cat >"$target" <<EOF
ARIA managed compose stack
=========================

Stack name: $STACK_NAME
Install dir: $INSTALL_DIR
Public URL: $PUBLIC_URL
HTTP port: $HTTP_PORT
Image: $ARIA_IMAGE

Common commands:
  cd $INSTALL_DIR
  ./aria-stack.sh ps
  ./aria-stack.sh logs
  ./aria-stack.sh update
  ./aria-stack.sh update-all
  aria-setup upgrade --install-dir $INSTALL_DIR
  ./aria-stack.sh health

Managed GUI update:
  - on managed installs the admin page /updates can trigger the same controlled stack refresh
  - helper state and logs live under $INSTALL_DIR/.aria-updater/

Persistent data lives under:
  $INSTALL_DIR/storage/
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stack-name)
      STACK_NAME="${2:-}"
      STACK_NAME_EXPLICIT="true"
      shift 2
      ;;
    --install-dir)
      INSTALL_DIR="${2:-}"
      INSTALL_DIR_EXPLICIT="true"
      shift 2
      ;;
    --http-port)
      HTTP_PORT="${2:-}"
      HTTP_PORT_EXPLICIT="true"
      shift 2
      ;;
    --public-url)
      PUBLIC_URL="${2:-}"
      PUBLIC_URL_EXPLICIT="true"
      shift 2
      ;;
    --aria-image)
      ARIA_IMAGE="${2:-}"
      ARIA_IMAGE_EXPLICIT="true"
      shift 2
      ;;
    --llm-api-base)
      LLM_API_BASE="${2:-}"
      LLM_API_BASE_EXPLICIT="true"
      shift 2
      ;;
    --llm-model)
      LLM_MODEL="${2:-}"
      LLM_MODEL_EXPLICIT="true"
      shift 2
      ;;
    --embeddings-api-base)
      EMBEDDINGS_API_BASE="${2:-}"
      EMBEDDINGS_API_BASE_EXPLICIT="true"
      shift 2
      ;;
    --embeddings-model)
      EMBEDDINGS_MODEL="${2:-}"
      EMBEDDINGS_MODEL_EXPLICIT="true"
      shift 2
      ;;
    --qdrant-key)
      ARIA_QDRANT_API_KEY="${2:-}"
      ARIA_QDRANT_API_KEY_EXPLICIT="true"
      shift 2
      ;;
    --searxng-secret)
      SEARXNG_SECRET="${2:-}"
      SEARXNG_SECRET_EXPLICIT="true"
      shift 2
      ;;
    --updater-token)
      ARIA_UPDATER_TOKEN="${2:-}"
      ARIA_UPDATER_TOKEN_EXPLICIT="true"
      shift 2
      ;;
    --cookie-namespace)
      ARIA_COOKIE_NAMESPACE="${2:-}"
      ARIA_COOKIE_NAMESPACE_EXPLICIT="true"
      shift 2
      ;;
    --upgrade-existing)
      UPGRADE_EXISTING="true"
      shift
      ;;
    --no-start)
      START_STACK="false"
      shift
      ;;
    --force)
      FORCE="true"
      shift
      ;;
    -h|--help|help)
      usage
      exit 0
      ;;
    *)
      die "Unbekannte Option: $1"
      ;;
  esac
done

require_cmd docker
compose_cmd version >/dev/null 2>&1

[[ -n "$STACK_NAME" ]] || die "--stack-name darf nicht leer sein"
[[ "$HTTP_PORT" =~ ^[0-9]+$ ]] || die "--http-port muss numerisch sein"
if [[ -z "$INSTALL_DIR" ]]; then
  INSTALL_DIR="$DEFAULT_INSTALL_BASE/$STACK_NAME"
fi
if [[ "$UPGRADE_EXISTING" == "true" ]]; then
  [[ -d "$INSTALL_DIR" ]] || die "Bestehendes Installationsverzeichnis nicht gefunden: $INSTALL_DIR"
  load_existing_env_defaults "$INSTALL_DIR/.env"
fi
[[ "$HTTP_PORT" =~ ^[0-9]+$ ]] || die "--http-port muss numerisch sein"
if [[ -z "$PUBLIC_URL" ]]; then
  PUBLIC_URL="http://localhost:$HTTP_PORT"
fi
if [[ -z "$ARIA_QDRANT_API_KEY" ]]; then
  ARIA_QDRANT_API_KEY="$(generate_secret)"
fi
if [[ -z "$SEARXNG_SECRET" ]]; then
  SEARXNG_SECRET="$(generate_secret)"
fi
if [[ -z "$ARIA_UPDATER_TOKEN" ]]; then
  ARIA_UPDATER_TOKEN="$(generate_secret)"
fi
if [[ -z "$ARIA_COOKIE_NAMESPACE" ]]; then
  ARIA_COOKIE_NAMESPACE="managed:${STACK_NAME}:${HTTP_PORT}"
fi

if [[ -e "$INSTALL_DIR/docker-compose.yml" && "$FORCE" != "true" && "$UPGRADE_EXISTING" != "true" ]]; then
  die "Im Zielverzeichnis existiert bereits ein Stack. Fuer bewusstes Ueberschreiben --force verwenden: $INSTALL_DIR"
fi

if [[ "$START_STACK" == "true" && "$UPGRADE_EXISTING" != "true" ]] && port_in_use "$HTTP_PORT"; then
  die "Host-Port $HTTP_PORT ist bereits belegt. Bitte --http-port anpassen."
fi

log "Installationsverzeichnis: $INSTALL_DIR"
log "Stack-Name: $STACK_NAME"
log "Public URL: $PUBLIC_URL"
log "Image: $ARIA_IMAGE"
if [[ "$UPGRADE_EXISTING" == "true" ]]; then
  log "Modus: Upgrade bestehender Installation"
fi

mkdir -p \
  "$INSTALL_DIR" \
  "$INSTALL_DIR/storage/aria-config" \
  "$INSTALL_DIR/storage/aria-prompts" \
  "$INSTALL_DIR/storage/aria-data" \
  "$INSTALL_DIR/storage/qdrant-storage" \
  "$INSTALL_DIR/storage/searxng-cache" \
  "$INSTALL_DIR/storage/searxng-valkey"

if [[ "$FORCE" == "true" || "$UPGRADE_EXISTING" == "true" ]]; then
  backup_if_exists "$INSTALL_DIR/docker-compose.yml"
  backup_if_exists "$INSTALL_DIR/.env"
  backup_if_exists "$INSTALL_DIR/aria-stack.sh"
  backup_if_exists "$INSTALL_DIR/INSTALL.txt"
fi

write_compose_file "$INSTALL_DIR/docker-compose.yml"
write_env_file "$INSTALL_DIR/.env"
write_stack_helper "$INSTALL_DIR/aria-stack.sh"
write_install_readme "$INSTALL_DIR/INSTALL.txt"

chmod 600 "$INSTALL_DIR/.env"
chmod +x "$INSTALL_DIR/aria-stack.sh"

log "Pruefe Compose-Konfiguration"
compose_cmd --env-file "$INSTALL_DIR/.env" -f "$INSTALL_DIR/docker-compose.yml" config -q >/dev/null

if [[ "$START_STACK" == "true" ]]; then
  log "Starte den Stack"
  compose_cmd --env-file "$INSTALL_DIR/.env" -f "$INSTALL_DIR/docker-compose.yml" up -d
  "$INSTALL_DIR/aria-stack.sh" health >/dev/null
  log "ARIA ist erreichbar: $PUBLIC_URL"
else
  log "Stack-Dateien geschrieben, Start uebersprungen (--no-start)"
fi

cat <<EOF

ARIA managed compose setup bereit.

Verzeichnis:
  $INSTALL_DIR

Wichtige Befehle:
  cd $INSTALL_DIR
  ./aria-stack.sh ps
  ./aria-stack.sh logs
  ./aria-stack.sh update
  aria-setup upgrade --install-dir $INSTALL_DIR
  ./aria-stack.sh health

Im Browser:
  $PUBLIC_URL

Persistente Daten:
  $INSTALL_DIR/storage/
EOF
