#!/usr/bin/env bash
set -euo pipefail
cd /mnt/NAS/aria-images
exec ./pull-from-dev.sh "$@"
