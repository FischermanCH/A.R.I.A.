#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_IMAGE="${1:-}"
PUBLIC_IMAGE="fischermanch/aria:0.1.0-alpha.604"
if [[ -z "${TARGET_IMAGE}" ]]; then
  echo "usage: scripts/e2e/upgrade_604.sh <alpha983-image>" >&2
  exit 2
fi
for image in "${PUBLIC_IMAGE}" "${TARGET_IMAGE}" "qdrant/qdrant:latest"; do
  docker image inspect "${image}" >/dev/null
done

E2E_PYTHON="${ARIA_E2E_PYTHON:-${ROOT_DIR}/.venv/bin/python}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-${ROOT_DIR}/.cache/ms-playwright}"
"${E2E_PYTHON}" -c 'import playwright, httpx' >/dev/null

RUN_ID="$(date -u +%Y%m%d%H%M%S)-$$"
PREFIX="aria-e2e-upgrade-${RUN_ID}"
NETWORK_NAME="${PREFIX}-net"
ARIA_NAME="${PREFIX}-aria"
FAKE_NAME="${PREFIX}-provider"
QDRANT_NAME="${PREFIX}-qdrant"
STACK_DIR="$(mktemp -d "/tmp/${PREFIX}.XXXXXX")"
ARTIFACT_DIR="${ARIA_E2E_ARTIFACT_DIR:-${ROOT_DIR}/test-results/e2e-upgrade/${RUN_ID}}"
EVIDENCE="${ARTIFACT_DIR}/upgrade-604-to-983.json"
CLEANED_UP=0
mkdir -p "${STACK_DIR}/config" "${STACK_DIR}/data" "${STACK_DIR}/qdrant" "${ARTIFACT_DIR}"

cleanup() {
  if [[ "${CLEANED_UP}" -eq 1 ]]; then return; fi
  CLEANED_UP=1
  set +e
  if [[ -n "${FAKE_URL:-}" ]]; then
    "${E2E_PYTHON}" - "${FAKE_URL}/__control/logs" "${ARTIFACT_DIR}/strict-provider.json" <<'PY' || true
import json, pathlib, sys, urllib.request
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(sys.argv[1], timeout=5) as response:
    pathlib.Path(sys.argv[2]).write_text(json.dumps(json.load(response), indent=2), encoding="utf-8")
PY
  fi
  if docker container inspect "${ARIA_NAME}" >/dev/null 2>&1; then
    docker exec "${ARIA_NAME}" chmod -R a+rwX /app/config /app/data >/dev/null 2>&1 || true
  fi
  if docker container inspect "${QDRANT_NAME}" >/dev/null 2>&1; then
    docker exec "${QDRANT_NAME}" chmod -R a+rwX /qdrant/storage >/dev/null 2>&1 || true
  fi
  for name in "${ARIA_NAME}" "${FAKE_NAME}" "${QDRANT_NAME}"; do
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
trap cleanup EXIT

cat >"${STACK_DIR}/config/config.yaml" <<YAML
aria:
  host: "0.0.0.0"
  port: 8800
  log_level: "info"
  public_url: ""
llm:
  model: "anthropic/claude-3-5-sonnet-20241022"
  api_base: "http://${FAKE_NAME}:9000"
  api_key: "upgrade-fake-key"
  temperature: 0.0
  max_tokens: 2048
  timeout_seconds: 20
embeddings:
  model: "openai/text-embedding-3-small"
  api_base: "http://${FAKE_NAME}:9000/v1"
  api_key: "upgrade-fake-key"
  timeout_seconds: 10
profiles:
  active:
    llm: "default"
    main_llm: "default"
    web_llm: ""
    embeddings: "default"
  llm:
    default:
      model: "anthropic/claude-3-5-sonnet-20241022"
      api_base: "http://${FAKE_NAME}:9000"
      api_key: "upgrade-fake-key"
      temperature: 0.0
      max_tokens: 2048
      timeout_seconds: 20
  embeddings:
    default:
      model: "openai/text-embedding-3-small"
      api_base: "http://${FAKE_NAME}:9000/v1"
      api_key: "upgrade-fake-key"
      timeout_seconds: 10
memory:
  enabled: true
  backend: "qdrant"
  qdrant_url: "http://${QDRANT_NAME}:6333"
  qdrant_api_key: ""
  collection: "aria_memory"
  top_k: 5
  collections:
    facts: {prefix: "aria_facts", weight: 1.0, top_k: 4, dedup_threshold: 0.85}
    preferences: {prefix: "aria_preferences", weight: 0.9, top_k: 4, dedup_threshold: 0.80}
    sessions: {prefix: "aria_sessions", weight: 0.5, top_k: 2, time_decay: true, compress_after_days: 7, archive_after_days: 90}
    knowledge: {prefix: "aria_knowledge", weight: 0.7, top_k: 2, dedup_threshold: 0.90}
auto_memory:
  enabled: true
  agentic_extraction_enabled: false
inventory_index:
  enabled: false
  run_on_startup: false
routing:
  qdrant_connection_routing_enabled: false
agentic_loop:
  enabled: true
  native_agent_memory_enabled: true
  native_agent_write_memory_enabled: true
  native_agent_memory_learn_enabled: false
  native_agent_mcp_enabled: false
ui:
  title: "ARIA Upgrade E2E"
  debug_mode: true
  language: "en"
  theme: "matrix"
  background: "grid-signal"
security:
  enabled: true
  db_path: "data/auth/aria_secure.sqlite"
  bootstrap_locked: false
connections:
  ssh: {}
  discord: {}
  sftp: {}
  smb: {}
  webhook: {}
  smtp: {}
  imap: {}
  http_api: {}
  rss: {}
  mqtt: {}
YAML

docker network create --internal "${NETWORK_NAME}" >/dev/null
docker run -d --name "${QDRANT_NAME}" --network "${NETWORK_NAME}" \
  -v "${STACK_DIR}/qdrant:/qdrant/storage:rw" qdrant/qdrant:latest >/dev/null
docker run -d --name "${FAKE_NAME}" --network "${NETWORK_NAME}" \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m \
  --tmpfs /app/config:rw,nosuid,nodev,size=8m --tmpfs /app/data:rw,nosuid,nodev,size=8m \
  --tmpfs /app/prompts:rw,nosuid,nodev,size=8m \
  -v "${ROOT_DIR}/tests/e2e:/e2e:ro" --entrypoint python "${TARGET_IMAGE}" \
  /e2e/strict_anthropic.py --port 9000 >/dev/null

container_ip() {
  docker inspect "$1" --format "{{with index .NetworkSettings.Networks \"${NETWORK_NAME}\"}}{{.IPAddress}}{{end}}"
}
wait_url() {
  "${E2E_PYTHON}" - "$1" <<'PY'
import sys, time, urllib.request
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    try:
        with opener.open(sys.argv[1], timeout=2) as response:
            if response.status < 500:
                raise SystemExit(0)
    except Exception:
        time.sleep(.25)
raise SystemExit("timeout waiting for " + sys.argv[1])
PY
}
wait_url "http://$(container_ip "${FAKE_NAME}"):9000/health"
wait_url "http://$(container_ip "${QDRANT_NAME}"):6333/healthz"

start_aria() {
  local image="$1"
  docker run -d --name "${ARIA_NAME}" --network "${NETWORK_NAME}" \
    -v "${STACK_DIR}/config:/app/config:rw" -v "${STACK_DIR}/data:/app/data:rw" \
    -v "${ROOT_DIR}/prompts:/app/prompts:ro" \
    -e ARIA_ARIA_HOST=0.0.0.0 -e ARIA_ARIA_PORT=8800 \
    --entrypoint python "${image}" -m uvicorn aria.main:app --host 0.0.0.0 --port 8800 >/dev/null
  ARIA_BASE_URL="http://$(container_ip "${ARIA_NAME}"):8800"
  wait_url "${ARIA_BASE_URL}/health"
}

FAKE_URL="http://$(container_ip "${FAKE_NAME}"):9000"
QDRANT_URL="http://$(container_ip "${QDRANT_NAME}"):6333"
start_aria "${PUBLIC_IMAGE}"
"${E2E_PYTHON}" "${ROOT_DIR}/tests/e2e/upgrade_604.py" seed604 \
  --base-url "${ARIA_BASE_URL}" --fake-url "${FAKE_URL}" --qdrant-url "${QDRANT_URL}" --evidence "${EVIDENCE}"

docker logs "${ARIA_NAME}" >"${ARTIFACT_DIR}/alpha604.log" 2>&1 || true
docker rm -f "${ARIA_NAME}" >/dev/null
start_aria "${TARGET_IMAGE}"
"${E2E_PYTHON}" "${ROOT_DIR}/tests/e2e/upgrade_604.py" verify_target \
  --base-url "${ARIA_BASE_URL}" --fake-url "${FAKE_URL}" --qdrant-url "${QDRANT_URL}" --evidence "${EVIDENCE}"

echo "Upgrade Alpha604 -> Alpha983 passed. Evidence: ${EVIDENCE}"
