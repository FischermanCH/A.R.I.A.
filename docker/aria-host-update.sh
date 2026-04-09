#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_TAR_DIR="/mnt/NAS/aria-images"
if [[ ! -d "$DEFAULT_TAR_DIR" ]]; then
  if [[ -d "$REPO_ROOT/dist" ]]; then
    DEFAULT_TAR_DIR="$REPO_ROOT/dist"
  else
    DEFAULT_TAR_DIR="$SCRIPT_DIR"
  fi
fi
DEFAULT_LOCAL_STACK_FILE="$SCRIPT_DIR/portainer-stack.alpha3.local.yml"
DEFAULT_INTERNAL_IMAGE_REF="aria:alpha-local"
DEFAULT_SERVICE_NAME="aria"
DEFAULT_HOST_UPDATE_ENV_FILE="$SCRIPT_DIR/aria-host-update.env"

HOST_UPDATE_ENV_FILE="${HOST_UPDATE_ENV_FILE:-$DEFAULT_HOST_UPDATE_ENV_FILE}"
if [[ -f "$HOST_UPDATE_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$HOST_UPDATE_ENV_FILE"
fi

PORTAINER_URL="${PORTAINER_URL:-}"
PORTAINER_API_KEY="${PORTAINER_API_KEY:-}"
PORTAINER_INSECURE="${PORTAINER_INSECURE:-false}"

log() {
  printf '[aria-host-update] %s\n' "$*"
}

warn() {
  printf '[aria-host-update] WARN: %s\n' "$*" >&2
}

die() {
  printf '[aria-host-update] ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Kommando fehlt: $1"
}

usage() {
  cat <<'USAGE'
Usage:
  aria-host-update.sh detect
  aria-host-update.sh update [--project NAME] [--stack-file PATH] [--env-file PATH] [--tar-dir PATH] [--dry-run]
  aria-host-update.sh help

What it does:
  - detect: list compose-based ARIA stacks on this host
  - update: update exactly one chosen ARIA stack and only recreate the ARIA service

Defaults:
  - internal alpha-local stacks load the newest TAR from /mnt/NAS/aria-images
  - registry/public stacks run docker compose pull for the aria service
  - qdrant, searxng, valkey and data volumes stay untouched

Options:
  --project NAME     Compose project to update. Required if multiple ARIA stacks exist.
  --stack-file PATH  Explicit compose/stack file to use for recreate.
                     Helpful for Portainer/custom stacks with own volume names.
  --env-file PATH    Optional env file for docker compose interpolation.
  --tar-dir PATH     TAR directory for internal alpha-local updates.
  --dry-run          Print the resolved plan without changing anything.

Optional Portainer API env:
  PORTAINER_URL         e.g. https://portainer.example.lan:9443
  PORTAINER_API_KEY     access token from the Portainer user account
  PORTAINER_INSECURE    true/false for self-signed TLS
USAGE
}

container_exists() {
  docker inspect "$1" >/dev/null 2>&1
}

inspect_label() {
  local container_name="$1"
  local key="$2"
  docker inspect "$container_name" --format "{{ index .Config.Labels \"$key\" }}" 2>/dev/null || true
}

inspect_env() {
  local container_name="$1"
  local key="$2"
  docker inspect "$container_name" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
    | sed -n "s/^${key}=//p" \
    | head -n1
}

inspect_config_image() {
  docker inspect "$1" --format '{{.Config.Image}}' 2>/dev/null || true
}

inspect_runtime_image_id() {
  docker inspect "$1" --format '{{.Image}}' 2>/dev/null || true
}

inspect_health() {
  docker inspect "$1" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' 2>/dev/null || true
}

container_for_service() {
  local project="$1"
  local service="$2"
  docker ps -a \
    --filter "label=com.docker.compose.project=$project" \
    --filter "label=com.docker.compose.service=$service" \
    --format '{{.Names}}' \
    | head -n1
}

published_host_port() {
  local container_name="$1"
  local mapping
  mapping="$(docker port "$container_name" 8800/tcp 2>/dev/null | head -n1 || true)"
  if [[ -z "$mapping" ]]; then
    return 0
  fi
  printf '%s\n' "$mapping" | awk -F: '{print $NF}' | tr -d '[:space:]'
}

mode_for_image() {
  local image_ref="$1"
  if [[ "$image_ref" == "$DEFAULT_INTERNAL_IMAGE_REF" ]]; then
    printf 'internal-local\n'
    return 0
  fi
  if [[ "$image_ref" == fischermanch/aria:* ]]; then
    printf 'registry\n'
    return 0
  fi
  printf 'custom\n'
}

project_rows() {
  local aria_container project
  docker ps -a --filter "label=com.docker.compose.service=$DEFAULT_SERVICE_NAME" --format '{{.Names}}' \
    | while IFS= read -r aria_container; do
        [[ -n "$aria_container" ]] || continue
        project="$(inspect_label "$aria_container" 'com.docker.compose.project')"
        [[ -n "$project" && "$project" != "<no value>" ]] || continue
        printf '%s\t%s\n' "$project" "$aria_container"
      done \
    | sort -u
}

print_detect_table() {
  local rows=()
  local line project aria_container qdrant_container searxng_container image_ref mode health port public_url stack_file_source

  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    rows+=("$line")
  done < <(project_rows)

  if (( ${#rows[@]} == 0 )); then
    die "Keine Compose-basierten ARIA-Stacks auf diesem Host gefunden."
  fi

  printf '%-18s %-24s %-14s %-10s %-6s %-10s %s\n' 'PROJECT' 'ARIA CONTAINER' 'MODE' 'HEALTH' 'PORT' 'STACK' 'PUBLIC URL'
  for line in "${rows[@]}"; do
    project="${line%%$'\t'*}"
    aria_container="${line#*$'\t'}"
    qdrant_container="$(container_for_service "$project" qdrant)"
    searxng_container="$(container_for_service "$project" searxng)"
    image_ref="$(inspect_config_image "$aria_container")"
    mode="$(mode_for_image "$image_ref")"
    health="$(inspect_health "$aria_container")"
    port="$(published_host_port "$aria_container")"
    public_url="$(inspect_env "$aria_container" ARIA_PUBLIC_URL)"
    stack_file_source="$(inspect_label "$aria_container" 'com.docker.compose.project.config_files')"
    if [[ -z "$stack_file_source" || "$stack_file_source" == "<no value>" ]]; then
      if [[ "$mode" == "internal-local" ]]; then
        stack_file_source="helper"
      else
        stack_file_source="unknown"
      fi
    fi
    printf '%-18s %-24s %-14s %-10s %-6s %-10s %s\n' "$project" "$aria_container" "$mode" "${health:-unknown}" "${port:--}" "${stack_file_source##*/}" "${public_url:--}"
    if [[ -n "$qdrant_container" || -n "$searxng_container" ]]; then
      printf '  qdrant=%s  searxng=%s  image=%s\n' "${qdrant_container:--}" "${searxng_container:--}" "$image_ref"
    fi
  done
}

resolve_project() {
  local requested="$1"
  local rows=()
  local line project

  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    rows+=("$line")
  done < <(project_rows)

  (( ${#rows[@]} > 0 )) || die "Keine Compose-basierten ARIA-Stacks auf diesem Host gefunden."

  if [[ -n "$requested" ]]; then
    for line in "${rows[@]}"; do
      project="${line%%$'\t'*}"
      if [[ "$project" == "$requested" ]]; then
        printf '%s\n' "$project"
        return 0
      fi
    done
    die "Compose-Projekt '$requested' nicht gefunden. Erst 'aria-host-update.sh detect' ausfuehren."
  fi

  if (( ${#rows[@]} == 1 )); then
    printf '%s\n' "${rows[0]%%$'\t'*}"
    return 0
  fi

  print_detect_table >&2
  die "Mehrere ARIA-Stacks gefunden. Bitte mit --project <name> das Ziel explizit waehlen."
}

resolve_stack_file() {
  local project="$1"
  local aria_container="$2"
  local mode="$3"
  local override="$4"
  local config_files working_dir candidate candidate_path hinted_path=""

  if [[ -n "$override" ]]; then
    [[ -f "$override" ]] || die "Stack-Datei nicht gefunden: $override"
    printf '%s\n' "$override"
    return 0
  fi

  config_files="$(inspect_label "$aria_container" 'com.docker.compose.project.config_files')"
  working_dir="$(inspect_label "$aria_container" 'com.docker.compose.project.working_dir')"
  if [[ -n "$config_files" && "$config_files" != "<no value>" ]]; then
    while IFS= read -r candidate; do
      [[ -n "$candidate" ]] || continue
      candidate_path="$candidate"
      if [[ ! "$candidate_path" = /* && -n "$working_dir" && "$working_dir" != "<no value>" ]]; then
        candidate_path="$working_dir/$candidate"
      fi
      if [[ -z "$hinted_path" ]]; then
        hinted_path="$candidate_path"
      fi
      if [[ -f "$candidate_path" ]]; then
        printf '%s\n' "$candidate_path"
        return 0
      fi
    done < <(printf '%s' "$config_files" | tr ',' '\n')
  fi

  if [[ -n "$working_dir" && "$working_dir" != "<no value>" ]]; then
    for candidate in docker-compose.yml compose.yml compose.yaml; do
      candidate_path="$working_dir/$candidate"
      if [[ -z "$hinted_path" ]]; then
        hinted_path="$candidate_path"
      fi
      if [[ -f "$candidate_path" ]]; then
        printf '%s\n' "$candidate_path"
        return 0
      fi
    done
  fi

  if [[ -n "$hinted_path" ]]; then
    die "Konnte fuer Projekt '$project' zwar einen Compose-Pfad aus Docker-Labels lesen ($hinted_path), aber die Datei ist fuer den aktuellen Benutzer nicht zugreifbar. Script bitte mit sudo starten oder --stack-file <pfad> angeben."
  fi

  if [[ "$mode" == "internal-local" ]]; then
    if [[ -f "$DEFAULT_TAR_DIR/portainer-stack.alpha3.local.yml" ]]; then
      printf '%s\n' "$DEFAULT_TAR_DIR/portainer-stack.alpha3.local.yml"
      return 0
    fi
    if [[ -f "$DEFAULT_LOCAL_STACK_FILE" ]]; then
      printf '%s\n' "$DEFAULT_LOCAL_STACK_FILE"
      return 0
    fi
  fi

  die "Konnte fuer Projekt '$project' keine Stack-Datei automatisch erkennen. Bitte --stack-file <pfad> angeben."
}

stack_file_hint_path() {
  local aria_container="$1"
  local config_files working_dir candidate candidate_path

  config_files="$(inspect_label "$aria_container" 'com.docker.compose.project.config_files')"
  working_dir="$(inspect_label "$aria_container" 'com.docker.compose.project.working_dir')"

  if [[ -n "$config_files" && "$config_files" != "<no value>" ]]; then
    while IFS= read -r candidate; do
      [[ -n "$candidate" ]] || continue
      candidate_path="$candidate"
      if [[ ! "$candidate_path" = /* && -n "$working_dir" && "$working_dir" != "<no value>" ]]; then
        candidate_path="$working_dir/$candidate"
      fi
      printf '%s\n' "$candidate_path"
      return 0
    done < <(printf '%s' "$config_files" | tr ',' '\n')
  fi

  if [[ -n "$working_dir" && "$working_dir" != "<no value>" ]]; then
    for candidate in docker-compose.yml compose.yml compose.yaml; do
      candidate_path="$working_dir/$candidate"
      printf '%s\n' "$candidate_path"
      return 0
    done
  fi

  return 1
}

resolve_accessible_stack_file() {
  local aria_container="$1"
  local mode="$2"
  local override="$3"
  local hint_path

  if [[ -n "$override" ]]; then
    [[ -f "$override" ]] || return 2
    printf '%s\n' "$override"
    return 0
  fi

  hint_path="$(stack_file_hint_path "$aria_container" || true)"
  if [[ -n "$hint_path" && -f "$hint_path" ]]; then
    printf '%s\n' "$hint_path"
    return 0
  fi

  if [[ "$mode" == "internal-local" ]]; then
    if [[ -f "$DEFAULT_TAR_DIR/portainer-stack.alpha3.local.yml" ]]; then
      printf '%s\n' "$DEFAULT_TAR_DIR/portainer-stack.alpha3.local.yml"
      return 0
    fi
    if [[ -f "$DEFAULT_LOCAL_STACK_FILE" ]]; then
      printf '%s\n' "$DEFAULT_LOCAL_STACK_FILE"
      return 0
    fi
  fi

  return 1
}

set_runtime_env() {
  local project="$1"
  local aria_container="$2"
  local qdrant_container="$3"
  local searxng_container="$4"
  local host_port qdrant_key value

  host_port="$(published_host_port "$aria_container")"
  if [[ -n "$host_port" ]]; then
    export ARIA_HTTP_PORT="$host_port"
  fi

  for key in ARIA_PUBLIC_URL ARIA_ARIA_HOST ARIA_ARIA_PORT ARIA_LLM_API_BASE ARIA_LLM_MODEL ARIA_EMBEDDINGS_API_BASE ARIA_EMBEDDINGS_MODEL ARIA_QDRANT_URL; do
    value="$(inspect_env "$aria_container" "$key")"
    if [[ -n "$value" ]]; then
      export "$key=$value"
    fi
  done

  qdrant_key=""
  if [[ -n "$qdrant_container" ]]; then
    qdrant_key="$(inspect_env "$qdrant_container" 'QDRANT__SERVICE__API_KEY')"
  fi
  if [[ -z "$qdrant_key" ]]; then
    qdrant_key="$(inspect_env "$aria_container" 'ARIA_QDRANT_API_KEY')"
  fi
  if [[ -n "$qdrant_key" ]]; then
    export ARIA_QDRANT_API_KEY="$qdrant_key"
  fi

  if [[ -n "$searxng_container" ]]; then
    value="$(inspect_env "$searxng_container" 'SEARXNG_SECRET')"
    if [[ -n "$value" ]]; then
      export SEARXNG_SECRET="$value"
    fi
    value="$(inspect_env "$searxng_container" 'SEARXNG_LIMITER')"
    if [[ -n "$value" ]]; then
      export SEARXNG_LIMITER="$value"
    fi
  fi

  log "Nutze Compose-Projekt: $project"
  if [[ -n "${ARIA_PUBLIC_URL:-}" ]]; then
    log "Public URL: ${ARIA_PUBLIC_URL}"
  fi
  if [[ -n "${ARIA_HTTP_PORT:-}" ]]; then
    log "Host-Port: ${ARIA_HTTP_PORT}"
  fi
}

find_latest_tar() {
  local tar_dir="$1"
  [[ -d "$tar_dir" ]] || die "TAR-Verzeichnis nicht gefunden: $tar_dir"

  find "$tar_dir" -maxdepth 1 -type f -name 'aria-alpha*-local.tar' \
    | sed 's#^.*/##' \
    | awk '
        $0 == "aria-alpha-local.tar" { printf "%012d %s\n", 0, $0; next }
        $0 ~ /^aria-alpha[0-9]+-local\.tar$/ {
          version = $0
          sub(/^aria-alpha/, "", version)
          sub(/-local\.tar$/, "", version)
          printf "%012d %s\n", version + 0, $0
          next
        }
      ' \
    | sort \
    | tail -n1 \
    | cut -d' ' -f2- \
    | sed "s#^#$tar_dir/#"
}

wait_for_aria_health() {
  local aria_container="$1"
  local attempts="${2:-30}"
  local delay_seconds="${3:-2}"
  local idx

  for idx in $(seq 1 "$attempts"); do
    if container_exists "$aria_container"; then
      if docker exec "$aria_container" python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8800/health', timeout=3); body=r.read().decode('utf-8','replace'); raise SystemExit(0 if r.status == 200 and 'ok' in body else 1)" >/dev/null 2>&1; then
        return 0
      fi
    fi
    sleep "$delay_seconds"
  done
  return 1
}

run_compose_recreate() {
  local project="$1"
  local stack_file="$2"
  local env_file="$3"
  local service_name="$4"
  local -a compose_args

  compose_args=(-p "$project")
  if [[ -n "$env_file" ]]; then
    [[ -f "$env_file" ]] || die "Env-Datei nicht gefunden: $env_file"
    compose_args+=(--env-file "$env_file")
  fi

  docker compose "${compose_args[@]}" -f "$stack_file" up -d --no-deps --force-recreate "$service_name"
}

run_registry_pull() {
  local project="$1"
  local stack_file="$2"
  local env_file="$3"
  local service_name="$4"
  local -a compose_args

  compose_args=(-p "$project")
  if [[ -n "$env_file" ]]; then
    [[ -f "$env_file" ]] || die "Env-Datei nicht gefunden: $env_file"
    compose_args+=(--env-file "$env_file")
  fi

  docker compose "${compose_args[@]}" -f "$stack_file" pull "$service_name"
}

validate_compose_plan() {
  local project="$1"
  local stack_file="$2"
  local env_file="$3"
  local -a compose_args

  compose_args=(-p "$project")
  if [[ -n "$env_file" ]]; then
    [[ -f "$env_file" ]] || die "Env-Datei nicht gefunden: $env_file"
    compose_args+=(--env-file "$env_file")
  fi

  docker compose "${compose_args[@]}" -f "$stack_file" config -q >/dev/null
}

portainer_is_enabled() {
  [[ -n "$PORTAINER_URL" && -n "$PORTAINER_API_KEY" ]]
}

portainer_python() {
  python3 - "$@"
}

portainer_request() {
  local method="$1"
  local path="$2"
  local body_file="${3:-}"
  local url="${PORTAINER_URL%/}/api${path}"
  local -a curl_args

  require_cmd curl
  require_cmd python3
  portainer_is_enabled || die "Portainer API ist nicht konfiguriert. PORTAINER_URL und PORTAINER_API_KEY setzen."

  curl_args=(-fsSL -X "$method" -H "X-API-Key: $PORTAINER_API_KEY" -H "Accept: application/json")
  if [[ "${PORTAINER_INSECURE,,}" == "true" || "${PORTAINER_INSECURE}" == "1" ]]; then
    curl_args+=(-k)
  fi
  if [[ -n "$body_file" ]]; then
    [[ -f "$body_file" ]] || die "Portainer-Body-Datei nicht gefunden: $body_file"
    curl_args+=(-H "Content-Type: application/json" --data-binary "@$body_file")
  fi
  curl "${curl_args[@]}" "$url"
}

portainer_find_stack() {
  local project="$1"
  local tmp_json stack_id stack_json
  tmp_json="$(mktemp /tmp/aria-portainer-stacks.XXXXXX.json)"
  portainer_request GET "/stacks" >"$tmp_json"
  stack_id="$(
    portainer_python "$project" "$tmp_json" <<'PY'
import json, sys

project = sys.argv[1]
path = sys.argv[2]
with open(path, "r", encoding="utf-8") as handle:
    stacks = json.load(handle)

matches = [item for item in stacks if str(item.get("Name", "")).strip() == project]
if not matches:
    print(f"NOT_FOUND:{project}")
    sys.exit(3)
if len(matches) > 1:
    print(f"MULTIPLE:{project}")
    sys.exit(4)

stack = matches[0]
print(stack.get("Id", ""))
PY
  )"
  local status=$?
  rm -f "$tmp_json"
  case "$status" in
    0) ;;
    3) die "Kein passender Portainer-Stack mit Name '$project' gefunden." ;;
    4) die "Mehrere Portainer-Stacks mit Name '$project' gefunden." ;;
    *) die "Portainer-Stacksuche fuer '$project' fehlgeschlagen." ;;
  esac
  [[ -n "$stack_id" ]] || die "Portainer-Stack '$project' hat keine Id."
  stack_json="$(portainer_request GET "/stacks/${stack_id}")"
  printf '%s' "$stack_json"
}

portainer_stack_file_content() {
  local stack_id="$1"
  local tmp_json
  tmp_json="$(mktemp /tmp/aria-portainer-stackfile.XXXXXX.json)"
  portainer_request GET "/stacks/${stack_id}/file" >"$tmp_json"
  portainer_python "$tmp_json" <<'PY'
import json, sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)
print(payload.get("StackFileContent", ""))
PY
  local status=$?
  rm -f "$tmp_json"
  return "$status"
}

portainer_build_update_payload() {
  local stack_json_file="$1"
  local stack_file_content_file="$2"
  local payload_file="$3"
  portainer_python "$stack_json_file" "$stack_file_content_file" "$payload_file" <<'PY'
import json, sys

stack_path, content_path, payload_path = sys.argv[1:4]
with open(stack_path, "r", encoding="utf-8") as handle:
    stack = json.load(handle)
with open(content_path, "r", encoding="utf-8") as handle:
    stack_file_content = handle.read()

git_config = stack.get("GitConfig")
if git_config:
    print("GIT_STACK_NOT_SUPPORTED")
    sys.exit(7)

payload = {
    "StackFileContent": stack_file_content,
    "Env": stack.get("Env") or [],
    "Prune": False,
    "RepullImageAndRedeploy": True,
}
with open(payload_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle)
PY
  local status=$?
  case "$status" in
    0) return 0 ;;
    7) die "Der Portainer-Stack ist git-basiert. Dieser Host-Helper unterstuetzt aktuell nur file-basierte Portainer-Stacks." ;;
    *) die "Konnte den Portainer-Update-Payload nicht erzeugen." ;;
  esac
}

portainer_update_stack() {
  local project="$1"
  local dry_run="$2"
  local stack_json stack_json_file stack_id endpoint_id stack_type stack_file_tmp payload_tmp

  stack_json="$(portainer_find_stack "$project")"
  stack_json_file="$(mktemp /tmp/aria-portainer-stack.XXXXXX.json)"
  printf '%s' "$stack_json" >"$stack_json_file"

  stack_id="$(portainer_python "$stack_json_file" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as handle:
    stack = json.load(handle)
print(stack.get("Id", ""))
PY
)"
  endpoint_id="$(portainer_python "$stack_json_file" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as handle:
    stack = json.load(handle)
print(stack.get("EndpointId", ""))
PY
)"
  stack_type="$(portainer_python "$stack_json_file" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as handle:
    stack = json.load(handle)
print(stack.get("Type", ""))
PY
)"

  [[ -n "$stack_id" ]] || die "Portainer-Stack '$project' hat keine Id."
  [[ -n "$endpoint_id" ]] || die "Portainer-Stack '$project' hat keine EndpointId."
  if [[ "$stack_type" != "2" && "$stack_type" != "3" ]]; then
    warn "Portainer-Stack '$project' hat Type=$stack_type. Ich versuche trotzdem ein file-basiertes Update."
  fi

  stack_file_tmp="$(mktemp /tmp/aria-portainer-stackfile.XXXXXX.yml)"
  portainer_stack_file_content "$stack_id" >"$stack_file_tmp"
  [[ -s "$stack_file_tmp" ]] || die "Portainer lieferte fuer Stack '$project' keinen StackFileContent."

  payload_tmp="$(mktemp /tmp/aria-portainer-payload.XXXXXX.json)"
  portainer_build_update_payload "$stack_json_file" "$stack_file_tmp" "$payload_tmp"

  log "Portainer-Stack: $project"
  log "Portainer-Stack-ID: $stack_id"
  log "Portainer-Endpoint-ID: $endpoint_id"
  log "Portainer-URL: ${PORTAINER_URL%/}"

  if [[ "$dry_run" == "true" ]]; then
    log "Dry-run: wuerde Portainer-Stack '$project' per API mit RepullImageAndRedeploy=true aktualisieren."
    rm -f "$stack_json_file" "$stack_file_tmp" "$payload_tmp"
    return 0
  fi

  log "Aktualisiere Portainer-Stack '$project' ueber die Portainer-API ..."
  portainer_request PUT "/stacks/${stack_id}?endpointId=${endpoint_id}" "$payload_tmp" >/dev/null
  rm -f "$stack_json_file" "$stack_file_tmp" "$payload_tmp"
}

acquire_lock() {
  local project="$1"
  local lock_dir="/tmp/aria-host-update-${project}.lock"
  if ! mkdir "$lock_dir" 2>/dev/null; then
    die "Fuer Projekt '$project' laeuft bereits ein Host-Update oder ein Lock ist haengen geblieben: $lock_dir"
  fi
  trap 'rm -rf "$lock_dir"' EXIT
}

update_project() {
  local requested_project="$1"
  local stack_file_override="$2"
  local env_file_override="$3"
  local tar_dir="$4"
  local dry_run="$5"
  local project aria_container qdrant_container searxng_container image_ref mode stack_file="" stack_hint="" env_file old_runtime_image_id loaded_image_ref latest_tar use_portainer_api="false"

  project="$(resolve_project "$requested_project")"
  aria_container="$(container_for_service "$project" "$DEFAULT_SERVICE_NAME")"
  [[ -n "$aria_container" ]] || die "Kein ARIA-Container fuer Compose-Projekt '$project' gefunden."
  qdrant_container="$(container_for_service "$project" qdrant)"
  searxng_container="$(container_for_service "$project" searxng)"
  image_ref="$(inspect_config_image "$aria_container")"
  mode="$(mode_for_image "$image_ref")"
  env_file="$env_file_override"
  stack_hint="$(stack_file_hint_path "$aria_container" || true)"

  if stack_file="$(resolve_accessible_stack_file "$aria_container" "$mode" "$stack_file_override")"; then
    :
  else
    if [[ -n "$stack_file_override" ]]; then
      die "Stack-Datei nicht gefunden: $stack_file_override"
    fi
    if [[ "$mode" != "internal-local" && -n "$stack_hint" && portainer_is_enabled ]]; then
      use_portainer_api="true"
    elif [[ -n "$stack_hint" ]]; then
      die "Konnte fuer Projekt '$project' zwar einen Compose-Pfad aus Docker-Labels lesen ($stack_hint), aber die Datei ist fuer den aktuellen Benutzer nicht zugreifbar. Fuer Portainer-Stacks entweder PORTAINER_URL/PORTAINER_API_KEY setzen oder --stack-file <pfad> angeben."
    else
      die "Konnte fuer Projekt '$project' keine Stack-Datei automatisch erkennen. Bitte --stack-file <pfad> angeben."
    fi
  fi

  set_runtime_env "$project" "$aria_container" "$qdrant_container" "$searxng_container"

  log "Zielprojekt: $project"
  log "ARIA-Container: $aria_container"
  log "Qdrant-Container: ${qdrant_container:-<nicht gefunden>}"
  log "SearXNG-Container: ${searxng_container:-<nicht gefunden>}"
  log "Modus: $mode"
  if [[ "$use_portainer_api" == "true" ]]; then
    log "Update-Pfad: Portainer-API"
    [[ -n "$stack_hint" ]] && log "Label-Hinweis: $stack_hint"
  else
    log "Stack-Datei: $stack_file"
  fi
  if [[ -n "$env_file" ]]; then
    log "Env-Datei: $env_file"
  fi
  if [[ "$use_portainer_api" != "true" ]]; then
    validate_compose_plan "$project" "$stack_file" "$env_file"
  fi

  if [[ "$mode" == "internal-local" ]]; then
    latest_tar="$(find_latest_tar "$tar_dir")"
    [[ -n "$latest_tar" ]] || die "Kein internes ARIA-TAR in $tar_dir gefunden."
    log "Neuestes TAR: $latest_tar"
  else
    log "Image-Referenz: $image_ref"
    if [[ "$mode" == "registry" && "$image_ref" != "fischermanch/aria:alpha" ]]; then
      warn "Das laufende Image ist auf einen festen Tag gepinnt ($image_ref). Das Script zieht denselben Tag erneut; fuer einen Versionssprung muss auch der Stack auf den neuen Tag zeigen."
    fi
    if [[ "$mode" == "custom" ]]; then
      warn "Das laufende Image ist kein Standard-ARIA-Tag. Ich versuche trotzdem einen Compose-Pull/Recreate fuer den Service '$DEFAULT_SERVICE_NAME'."
    fi
  fi

  if [[ "$dry_run" == "true" ]]; then
    if [[ "$use_portainer_api" == "true" ]]; then
      portainer_update_stack "$project" "$dry_run"
    elif [[ "$mode" == "internal-local" ]]; then
      log "Dry-run: wuerde '$latest_tar' laden, nach '$DEFAULT_INTERNAL_IMAGE_REF' taggen und dann nur den ARIA-Service neu erstellen."
    else
      log "Dry-run: wuerde 'docker compose pull $DEFAULT_SERVICE_NAME' und danach nur den ARIA-Service neu erstellen."
    fi
    return 0
  fi

  if [[ "$use_portainer_api" == "true" ]]; then
    acquire_lock "$project"
    portainer_update_stack "$project" "$dry_run"
    local refreshed_aria_container
    refreshed_aria_container="$(container_for_service "$project" "$DEFAULT_SERVICE_NAME")"
    if wait_for_aria_health "${refreshed_aria_container:-$aria_container}"; then
      log "Portainer-Update erfolgreich. ARIA ist wieder gesund erreichbar."
      return 0
    fi
    die "Portainer-Update wurde ausgelöst, aber der ARIA-Healthcheck wurde danach nicht wieder gesund. Bitte Stack/Portainer-Logs pruefen."
  fi

  acquire_lock "$project"
  old_runtime_image_id="$(inspect_runtime_image_id "$aria_container")"
  [[ -n "$old_runtime_image_id" ]] || die "Konnte das bisher laufende Image des Containers '$aria_container' nicht lesen."

  if [[ "$mode" == "internal-local" ]]; then
    local docker_load_log
    docker_load_log="$(mktemp /tmp/aria-host-update-docker-load.XXXXXX.log)"
    log "Lade neues internes TAR ..."
    docker load -i "$latest_tar" >"$docker_load_log"
    cat "$docker_load_log"
    loaded_image_ref="$(sed -n 's/^Loaded image: //p' "$docker_load_log" | head -n1 | tr -d '\r')"
    rm -f "$docker_load_log"
    [[ -n "$loaded_image_ref" ]] || die "Konnte geladenes Image-Tag aus docker load nicht erkennen."
    if [[ "$loaded_image_ref" != "$DEFAULT_INTERNAL_IMAGE_REF" ]]; then
      log "Retagge geladenes Image: $loaded_image_ref -> $DEFAULT_INTERNAL_IMAGE_REF"
      docker tag "$loaded_image_ref" "$DEFAULT_INTERNAL_IMAGE_REF"
    fi
  else
    log "Hole neues Registry-Image fuer den ARIA-Service ..."
    run_registry_pull "$project" "$stack_file" "$env_file" "$DEFAULT_SERVICE_NAME"
  fi

  log "Erstelle nur den ARIA-Service neu. Qdrant, SearXNG und Volumes bleiben unberuehrt."
  run_compose_recreate "$project" "$stack_file" "$env_file" "$DEFAULT_SERVICE_NAME"

  if wait_for_aria_health "$aria_container"; then
    log "Update erfolgreich. ARIA ist wieder gesund erreichbar."
    return 0
  fi

  warn "Healthcheck nach Update fehlgeschlagen. Starte best-effort Rollback auf das vorher laufende Image."
  docker tag "$old_runtime_image_id" "$image_ref"
  run_compose_recreate "$project" "$stack_file" "$env_file" "$DEFAULT_SERVICE_NAME" || true

  if wait_for_aria_health "$aria_container"; then
    die "Update fehlgeschlagen, Rollback auf das vorherige ARIA-Image war erfolgreich."
  fi

  die "Update fehlgeschlagen und Rollback konnte die Health nicht wiederherstellen. Bitte 'docker compose -p $project -f $stack_file logs aria' pruefen."
}

main() {
  require_cmd docker
  docker compose version >/dev/null 2>&1 || die "docker compose ist nicht verfuegbar"

  local command="${1:-detect}"
  shift || true

  case "$command" in
    detect)
      [[ $# -eq 0 ]] || die "detect erwartet keine weiteren Argumente"
      print_detect_table
      ;;
    update)
      local project=""
      local stack_file=""
      local env_file=""
      local tar_dir="$DEFAULT_TAR_DIR"
      local dry_run="false"
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --project)
            project="${2:-}"
            shift 2
            ;;
          --stack-file)
            stack_file="${2:-}"
            shift 2
            ;;
          --env-file)
            env_file="${2:-}"
            shift 2
            ;;
          --tar-dir)
            tar_dir="${2:-}"
            shift 2
            ;;
          --dry-run)
            dry_run="true"
            shift
            ;;
          -h|--help)
            usage
            exit 0
            ;;
          *)
            die "Unbekannte Option fuer update: $1"
            ;;
        esac
      done
      update_project "$project" "$stack_file" "$env_file" "$tar_dir" "$dry_run"
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      die "Unbekanntes Kommando: $command"
      ;;
  esac
}

main "$@"
