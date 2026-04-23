from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from aria.core.guardrails import guardrail_kind_label, guardrail_kind_options, normalize_guardrail_kind

RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]
StringSanitizer = Callable[[str | None], str]
LocalizedMessage = Callable[[str, str, str], str]
GuardrailCompatibilityChecker = Callable[[str, str], bool]
ReferenceSanitizer = Callable[[str | None], str]
SshKeysDirImpl = Callable[[Path], Path]
EnsureSshKeypairImpl = Callable[[Path, str, bool], Path]
PerformSshKeyExchangeImpl = Callable[..., tuple[str, Path]]


@dataclass(frozen=True)
class ConfigSupportHelperDeps:
    base_dir: Path
    sample_guardrails_dir: Path
    read_raw_config: RawConfigReader
    write_raw_config: RawConfigWriter
    reload_runtime: RuntimeReloader
    sanitize_connection_name: StringSanitizer
    sanitize_reference_name_local: ReferenceSanitizer
    msg: LocalizedMessage
    guardrail_is_compatible: GuardrailCompatibilityChecker
    ssh_keys_dir_impl: SshKeysDirImpl
    ensure_ssh_keypair_impl: EnsureSshKeypairImpl
    perform_ssh_key_exchange_impl: PerformSshKeyExchangeImpl
    prompts_root: Path
    skills_root: Path


@dataclass(frozen=True)
class ConfigSupportHelpers:
    import_sample_guardrail_manifest: Callable[[str], tuple[int, int]]
    ssh_keys_dir: Callable[[], Path]
    ensure_ssh_keypair: Callable[[str, bool], Path]
    file_affects_runtime: Callable[[Path], bool]
    save_text_file_and_maybe_reload: Callable[[Path, str], tuple[bool, str]]
    perform_ssh_key_exchange: Callable[..., tuple[str, Path]]
    read_guardrails: Callable[[], dict[str, dict[str, Any]]]
    build_guardrail_ref_options: Callable[..., list[dict[str, str]]]


def build_config_support_helpers(deps: ConfigSupportHelperDeps) -> ConfigSupportHelpers:
    BASE_DIR = deps.base_dir
    _SAMPLE_GUARDRAILS_DIR = deps.sample_guardrails_dir
    _read_raw_config = deps.read_raw_config
    _write_raw_config = deps.write_raw_config
    _reload_runtime = deps.reload_runtime
    _sanitize_connection_name = deps.sanitize_connection_name
    _sanitize_reference_name_local = deps.sanitize_reference_name_local
    _msg = deps.msg
    guardrail_is_compatible = deps.guardrail_is_compatible
    _ssh_keys_dir_impl = deps.ssh_keys_dir_impl
    _ensure_ssh_keypair_impl = deps.ensure_ssh_keypair_impl
    _perform_ssh_key_exchange_impl = deps.perform_ssh_key_exchange_impl
    prompts_root = deps.prompts_root
    skills_root = deps.skills_root

    def import_sample_guardrail_manifest(sample_file: str) -> tuple[int, int]:
        clean_name = Path(str(sample_file or "").strip()).name
        if not clean_name or not clean_name.endswith(".sample.yaml"):
            raise ValueError("Unknown sample guardrail pack.")
        sample_path = _SAMPLE_GUARDRAILS_DIR / clean_name
        if not sample_path.exists() or not sample_path.is_file():
            raise ValueError("Sample guardrail pack not found.")
        payload = yaml.safe_load(sample_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Sample guardrail import expects a YAML object.")

        security = payload.get("security")
        if not isinstance(security, dict):
            raise ValueError("Sample guardrail file does not contain a security section.")
        sample_guardrails = security.get("guardrails")
        if not isinstance(sample_guardrails, dict) or not sample_guardrails:
            raise ValueError("Sample guardrail file does not contain guardrails.")

        raw = _read_raw_config()
        raw.setdefault("security", {})
        if not isinstance(raw["security"], dict):
            raw["security"] = {}
        raw["security"].setdefault("guardrails", {})
        if not isinstance(raw["security"]["guardrails"], dict):
            raw["security"]["guardrails"] = {}

        existing = raw["security"]["guardrails"]
        imported_count = 0
        skipped_count = 0
        for raw_ref, profile in sample_guardrails.items():
            ref = _sanitize_reference_name_local(str(raw_ref).strip())
            if not ref or not isinstance(profile, dict):
                skipped_count += 1
                continue
            if ref in existing:
                skipped_count += 1
                continue
            clean_kind = normalize_guardrail_kind(str(profile.get("kind", "")).strip() or "ssh_command")
            if clean_kind not in guardrail_kind_options():
                skipped_count += 1
                continue
            existing[ref] = {
                "kind": clean_kind,
                "title": str(profile.get("title", "")).strip(),
                "description": str(profile.get("description", "")).strip(),
                "allow_terms": [
                    str(item).strip()[:160]
                    for item in (profile.get("allow_terms", []) or [])
                    if str(item).strip()
                ][:40],
                "deny_terms": [
                    str(item).strip()[:160]
                    for item in (profile.get("deny_terms", []) or [])
                    if str(item).strip()
                ][:40],
            }
            imported_count += 1

        if imported_count <= 0 and skipped_count <= 0:
            raise ValueError("Sample guardrail file contains no importable profiles.")
        _write_raw_config(raw)
        _reload_runtime()
        return imported_count, skipped_count

    def ssh_keys_dir() -> Path:
        return _ssh_keys_dir_impl(BASE_DIR)

    def ensure_ssh_keypair(ref: str, overwrite: bool = False) -> Path:
        return _ensure_ssh_keypair_impl(BASE_DIR, ref, overwrite=overwrite)

    def file_affects_runtime(target: Path) -> bool:
        resolved = target.resolve()
        return (
            resolved == prompts_root
            or prompts_root in resolved.parents
            or resolved == skills_root
            or skills_root in resolved.parents
        )

    def save_text_file_and_maybe_reload(target: Path, content: str) -> tuple[bool, str]:
        target.write_text(content, encoding="utf-8")
        if not file_affects_runtime(target):
            return True, ""
        try:
            _reload_runtime()
            return True, ""
        except (OSError, ValueError) as exc:
            return True, f"Datei gespeichert, aber Runtime-Neuladen fehlgeschlagen: {exc}"

    def perform_ssh_key_exchange(
        *,
        ref: str,
        host: str,
        port: int,
        profile_user: str,
        login_user: str,
        login_password: str,
    ) -> tuple[str, Path]:
        return _perform_ssh_key_exchange_impl(
            BASE_DIR,
            ref=ref,
            host=host,
            port=port,
            profile_user=profile_user,
            login_user=login_user,
            login_password=login_password,
        )

    def read_guardrails() -> dict[str, dict[str, Any]]:
        raw = _read_raw_config()
        security = raw.get("security", {})
        if not isinstance(security, dict):
            return {}
        rows = security.get("guardrails", {})
        if not isinstance(rows, dict):
            return {}
        result: dict[str, dict[str, Any]] = {}
        for ref, value in rows.items():
            clean_ref = _sanitize_connection_name(ref)
            if not clean_ref or not isinstance(value, dict):
                continue
            kind = normalize_guardrail_kind(str(value.get("kind", "")).strip() or "ssh_command")
            result[clean_ref] = {
                "kind": kind,
                "kind_label": guardrail_kind_label(kind),
                "title": str(value.get("title", "")).strip(),
                "description": str(value.get("description", "")).strip(),
                "allow_terms": list(value.get("allow_terms", []) if isinstance(value.get("allow_terms", []), list) else []),
                "deny_terms": list(value.get("deny_terms", []) if isinstance(value.get("deny_terms", []), list) else []),
            }
        return result

    def build_guardrail_ref_options(rows: dict[str, dict[str, Any]], *, connection_kind: str = "", lang: str = "de") -> list[dict[str, str]]:
        options = [{"ref": "", "label": _msg(lang, "Kein Guardrail-Profil", "No guardrail profile")}]
        for ref in sorted(rows.keys()):
            item = rows.get(ref, {})
            kind = str(item.get("kind", "")).strip()
            if connection_kind and kind and not guardrail_is_compatible(kind, connection_kind):
                continue
            title = str(item.get("title", "")).strip()
            kind_label = str(item.get("kind_label", "")).strip()
            label_core = f"{title} · {ref}" if title and title != ref else ref
            label = f"{label_core} · {kind_label}" if kind_label else label_core
            options.append({"ref": ref, "label": label})
        return options

    return ConfigSupportHelpers(
        import_sample_guardrail_manifest=import_sample_guardrail_manifest,
        ssh_keys_dir=ssh_keys_dir,
        ensure_ssh_keypair=ensure_ssh_keypair,
        file_affects_runtime=file_affects_runtime,
        save_text_file_and_maybe_reload=save_text_file_and_maybe_reload,
        perform_ssh_key_exchange=perform_ssh_key_exchange,
        read_guardrails=read_guardrails,
        build_guardrail_ref_options=build_guardrail_ref_options,
    )
