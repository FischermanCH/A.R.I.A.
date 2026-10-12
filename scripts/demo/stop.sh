#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
[[ -f "${DEMO_ENV}" ]] || exit 0
require_demo_names
demo_compose stop
