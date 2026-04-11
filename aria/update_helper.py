from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
from fastapi.responses import JSONResponse


INSTALL_DIR = Path(os.environ.get("ARIA_UPDATE_INSTALL_DIR", "/managed")).resolve()
STATE_DIR = Path(os.environ.get("ARIA_UPDATE_STATE_DIR", str(INSTALL_DIR / ".aria-updater"))).resolve()
STATE_PATH = STATE_DIR / "state.json"
LOG_PATH = STATE_DIR / "update.log"
TOKEN = str(os.environ.get("ARIA_UPDATE_TOKEN", "") or "").strip()
HELPER_HOST = str(os.environ.get("ARIA_UPDATE_HELPER_HOST", "0.0.0.0") or "0.0.0.0").strip() or "0.0.0.0"
HELPER_PORT = int(str(os.environ.get("ARIA_UPDATE_HELPER_PORT", "8094") or "8094").strip() or "8094")
EXCLUDED_SERVICES = {part.strip() for part in str(os.environ.get("ARIA_UPDATE_EXCLUDE_SERVICES", "aria-updater")).split(",") if part.strip()}
HEALTH_URL = str(os.environ.get("ARIA_UPDATE_HEALTH_URL", "http://aria:8800/health") or "http://aria:8800/health").strip()
HELPER_MODE = str(os.environ.get("ARIA_UPDATE_HELPER_MODE", "managed") or "managed").strip().lower()
LOCAL_UPDATE_SCRIPT = Path(os.environ.get("ARIA_UPDATE_LOCAL_SCRIPT", "/mnt/NAS/aria-images/update-local-aria.sh")).resolve()
LOCAL_TAR_DIR = str(os.environ.get("ARIA_UPDATE_LOCAL_TAR_DIR", "/mnt/NAS/aria-images") or "/mnt/NAS/aria-images").strip()
LOCAL_STACK_FILE = str(
    os.environ.get("ARIA_UPDATE_LOCAL_STACK_FILE", "/mnt/NAS/aria-images/portainer-stack.alpha3.local.yml")
    or "/mnt/NAS/aria-images/portainer-stack.alpha3.local.yml"
).strip()
LOCAL_ENV_FILE = str(os.environ.get("ARIA_UPDATE_LOCAL_ENV_FILE", "/mnt/NAS/aria-images/aria-stack.env") or "/mnt/NAS/aria-images/aria-stack.env").strip()
LOCAL_IMAGE_REF = str(os.environ.get("ARIA_UPDATE_LOCAL_IMAGE_REF", "aria:alpha-local") or "aria:alpha-local").strip()
LOCAL_SERVICE_NAME = str(os.environ.get("ARIA_UPDATE_LOCAL_SERVICE_NAME", "aria") or "aria").strip()
LOCAL_QDRANT_SERVICE_NAME = str(os.environ.get("ARIA_UPDATE_LOCAL_QDRANT_SERVICE_NAME", "aria-qdrant") or "aria-qdrant").strip()
LOCAL_COMPOSE_PROJECT_NAME = str(os.environ.get("ARIA_UPDATE_LOCAL_PROJECT_NAME", "") or "").strip()
STATE_LOCK = threading.Lock()

app = FastAPI(title="ARIA Update Helper")


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _default_state() -> dict[str, Any]:
    return {
        "status": "idle",
        "running": False,
        "current_step": "",
        "last_started_at": "",
        "last_finished_at": "",
        "last_error": "",
        "last_result": "",
        "log_path": str(LOG_PATH),
        "log_tail": [],
    }


def _load_state() -> dict[str, Any]:
    _ensure_state_dir()
    if not STATE_PATH.exists():
        return _default_state()
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_state()
    if not isinstance(payload, dict):
        return _default_state()
    base = _default_state()
    base.update(payload)
    return base


def _save_state(state: dict[str, Any]) -> None:
    _ensure_state_dir()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_log_tail(*, max_lines: int = 40) -> list[str]:
    if not LOG_PATH.exists():
        return []
    try:
        lines = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    if max_lines <= 0:
        return []
    return lines[-max_lines:]


def _write_log_line(message: str) -> None:
    _ensure_state_dir()
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def _update_state(**updates: Any) -> dict[str, Any]:
    with STATE_LOCK:
        state = _load_state()
        state.update(updates)
        state["log_tail"] = _read_log_tail()
        _save_state(state)
        return state


def _require_auth(provided: str | None) -> None:
    if not TOKEN:
        raise HTTPException(status_code=503, detail="Update helper token missing.")
    if str(provided or "").strip() != TOKEN:
        raise HTTPException(status_code=401, detail="Invalid update helper token.")


def _compose_base_command() -> list[str]:
    if subprocess.run(["docker", "compose", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0:
        return [
            "docker",
            "compose",
            "--env-file",
            str(INSTALL_DIR / ".env"),
            "-f",
            str(INSTALL_DIR / "docker-compose.yml"),
        ]
    if subprocess.run(["docker-compose", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0:
        return [
            "docker-compose",
            "--env-file",
            str(INSTALL_DIR / ".env"),
            "-f",
            str(INSTALL_DIR / "docker-compose.yml"),
        ]
    raise RuntimeError("Neither 'docker compose' nor 'docker-compose' is available inside the update helper.")


def _read_install_env_value(key: str) -> str:
    env_path = INSTALL_DIR / ".env"
    if not env_path.exists():
        return ""
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            if raw_line.startswith(f"{key}="):
                return raw_line.split("=", 1)[1].strip()
    except OSError:
        return ""
    return ""


def _managed_target_image() -> str:
    image = _read_install_env_value("ARIA_IMAGE")
    return image or "fischermanch/aria:alpha"


def _refresh_managed_stack_files_from_target_image() -> None:
    image = _managed_target_image()
    _run_logged(["docker", "pull", image], step="Pull ARIA target image for stack refresh")
    _run_logged(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{INSTALL_DIR}:/managed",
            image,
            "/app/docker/setup-compose-stack.sh",
            "--install-dir",
            "/managed",
            "--upgrade-existing",
            "--force",
            "--no-start",
        ],
        step="Refresh managed stack files",
    )


def _run_logged(command: list[str], *, step: str) -> None:
    _write_log_line(f"[{_now_iso()}] {step}")
    _write_log_line(f"$ {' '.join(command)}")
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        process = subprocess.run(
            command,
            cwd=str(INSTALL_DIR),
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    if process.returncode != 0:
        raise RuntimeError(f"{step} failed with exit code {process.returncode}.")


def _run_logged_with_env(
    command: list[str],
    *,
    step: str,
    extra_env: dict[str, str],
    cwd: Path | str | None = None,
) -> None:
    _write_log_line(f"[{_now_iso()}] {step}")
    _write_log_line(f"$ {' '.join(command)}")
    env = os.environ.copy()
    env.update(extra_env)
    working_dir = str(cwd or INSTALL_DIR)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        process = subprocess.run(
            command,
            cwd=working_dir,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            env=env,
        )
    if process.returncode != 0:
        raise RuntimeError(f"{step} failed with exit code {process.returncode}.")


def _compose_services() -> list[str]:
    command = _compose_base_command() + ["config", "--services"]
    result = subprocess.run(
        command,
        cwd=str(INSTALL_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Could not resolve compose services.")
    services = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [service for service in services if service not in EXCLUDED_SERVICES]


def _wait_for_health(*, timeout_seconds: float = 120.0, sleep_seconds: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(HEALTH_URL, timeout=3.0) as response:
                payload = response.read().decode("utf-8", errors="replace")
                if response.status == 200 and "ok" in payload.lower():
                    return
        except (URLError, OSError, TimeoutError):
            pass
        time.sleep(sleep_seconds)
    raise RuntimeError(f"ARIA healthcheck did not recover: {HEALTH_URL}")


def _run_managed_update_worker() -> None:
    _update_state(
        status="running",
        running=True,
        current_step="refresh_stack",
        last_started_at=_now_iso(),
        last_finished_at="",
        last_error="",
        last_result="",
    )
    try:
        LOG_PATH.write_text("", encoding="utf-8")
        _write_log_line(f"[{_now_iso()}] ARIA managed update started.")
        if not (INSTALL_DIR / ".env").exists() or not (INSTALL_DIR / "docker-compose.yml").exists():
            raise RuntimeError(f"Managed install directory incomplete: {INSTALL_DIR}")
        _refresh_managed_stack_files_from_target_image()

        services = _compose_services()
        if not services:
            raise RuntimeError("No updatable compose services found.")
        _update_state(current_step="pull_images")
        _run_logged(_compose_base_command() + ["pull", *services], step="Pull updated images")

        _update_state(current_step="restart_services")
        _run_logged(
            _compose_base_command() + ["up", "-d", "--force-recreate", *services],
            step="Recreate updated services",
        )

        _update_state(current_step="healthcheck")
        _wait_for_health()
        _update_state(current_step="validate_runtime")
        _run_logged([str(INSTALL_DIR / "aria-stack.sh"), "validate"], step="Validate managed services")
        _write_log_line(f"[{_now_iso()}] ARIA managed update completed successfully.")
        _update_state(
            status="ok",
            running=False,
            current_step="",
            last_finished_at=_now_iso(),
            last_result="Update completed successfully.",
        )
    except Exception as exc:  # noqa: BLE001
        _write_log_line(f"[{_now_iso()}] ERROR: {exc}")
        _update_state(
            status="error",
            running=False,
            current_step="",
            last_finished_at=_now_iso(),
            last_error=str(exc),
            last_result="Update failed.",
        )


def _run_internal_local_update_worker() -> None:
    _update_state(
        status="running",
        running=True,
        current_step="aria_pull_refresh",
        last_started_at=_now_iso(),
        last_finished_at="",
        last_error="",
        last_result="",
    )
    try:
        LOG_PATH.write_text("", encoding="utf-8")
        _write_log_line(f"[{_now_iso()}] ARIA internal-local update started.")
        if not LOCAL_UPDATE_SCRIPT.exists():
            raise RuntimeError(f"Local update script missing: {LOCAL_UPDATE_SCRIPT}")
        extra_env = {
            "TAR_DIR": LOCAL_TAR_DIR,
            "STACK_FILE": LOCAL_STACK_FILE,
            "ENV_FILE": LOCAL_ENV_FILE,
            "IMAGE_REF": LOCAL_IMAGE_REF,
            "SERVICE_NAME": LOCAL_SERVICE_NAME,
            "QDRANT_SERVICE_NAME": LOCAL_QDRANT_SERVICE_NAME,
            "HEALTH_URL": HEALTH_URL,
        }
        if LOCAL_COMPOSE_PROJECT_NAME:
            extra_env["COMPOSE_PROJECT_NAME_OVERRIDE"] = LOCAL_COMPOSE_PROJECT_NAME
        local_cwd = LOCAL_UPDATE_SCRIPT.parent if LOCAL_UPDATE_SCRIPT.parent.exists() else Path(LOCAL_TAR_DIR)
        _run_logged_with_env(
            [str(LOCAL_UPDATE_SCRIPT)],
            step="Run internal aria-pull/update-local flow",
            extra_env=extra_env,
            cwd=local_cwd,
        )
        _write_log_line(f"[{_now_iso()}] ARIA internal-local update completed successfully.")
        _update_state(
            status="ok",
            running=False,
            current_step="",
            last_finished_at=_now_iso(),
            last_result="Update completed successfully.",
        )
    except Exception as exc:  # noqa: BLE001
        _write_log_line(f"[{_now_iso()}] ERROR: {exc}")
        _update_state(
            status="error",
            running=False,
            current_step="",
            last_finished_at=_now_iso(),
            last_error=str(exc),
            last_result="Update failed.",
        )


def _run_update_worker() -> None:
    if HELPER_MODE == "internal-local":
        _run_internal_local_update_worker()
        return
    _run_managed_update_worker()


@app.on_event("startup")
def _normalize_state_after_restart() -> None:
    state = _load_state()
    if state.get("running"):
        state["running"] = False
        state["status"] = "error"
        state["current_step"] = ""
        state["last_error"] = "Updater service restarted while an update was running."
        state["last_result"] = "Previous update was interrupted."
        state["last_finished_at"] = _now_iso()
        _save_state(state)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": HELPER_MODE,
        "install_dir": str(INSTALL_DIR),
        "token_configured": bool(TOKEN),
    }


@app.get("/status")
def status(x_aria_update_token: str | None = Header(default=None, alias="X-ARIA-Update-Token")) -> dict[str, Any]:
    _require_auth(x_aria_update_token)
    state = _load_state()
    state["supported"] = True
    state["reachable"] = True
    state["install_dir"] = str(INSTALL_DIR)
    state["health_url"] = HEALTH_URL
    state["mode"] = HELPER_MODE
    state["log_tail"] = _read_log_tail()
    return state


@app.post("/run")
def run_update(x_aria_update_token: str | None = Header(default=None, alias="X-ARIA-Update-Token")) -> JSONResponse:
    _require_auth(x_aria_update_token)
    with STATE_LOCK:
        state = _load_state()
        if state.get("running"):
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "detail": "An update is already running.",
                    "status": state.get("status", "running"),
                    "running": True,
                },
            )
        worker = threading.Thread(target=_run_update_worker, daemon=True, name="aria-managed-update")
        worker.start()
    return JSONResponse(status_code=202, content={"ok": True, "status": "accepted", "running": True})


def main() -> None:
    import uvicorn

    uvicorn.run("aria.update_helper:app", host=HELPER_HOST, port=HELPER_PORT, log_level="info")


if __name__ == "__main__":
    main()
