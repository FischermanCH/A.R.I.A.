#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
mkdir -p "${DEMO_ROOT}/demo/generated"
"${DEMO_ROOT}/.venv/bin/python" "${DEMO_ROOT}/scripts/demo/seed.py" --root "${DEMO_ROOT}"
require_demo_names
demo_compose down -v --remove-orphans
demo_compose --profile seed run --rm seed
demo_compose up -d qdrant
"${DEMO_ROOT}/.venv/bin/python" "${DEMO_ROOT}/scripts/demo/seed_qdrant.py" --url "http://127.0.0.1:${ARIA_DEMO_QDRANT_PORT:-8091}"
demo_compose up -d aria
wait_demo_health
echo "ARIA demo reset: http://localhost:${ARIA_DEMO_PORT:-8090} (demo-admin / aria-demo-access)"
