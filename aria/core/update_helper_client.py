from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.request import Request as URLRequest
from urllib.request import urlopen


UPDATE_HELPER_URL_SECRET = "updates.helper_url"
UPDATE_HELPER_TOKEN_SECRET = "updates.helper_token"


@dataclass(slots=True)
class UpdateHelperConfig:
    mode: str
    url: str
    token: str

    @property
    def enabled(self) -> bool:
        return self.mode in {"managed-helper", "internal-local-helper"} and bool(self.url) and bool(self.token)


def helper_status_visual(
    status: str,
    *,
    running: bool = False,
    configured: bool = True,
    reachable: bool = True,
    last_error: str = "",
) -> str:
    if not configured:
        return "warn"
    if not reachable:
        return "error"
    if running:
        return "warn"
    normalized = str(status or "").strip().lower()
    if last_error and normalized not in {"ok", "idle"}:
        return "error"
    if normalized in {"ok", "idle", "accepted", "complete", "completed", "success"}:
        return "ok"
    if normalized in {"warn", "warning", "requested", "pending", "starting"}:
        return "warn"
    if normalized in {"error", "failed", "unreachable"}:
        return "error"
    if normalized == "disabled":
        return "warn"
    return "warn"


def resolve_update_helper_config(*, env: dict[str, str] | None = None, secure_store: Any | None = None) -> UpdateHelperConfig:
    source = env if env is not None else os.environ
    mode = str(source.get("ARIA_UPDATE_MODE", "") or "").strip().lower()
    url = str(source.get("ARIA_UPDATER_URL", "") or "").strip()
    token = str(source.get("ARIA_UPDATER_TOKEN", "") or "").strip()
    if secure_store is not None:
        try:
            url = str(secure_store.get_secret(UPDATE_HELPER_URL_SECRET, url) or url).strip()
        except Exception:
            pass
        try:
            token = str(secure_store.get_secret(UPDATE_HELPER_TOKEN_SECRET, token) or token).strip()
        except Exception:
            pass
    return UpdateHelperConfig(mode=mode, url=url.rstrip("/"), token=token)


def _decode_json_response(response: Any) -> dict[str, Any]:
    payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Update helper response is not an object.")
    return payload


def _request_json(
    config: UpdateHelperConfig,
    *,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 2.5,
) -> dict[str, Any]:
    if not config.enabled:
        raise ValueError("GUI update helper is not enabled.")
    body = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "ARIA Update UI/1.0",
        "X-ARIA-Update-Token": config.token,
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = URLRequest(f"{config.url}{path}", data=body, method=method.upper(), headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            return _decode_json_response(response)
    except HTTPError as exc:
        try:
            details = _decode_json_response(exc)
            message = str(details.get("detail", "") or details.get("error", "") or "").strip()
        except Exception:
            message = ""
        raise RuntimeError(message or f"HTTP {exc.code} from update helper.") from exc
    except (URLError, OSError, TimeoutError) as exc:
        raise RuntimeError(f"Update helper not reachable: {exc}") from exc


def fetch_update_helper_status(config: UpdateHelperConfig, *, timeout: float = 2.0) -> dict[str, Any]:
    if not config.enabled:
        return {
            "supported": False,
            "reachable": False,
            "running": False,
            "status": "disabled",
            "error": "",
            "last_error": "",
            "log_tail": [],
            "visual_status": helper_status_visual("disabled", configured=False, reachable=False),
        }
    payload = _request_json(config, method="GET", path="/status", timeout=timeout)
    payload["supported"] = True
    payload["reachable"] = True
    payload.setdefault("running", False)
    payload.setdefault("status", "idle")
    payload.setdefault("error", "")
    payload.setdefault("last_error", "")
    payload.setdefault("log_tail", [])
    payload["visual_status"] = helper_status_visual(
        str(payload.get("status", "") or ""),
        running=bool(payload.get("running", False)),
        configured=True,
        reachable=True,
        last_error=str(payload.get("last_error", "") or payload.get("error", "") or ""),
    )
    return payload


def trigger_update_helper_run(config: UpdateHelperConfig, *, timeout: float = 2.5) -> dict[str, Any]:
    return _request_json(
        config,
        method="POST",
        path="/run",
        payload={"action": "run-update"},
        timeout=timeout,
    )
