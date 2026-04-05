from __future__ import annotations

import socket
from typing import Any


def _host_port_url(scheme: str, host: str, port: int) -> str:
    clean_scheme = str(scheme or "http").strip() or "http"
    clean_host = str(host or "").strip()
    clean_port = int(port or 0)
    if not clean_host:
        clean_host = "localhost"
    if (clean_scheme == "http" and clean_port == 80) or (clean_scheme == "https" and clean_port == 443):
        return f"{clean_scheme}://{clean_host}"
    return f"{clean_scheme}://{clean_host}:{clean_port}"


def _detect_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("1.1.1.1", 80))
            candidate = str(sock.getsockname()[0] or "").strip()
            if candidate and not candidate.startswith("127."):
                return candidate
    except Exception:
        pass
    try:
        candidate = str(socket.gethostbyname(socket.gethostname()) or "").strip()
        if candidate and not candidate.startswith("127."):
            return candidate
    except Exception:
        pass
    return "localhost"


def _forwarded_header_proto(headers: Any) -> str:
    raw = str((headers or {}).get("forwarded", "") or "").strip()
    if not raw:
        return ""
    first_hop = raw.split(",", 1)[0]
    for part in first_hop.split(";"):
        key, sep, value = part.partition("=")
        if not sep:
            continue
        if key.strip().lower() != "proto":
            continue
        return value.strip().strip('"').lower()
    return ""


def request_is_secure(request: Any | None) -> bool:
    if request is None:
        return False
    try:
        headers = getattr(request, "headers", {}) or {}
        scheme = str(getattr(getattr(request, "url", object()), "scheme", "") or "").strip().lower()
        if scheme == "https":
            return True

        forwarded_proto = _forwarded_header_proto(headers)
        if forwarded_proto:
            return forwarded_proto == "https"

        forwarded_proto = str(headers.get("x-forwarded-proto", "") or "").strip()
        if forwarded_proto:
            forwarded_first = forwarded_proto.split(",", 1)[0].strip().lower()
            if forwarded_first != "https":
                return False
            forwarded_host = str(headers.get("x-forwarded-host", "") or "").strip()
            forwarded_port = str(headers.get("x-forwarded-port", "") or "").strip()
            if forwarded_host or forwarded_port == "443":
                return True
            # Be conservative: plain HTTP requests should not become secure-cookie
            # candidates just because a stray x-forwarded-proto header is present.
            return False
        return False
    except Exception:
        return False


def resolve_runtime_url(settings: Any, request: Any | None = None) -> str:
    port = int(getattr(getattr(settings, "aria", object()), "port", 8800) or 8800)
    public_url = str(getattr(getattr(settings, "aria", object()), "public_url", "") or "").strip()
    if public_url:
        return public_url.rstrip("/")

    if request is not None:
        try:
            scheme = "https" if request_is_secure(request) else str(
                getattr(getattr(request, "url", object()), "scheme", "") or "http"
            ).strip() or "http"
            host_header = str(getattr(request, "headers", {}).get("x-forwarded-host", "") or "").strip()
            if not host_header:
                host_header = str(getattr(request, "headers", {}).get("host", "") or "").strip()
            if host_header:
                return f"{scheme}://{host_header}"
            host = str(getattr(getattr(request, "url", object()), "hostname", "") or "").strip()
            req_port = int(getattr(getattr(request, "url", object()), "port", port) or port)
            if host:
                return _host_port_url(scheme, host, req_port)
        except Exception:
            pass

    configured_host = str(getattr(getattr(settings, "aria", object()), "host", "") or "").strip()
    if configured_host and configured_host not in {"0.0.0.0", "::"}:
        return _host_port_url("http", configured_host, port)
    return _host_port_url("http", _detect_lan_ip(), port)
