#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
if [[ ! -f "${DEMO_ENV}" ]]; then
  "${DEMO_ROOT}/scripts/demo/reset.sh"
  exit
fi
require_demo_names
demo_compose up -d qdrant llm-stub aria
wait_demo_health
echo "ARIA demo: http://localhost:${ARIA_DEMO_PORT:-8090} (demo-admin / aria-demo-access)"
