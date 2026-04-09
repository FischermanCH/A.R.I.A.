#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_NAS_DIR="/mnt/NAS/aria-images"
DEFAULT_FALLBACK_DIR="$HOME/aria-images"
DEFAULT_LOCAL_DIR="$DEFAULT_NAS_DIR"

if [[ ! -d "$DEFAULT_LOCAL_DIR" ]]; then
  DEFAULT_LOCAL_DIR="$DEFAULT_FALLBACK_DIR"
fi

LOCAL_DIR="${LOCAL_DIR:-$DEFAULT_LOCAL_DIR}"
LOCAL_PULL_ENV_FILE="${LOCAL_PULL_ENV_FILE:-$LOCAL_DIR/aria-pull.env}"

if [[ -f "$LOCAL_PULL_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$LOCAL_PULL_ENV_FILE"
fi

DEV_SSH="${DEV_SSH:-}"
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/aria_dev_pull}"
REMOTE_BASE_DIR="${REMOTE_BASE_DIR:-/home/aria/ARIA}"
LOCAL_UPDATE_SCRIPT="${LOCAL_UPDATE_SCRIPT:-$LOCAL_DIR/update-local-aria.sh}"
REMOTE_ARTIFACT_DIR="${REMOTE_ARTIFACT_DIR:-/mnt/NAS/aria-images}"
REMOTE_DIST_DIR="${REMOTE_DIST_DIR:-$REMOTE_BASE_DIR/dist}"
REMOTE_DOCKER_DIR="${REMOTE_DOCKER_DIR:-$REMOTE_BASE_DIR/docker}"
REMOTE_SAMPLES_DIR="${REMOTE_SAMPLES_DIR:-$REMOTE_BASE_DIR/samples}"

log() {
  printf '[aria-pull] %s\n' "$*"
}

die() {
  printf '[aria-pull] ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Kommando fehlt: $1"
}

copy_file() {
  local remote_path="$1"
  local local_path="$2"
  if command -v rsync >/dev/null 2>&1; then
    rsync -av -e "ssh -i $SSH_KEY_PATH" "$DEV_SSH:$remote_path" "$local_path"
  else
    scp -i "$SSH_KEY_PATH" "$DEV_SSH:$remote_path" "$local_path"
  fi
}

copy_dir() {
  local remote_path="$1"
  local local_path="$2"
  mkdir -p "$local_path"
  if command -v rsync >/dev/null 2>&1; then
    rsync -av --delete -e "ssh -i $SSH_KEY_PATH" "$DEV_SSH:$remote_path/" "$local_path/"
  else
    scp -i "$SSH_KEY_PATH" -r "$DEV_SSH:$remote_path" "$local_path"
  fi
}

require_cmd ssh
[[ -n "${DEV_SSH}" ]] || die "DEV_SSH ist nicht gesetzt. Lege $LOCAL_PULL_ENV_FILE mit DEV_SSH=<dev-user>@<dev-host> an oder setze DEV_SSH direkt."
require_cmd scp
[[ -f "$SSH_KEY_PATH" ]] || die "SSH-Key nicht gefunden: $SSH_KEY_PATH"
mkdir -p "$LOCAL_DIR"

if [[ "$LOCAL_DIR" == "$DEFAULT_FALLBACK_DIR" ]]; then
  log "NAS-Pfad nicht gefunden, nutze lokalen Fallback: $LOCAL_DIR"
else
  log "Nutze Artefaktverzeichnis: $LOCAL_DIR"
fi

LATEST_REMOTE_TAR="$(
  ssh -i "$SSH_KEY_PATH" "$DEV_SSH" "artifact_dir=''; \
    if [ -d '$REMOTE_ARTIFACT_DIR' ]; then artifact_dir='$REMOTE_ARTIFACT_DIR'; \
    elif [ -d '$REMOTE_DIST_DIR' ]; then artifact_dir='$REMOTE_DIST_DIR'; fi; \
    [ -n \"\$artifact_dir\" ] || exit 0; \
    find \"\$artifact_dir\" -maxdepth 1 -type f -name 'aria-alpha*-local.tar' | sed 's#^.*/##' | awk '
      \$0 == \"aria-alpha-local.tar\" { printf \"%012d %s\\n\", 0, \$0; next }
      \$0 ~ /^aria-alpha[0-9]+-local\\.tar$/ {
        version = \$0
        sub(/^aria-alpha/, \"\", version)
        sub(/-local\\.tar$/, \"\", version)
        printf \"%012d %s\\n\", version + 0, \$0
        next
      }
    ' | sort | tail -n1 | cut -d' ' -f2- | sed \"s#^#\$artifact_dir/#\""
)"

[[ -n "$LATEST_REMOTE_TAR" ]] || die "Kein ARIA-TAR auf dem Dev-Host gefunden"

log "Hole neuestes TAR vom Dev-Host: $LATEST_REMOTE_TAR"
copy_file "$LATEST_REMOTE_TAR" "$LOCAL_DIR/"

log "Hole Stack-Datei"
copy_file "$REMOTE_DOCKER_DIR/portainer-stack.alpha3.local.yml" "$LOCAL_DIR/"
copy_file "$REMOTE_BASE_DIR/docker-compose.managed.yml" "$LOCAL_DIR/"

log "Hole lokales Update-Script"
copy_file "$REMOTE_DOCKER_DIR/update-local-aria.sh" "$LOCAL_DIR/"

log "Hole Host-Update-Helper"
copy_file "$REMOTE_DOCKER_DIR/aria-host-update.sh" "$LOCAL_DIR/"
copy_file "$REMOTE_DOCKER_DIR/aria-host-update.env.example" "$LOCAL_DIR/"
copy_file "$REMOTE_DOCKER_DIR/setup-compose-stack.sh" "$LOCAL_DIR/"
copy_file "$REMOTE_BASE_DIR/aria-setup" "$LOCAL_DIR/"

log "Hole Env-Vorlage"
copy_file "$REMOTE_DOCKER_DIR/aria-stack.env.example" "$LOCAL_DIR/"

if ssh -i "$SSH_KEY_PATH" "$DEV_SSH" "[ -d '$REMOTE_SAMPLES_DIR' ]"; then
  log "Hole Samples"
  copy_dir "$REMOTE_SAMPLES_DIR" "$LOCAL_DIR/samples"
fi

chmod +x "$LOCAL_UPDATE_SCRIPT" 2>/dev/null || true
chmod +x "$LOCAL_DIR/aria-host-update.sh" 2>/dev/null || true

if [[ ! -f "$LOCAL_DIR/aria-stack.env" && -f "$LOCAL_DIR/aria-stack.env.example" ]]; then
  log "Lokale aria-stack.env fehlt, lege Vorlage an"
  cp "$LOCAL_DIR/aria-stack.env.example" "$LOCAL_DIR/aria-stack.env"
  log "Bitte den echten Qdrant-Key in $LOCAL_DIR/aria-stack.env setzen"
fi

log "Starte lokales ARIA-Update"
bash "$LOCAL_UPDATE_SCRIPT"
