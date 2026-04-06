#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PREFERRED_ARTIFACT_DIR="${PREFERRED_ARTIFACT_DIR:-/mnt/NAS/aria-images}"
FALLBACK_ARTIFACT_DIR="${FALLBACK_ARTIFACT_DIR:-$REPO_ROOT/dist}"
SAMPLES_DIR="${SAMPLES_DIR:-$REPO_ROOT/samples}"
DOCKER_HELPER_DIR="${DOCKER_HELPER_DIR:-$REPO_ROOT/docker}"
ARTIFACT_DIR="${ARTIFACT_DIR:-}"
IMAGE_REF="${IMAGE_REF:-}"
KEEP_TARS="${KEEP_TARS:-7}"

log() {
  printf '[aria-export] %s\n' "$*"
}

die() {
  printf '[aria-export] ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Kommando fehlt: $1"
}

pick_artifact_dir() {
  if [[ -n "$ARTIFACT_DIR" ]]; then
    printf '%s\n' "$ARTIFACT_DIR"
    return 0
  fi
  if [[ -d "$PREFERRED_ARTIFACT_DIR" ]]; then
    printf '%s\n' "$PREFERRED_ARTIFACT_DIR"
    return 0
  fi
  printf '%s\n' "$FALLBACK_ARTIFACT_DIR"
}

detect_image_ref() {
  if [[ -n "$IMAGE_REF" ]]; then
    printf '%s\n' "$IMAGE_REF"
    return 0
  fi

  docker images --format '{{.Repository}}:{{.Tag}}' \
    | awk '
        match($0, /^fischermanch\/aria:0\.1\.0-alpha\.([0-9]+)$/, m) {
          printf "%012d %s\n", m[1], $0
        }
      ' \
    | sort \
    | tail -n1 \
    | cut -d' ' -f2-
}

tar_name_for_image() {
  local image_ref="$1"
  local version_tag="${image_ref##*:}"
  local alpha_number

  alpha_number="$(printf '%s\n' "$version_tag" | sed -n 's/^0\.1\.0-alpha\.\([0-9][0-9]*\)$/\1/p')"
  [[ -n "$alpha_number" ]] || die "Konnte Alpha-Nummer aus Image-Tag nicht lesen: $image_ref"
  printf 'aria-alpha%s-local.tar\n' "$alpha_number"
}

copy_if_exists() {
  local source_path="$1"
  local target_dir="$2"
  [[ -e "$source_path" ]] || return 0
  cp -f "$source_path" "$target_dir/"
}

copy_dir_if_exists() {
  local source_dir="$1"
  local target_dir="$2"
  [[ -d "$source_dir" ]] || return 0
  rm -rf "$target_dir/$(basename "$source_dir")"
  cp -a "$source_dir" "$target_dir/"
}

prune_old_tars() {
  local target_dir="$1"
  local keep_count="$2"
  local prune_list=""

  [[ "$keep_count" =~ ^[0-9]+$ ]] || die "KEEP_TARS muss numerisch sein: $keep_count"
  (( keep_count >= 1 )) || die "KEEP_TARS muss mindestens 1 sein"

  prune_list="$(
    find "$target_dir" -maxdepth 1 -type f -name 'aria-alpha*-local.tar' \
      | sed 's#^.*/##' \
      | awk '
          match($0, /^aria-alpha([0-9]+)-local\.tar$/, m) { printf "%012d %s\n", m[1], $0; next }
        ' \
      | sort \
      | head -n "-$keep_count" \
      | cut -d' ' -f2-
  )"

  [[ -n "$prune_list" ]] || return 0

  while IFS= read -r tar_name; do
    [[ -n "$tar_name" ]] || continue
    rm -f "$target_dir/$tar_name"
    log "Altes TAR entfernt: $target_dir/$tar_name"
  done <<< "$prune_list"
}

require_cmd docker

TARGET_DIR="$(pick_artifact_dir)"
mkdir -p "$TARGET_DIR"

TARGET_IMAGE_REF="$(detect_image_ref)"
[[ -n "$TARGET_IMAGE_REF" ]] || die "Kein versioniertes ARIA-Image gefunden. IMAGE_REF setzen oder zuerst bauen."

docker image inspect "$TARGET_IMAGE_REF" >/dev/null 2>&1 || die "Image nicht gefunden: $TARGET_IMAGE_REF"

TARGET_TAR_NAME="$(tar_name_for_image "$TARGET_IMAGE_REF")"
TARGET_TAR_PATH="$TARGET_DIR/$TARGET_TAR_NAME"

log "Nutze Artefaktverzeichnis: $TARGET_DIR"
log "Exportiere Image: $TARGET_IMAGE_REF"
docker save -o "$TARGET_TAR_PATH" "$TARGET_IMAGE_REF"
log "TAR geschrieben: $TARGET_TAR_PATH"

copy_if_exists "$DOCKER_HELPER_DIR/update-local-aria.sh" "$TARGET_DIR"
copy_if_exists "$DOCKER_HELPER_DIR/pull-from-dev.sh" "$TARGET_DIR"
copy_if_exists "$DOCKER_HELPER_DIR/aria-pull-shortcut.sh" "$TARGET_DIR"
copy_if_exists "$DOCKER_HELPER_DIR/aria-pull.env.example" "$TARGET_DIR"
copy_if_exists "$DOCKER_HELPER_DIR/portainer-stack.alpha3.local.yml" "$TARGET_DIR"
copy_if_exists "$DOCKER_HELPER_DIR/aria-stack.env.example" "$TARGET_DIR"
copy_dir_if_exists "$SAMPLES_DIR" "$TARGET_DIR"
prune_old_tars "$TARGET_DIR" "$KEEP_TARS"

if [[ "$TARGET_DIR" != "$FALLBACK_ARTIFACT_DIR" ]]; then
  log "Hinweis: Repo-dist bleibt unberuehrt. Fallback waere: $FALLBACK_ARTIFACT_DIR"
fi

ls -lh "$TARGET_TAR_PATH"
