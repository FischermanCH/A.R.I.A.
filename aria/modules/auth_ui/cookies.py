from __future__ import annotations

import hashlib
import os
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import Response


@dataclass(frozen=True)
class CookieHelper:
    cookie_name_bases: Mapping[str, str]
    cookie_key_by_base: Mapping[str, str]
    legacy_cookie_fallback_bases: Collection[str] = ()

    def cookie_scope_source(self, request: Request | None = None, *, public_url: str = "") -> str:
        explicit_namespace = str(os.getenv("ARIA_COOKIE_NAMESPACE", "") or "").strip()
        if explicit_namespace:
            return explicit_namespace

        if request is not None:
            headers = getattr(request, "headers", {}) or {}
            forwarded_host = str(headers.get("x-forwarded-host", "") or "").strip()
            host_header = str(headers.get("host", "") or "").strip()
            host = (forwarded_host or host_header).lower()
            if not host:
                try:
                    req_url = getattr(request, "url", object())
                    hostname = str(getattr(req_url, "hostname", "") or "").strip().lower()
                    port = getattr(req_url, "port", None)
                    if hostname:
                        host = f"{hostname}:{int(port)}" if port else hostname
                except Exception:
                    host = ""
            root_path = str(getattr(request, "scope", {}).get("root_path", "") or "").strip().rstrip("/")
            if host:
                return f"{host}{root_path}"

        configured_public_url = str(public_url or "").strip()
        if configured_public_url:
            parsed = urlparse(configured_public_url)
            host = str(parsed.netloc or "").strip().lower()
            path = str(parsed.path or "").strip().rstrip("/")
            if host:
                return f"{host}{path}"

        return "default"

    def cookie_name(self, base_name: str, request: Request | None = None, *, public_url: str = "") -> str:
        scope_source = self.cookie_scope_source(request, public_url=public_url)
        scope_hash = hashlib.sha1(scope_source.encode("utf-8")).hexdigest()[:10]
        return f"{base_name}_{scope_hash}"

    def cookie_names_for_request(self, request: Request | None = None, *, public_url: str = "") -> dict[str, str]:
        return {
            key: self.cookie_name(base_name, request, public_url=public_url)
            for key, base_name in self.cookie_name_bases.items()
        }

    def request_cookie_name(self, request: Request | None, base_name: str, *, public_url: str = "") -> str:
        if request is not None:
            cookie_names = getattr(getattr(request, "state", object()), "cookie_names", None)
            key = self.cookie_key_by_base.get(base_name)
            if key and isinstance(cookie_names, dict) and cookie_names.get(key):
                return str(cookie_names[key])
            state_public_url = str(getattr(getattr(request, "state", object()), "cookie_public_url", "") or "").strip()
            if state_public_url:
                public_url = state_public_url
        return self.cookie_name(base_name, request, public_url=public_url)

    def request_cookie_value(
        self,
        request: Request,
        base_name: str,
        *,
        allow_legacy: bool | None = None,
        public_url: str = "",
    ) -> str:
        current_name = self.request_cookie_name(request, base_name, public_url=public_url)
        current_value = request.cookies.get(current_name)
        if current_value not in {None, ""}:
            return str(current_value)
        if allow_legacy is None:
            allow_legacy = base_name in self.legacy_cookie_fallback_bases
        if allow_legacy and current_name != base_name:
            legacy_value = request.cookies.get(base_name)
            if legacy_value not in {None, ""}:
                return str(legacy_value)
        return ""

    def set_response_cookie(
        self,
        response: Response,
        request: Request,
        base_name: str,
        value: str,
        *,
        max_age: int,
        secure: bool,
        httponly: bool,
        samesite: str = "lax",
    ) -> None:
        response.set_cookie(
            key=self.request_cookie_name(request, base_name),
            value=value,
            max_age=max_age,
            samesite=samesite,
            secure=secure,
            httponly=httponly,
        )

    def delete_response_cookie(self, response: Response, request: Request | None, base_name: str) -> None:
        response.delete_cookie(self.request_cookie_name(request, base_name))

    def delete_response_cookie_variants(self, response: Response, request: Request | None, base_name: str) -> None:
        current_name = self.request_cookie_name(request, base_name)
        response.delete_cookie(current_name)
        if current_name != base_name:
            response.delete_cookie(base_name)

    def clear_auth_related_cookies(
        self,
        response: Response,
        request: Request | None = None,
        *,
        clear_preferences: bool = False,
        auth_related_cookie_bases: Iterable[str],
        preference_cookie_bases: Iterable[str] = (),
    ) -> None:
        for base_name in auth_related_cookie_bases:
            self.delete_response_cookie_variants(response, request, base_name)
        if clear_preferences:
            for base_name in preference_cookie_bases:
                self.delete_response_cookie_variants(response, request, base_name)
