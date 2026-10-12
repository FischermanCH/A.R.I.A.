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
WEBKIT_IMAGE="${ARIA_E2E_WEBKIT_IMAGE:-mcr.microsoft.com/playwright/python:v1.55.0-noble}"
WEBKIT_WHEEL_DIR="${ARIA_E2E_WEBKIT_WHEEL_DIR:-${ROOT_DIR}/.cache/e2e-wheels}"
if ! docker image inspect "${WEBKIT_IMAGE}" >/dev/null 2>&1; then
  echo "E2E WebKit image not found: ${WEBKIT_IMAGE}" >&2
  echo "Pull this development-only image before running the full browser gate." >&2
  exit 2
fi
if [[ ! -f "${WEBKIT_WHEEL_DIR}/playwright-1.55.0-py3-none-manylinux1_x86_64.whl" ]]; then
  echo "E2E WebKit wheel cache missing: ${WEBKIT_WHEEL_DIR}" >&2
  echo "Run: ./.venv/bin/pip download --dest .cache/e2e-wheels playwright==1.55.0" >&2
  exit 2
fi
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
mkdir -p "${ARTIFACT_DIR}" "${STACK_DIR}/config" "${STACK_DIR}/data" "${STACK_DIR}/prompts" "${STACK_DIR}/qdrant"
cp -a "${ROOT_DIR}/prompts/." "${STACK_DIR}/prompts/"

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
  # Qdrant can create one final root-owned atomic-write directory after the
  # pre-stop chmod. Normalize this disposable mount only after every writer
  # has stopped, using a predictably named one-shot container.
  if [[ "${PREFIX}" == aria-e2e-* ]] && [[ -d "${STACK_DIR}" ]]; then
    docker run --rm --name "${PREFIX}-cleanup" \
      -v "${STACK_DIR}:/cleanup:rw" --entrypoint chmod "${IMAGE_TAG}" \
      -R a+rwX /cleanup >/dev/null 2>&1 || true
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
  collections:
    knowledge:
      prefix: "aria_knowledge"
      weight: 0.7
      top_k: 1
inventory_index:
  enabled: false
  run_on_startup: false
routing:
  qdrant_connection_routing_enabled: false
agentic_loop:
  enabled: true
  native_agent_memory_enabled: true
  native_agent_memory_learn_enabled: false
  native_agent_connections_enabled: true
  native_agent_admin_enabled: false
  native_agent_admin_write_enabled: false
  native_agent_write_notes_enabled: false
  native_agent_write_memory_enabled: false
  native_agent_ssh_enabled: true
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
  activity_journal_enabled: true
  activity_journal_retention_days: 90
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
connections:
  ssh:
    srv-dev02:
      title: "Development server"
      host: "debdev-srv02"
      user: "e2e"
      timeout_seconds: 1
    srv-duplicate-a:
      title: "Duplicate host"
      host: "duplicate-a.invalid"
      user: "e2e"
      timeout_seconds: 1
    srv-duplicate-b:
      title: "Duplicate host"
      host: "duplicate-b.invalid"
      user: "e2e"
      timeout_seconds: 1
    seed-04: {title: "Seed host 04", host: "seed-04.invalid", user: "e2e", timeout_seconds: 1}
    seed-05: {title: "Seed host 05", host: "seed-05.invalid", user: "e2e", timeout_seconds: 1}
    seed-06: {title: "Seed host 06", host: "seed-06.invalid", user: "e2e", timeout_seconds: 1}
    seed-07: {title: "Seed host 07", host: "seed-07.invalid", user: "e2e", timeout_seconds: 1}
    seed-08: {title: "Seed host 08", host: "seed-08.invalid", user: "e2e", timeout_seconds: 1}
    seed-09: {title: "Seed host 09", host: "seed-09.invalid", user: "e2e", timeout_seconds: 1}
    seed-10: {title: "Seed host 10", host: "seed-10.invalid", user: "e2e", timeout_seconds: 1}
    seed-11: {title: "Seed host 11", host: "seed-11.invalid", user: "e2e", timeout_seconds: 1}
    seed-12: {title: "Seed host 12", host: "seed-12.invalid", user: "e2e", timeout_seconds: 1}
    seed-13: {title: "Seed host 13", host: "seed-13.invalid", user: "e2e", timeout_seconds: 1}
    seed-14: {title: "Seed host 14", host: "seed-14.invalid", user: "e2e", timeout_seconds: 1}
  webhook:
    e2e-webhook:
      title: "E2E webhook"
      url: "http://${ANTHROPIC_NAME}:9000/e2e-webhook"
      method: "POST"
      timeout_seconds: 1
  email:
    e2e-mail:
      title: "E2E mail"
      smtp_host: "mail.invalid"
      from_email: "sender@example.invalid"
      to_email: "receiver@example.invalid"
      timeout_seconds: 1
  imap:
    e2e-inbox:
      title: "E2E inbox"
      host: "mail.invalid"
      user: "e2e"
      mailbox: "INBOX"
      timeout_seconds: 1
  sftp:
    e2e-sftp: {title: "E2E SFTP", host: "sftp.invalid", user: "e2e", root_path: "/data", timeout_seconds: 1}
  smb:
    e2e-smb: {title: "E2E SMB", host: "smb.invalid", share: "documents", user: "e2e", root_path: "/", timeout_seconds: 1}
  discord:
    e2e-discord: {title: "E2E Discord", webhook_url: "https://discord.invalid/webhook", timeout_seconds: 1}
  http_api:
    e2e-api: {title: "E2E API", base_url: "https://api.invalid/v1", health_path: "/health", method: "GET", timeout_seconds: 1}
  mqtt:
    e2e-mqtt: {title: "E2E MQTT", host: "mqtt.invalid", port: 1883, topic: "aria/e2e", timeout_seconds: 1}
  google_calendar:
    e2e-calendar: {title: "E2E Calendar", ical_url: "https://calendar.invalid/e2e.ics", timeout_seconds: 1}
  website:
    e2e-website: {title: "E2E Website", url: "https://website.invalid", group_name: "Research", timeout_seconds: 1}
YAML

# Scale fixture for the grouped RSS overview and statistics latency gate:
# 32 feeds plus 89 SSH profiles yield 131 configured connections in total.
# This disposable config is the only file modified by this block.
"${E2E_PYTHON}" - "${STACK_DIR}/config/config.yaml" <<'PY'
from pathlib import Path
import sys
import yaml

path = Path(sys.argv[1])
payload = yaml.safe_load(path.read_text(encoding="utf-8"))
rss = {}
groups = ("Engineering", "Security", "Research")
for index in range(1, 33):
    group = groups[(index - 1) % len(groups)] if index <= 27 else ""
    row = {
        "title": f"E2E Feed {index:02d}",
        "feed_url": f"https://feed-{index:02d}.invalid/rss.xml",
        "timeout_seconds": 1,
    }
    if group:
        row["group_name"] = group
    rss[f"e2e-feed-{index:02d}"] = row
payload.setdefault("connections", {})["rss"] = rss
ssh = payload.setdefault("connections", {}).setdefault("ssh", {})
for index in range(1, 76):
    ssh[f"latency-{index:03d}"] = {
        "title": f"Latency fixture {index:03d}",
        "host": f"latency-{index:03d}.invalid",
        "user": "e2e",
        "timeout_seconds": 1,
    }
assert sum(len(rows) for rows in payload["connections"].values()) == 131
path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
PY

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
  -v "${STACK_DIR}/qdrant:/qdrant/storage:ro" \
  -e ARIA_ARIA_HOST=0.0.0.0 -e ARIA_ARIA_PORT=8800 \
  -v "${STACK_DIR}/config:/app/config:rw" \
  -v "${STACK_DIR}/prompts:/app/prompts:rw" \
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
export ARIA_E2E_QDRANT_URL="http://${QDRANT_IP}:6333"
export ARIA_E2E_CONTAINER_NAME="${ARIA_NAME}"
export ARIA_E2E_ARTIFACT_DIR="${ARTIFACT_DIR}"
export ARIA_E2E_USERNAME="${E2E_USERNAME}"
export ARIA_E2E_PASSWORD="${E2E_PASSWORD}"
export ARIA_E2E_DATA_DIR="${STACK_DIR}/data"

set +e
PYTEST_ARGS=(-o addopts= -q tests/e2e/scenarios.py --junitxml="${ARTIFACT_DIR}/junit.xml")
if [[ -n "${ARIA_E2E_TEST_EXPR:-}" ]]; then
  PYTEST_ARGS+=(-k "${ARIA_E2E_TEST_EXPR}")
fi
"${E2E_PYTHON}" -m pytest "${PYTEST_ARGS[@]}"
PYTEST_STATUS=$?
set -e
if [[ "${PYTEST_STATUS}" -eq 0 ]]; then
  set +e
  docker run --rm --name "${PREFIX}-webkit" --network "${NETWORK_NAME}" \
    -v "${ROOT_DIR}/tests/e2e:/e2e:ro" \
    -v "${WEBKIT_WHEEL_DIR}:/wheels:ro" \
    -e E2E_WEBKIT_URL="http://${ARIA_NAME}:8800" \
    -e E2E_WEBKIT_USERNAME="${E2E_USERNAME}" \
    -e E2E_WEBKIT_PASSWORD="${E2E_PASSWORD}" \
    --entrypoint sh "${WEBKIT_IMAGE}" -c \
    'python -m pip install --quiet --disable-pip-version-check --no-index --find-links=/wheels playwright==1.55.0 && exec python /e2e/webkit_journal.py --url "$E2E_WEBKIT_URL" --username "$E2E_WEBKIT_USERNAME" --password "$E2E_WEBKIT_PASSWORD"'
  PYTEST_STATUS=$?
  set -e
fi
"${E2E_PYTHON}" scripts/e2e/report.py "${ARTIFACT_DIR}/junit.xml"
echo "Artifacts: ${ARTIFACT_DIR}"
exit "${PYTEST_STATUS}"
