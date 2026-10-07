from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


_REF_LIKE_TOKEN_RE = re.compile(
    r"(?<![\w./@])([A-Za-z0-9][A-Za-z0-9_.-]*-[A-Za-z0-9][A-Za-z0-9_.-]*)(?![\w./@])"
)


def normalize_ref_like_token(value: str) -> str:
    return str(value or "").strip().lower()


def is_ref_like_token(value: str) -> bool:
    clean = normalize_ref_like_token(value)
    return bool(clean and _REF_LIKE_TOKEN_RE.fullmatch(clean) and any(ch.isdigit() for ch in clean))


def extract_ref_like_connection_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _REF_LIKE_TOKEN_RE.finditer(str(text or "")):
        token = normalize_ref_like_token(match.group(1))
        if token and any(ch.isdigit() for ch in token) and token not in tokens:
            tokens.append(token)
    return tokens


@dataclass(frozen=True, slots=True)
class ConnectionRefScope:
    explicit_ref: str = ""
    requested_ref: str = ""

    @classmethod
    def from_draft(cls, draft: Any | None) -> "ConnectionRefScope":
        return cls(
            explicit_ref=str(getattr(draft, "explicit_connection_ref", "") or "").strip(),
            requested_ref=str(getattr(draft, "requested_connection_ref", "") or "").strip(),
        )

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        *,
        routing_decision: dict[str, Any] | None = None,
        explicit_ref_source: str = "",
    ) -> "ConnectionRefScope":
        decision = dict(routing_decision or {})
        requested_ref = str(payload.get("requested_connection_ref", "") or "").strip()
        route_ref = str(decision.get("ref", "") or payload.get("connection_ref", "") or "").strip()
        explicit_ref = requested_ref if str(explicit_ref_source or "").strip() == "requested" else route_ref
        return cls(explicit_ref=explicit_ref, requested_ref=requested_ref)

    @property
    def has_explicit(self) -> bool:
        return bool(self.explicit_ref)

    @property
    def has_requested(self) -> bool:
        return bool(self.requested_ref)

    @property
    def has_any(self) -> bool:
        return self.has_explicit or self.has_requested

    def with_explicit_ref(self, explicit_ref: str) -> "ConnectionRefScope":
        return ConnectionRefScope(
            explicit_ref=str(explicit_ref or "").strip(),
            requested_ref=self.requested_ref,
        )

    def debug_fields(self) -> dict[str, str]:
        return {
            "explicit_ref": self.explicit_ref or "-",
            "requested_ref": self.requested_ref or "-",
        }
