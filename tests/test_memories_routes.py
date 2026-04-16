from __future__ import annotations

from aria.web.memories_routes import (
    _document_matches_filter,
    _memory_collection_link,
    _memory_document_link,
    _build_routing_collection_rows,
    _build_memory_graph,
    _build_document_collection_groups,
    _build_document_entries,
    _build_memory_groups,
    _build_rollup_entries,
    _build_rollup_groups,
    _default_document_collection_for_user,
    _document_collection_names,
    _is_uploaded_file,
    _memories_redirect,
    _memories_map_redirect,
    _normalize_document_collection_name,
    _resolve_document_target_collection,
)
from fastapi import UploadFile as FastAPIUploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile


def _sanitize_collection_name(value: str | None) -> str:
    import re

    if not value:
        return ""
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", value).strip("_")
    clean = re.sub(r"_+", "_", clean)
    return clean[:64]


def test_default_document_collection_for_user_uses_docs_prefix() -> None:
    assert _default_document_collection_for_user("Neo User") == "aria_docs_neo_user"


def test_document_collection_names_only_keep_docs_collections() -> None:
    names = _document_collection_names(
        ["aria_docs_handbuch", "aria_facts_neo", "aria_docs_manual", "aria_memory", "aria_docs_manual"]
    )

    assert names == ["aria_docs_handbuch", "aria_docs_manual"]


def test_build_routing_collection_rows_keeps_only_system_routing_collections() -> None:
    rows = _build_routing_collection_rows(
        [
            {"name": "aria_routing_connections_aria_8800", "points": 116, "status": "green"},
            {"name": "aria_facts_neo", "points": 12, "status": "ok"},
            {"name": "aria_docs_neo_manuals", "points": 24, "status": "ok"},
            {"name": "aria_routing_skills_aria_8800", "points": 8, "status": "yellow"},
        ],
        known_user_collection_names={"aria_facts_neo", "aria_docs_neo_manuals"},
        browse_url="/config/routing",
    )

    assert [row["name"] for row in rows] == [
        "aria_routing_connections_aria_8800",
        "aria_routing_skills_aria_8800",
    ]
    assert all(row["kind"] == "routing" for row in rows)
    assert all(row["browse_url"] == "/config/routing" for row in rows)
    assert rows[0]["share_pct"] == 93


def test_normalize_document_collection_name_adds_docs_prefix() -> None:
    assert _normalize_document_collection_name("handbuch", _sanitize_collection_name) == "aria_docs_handbuch"
    assert _normalize_document_collection_name("aria_docs_manual", _sanitize_collection_name) == "aria_docs_manual"


def test_resolve_document_target_collection_rejects_non_docs_selection() -> None:
    try:
        _resolve_document_target_collection(
            request=object(),  # type: ignore[arg-type]
            username="Neo User",
            selected_collection="aria_facts_neo_user",
            new_collection_name="",
            existing_collections=["aria_docs_neo_user", "aria_facts_neo_user"],
            sanitize_collection_name=_sanitize_collection_name,
            get_effective_memory_collection=lambda _request, _username: "aria_memory_neo_user",
        )
    except ValueError as exc:
        assert "Dokument-Collections" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-document collection selection")


def test_resolve_document_target_collection_defaults_to_personal_docs_collection() -> None:
    target = _resolve_document_target_collection(
        request=object(),  # type: ignore[arg-type]
        username="Neo User",
        selected_collection="",
        new_collection_name="",
        existing_collections=["aria_facts_neo_user"],
        sanitize_collection_name=_sanitize_collection_name,
        get_effective_memory_collection=lambda _request, _username: "aria_memory_neo_user",
    )

    assert target == "aria_docs_neo_user"


def test_build_document_entries_groups_chunks_by_document() -> None:
    rows = [
        {
            "type": "document",
            "collection": "aria_docs_manuals",
            "document_id": "doc-1",
            "document_name": "Arlo.pdf",
            "timestamp": "2026-04-06T02:00:00+00:00",
            "text": "Erster Chunk mit etwas Text",
            "source": "rag_upload",
        },
        {
            "type": "document",
            "collection": "aria_docs_manuals",
            "document_id": "doc-1",
            "document_name": "Arlo.pdf",
            "timestamp": "2026-04-06T02:01:00+00:00",
            "text": "Zweiter Chunk mit mehr Kontext",
            "source": "rag_upload",
        },
        {
            "type": "knowledge",
            "collection": "aria_context-mem_neo",
            "document_id": "",
            "document_name": "",
            "timestamp": "2026-04-06T02:02:00+00:00",
            "text": "Nicht als Dokument gruppieren",
            "source": "compression",
        },
    ]

    entries = _build_document_entries(rows)

    assert len(entries) == 1
    assert entries[0]["document_name"] == "Arlo.pdf"
    assert entries[0]["chunk_count"] == 2
    assert entries[0]["collection"] == "aria_docs_manuals"


def test_build_document_collection_groups_summarizes_per_collection() -> None:
    entries = [
        {
            "collection": "aria_docs_manuals",
            "document_id": "doc-1",
            "document_name": "Arlo.pdf",
            "chunk_count": 12,
            "latest_timestamp": "2026-04-06T02:01:00+00:00",
            "preview": "Arlo preview",
        },
        {
            "collection": "aria_docs_manuals",
            "document_id": "doc-2",
            "document_name": "Camera.pdf",
            "chunk_count": 8,
            "latest_timestamp": "2026-04-06T02:05:00+00:00",
            "preview": "Camera preview",
        },
        {
            "collection": "aria_docs_notes",
            "document_id": "doc-3",
            "document_name": "Notes.md",
            "chunk_count": 3,
            "latest_timestamp": "2026-04-05T10:00:00+00:00",
            "preview": "Notes preview",
        },
    ]

    groups = _build_document_collection_groups(entries)

    assert [group["collection"] for group in groups] == ["aria_docs_manuals", "aria_docs_notes"]
    assert groups[0]["document_count"] == 2
    assert groups[0]["chunk_count"] == 20
    assert groups[0]["documents"][0]["document_name"] == "Camera.pdf"


def test_memories_map_redirect_keeps_feedback_on_map() -> None:
    response = _memories_map_redirect(info="ok", error="problem")

    assert response.status_code == 303
    assert response.headers["location"] == "/memories/map?info=ok&error=problem"


def test_memories_redirect_keeps_collection_filter() -> None:
    response = _memories_redirect(
        filter_type="all",
        query="atlas",
        collection_filter="aria_docs_fischerman",
        page=2,
        limit=50,
        sort="collection",
    )

    assert response.status_code == 303
    assert "collection_filter=aria_docs_fischerman" in response.headers["location"]


def test_memory_collection_link_uses_matching_type_for_document_collections() -> None:
    url = _memory_collection_link(kind="document", collection="aria_docs_fischerman_manuals")

    assert url.startswith("/memories?type=document")
    assert "collection_filter=aria_docs_fischerman_manuals" in url


def test_memory_document_link_points_to_document_chunks_view() -> None:
    url = _memory_document_link(
        collection="aria_docs_fischerman",
        document_id="doc-42",
        document_name="Atlas.pdf",
    )

    assert url.startswith("/memories?type=document")
    assert "collection_filter=aria_docs_fischerman" in url
    assert "document_id=doc-42" in url


def test_document_matches_filter_accepts_id_or_name() -> None:
    row = {"document_id": "doc-42", "document_name": "Atlas.pdf"}

    assert _document_matches_filter(row, document_id="doc-42") is True
    assert _document_matches_filter(row, document_name="Atlas.pdf") is True
    assert _document_matches_filter(row, document_id="doc-99", document_name="Other.pdf") is False


def test_build_memory_groups_orders_document_before_other_types() -> None:
    rows = [
        {"type": "fact", "label": "FAKT", "text": "a"},
        {"type": "document", "label": "DOKUMENT", "text": "b"},
        {"type": "knowledge", "label": "WISSEN", "text": "c"},
        {"type": "document", "label": "DOKUMENT", "text": "d"},
    ]

    groups = _build_memory_groups(rows)

    assert [group["type"] for group in groups] == ["document", "knowledge", "fact"]
    assert groups[0]["count"] == 2


def test_build_rollup_entries_and_groups() -> None:
    rows = [
        {
            "id": "r1",
            "collection": "aria_context-mem_neo",
            "source": "compression",
            "rollup_level": "week",
            "rollup_bucket": "2026-W14",
            "rollup_period_start": "2026-03-30",
            "rollup_period_end": "2026-04-05",
            "rollup_source_kind": "session_day",
            "rollup_source_count": 4,
            "timestamp": "2026-04-06T02:00:00+00:00",
            "text": "Wochen-Rollup mit Netzwerk- und Kamera-Themen",
        },
        {
            "id": "r2",
            "collection": "aria_context-mem_neo",
            "source": "compression",
            "rollup_level": "month",
            "rollup_bucket": "2026-03",
            "rollup_period_start": "2026-03-01",
            "rollup_period_end": "2026-03-31",
            "rollup_source_kind": "session_week",
            "rollup_source_count": 3,
            "timestamp": "2026-04-06T03:00:00+00:00",
            "text": "Monats-Rollup mit den wichtigsten Infrastruktur-Themen",
        },
    ]

    entries = _build_rollup_entries(rows)
    groups = _build_rollup_groups(entries)

    assert [entry["level"] for entry in entries] == ["week", "month"]
    assert groups[0]["level"] == "week"
    assert groups[1]["level"] == "month"
    assert groups[0]["entries"][0]["bucket"] == "2026-W14"


def test_build_memory_graph_includes_root_kinds_and_detail_nodes() -> None:
    graph = _build_memory_graph(
        username="neo",
        map_rows=[
            {"name": "aria_facts_neo", "kind": "fact", "points": 12, "share_pct": 20},
            {"name": "aria_prefs_neo", "kind": "preference", "points": 8, "share_pct": 13},
            {"name": "aria_docs_neo_manuals", "kind": "document", "points": 24, "share_pct": 40},
            {"name": "aria_context-mem_neo", "kind": "knowledge", "points": 16, "share_pct": 27},
        ],
        kind_totals={"fact": 12, "preference": 8, "knowledge": 16, "document": 24, "session": 0},
        document_groups=[
            {
                "collection": "aria_docs_neo_manuals",
                "document_count": 2,
                "chunk_count": 24,
            }
        ],
        rollup_groups=[
            {
                "level": "week",
                "label": "WOCHE",
                "count": 3,
            }
        ],
        routing_rows=[
            {
                "name": "aria_routing_connections_neo_8800",
                "kind": "routing",
                "points": 116,
                "share_pct": 100,
                "browse_url": "/config/routing",
            }
        ],
    )

    labels = [node["label"] for node in graph["nodes"]]
    hrefs = {node["label"]: node.get("href", "") for node in graph["nodes"]}
    assert graph["has_graph"] is True
    assert "neo" in labels
    assert "Fakten" in labels
    assert "Dokumente" in labels
    assert "aria_docs_neo_manuals" in labels
    assert "WOCHE" in labels
    assert "Routing" in labels
    assert "aria_routing_connections_neo_8800" in labels
    assert "type=document" in str(hrefs.get("aria_docs_neo_manuals", ""))
    assert hrefs.get("Routing", "") == "/config/routing"
    assert hrefs.get("aria_routing_connections_neo_8800", "") == "/config/routing"
    assert graph["edges"]


def test_is_uploaded_file_accepts_fastapi_and_starlette_uploadfile() -> None:
    assert _is_uploaded_file(FastAPIUploadFile(filename="a.txt", file=None)) is True
    assert _is_uploaded_file(StarletteUploadFile(filename="b.txt", file=None)) is True
    assert _is_uploaded_file("not-a-file") is False
