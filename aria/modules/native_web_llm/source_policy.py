from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NativeWebSourcePolicy:
    allowed_domains: tuple[str, ...] = ()
    required_url_prefixes: tuple[str, ...] = ()
    authority_mode: str = "prefer_primary"
    policy_id: str = "public-primary-preferred"


def resolve_native_web_source_policy(message: str) -> NativeWebSourcePolicy:
    _ = message
    return NativeWebSourcePolicy()
