from __future__ import annotations

import ipaddress
import warnings
from urllib.parse import urlparse

from qdrant_client import AsyncQdrantClient


def qdrant_url_is_private_http(url: str) -> bool:
    clean = str(url or "").strip()
    if not clean:
        return False
    parsed = urlparse(clean)
    if str(parsed.scheme or "").strip().lower() != "http":
        return False
    host = str(parsed.hostname or "").strip().lower()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1", "0.0.0.0", "qdrant", "host.docker.internal"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host.endswith(".local") or "." not in host
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local)


def create_async_qdrant_client(*, url: str, api_key: str | None = None, timeout: float | int = 10) -> AsyncQdrantClient:
    client_kwargs = {
        "url": url,
        "api_key": api_key or None,
        "timeout": timeout,
    }
    if api_key and qdrant_url_is_private_http(url):
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Api key is used with an insecure connection.",
                category=UserWarning,
            )
            return AsyncQdrantClient(**client_kwargs)
    return AsyncQdrantClient(**client_kwargs)
