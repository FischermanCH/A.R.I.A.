"""Deterministic, secret-free connection reference normalization for Native Tools."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class ConnectionResolutionError:
    status: str
    requested: str
    connection_kind: str
    candidate_refs: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        if self.status == "connection_ambiguous":
            message = "The connection name is ambiguous; use one of the exact configured references."
        else:
            message = "No configured connection matches this exact reference, display name, or host name."
        return {
            "status": self.status,
            "requested_connection": self.requested,
            "connection_kind": self.connection_kind,
            "candidate_refs": list(self.candidate_refs),
            "message": message,
        }


@dataclass(frozen=True, slots=True)
class NativeConnectionArgumentsResolution:
    arguments: Mapping[str, Any]
    error: ConnectionResolutionError | None = None


def _field(profile: Any, name: str) -> Any:
    if isinstance(profile, Mapping):
        return profile.get(name)
    return getattr(profile, name, None)


def _profiles(connections: Any, kind: str) -> Mapping[str, Any]:
    value = connections.get(kind) if isinstance(connections, Mapping) else getattr(connections, kind, None)
    return value if isinstance(value, Mapping) else {}


def _profile_names(profile: Any) -> tuple[str, ...]:
    values: list[str] = []
    for field in ("title", "display_name", "name"):
        value = str(_field(profile, field) or "").strip()
        if value:
            values.append(value)
    aliases = _field(profile, "aliases")
    if isinstance(aliases, Sequence) and not isinstance(aliases, (str, bytes)):
        values.extend(str(value).strip() for value in aliases if str(value).strip())
    return tuple(dict.fromkeys(values))


def _host_value(value: Any) -> str:
    clean = str(value or "").strip().rstrip(".")
    if not clean:
        return ""
    parsed = urlsplit(clean if "://" in clean else f"//{clean}")
    return str(parsed.hostname or clean.split("/", 1)[0].split(":", 1)[0]).strip().rstrip(".")


def _profile_hosts(profile: Any) -> tuple[str, ...]:
    values: list[str] = []
    for field in ("host", "hostname", "fqdn", "ip", "smtp_host"):
        value = _host_value(_field(profile, field))
        if value:
            values.append(value)
    for field in ("service_url", "base_url", "url", "webhook_url", "ical_url", "feed_url"):
        value = _host_value(_field(profile, field))
        if value:
            values.append(value)
    return tuple(dict.fromkeys(values))


def _resolve_one(
    connections: Any, *, kinds: Sequence[str], requested: str,
) -> tuple[str, str] | ConnectionResolutionError:
    clean = str(requested or "").strip()
    folded = clean.casefold().rstrip(".")
    candidates: list[tuple[str, str, Any]] = []
    for kind in kinds:
        candidates.extend((str(kind), str(ref), profile) for ref, profile in _profiles(connections, kind).items())
    configured_refs = tuple(sorted(dict.fromkeys(ref for _kind, ref, _profile in candidates)))[:8]

    tiers = (
        [(kind, ref) for kind, ref, _profile in candidates if ref == clean],
        [(kind, ref) for kind, ref, _profile in candidates if ref.casefold() == folded],
        [
            (kind, ref) for kind, ref, profile in candidates
            if any(value.casefold() == folded for value in _profile_names(profile))
        ],
        [
            (kind, ref) for kind, ref, profile in candidates
            if any(value.casefold().rstrip(".") == folded for value in _profile_hosts(profile))
        ],
    )
    for matches in tiers:
        unique = tuple(dict.fromkeys(matches))
        if len(unique) == 1:
            return unique[0]
        if len(unique) > 1:
            return ConnectionResolutionError(
                status="connection_ambiguous", requested=clean,
                connection_kind=unique[0][0] if len({kind for kind, _ref in unique}) == 1 else "",
                candidate_refs=tuple(ref for _kind, ref in unique)[:8],
            )
    return ConnectionResolutionError(
        status="connection_not_found", requested=clean,
        connection_kind=str(kinds[0]) if len(kinds) == 1 else "",
        candidate_refs=configured_refs,
    )


def resolve_native_connection_arguments(
    contract: Any, arguments: Mapping[str, Any], connections: Any,
) -> NativeConnectionArgumentsResolution:
    """Canonicalize connection arguments without fuzzy routing or secret exposure."""

    resolved = dict(arguments)
    required_kinds = tuple(str(kind).strip() for kind in contract.required_connection_kinds if str(kind).strip())
    if not required_kinds and str(getattr(contract, "name", "") or "") != "lookup_connection":
        return NativeConnectionArgumentsResolution(arguments=resolved)
    explicit_kind = str(resolved.get("connection_kind") or "").strip()
    if explicit_kind:
        if required_kinds and explicit_kind not in required_kinds:
            return NativeConnectionArgumentsResolution(arguments=resolved)
        kinds = (explicit_kind,)
    elif required_kinds:
        kinds = required_kinds
    else:
        values = vars(connections) if hasattr(connections, "__dict__") else connections
        kinds = tuple(
            str(kind) for kind, profiles in (values.items() if isinstance(values, Mapping) else ())
            if isinstance(profiles, Mapping)
        )

    if "connection_ref" in resolved and isinstance(resolved.get("connection_ref"), str) and kinds:
        match = _resolve_one(connections, kinds=kinds, requested=str(resolved["connection_ref"]))
        if isinstance(match, ConnectionResolutionError):
            return NativeConnectionArgumentsResolution(arguments=resolved, error=match)
        matched_kind, canonical_ref = match
        resolved["connection_ref"] = canonical_ref
        if explicit_kind:
            resolved["connection_kind"] = matched_kind

    targets = resolved.get("targets")
    if isinstance(targets, list) and targets and len(kinds) == 1:
        canonical_targets: list[str] = []
        for target in targets:
            if not isinstance(target, str):
                return NativeConnectionArgumentsResolution(arguments=resolved)
            match = _resolve_one(connections, kinds=kinds, requested=target)
            if isinstance(match, ConnectionResolutionError):
                return NativeConnectionArgumentsResolution(arguments=resolved, error=match)
            canonical_targets.append(match[1])
        resolved["targets"] = canonical_targets

    return NativeConnectionArgumentsResolution(arguments=resolved)
