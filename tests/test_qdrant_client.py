from aria.core.qdrant_client import qdrant_url_is_private_http


def test_qdrant_url_is_private_http_detects_local_and_private_hosts() -> None:
    assert qdrant_url_is_private_http("http://localhost:6333") is True
    assert qdrant_url_is_private_http("http://127.0.0.1:6333") is True
    assert qdrant_url_is_private_http("http://qdrant:6333") is True
    assert qdrant_url_is_private_http("http://10.0.10.110:6333") is True


def test_qdrant_url_is_private_http_rejects_https_and_public_hosts() -> None:
    assert qdrant_url_is_private_http("https://localhost:6333") is False
    assert qdrant_url_is_private_http("http://8.8.8.8:6333") is False
