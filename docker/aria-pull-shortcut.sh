#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAS_DIR="/mnt/NAS/aria-images"
FALLBACK_DIR="$HOME/aria-images"
TARGET_DIR="$NAS_DIR"

if [[ ! -d "$TARGET_DIR" ]]; then
  TARGET_DIR="$FALLBACK_DIR"
fi

mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

if [[ -x "./pull-from-dev.sh" ]]; then
  exec ./pull-from-dev.sh "$@"
fi

exec "$SCRIPT_DIR/pull-from-dev.sh" "$@"
