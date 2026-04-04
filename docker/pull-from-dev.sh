#!/usr/bin/env bash
set -Eeuo pipefail

DEV_SSH="${DEV_SSH:-}"
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/aria_dev_pull}"
REMOTE_BASE_DIR="${REMOTE_BASE_DIR:-/home/aria/ARIA}"
LOCAL_DIR="${LOCAL_DIR:-/mnt/NAS/aria-images}"
LOCAL_UPDATE_SCRIPT="${LOCAL_UPDATE_SCRIPT:-$LOCAL_DIR/update-local-aria.sh}"
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
[[ -n "${DEV_SSH}" ]] || die "DEV_SSH ist nicht gesetzt. Beispiel: DEV_SSH=<dev-user>@<dev-host> ./pull-from-dev.sh"
require_cmd scp
[[ -f "$SSH_KEY_PATH" ]] || die "SSH-Key nicht gefunden: $SSH_KEY_PATH"
mkdir -p "$LOCAL_DIR"

LATEST_REMOTE_TAR="$(
  ssh -i "$SSH_KEY_PATH" "$DEV_SSH" "find '$REMOTE_DIST_DIR' -maxdepth 1 -type f -name 'aria-alpha*-local.tar' | sed 's#^.*/##' | awk '
    match(\$0, /^aria-alpha([0-9]+)-local\\.tar$/, m) { printf \"%012d %s\\n\", m[1], \$0; next }
    \$0 == \"aria-alpha-local.tar\" { printf \"%012d %s\\n\", 0, \$0; next }
  ' | sort | tail -n1 | cut -d' ' -f2- | sed 's#^#$REMOTE_DIST_DIR/#'"
)"

[[ -n "$LATEST_REMOTE_TAR" ]] || die "Kein ARIA-TAR auf dem Dev-Host gefunden"

log "Hole neuestes TAR vom Dev-Host: $LATEST_REMOTE_TAR"
copy_file "$LATEST_REMOTE_TAR" "$LOCAL_DIR/"

log "Hole Stack-Datei"
copy_file "$REMOTE_DOCKER_DIR/portainer-stack.alpha3.local.yml" "$LOCAL_DIR/"

log "Hole lokales Update-Script"
copy_file "$REMOTE_DOCKER_DIR/update-local-aria.sh" "$LOCAL_DIR/"

log "Hole Env-Vorlage"
copy_file "$REMOTE_DOCKER_DIR/aria-stack.env.example" "$LOCAL_DIR/"

if ssh -i "$SSH_KEY_PATH" "$DEV_SSH" "[ -d '$REMOTE_SAMPLES_DIR' ]"; then
  log "Hole Samples"
  copy_dir "$REMOTE_SAMPLES_DIR" "$LOCAL_DIR/samples"
fi

chmod +x "$LOCAL_UPDATE_SCRIPT" 2>/dev/null || true

if [[ ! -f "$LOCAL_DIR/aria-stack.env" && -f "$LOCAL_DIR/aria-stack.env.example" ]]; then
  log "Lokale aria-stack.env fehlt, lege Vorlage an"
  cp "$LOCAL_DIR/aria-stack.env.example" "$LOCAL_DIR/aria-stack.env"
  log "Bitte den echten Qdrant-Key in $LOCAL_DIR/aria-stack.env setzen"
fi

log "Starte lokales ARIA-Update"
bash "$LOCAL_UPDATE_SCRIPT"
