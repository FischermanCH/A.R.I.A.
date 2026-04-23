from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Request


SanitizeUsername = Callable[[str | None], str]
SanitizeRole = Callable[[str | None], str]
RequestCookieValue = Callable[[Request, str], str]
CookieScopeSource = Callable[..., str]
SecretProvider = Callable[[], str]
MaxAgeProvider = Callable[[], int]


@dataclass(frozen=True)
class AuthSessionHelper:
    auth_cookie_name: str
    get_signing_secret: SecretProvider
    get_max_age_seconds: MaxAgeProvider
    sanitize_username: SanitizeUsername
    sanitize_role: SanitizeRole
    request_cookie_value: RequestCookieValue
    cookie_scope_source: CookieScopeSource

    def encode_auth_session(
        self,
        username: str,
        role: str,
        issued_at: int | None = None,
        *,
        scope: str = "",
    ) -> str:
        payload = {
            "username": self.sanitize_username(username),
            "role": self.sanitize_role(role),
            "iat": int(issued_at if issued_at is not None else time.time()),
            "scope": str(scope or "").strip(),
        }
        raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        encoded = base64.urlsafe_b64encode(raw).decode("ascii")
        signature = hmac.new(self.get_signing_secret().encode("utf-8"), raw, hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def decode_auth_session(self, raw: str | None, *, expected_scope: str = "") -> dict[str, Any] | None:
        payload, _ = self.decode_auth_session_with_reason(raw, expected_scope=expected_scope)
        return payload

    def decode_auth_session_with_reason(
        self,
        raw: str | None,
        *,
        expected_scope: str = "",
    ) -> tuple[dict[str, Any] | None, str]:
        if not raw:
            return None, "no_cookie"
        try:
            encoded, signature = str(raw).split(".", 1)
            decoded = base64.urlsafe_b64decode(encoded.encode("ascii"))
            expected = hmac.new(self.get_signing_secret().encode("utf-8"), decoded, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return None, "signature_invalid"
            payload = json.loads(decoded.decode("utf-8"))
            if not isinstance(payload, dict):
                return None, "payload_invalid"
            username = self.sanitize_username(str(payload.get("username", "")))
            role = self.sanitize_role(payload.get("role"))
            issued_at = int(payload.get("iat", 0) or 0)
            scope = str(payload.get("scope", "") or "").strip()
            if not username or issued_at <= 0:
                return None, "payload_invalid"
            if expected_scope:
                if not scope:
                    return None, "scope_missing"
                if not hmac.compare_digest(scope, expected_scope):
                    return None, "scope_mismatch"
            if int(time.time()) - issued_at > self.get_max_age_seconds():
                return None, "expired"
            return {"username": username, "role": role, "iat": issued_at, "scope": scope}, "ok"
        except Exception:
            return None, "decode_failed"

    def get_auth_session_from_request(self, request: Request) -> dict[str, Any] | None:
        raw = self.request_cookie_value(request, self.auth_cookie_name)
        expected_scope = self.cookie_scope_source(
            request,
            public_url=str(getattr(getattr(request, "state", object()), "cookie_public_url", "") or ""),
        )
        return self.decode_auth_session(raw, expected_scope=expected_scope)

    def get_auth_session_from_request_with_reason(self, request: Request) -> tuple[dict[str, Any] | None, str]:
        raw = self.request_cookie_value(request, self.auth_cookie_name)
        expected_scope = self.cookie_scope_source(
            request,
            public_url=str(getattr(getattr(request, "state", object()), "cookie_public_url", "") or ""),
        )
        return self.decode_auth_session_with_reason(raw, expected_scope=expected_scope)


def sanitize_auth_session_max_age_seconds(value: Any, *, default_seconds: int) -> int:
    try:
        seconds = int(value or 0)
    except (TypeError, ValueError):
        return default_seconds
    return max(60 * 5, min(seconds, 60 * 60 * 24 * 30))


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)
