#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/app"
CONFIG_DIR="${APP_DIR}/config"
PROMPTS_DIR="${APP_DIR}/prompts"
BOOTSTRAP_DIR="${APP_DIR}/bootstrap"
SECRETS_ENV_FILE="${CONFIG_DIR}/secrets.env"

mkdir -p "${CONFIG_DIR}" "${PROMPTS_DIR}" "${APP_DIR}/data/auth" "${APP_DIR}/data/logs" "${APP_DIR}/data/skills"

if [[ ! -f "${CONFIG_DIR}/config.example.yaml" && -f "${BOOTSTRAP_DIR}/config/config.example.yaml" ]]; then
  cp "${BOOTSTRAP_DIR}/config/config.example.yaml" "${CONFIG_DIR}/config.example.yaml"
fi

if [[ ! -f "${CONFIG_DIR}/secrets.env.example" && -f "${BOOTSTRAP_DIR}/config/secrets.env.example" ]]; then
  cp "${BOOTSTRAP_DIR}/config/secrets.env.example" "${CONFIG_DIR}/secrets.env.example"
fi

if [[ ! -f "${CONFIG_DIR}/error_interpreter.yaml" && -f "${BOOTSTRAP_DIR}/config/error_interpreter.yaml" ]]; then
  cp "${BOOTSTRAP_DIR}/config/error_interpreter.yaml" "${CONFIG_DIR}/error_interpreter.yaml"
fi

if [[ ! -f "${PROMPTS_DIR}/persona.md" && -d "${BOOTSTRAP_DIR}/prompts" ]]; then
  cp -a "${BOOTSTRAP_DIR}/prompts/." "${PROMPTS_DIR}/"
fi

if [[ ! -f "${CONFIG_DIR}/config.yaml" && -f "${CONFIG_DIR}/config.example.yaml" ]]; then
  cp "${CONFIG_DIR}/config.example.yaml" "${CONFIG_DIR}/config.yaml"
fi

if [[ ! -f "${SECRETS_ENV_FILE}" && -f "${CONFIG_DIR}/secrets.env.example" ]]; then
  cp "${CONFIG_DIR}/secrets.env.example" "${SECRETS_ENV_FILE}"
fi

if [[ -f "${SECRETS_ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${SECRETS_ENV_FILE}"
  set +a
fi

HOST="${ARIA_ARIA_HOST:-0.0.0.0}"
PORT="${ARIA_ARIA_PORT:-8800}"

cd "${APP_DIR}"
exec python -m uvicorn aria.main:app --host "${HOST}" --port "${PORT}"
