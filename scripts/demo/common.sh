#!/usr/bin/env bash
set -euo pipefail

DEMO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEMO_COMPOSE="${DEMO_ROOT}/demo/compose.yml"
DEMO_ENV="${DEMO_ROOT}/demo/generated/.env"
DEMO_PROJECT="aria-demo"

demo_compose() {
  docker compose -p "${DEMO_PROJECT}" --env-file "${DEMO_ENV}" -f "${DEMO_COMPOSE}" "$@"
}

require_demo_names() {
  [[ "${DEMO_PROJECT}" == "aria-demo" ]] || { echo "Refusing non-demo project" >&2; exit 2; }
  [[ "$(docker compose -p "${DEMO_PROJECT}" --env-file "${DEMO_ENV}" -f "${DEMO_COMPOSE}" config --format json | tr -d '\n')" == *'aria-demo-data'* ]] || {
    echo "Refusing compose file without isolated demo volume" >&2; exit 2;
  }
}

wait_demo_health() {
  local demo_url="http://127.0.0.1:${ARIA_DEMO_PORT:-8090}/health"
  "${DEMO_ROOT}/.venv/bin/python" - "${demo_url}" <<'PY'
import sys
import time
import urllib.request

url = sys.argv[1]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
deadline = time.monotonic() + 45
while time.monotonic() < deadline:
    try:
        with opener.open(url, timeout=2) as response:
            if response.status < 500:
                raise SystemExit(0)
    except Exception:
        time.sleep(0.25)
raise SystemExit(f"Demo health check timed out: {url}")
PY
}
