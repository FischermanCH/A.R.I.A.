from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request as URLRequest, urlopen

import yaml

from aria.core.config import get_master_key
from aria.core.pricing_catalog import resolve_litellm_pricing_entry
from aria.core.release_meta import read_release_meta
from aria.core.update_check import get_update_status


@dataclass(frozen=True)
class MainConfigHelperDeps:
    get_base_dir: Callable[[], Path]
    get_config_path: Callable[[], Path]
    get_error_interpreter_path: Callable[[], Path]
    file_editor_catalog: tuple[dict[str, str], ...] | list[dict[str, str]]
    raw_config_cache: dict[str, Any]


@dataclass(frozen=True)
class MainConfigHelpers:
    list_file_editor_entries: Callable[[], list[dict[str, str]]]
    resolve_file_editor_entry: Callable[[str], dict[str, str]]
    resolve_file_editor_file: Callable[[str], Path]
    is_allowed_edit_path: Callable[[Path], bool]
    list_editable_files: Callable[[], list[str]]
    resolve_edit_file: Callable[[str], Path]
    resolve_prompt_file: Callable[[str], Path]
    clear_raw_config_cache: Callable[[], None]
    read_raw_config: Callable[[], dict[str, Any]]
    write_raw_config: Callable[[dict[str, Any]], None]
    enable_bootstrap_admin_mode_in_raw_config: Callable[[dict[str, Any]], dict[str, Any]]
    read_error_interpreter_raw: Callable[[], str]
    parse_lines: Callable[[str], list[str]]
    is_ollama_model: Callable[[str], bool]
    sanitize_profile_name: Callable[[str | None], str]
    normalize_model_key: Callable[[str], str]
    sanitize_connection_name: Callable[[str | None], str]
    resolve_pricing_entry: Callable[[dict[str, Any], str], Any | None]
    load_models_from_api_base: Callable[[str, str, int], list[str]]
    read_release_meta: Callable[[Path], dict[str, str]]
    get_update_status: Callable[[str, int], dict[str, Any]]


def build_main_config_helpers(deps: MainConfigHelperDeps) -> MainConfigHelpers:
    _get_base_dir = deps.get_base_dir
    _get_config_path = deps.get_config_path
    _get_error_interpreter_path = deps.get_error_interpreter_path
    _file_editor_catalog = tuple(deps.file_editor_catalog)
    _raw_config_cache = deps.raw_config_cache

    def _list_file_editor_entries() -> list[dict[str, str]]:
        base_dir = _get_base_dir()
        rows: list[dict[str, str]] = []
        for raw in _file_editor_catalog:
            rel_path = str(raw.get("path", "")).strip().replace("\\", "/")
            if not rel_path or "\x00" in rel_path:
                continue
            candidate = (base_dir / rel_path).resolve()
            try:
                candidate.relative_to(base_dir.resolve())
            except ValueError:
                continue
            if not candidate.exists() or not candidate.is_file():
                continue
            rows.append(
                {
                    "path": rel_path,
                    "label": str(raw.get("label", candidate.name)).strip() or candidate.name,
                    "group": str(raw.get("group", "misc")).strip() or "misc",
                    "mode": str(raw.get("mode", "readonly")).strip() or "readonly",
                }
            )
        return rows

    def _resolve_file_editor_entry(rel_path: str) -> dict[str, str]:
        clean = str(rel_path or "").strip().replace("\\", "/")
        if not clean or "\x00" in clean:
            raise ValueError("Ungültiger Dateipfad.")
        for row in _list_file_editor_entries():
            if row.get("path") == clean:
                return row
        raise ValueError("Datei ist nicht für den Editor freigegeben.")

    def _resolve_file_editor_file(rel_path: str) -> Path:
        entry = _resolve_file_editor_entry(rel_path)
        return (_get_base_dir() / entry["path"]).resolve()

    def _is_allowed_edit_path(path: Path) -> bool:
        base_dir = _get_base_dir()
        resolved = path.resolve()
        for row in _list_file_editor_entries():
            if row.get("mode") != "edit":
                continue
            if resolved == (base_dir / row["path"]).resolve():
                return True
        return False

    def _list_editable_files() -> list[str]:
        return [row["path"] for row in _list_file_editor_entries() if row.get("mode") == "edit"]

    def _resolve_edit_file(rel_path: str) -> Path:
        entry = _resolve_file_editor_entry(rel_path)
        if entry.get("mode") != "edit":
            raise ValueError("Datei ist im Editor nur lesbar.")
        return _resolve_file_editor_file(rel_path)

    def _resolve_prompt_file(rel_path: str) -> Path:
        if not rel_path or "\x00" in rel_path:
            raise ValueError("Ungültiger Dateipfad.")
        base_dir = _get_base_dir()
        candidate = (base_dir / rel_path).resolve()
        prompts_root = (base_dir / "prompts").resolve()
        if prompts_root not in candidate.parents and candidate != prompts_root:
            raise ValueError("Nur Dateien unter prompts/ sind erlaubt.")
        if candidate.suffix.lower() != ".md":
            raise ValueError("Nur Markdown-Prompt-Dateien sind erlaubt.")
        return candidate

    def _clear_raw_config_cache() -> None:
        _raw_config_cache["path"] = ""
        _raw_config_cache["mtime_ns"] = -1
        _raw_config_cache["size"] = -1
        _raw_config_cache["data"] = None

    def _read_raw_config() -> dict[str, Any]:
        config_path = _get_config_path()
        if not config_path.exists():
            raise ValueError(f"Konfigurationsdatei fehlt: {config_path}")
        try:
            stat = config_path.stat()
        except OSError as exc:
            raise ValueError(f"Konfigurationsdatei fehlt: {config_path}") from exc
        resolved_path = str(config_path.resolve())
        if (
            _raw_config_cache.get("data") is not None
            and _raw_config_cache.get("path") == resolved_path
            and int(_raw_config_cache.get("mtime_ns", -1)) == int(stat.st_mtime_ns)
            and int(_raw_config_cache.get("size", -1)) == int(stat.st_size)
        ):
            return copy.deepcopy(_raw_config_cache["data"])
        with config_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        if not isinstance(data, dict):
            raise ValueError("config.yaml muss ein Mapping/Objekt enthalten.")
        _raw_config_cache["path"] = resolved_path
        _raw_config_cache["mtime_ns"] = int(stat.st_mtime_ns)
        _raw_config_cache["size"] = int(stat.st_size)
        _raw_config_cache["data"] = copy.deepcopy(data)
        return copy.deepcopy(data)

    def _write_raw_config(data: dict[str, Any]) -> None:
        config_path = _get_config_path()
        with config_path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(data, file, sort_keys=False, allow_unicode=True)
        try:
            stat = config_path.stat()
        except OSError:
            _clear_raw_config_cache()
            return
        _raw_config_cache["path"] = str(config_path.resolve())
        _raw_config_cache["mtime_ns"] = int(stat.st_mtime_ns)
        _raw_config_cache["size"] = int(stat.st_size)
        _raw_config_cache["data"] = copy.deepcopy(data)

    def _enable_bootstrap_admin_mode_in_raw_config(raw: dict[str, Any]) -> dict[str, Any]:
        data = dict(raw or {})
        ui = data.get("ui")
        if not isinstance(ui, dict):
            ui = {}
        ui["debug_mode"] = True
        data["ui"] = ui
        return data

    def _read_error_interpreter_raw() -> str:
        error_interpreter_path = _get_error_interpreter_path()
        if not error_interpreter_path.exists():
            return ""
        return error_interpreter_path.read_text(encoding="utf-8")

    def _parse_lines(raw: str) -> list[str]:
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def _is_ollama_model(model: str) -> bool:
        return model.strip().lower().startswith("ollama")

    def _sanitize_profile_name(value: str | None) -> str:
        if not value:
            return ""
        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", value).strip("_")
        clean = re.sub(r"_+", "_", clean)
        return clean[:48]

    def _normalize_model_key(value: str) -> str:
        return value.strip().lower()

    def _sanitize_connection_name(value: str | None) -> str:
        raw = str(value or "").strip().lower()
        raw = re.sub(r"[^a-z0-9_-]", "-", raw)
        raw = re.sub(r"-+", "-", raw).strip("-")
        return raw[:48]

    def _resolve_pricing_entry(entries: dict[str, Any], model_name: str) -> Any | None:
        clean = str(model_name or "").strip()
        if not clean:
            return None
        if entries:
            if clean in entries:
                return entries[clean]
            lowered = {_normalize_model_key(k): v for k, v in entries.items()}
            entry = lowered.get(_normalize_model_key(clean))
            if entry is not None:
                return entry
        return resolve_litellm_pricing_entry(clean)

    def _load_models_from_api_base(api_base: str, api_key: str = "", timeout_seconds: int = 8) -> list[str]:
        base = api_base.strip().rstrip("/")
        if not base:
            raise ValueError("API Base fehlt.")

        def _fetch_json(url: str) -> dict[str, Any]:
            headers: dict[str, str] = {}
            if api_key.strip():
                headers["Authorization"] = f"Bearer {api_key.strip()}"
            request = URLRequest(url=url, headers=headers)
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                raw = response.read().decode("utf-8")
                data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("Ungültige API-Antwort.")
            return data

        models: list[str] = []
        errors: list[str] = []
        try:
            data = _fetch_json(f"{base}/v1/models")
            entries = data.get("data", [])
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        model_id = str(entry.get("id", "")).strip()
                        if model_id:
                            models.append(model_id)
        except (ValueError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            errors.append(str(exc))

        if not models:
            try:
                data = _fetch_json(f"{base}/api/tags")
                entries = data.get("models", [])
                if isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, dict):
                            name = str(entry.get("name", "")).strip()
                            if name:
                                models.append(f"ollama_chat/{name}")
            except (ValueError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                errors.append(str(exc))

        models = sorted(set(models))
        if models:
            return models
        if errors:
            raise ValueError(f"Modelle konnten nicht geladen werden: {errors[-1]}")
        raise ValueError("Modelle konnten nicht geladen werden.")

    def _read_release_meta(base_dir: Path) -> dict[str, str]:
        return read_release_meta(base_dir)

    def _get_update_status(current_label: str, ttl_seconds: int = 60 * 60 * 6) -> dict[str, Any]:
        return get_update_status(_get_base_dir(), current_label=current_label, ttl_seconds=ttl_seconds)

    return MainConfigHelpers(
        list_file_editor_entries=_list_file_editor_entries,
        resolve_file_editor_entry=_resolve_file_editor_entry,
        resolve_file_editor_file=_resolve_file_editor_file,
        is_allowed_edit_path=_is_allowed_edit_path,
        list_editable_files=_list_editable_files,
        resolve_edit_file=_resolve_edit_file,
        resolve_prompt_file=_resolve_prompt_file,
        clear_raw_config_cache=_clear_raw_config_cache,
        read_raw_config=_read_raw_config,
        write_raw_config=_write_raw_config,
        enable_bootstrap_admin_mode_in_raw_config=_enable_bootstrap_admin_mode_in_raw_config,
        read_error_interpreter_raw=_read_error_interpreter_raw,
        parse_lines=_parse_lines,
        is_ollama_model=_is_ollama_model,
        sanitize_profile_name=_sanitize_profile_name,
        normalize_model_key=_normalize_model_key,
        sanitize_connection_name=_sanitize_connection_name,
        resolve_pricing_entry=_resolve_pricing_entry,
        load_models_from_api_base=_load_models_from_api_base,
        read_release_meta=_read_release_meta,
        get_update_status=_get_update_status,
    )
