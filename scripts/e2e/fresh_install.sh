#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_IMAGE="${1:-}"
if [[ -z "${TARGET_IMAGE}" ]]; then
  echo "usage: scripts/e2e/fresh_install.sh <alpha983-image>" >&2
  exit 2
fi
docker image inspect "${TARGET_IMAGE}" >/dev/null
docker image inspect qdrant/qdrant:latest >/dev/null
E2E_PYTHON="${ARIA_E2E_PYTHON:-${ROOT_DIR}/.venv/bin/python}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-${ROOT_DIR}/.cache/ms-playwright}"

RUN_ID="$(date -u +%Y%m%d%H%M%S)-$$"
PREFIX="aria-e2e-fresh-${RUN_ID}"
NETWORK_NAME="${PREFIX}-net"
ARIA_NAME="${PREFIX}-aria"
FAKE_NAME="${PREFIX}-provider"
QDRANT_NAME="${PREFIX}-qdrant"
STACK_DIR="$(mktemp -d "/tmp/${PREFIX}.XXXXXX")"
ARTIFACT_DIR="${ARIA_E2E_ARTIFACT_DIR:-${ROOT_DIR}/test-results/e2e-fresh/${RUN_ID}}"
CLEANED_UP=0
mkdir -p "${STACK_DIR}/config" "${STACK_DIR}/data" "${STACK_DIR}/qdrant" "${ARTIFACT_DIR}"

cleanup() {
  if [[ "${CLEANED_UP}" -eq 1 ]]; then return; fi
  CLEANED_UP=1
  set +e
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

# Start from the exact example shipped in the image, then apply only disposable
# provider/Qdrant addresses. This validates the fresh public config shape.
docker run --rm --entrypoint sh "${TARGET_IMAGE}" -c 'cat /app/config/config.example.yaml' \
  >"${STACK_DIR}/config/config.yaml"
docker network create --internal "${NETWORK_NAME}" >/dev/null
docker run -d --name "${QDRANT_NAME}" --network "${NETWORK_NAME}" \
  -v "${STACK_DIR}/qdrant:/qdrant/storage:rw" qdrant/qdrant:latest >/dev/null
docker run -d --name "${FAKE_NAME}" --network "${NETWORK_NAME}" \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m \
  --tmpfs /app/config:rw,nosuid,nodev,size=8m --tmpfs /app/data:rw,nosuid,nodev,size=8m \
  --tmpfs /app/prompts:rw,nosuid,nodev,size=8m \
  -v "${ROOT_DIR}/tests/e2e:/e2e:ro" --entrypoint python "${TARGET_IMAGE}" \
  /e2e/strict_anthropic.py --port 9000 >/dev/null

FAKE_NAME_ENV="${FAKE_NAME}" QDRANT_NAME_ENV="${QDRANT_NAME}" CONFIG_FILE="${STACK_DIR}/config/config.yaml" \
  "${E2E_PYTHON}" - <<'PY'
import os, pathlib, yaml
path = pathlib.Path(os.environ["CONFIG_FILE"])
raw = yaml.safe_load(path.read_text()) or {}
fake = os.environ["FAKE_NAME_ENV"]
qdrant = os.environ["QDRANT_NAME_ENV"]
profile = {
    "model": "anthropic/claude-sonnet-5", "api_base": f"http://{fake}:9000",
    "api_key": "fresh-fake-key", "temperature": 0.0, "max_tokens": 2048, "timeout_seconds": 20,
}
raw["llm"] = dict(profile)
raw.setdefault("profiles", {}).setdefault("active", {}).update({"llm": "default", "main_llm": "default"})
raw["profiles"].setdefault("llm", {})["default"] = dict(profile)
embedding = {"model": "openai/text-embedding-3-small", "api_base": f"http://{fake}:9000/v1", "api_key": "fresh-fake-key", "timeout_seconds": 10}
raw["embeddings"] = dict(embedding)
raw["profiles"].setdefault("active", {})["embeddings"] = "default"
raw["profiles"].setdefault("embeddings", {})["default"] = dict(embedding)
raw.setdefault("memory", {}).update({"enabled": True, "backend": "qdrant", "qdrant_url": f"http://{qdrant}:6333", "qdrant_api_key": ""})
raw.setdefault("inventory_index", {})["run_on_startup"] = False
raw.setdefault("routing", {})["qdrant_connection_routing_enabled"] = False
raw.setdefault("agentic_loop", {})["native_agent_mcp_enabled"] = False
raw.setdefault("ui", {})["language"] = "en"
path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
PY

docker run -d --name "${ARIA_NAME}" --network "${NETWORK_NAME}" \
  -v "${STACK_DIR}/config:/app/config:rw" -v "${STACK_DIR}/data:/app/data:rw" \
  -v "${ROOT_DIR}/prompts:/app/prompts:ro" \
  -e ARIA_ARIA_HOST=0.0.0.0 -e ARIA_ARIA_PORT=8800 \
  --entrypoint python "${TARGET_IMAGE}" -m uvicorn aria.main:app --host 0.0.0.0 --port 8800 >/dev/null

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
            if response.status < 500: raise SystemExit(0)
    except Exception: time.sleep(.25)
raise SystemExit("timeout waiting for " + sys.argv[1])
PY
}
ARIA_URL="http://$(container_ip "${ARIA_NAME}"):8800"
FAKE_URL="http://$(container_ip "${FAKE_NAME}"):9000"
wait_url "${FAKE_URL}/health"
wait_url "${ARIA_URL}/health"
"${E2E_PYTHON}" "${ROOT_DIR}/tests/e2e/upgrade_604.py" fresh \
  --base-url "${ARIA_URL}" --fake-url "${FAKE_URL}" \
  --evidence "${ARTIFACT_DIR}/fresh-install.json"

echo "Fresh Alpha983 install passed. Evidence: ${ARTIFACT_DIR}/fresh-install.json"
