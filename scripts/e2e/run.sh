#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE_TAG="${1:-}"
if [[ -z "${IMAGE_TAG}" ]]; then
  echo "usage: scripts/e2e/run.sh <aria-image-tag>" >&2
  exit 2
fi
if ! docker image inspect "${IMAGE_TAG}" >/dev/null 2>&1; then
  echo "E2E image not found: ${IMAGE_TAG}" >&2
  exit 2
fi
if ! docker image inspect qdrant/qdrant:latest >/dev/null 2>&1; then
  echo "E2E Qdrant image not found: qdrant/qdrant:latest" >&2
  exit 2
fi

E2E_PYTHON="${ARIA_E2E_PYTHON:-${ROOT_DIR}/.venv/bin/python}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-${ROOT_DIR}/.cache/ms-playwright}"
if [[ ! -x "${E2E_PYTHON}" ]]; then
  echo "E2E Python not found: ${E2E_PYTHON}" >&2
  exit 2
fi
"${E2E_PYTHON}" -c 'import playwright' >/dev/null 2>&1 || {
  echo "Playwright is missing. Install requirements-e2e.txt and Chromium in the dev cache." >&2
  exit 2
}

RUN_ID="$(date -u +%Y%m%d%H%M%S)-$$"
PREFIX="aria-e2e-${RUN_ID}"
NETWORK_NAME="${PREFIX}-net"
ANTHROPIC_NAME="${PREFIX}-anthropic"
MCP_NAME="${PREFIX}-mcp"
QDRANT_NAME="${PREFIX}-qdrant"
ARIA_NAME="${PREFIX}-aria"
STACK_DIR="$(mktemp -d "/tmp/${PREFIX}.XXXXXX")"
ARTIFACT_DIR="${ARIA_E2E_ARTIFACT_DIR:-${ROOT_DIR}/test-results/e2e/${RUN_ID}}"
mkdir -p "${ARTIFACT_DIR}" "${STACK_DIR}/config" "${STACK_DIR}/data" "${STACK_DIR}/qdrant"

E2E_USERNAME="e2e-admin"
E2E_PASSWORD="e2e-only-password-975"
PYTEST_STATUS=1
CLEANED_UP=0

collect_url() {
  local url="$1"
  local output="$2"
  "${E2E_PYTHON}" - "$url" "$output" <<'PY' || true
import json, sys, urllib.request
try:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(sys.argv[1], timeout=5) as response:
        payload = json.load(response)
    with open(sys.argv[2], "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
except Exception as exc:
    with open(sys.argv[2], "w", encoding="utf-8") as handle:
        json.dump({"collection_error": type(exc).__name__}, handle)
PY
}

cleanup() {
  if [[ "${CLEANED_UP}" -eq 1 ]]; then
    return
  fi
  CLEANED_UP=1
  set +e
  if [[ -n "${ANTHROPIC_CONTROL_URL:-}" ]]; then
    collect_url "${ANTHROPIC_CONTROL_URL}/__control/logs" "${ARTIFACT_DIR}/strict-anthropic.json"
  fi
  if [[ -n "${MCP_CONTROL_URL:-}" ]]; then
    collect_url "${MCP_CONTROL_URL}/__control/logs" "${ARTIFACT_DIR}/fake-mcp.json"
  fi
  if [[ "${ARIA_NAME}" == aria-e2e-* ]] && docker container inspect "${ARIA_NAME}" >/dev/null 2>&1; then
    # Files written after the initial health check can again be root-owned.
    # Normalize only this disposable mount before removing its container so
    # the trap can always delete the isolated stack directory.
    docker exec "${ARIA_NAME}" chmod -R a+rwX /app/data >/dev/null 2>&1 || true
  fi
  if [[ "${QDRANT_NAME}" == aria-e2e-* ]] && docker container inspect "${QDRANT_NAME}" >/dev/null 2>&1; then
    docker exec "${QDRANT_NAME}" chmod -R a+rwX /qdrant/storage >/dev/null 2>&1 || true
  fi
  for name in "${ARIA_NAME}" "${MCP_NAME}" "${ANTHROPIC_NAME}" "${QDRANT_NAME}"; do
    if [[ "${name}" == aria-e2e-* ]] && docker container inspect "${name}" >/dev/null 2>&1; then
      docker logs --tail 500 "${name}" >"${ARTIFACT_DIR}/${name##${PREFIX}-}.log" 2>&1 || true
      docker rm -fv "${name}" >/dev/null 2>&1 || true
    fi
  done
  if [[ "${NETWORK_NAME}" == aria-e2e-* ]] && docker network inspect "${NETWORK_NAME}" >/dev/null 2>&1; then
    docker network rm "${NETWORK_NAME}" >/dev/null 2>&1 || true
  fi
  chmod -R u+rwX "${STACK_DIR}" >/dev/null 2>&1 || true
  rm -rf -- "${STACK_DIR}"
}
terminate() {
  exit 130
}
trap cleanup EXIT
trap terminate INT TERM

cat >"${STACK_DIR}/config/config.yaml" <<YAML
aria:
  host: "0.0.0.0"
  port: 8800
  log_level: "info"
  public_url: ""
llm:
  model: "anthropic/claude-sonnet-5"
  api_base: "http://${ANTHROPIC_NAME}:9000"
  api_key: "e2e-fake-key"
  temperature: 0.0
  max_tokens: 1024
  timeout_seconds: 20
profiles:
  active:
    llm: "default"
    main_llm: "default"
    web_llm: ""
    embeddings: "default"
  llm:
    default:
      model: "anthropic/claude-sonnet-5"
      api_base: "http://${ANTHROPIC_NAME}:9000"
      api_key: "e2e-fake-key"
      temperature: 0.0
      max_tokens: 1024
      timeout_seconds: 20
  embeddings:
    default:
      model: "openai/text-embedding-3-small"
      api_base: "http://${ANTHROPIC_NAME}:9000/v1"
      api_key: "e2e-fake-key"
      timeout_seconds: 10
embeddings:
  model: "openai/text-embedding-3-small"
  api_base: "http://${ANTHROPIC_NAME}:9000/v1"
  api_key: "e2e-fake-key"
  timeout_seconds: 10
memory:
  enabled: true
  backend: "qdrant"
  qdrant_url: "http://${QDRANT_NAME}:6333"
  qdrant_api_key: ""
inventory_index:
  enabled: false
  run_on_startup: false
routing:
  qdrant_connection_routing_enabled: false
agentic_loop:
  enabled: true
  native_agent_memory_enabled: true
  native_agent_memory_learn_enabled: false
  native_agent_connections_enabled: false
  native_agent_admin_enabled: false
  native_agent_admin_write_enabled: false
  native_agent_write_notes_enabled: false
  native_agent_write_memory_enabled: false
  native_agent_ssh_enabled: false
  native_agent_messaging_enabled: false
  native_agent_infra_write_enabled: false
  native_agent_recipe_execute_enabled: false
  native_agent_recipe_learn_enabled: false
  native_agent_mcp_enabled: true
  native_agent_mcp_vision_enabled: true
  native_tool_selector_top_k: 128
  native_agent_max_steps: 32
  native_agent_max_provider_calls: 36
  async_agent_job_sync_budget_seconds: 3
mcp_servers:
  blender:
    transport: "sse"
    url: "http://${MCP_NAME}:9000/sse"
    headers: {}
    enabled: true
    trusted: true
    title: "E2E Blender"
  review:
    transport: "sse"
    url: "http://${MCP_NAME}:9000/sse"
    headers: {}
    enabled: true
    trusted: false
    title: "E2E Confirmation"
ui:
  title: "ARIA E2E"
  debug_mode: true
  language: "de"
  theme: "matrix"
  background: "grid-signal"
security:
  enabled: true
  db_path: "data/auth/aria_secure.sqlite"
  bootstrap_locked: false
pricing:
  enabled: false
token_tracking:
  enabled: false
connections: {}
YAML

docker network create --internal "${NETWORK_NAME}" >/dev/null

CONTAINER_USER="$(id -u):$(id -g)"

docker run -d --name "${QDRANT_NAME}" --network "${NETWORK_NAME}" \
  -v "${STACK_DIR}/qdrant:/qdrant/storage:rw" qdrant/qdrant:latest >/dev/null

docker run -d --name "${ANTHROPIC_NAME}" --network "${NETWORK_NAME}" \
  --user "${CONTAINER_USER}" \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m \
  --tmpfs /app/config:rw,nosuid,nodev,size=8m \
  --tmpfs /app/prompts:rw,nosuid,nodev,size=8m \
  --tmpfs /app/data:rw,nosuid,nodev,size=8m \
  -v "${ROOT_DIR}/tests/e2e:/e2e:ro" \
  --entrypoint python "${IMAGE_TAG}" /e2e/strict_anthropic.py --port 9000 >/dev/null

docker run -d --name "${MCP_NAME}" --network "${NETWORK_NAME}" \
  --user "${CONTAINER_USER}" \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m \
  --tmpfs /app/config:rw,nosuid,nodev,size=8m \
  --tmpfs /app/prompts:rw,nosuid,nodev,size=8m \
  --tmpfs /app/data:rw,nosuid,nodev,size=8m \
  -v "${ROOT_DIR}/tests/e2e:/e2e:ro" \
  --entrypoint python "${IMAGE_TAG}" /e2e/fake_mcp.py --mcp-port 9000 --control-port 9001 >/dev/null

docker run -d --name "${ARIA_NAME}" --network "${NETWORK_NAME}" \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=128m \
  -v "${STACK_DIR}/data:/app/data:rw" \
  -e ARIA_ARIA_HOST=0.0.0.0 -e ARIA_ARIA_PORT=8800 \
  -v "${STACK_DIR}/config:/app/config:rw" \
  -v "${ROOT_DIR}/prompts:/app/prompts:ro" \
  --entrypoint python "${IMAGE_TAG}" -m uvicorn aria.main:app --host 0.0.0.0 --port 8800 >/dev/null

container_ip() {
  docker inspect "$1" --format "{{with index .NetworkSettings.Networks \"${NETWORK_NAME}\"}}{{.IPAddress}}{{end}}"
}
ANTHROPIC_IP="$(container_ip "${ANTHROPIC_NAME}")"
MCP_IP="$(container_ip "${MCP_NAME}")"
QDRANT_IP="$(container_ip "${QDRANT_NAME}")"
ARIA_IP="$(container_ip "${ARIA_NAME}")"
if [[ -z "${ANTHROPIC_IP}" || -z "${MCP_IP}" || -z "${QDRANT_IP}" || -z "${ARIA_IP}" ]]; then
  echo "One or more isolated E2E containers exited before network setup" >&2
  exit 1
fi
ANTHROPIC_CONTROL_URL="http://${ANTHROPIC_IP}:9000"
MCP_CONTROL_URL="http://${MCP_IP}:9001"
ARIA_BASE_URL="http://${ARIA_IP}:8800"

wait_url() {
  local url="$1"
  "${E2E_PYTHON}" - "$url" <<'PY'
import sys, time, urllib.request
deadline = time.monotonic() + 45
last = None
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
while time.monotonic() < deadline:
    try:
        with opener.open(sys.argv[1], timeout=2) as response:
            if response.status < 500:
                raise SystemExit(0)
    except Exception as exc:
        last = type(exc).__name__
        time.sleep(0.25)
raise SystemExit(f"timeout waiting for {sys.argv[1]} ({last})")
PY
}
wait_url "${ANTHROPIC_CONTROL_URL}/health"
wait_url "${MCP_CONTROL_URL}/health"
wait_url "http://${QDRANT_IP}:6333/healthz"
wait_url "${ARIA_BASE_URL}/health"
# The production image runs as root and preserves the repository's restrictive
# source permissions. Keep that production execution shape, but make this
# disposable stack's isolated data mount writable for host-side SQLite E2E
# fixtures (S18). No real ARIA volume is mounted here.
docker exec "${ARIA_NAME}" chmod -R a+rwX /app/data

export ARIA_E2E_BASE_URL="${ARIA_BASE_URL}"
export ARIA_E2E_ANTHROPIC_CONTROL_URL="${ANTHROPIC_CONTROL_URL}"
export ARIA_E2E_MCP_CONTROL_URL="${MCP_CONTROL_URL}"
export ARIA_E2E_ARTIFACT_DIR="${ARTIFACT_DIR}"
export ARIA_E2E_USERNAME="${E2E_USERNAME}"
export ARIA_E2E_PASSWORD="${E2E_PASSWORD}"
export ARIA_E2E_DATA_DIR="${STACK_DIR}/data"

set +e
"${E2E_PYTHON}" -m pytest -o addopts= -q tests/e2e/scenarios.py \
  --junitxml="${ARTIFACT_DIR}/junit.xml"
PYTEST_STATUS=$?
set -e
"${E2E_PYTHON}" scripts/e2e/report.py "${ARTIFACT_DIR}/junit.xml"
echo "Artifacts: ${ARTIFACT_DIR}"
exit "${PYTEST_STATUS}"
