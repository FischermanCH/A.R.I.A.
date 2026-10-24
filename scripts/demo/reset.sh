#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
mkdir -p "${DEMO_ROOT}/demo/generated"
# Follow the current source version: use the locally built image of the
# version in pyproject.toml when it exists, unless ARIA_DEMO_IMAGE is set.
if [[ -z "${ARIA_DEMO_IMAGE:-}" ]]; then
  current="$(sed -nE 's/^version = "([0-9]+\.[0-9]+\.[0-9]+)-alpha([0-9]+)"/\1-alpha.\2/p' "${DEMO_ROOT}/pyproject.toml" | head -1)"
  if [[ -n "${current}" ]] && docker image inspect "fischermanch/aria:${current}" >/dev/null 2>&1; then
    export ARIA_DEMO_IMAGE="fischermanch/aria:${current}"
  fi
fi
echo "ARIA demo image: ${ARIA_DEMO_IMAGE:-default from scripts/demo/seed.py}"
"${DEMO_ROOT}/.venv/bin/python" "${DEMO_ROOT}/scripts/demo/seed.py" --root "${DEMO_ROOT}"
"${DEMO_ROOT}/.venv/bin/python" "${DEMO_ROOT}/scripts/demo/seed_notes.py" --root "${DEMO_ROOT}"
"${DEMO_ROOT}/.venv/bin/python" "${DEMO_ROOT}/scripts/demo/seed_features.py" --root "${DEMO_ROOT}"
require_demo_names
demo_compose down -v --remove-orphans
demo_compose --profile seed run --rm seed
demo_compose up -d qdrant
"${DEMO_ROOT}/.venv/bin/python" "${DEMO_ROOT}/scripts/demo/seed_qdrant.py" --url "http://127.0.0.1:${ARIA_DEMO_QDRANT_PORT:-8091}"
demo_compose up -d llm-stub aria
wait_demo_health
echo "ARIA demo reset: http://localhost:${ARIA_DEMO_PORT:-8090} (demo-admin / aria-demo-access)"
