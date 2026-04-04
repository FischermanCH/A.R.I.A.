#!/usr/bin/env bash
set -Eeuo pipefail

TAR_DIR="${TAR_DIR:-/mnt/NAS/aria-images}"
STACK_FILE="${STACK_FILE:-/mnt/NAS/aria-images/portainer-stack.alpha3.local.yml}"
ENV_FILE="${ENV_FILE:-/mnt/NAS/aria-images/aria-stack.env}"
IMAGE_REF="${IMAGE_REF:-aria:alpha-local}"
SERVICE_NAME="${SERVICE_NAME:-aria}"
QDRANT_SERVICE_NAME="${QDRANT_SERVICE_NAME:-aria-qdrant}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1/health}"
COMPOSE_PROJECT_NAME_OVERRIDE="${COMPOSE_PROJECT_NAME_OVERRIDE:-}"

log() {
  printf '[aria-update] %s\n' "$*"
}

die() {
  printf '[aria-update] ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Kommando fehlt: $1"
}

read_env_from_container() {
  local container_name="$1"
  local key="$2"
  docker inspect "$container_name" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
    | sed -n "s/^${key}=//p" \
    | head -n1
}

read_label_from_container() {
  local container_name="$1"
  local label_key="$2"
  docker inspect "$container_name" --format "{{ index .Config.Labels \"$label_key\" }}" 2>/dev/null || true
}

require_cmd docker
docker compose version >/dev/null 2>&1 || die "docker compose ist nicht verfügbar"

[[ -d "$TAR_DIR" ]] || die "TAR-Verzeichnis nicht gefunden: $TAR_DIR"
[[ -f "$STACK_FILE" ]] || die "Stack-Datei nicht gefunden: $STACK_FILE"

LATEST_TAR="$(
  find "$TAR_DIR" -maxdepth 1 -type f -name 'aria-alpha*-local.tar' \
    | sed 's#^.*/##' \
    | awk '
        match($0, /^aria-alpha([0-9]+)-local\.tar$/, m) { printf "%012d %s\n", m[1], $0; next }
        $0 == "aria-alpha-local.tar" { printf "%012d %s\n", 0, $0; next }
      ' \
    | sort \
    | tail -n1 \
    | cut -d' ' -f2- \
    | sed "s#^#$TAR_DIR/#"
)"

[[ -n "$LATEST_TAR" ]] || die "Kein ARIA-TAR in $TAR_DIR gefunden"

OLD_IMAGE_ID="$(docker image inspect "$IMAGE_REF" --format '{{.Id}}' 2>/dev/null || true)"
log "Lade neuestes TAR: $LATEST_TAR"
docker load -i "$LATEST_TAR" >/tmp/aria-docker-load.log
cat /tmp/aria-docker-load.log
rm -f /tmp/aria-docker-load.log

NEW_IMAGE_ID="$(docker image inspect "$IMAGE_REF" --format '{{.Id}}' 2>/dev/null || true)"
log "Image vorher: ${OLD_IMAGE_ID:-<keins>}"
log "Image jetzt:   ${NEW_IMAGE_ID:-<unbekannt>}"

COMPOSE_ARGS=()
if [[ -f "$ENV_FILE" ]]; then
  log "Nutze Env-Datei: $ENV_FILE"
  COMPOSE_ARGS+=(--env-file "$ENV_FILE")
else
  CURRENT_QDRANT_KEY="$(read_env_from_container "$SERVICE_NAME" "ARIA_QDRANT_API_KEY" || true)"
  if [[ -z "$CURRENT_QDRANT_KEY" ]]; then
    CURRENT_QDRANT_KEY="$(read_env_from_container "$QDRANT_SERVICE_NAME" "QDRANT__SERVICE__API_KEY" || true)"
  fi
  if [[ -n "$CURRENT_QDRANT_KEY" ]]; then
    export ARIA_QDRANT_API_KEY="$CURRENT_QDRANT_KEY"
    log "Keine Env-Datei gefunden, nutze vorhandenen Qdrant-Key aus laufendem Container"
  else
    log "Keine Env-Datei und kein bestehender Qdrant-Key gefunden, Compose-Fallback aus dem Stack wird verwendet"
  fi
fi

COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME_OVERRIDE"
if [[ -z "$COMPOSE_PROJECT_NAME" ]]; then
  COMPOSE_PROJECT_NAME="$(read_label_from_container "$SERVICE_NAME" "com.docker.compose.project")"
fi
if [[ -z "$COMPOSE_PROJECT_NAME" ]]; then
  COMPOSE_PROJECT_NAME="$(read_label_from_container "$QDRANT_SERVICE_NAME" "com.docker.compose.project")"
fi
if [[ -n "$COMPOSE_PROJECT_NAME" && "$COMPOSE_PROJECT_NAME" != "<no value>" ]]; then
  COMPOSE_ARGS+=(-p "$COMPOSE_PROJECT_NAME")
  log "Nutze Compose-Projekt: $COMPOSE_PROJECT_NAME"
else
  log "Kein bestehendes Compose-Projektlabel gefunden, nutze Standardprojekt aus aktuellem Pfad"
fi

log "Erstelle nur den Service '$SERVICE_NAME' neu. Qdrant und Volumes bleiben unberuehrt."
docker compose "${COMPOSE_ARGS[@]}" -f "$STACK_FILE" up -d --no-deps --force-recreate "$SERVICE_NAME"

if command -v curl >/dev/null 2>&1; then
  log "Pruefe Health auf $HEALTH_URL"
  for _ in $(seq 1 30); do
    if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
      log "Healthcheck ok"
      exit 0
    fi
    sleep 2
  done
  die "Healthcheck nicht erfolgreich. Bitte 'docker compose -f $STACK_FILE logs $SERVICE_NAME' pruefen."
fi

log "Update fertig. Healthcheck wurde uebersprungen, weil curl nicht installiert ist."
