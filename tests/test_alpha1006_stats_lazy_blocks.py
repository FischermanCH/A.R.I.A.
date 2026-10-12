from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from aria.modules.stats_ui import routes as stats_routes


ROOT = Path(__file__).resolve().parents[1]


def test_stats_page_renders_closed_lazy_shells_and_retry_contract() -> None:
    template = (ROOT / "aria/templates/stats.html").read_text(encoding="utf-8")

    assert "{% if block.open %}open{% endif %}" not in template
    assert "data-stats-block-content" in template
    assert "data-stats-block-url" in template
    assert "data-stats-block-retry" in template
    assert "credentials: \"same-origin\"" in template
    assert "block.dataset.loaded = \"true\"" in template


def test_stats_fragment_template_preserves_alpha1005_lamps_and_actions() -> None:
    template = (ROOT / "aria/templates/_stats_check_block.html").read_text(encoding="utf-8")

    assert 'class="health-lamp status-{{ row.status }}"' in template
    assert "data-stats-check-tile" in template
    assert "data-stats-check-key" in template
    assert "row.summary" in template
    assert "row.detail" in template
    assert "row.url and (row.status != 'ok' or row.key == 'connections')" in template


def test_connection_summary_counts_cached_rows_without_live_probes() -> None:
    summary = stats_routes._stats_connection_summary(
        total=5,
        cached_rows=[
            {"status": "ok"},
            {"status": "ok"},
            {"status": "error"},
        ],
    )

    assert summary == {"total": 5, "ok": 2, "error": 1, "never": 2}


def test_live_probe_timeout_is_bounded_and_returns_honest_warning() -> None:
    async def slow_probe() -> dict[str, object]:
        await asyncio.sleep(0.05)
        return {"status": "ok"}

    row = asyncio.run(
        stats_routes._bounded_stats_live_probe(
            slow_probe(),
            timeout_seconds=0.001,
            key="routing_index",
            name="Routing-Index",
            language="de",
            url="/config/routing",
        )
    )

    assert row["status"] == "warn"
    assert "nicht erreichbar" in row["summary"].lower()
    assert "timeout" in row["detail"].lower()


def test_manifest_declares_authenticated_lazy_fragment_route_and_template() -> None:
    manifest = (ROOT / "aria/modules/stats_ui/manifest.py").read_text(encoding="utf-8")

    assert '"/stats/blocks/{block_id}"' in manifest
    assert '"_stats_check_block.html"' in manifest


def test_german_live_rows_do_not_leak_english_qdrant_status_copy(monkeypatch) -> None:
    async def routing(_settings):  # type: ignore[no-untyped-def]
        return {
            "status": "warn",
            "message": "No routable connection profiles configured.",
            "document_count": 131,
            "indexed_count": 0,
        }

    async def recipe(_settings):  # type: ignore[no-untyped-def]
        return {"status": "ok", "collection_count": 1, "point_count": 4}

    monkeypatch.setattr(stats_routes, "build_connection_routing_index_status", routing)
    monkeypatch.setattr(stats_routes, "_build_recipe_experience_memory_meta", recipe)
    rows = asyncio.run(
        stats_routes._build_stats_live_operation_rows(SimpleNamespace(), language="de")
    )

    rendered = " ".join(str(value) for value in rows["routing_index"].values()).lower()
    assert "profiles" not in rendered
    assert "verbindungsprofile" in rendered
