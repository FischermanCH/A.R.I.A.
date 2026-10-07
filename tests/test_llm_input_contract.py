import json

from aria.modules.llm_input_contract.contract import build_llm_input_contract
from aria.modules.llm_input_contract.contract import ANSWER_COMPOSER_OUTPUT_PROFILE
from aria.modules.llm_input_contract.contract import TURN_ROUTER_OUTPUT_PROFILE
from aria.modules.llm_input_contract.contract import llm_input_contract_diagnostics
from aria.modules.llm_input_contract.contract import validated_used_learning_hint_ids


def _expanded_world_rows(value: object) -> list[dict[str, object]]:
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    if not isinstance(value, dict):
        return []
    fields = [str(field) for field in list(value.get("fields") or [])]
    rows: list[dict[str, object]] = []
    for raw_row in list(value.get("rows") or []):
        if not isinstance(raw_row, list):
            continue
        rows.append({field: raw_row[index] for index, field in enumerate(fields) if index < len(raw_row) and raw_row[index] is not None})
    return rows


def test_llm_input_contract_normalizes_world_map_without_routing() -> None:
    contract = build_llm_input_contract(
        message="  welche verbindungen kennst du fuer syncthing?  ",
        language="de",
        user_id="u1",
        routing_meta_context={
            "collections": [{"name": "aria_facts_u1", "kind": "facts"}],
            "actions": [{"name": "ssh_run_command", "risk": "medium"}],
        },
        surface_meta_context={
            "surfaces": [
                {
                    "id": "connections",
                    "type": "connections",
                    "routing": {"configured_kinds": ["ssh", "sftp"]},
                    "loader_contract": "must not leak into compact contract",
                    "url": "https://internal.example.invalid",
                }
            ]
        },
        world_map_extensions={
            "meta_catalog": [{"catalog_id": "connection|ssh|sync-node-01", "surface_id": "connections"}],
            "web_search_profiles": [
                {
                    "ref": "www-search",
                    "title": "Internet Search",
                    "categories": ["general", "news"],
                    "base_url": "https://search.example.invalid",
                }
            ],
        },
        last_turn_frame={"surface_id": "docs", "mode": "search"},
        recent_visible_chat_context={"messages": [{"role": "assistant", "text": "previous answer"}]},
        current_date="2026-07-13",
    )

    assert contract["contract_version"] == "llm_input_v1"
    assert contract["canonical_input"] is True
    assert contract["decision_task"] == "select_relevant_context_or_action"
    assert contract["runtime"]["current_date"] == "2026-07-13"
    assert contract["user_prompt"] == "welche verbindungen kennst du fuer syncthing?"
    assert contract["global_rules"]["normalizer_is_not_router"] is True
    assert contract["global_rules"]["top_level_payload_fields_are_legacy_mirrors"] is False
    assert contract["global_rules"]["top_level_payload_fields_removed"] is True
    assert contract["requested_output_schema"]["select_only_from_world_map"] is True
    assert contract["requested_output_schema"]["allowed_surface_ids"] == ["connections"]
    assert contract["requested_output_schema"]["allowed_collection_names"] == ["aria_facts_u1"]
    assert contract["requested_output_schema"]["allowed_action_names"] == ["ssh_run_command"]
    assert contract["requested_output_schema"]["allowed_catalog_ids"] == ["connection|ssh|sync-node-01"]
    assert contract["requested_output_schema"]["allowed_web_search_profile_refs"] == ["www-search"]
    assert contract["requested_output_schema"]["web_source_plan"]["search_profile_ref"].startswith("optional")
    learning_schema = contract["requested_output_schema"]["learning_directive"]
    assert "behavior_feedback" in learning_schema["lanes"]
    assert "immediately previous answer" in learning_schema["consistency"]
    assert "action" in contract["requested_output_schema"]["allowed_context_request_modes"]
    assert contract["world_map"]["surfaces"][0]["id"] == "connections"
    assert "loader_contract" not in contract["world_map"]["surfaces"][0]
    assert "url" not in contract["world_map"]["surfaces"][0]
    assert contract["world_map"]["collections"][0]["name"] == "aria_facts_u1"
    assert contract["world_map"]["actions"][0]["name"] == "ssh_run_command"
    assert contract["world_map"]["meta_catalog"][0]["catalog_id"] == "connection|ssh|sync-node-01"
    assert contract["world_map"]["web_search_profiles"][0]["ref"] == "www-search"
    assert "base_url" not in contract["world_map"]["web_search_profiles"][0]
    assert contract["conversation_context"]["last_turn_frame"]["surface_id"] == "docs"

    diagnostics = llm_input_contract_diagnostics(contract)
    assert diagnostics["llm_input_contract_v1"] == 1
    assert diagnostics["llm_input_world_surfaces"] == 1
    assert diagnostics["llm_input_world_collections"] == 1
    assert diagnostics["llm_input_world_actions"] == 1
    assert diagnostics["llm_input_world_meta_catalog"] == 1
    assert diagnostics["llm_input_contract_bytes"] > diagnostics["llm_input_world_map_bytes"] > 0
    assert diagnostics["llm_input_output_schema_bytes"] > 0


def test_llm_input_contract_compacts_static_router_schema_but_keeps_dynamic_allowlists() -> None:
    verbose = build_llm_input_contract(
        message="route this",
        routing_meta_context={
            "collections": [{"name": "aria_facts_u1", "kind": "facts"}],
            "actions": [{"name": "personal_memory_capture", "risk": "low"}],
        },
        surface_meta_context={"surfaces": [{"id": "memory", "type": "memory"}]},
        world_map_extensions={"meta_catalog": [{"catalog_id": "local|memory|facts", "surface_id": "memory"}]},
        current_date="2026-07-29",
    )
    compact = build_llm_input_contract(
        message="route this",
        routing_meta_context={
            "collections": [{"name": "aria_facts_u1", "kind": "facts"}],
            "actions": [{"name": "personal_memory_capture", "risk": "low"}],
        },
        surface_meta_context={"surfaces": [{"id": "memory", "type": "memory"}]},
        world_map_extensions={"meta_catalog": [{"catalog_id": "local|memory|facts", "surface_id": "memory"}]},
        current_date="2026-07-29",
        output_profile="aria_turn_router_output_v1",
    )

    assert compact["global_rules"]["profile"] == "llm_first_guarded_v1"
    assert compact["global_rules"]["turn_semantics_authority"] == "turn_semantics_v1"
    assert compact["global_rules"]["world_map_rows"] == "world_rows_v1"
    assert compact["requested_output_schema"]["profile"] == "aria_turn_router_output_v1"
    assert compact["requested_output_schema"]["decision_contract"] == {
        "name": "turn_decision_v3",
        "decision_kind": "answer|context|action|clarify",
        "contract": {"mode": "answer|action|clarify"},
    }
    assert compact["requested_output_schema"]["id_sources"]["surface_ids"] == "surfaces[id]"
    assert "allowed_collection_names" not in compact["requested_output_schema"]
    assert compact["requested_output_schema"]["id_sources"]["action_names"] == "actions[name]"
    assert compact["requested_output_schema"]["action_name"].startswith("zero or one name")
    assert "do not return action_inputs" in compact["requested_output_schema"]["action_input_phase"]
    assert compact["requested_output_schema"]["id_sources"]["catalog_ids"].startswith("meta_catalog")
    assert _expanded_world_rows(compact["world_map"]["surfaces"])[0]["id"] == "memory"
    assert _expanded_world_rows(compact["world_map"]["actions"])[0]["name"] == "personal_memory_capture"
    assert _expanded_world_rows(compact["world_map"]["meta_catalog"])[0]["catalog_id"] == "local|memory|facts"
    assert "collections" not in compact["world_map"]
    assert "conversation_context" not in compact
    assert "reviewed_learning_hints" not in compact
    assert "personal_context_capsule" not in compact
    assert (
        llm_input_contract_diagnostics(compact)["llm_input_output_schema_bytes"]
        < llm_input_contract_diagnostics(verbose)["llm_input_output_schema_bytes"] // 2
    )


def test_router_contract_preserves_complete_configured_connection_inventory() -> None:
    configured_connections = [
        {
            "catalog_id": f"connection|ssh|node-{index:03d}",
            "kind": "ssh",
            "ref": f"node-{index:03d}",
        }
        for index in range(75)
    ]

    contract = build_llm_input_contract(
        message="route this",
        world_map_extensions={"configured_connections": configured_connections},
        output_profile=TURN_ROUTER_OUTPUT_PROFILE,
    )

    assert _expanded_world_rows(contract["world_map"]["configured_connections"]) == configured_connections


def test_llm_input_contract_preserves_complete_empty_personal_model() -> None:
    contract = build_llm_input_contract(
        message="Was weisst du ueber meinen temporaeren Testwert?",
        personal_context_capsule={
            "contract": "personal_context_capsule_v1",
            "authority_policy": "A complete empty set is an authoritative structured no-hit.",
            "coverage": "complete_active_set",
            "active_claim_count": 0,
            "provided_claim_count": 0,
            "claims": [],
        },
        output_profile="aria_turn_router_output_v1",
    )

    capsule = contract["personal_context_capsule"]
    assert capsule["coverage"] == "complete_active_set"
    assert capsule["active_claim_count"] == 0
    assert capsule["provided_claim_count"] == 0
    assert capsule["claims"] == []
    assert "authority_policy" not in capsule


def test_llm_input_contract_compacts_personal_claim_rows_without_losing_values() -> None:
    claims = [
        {
            "claim_id": f"claim-{index:02d}",
            "claim_kind": "preference",
            "subject": "u1",
            "predicate": f"preference_{index:02d}",
            "value": {"enabled": True, "rank": index},
            "scope": "project",
            "scope_ref": "project-nebel",
            "authority": "explicit_user",
            "valid_from": "2026-01-01",
            "review_after": "2027-01-01",
        }
        for index in range(24)
    ]
    capsule = {
        "contract": "personal_context_capsule_v1",
        "authority_policy": "Static policy already bound by the router system contract.",
        "coverage": "complete_active_set",
        "active_claim_count": len(claims),
        "provided_claim_count": len(claims),
        "claims": claims,
    }
    verbose = build_llm_input_contract(message="route this", personal_context_capsule=capsule)
    compact = build_llm_input_contract(
        message="route this",
        personal_context_capsule=capsule,
        output_profile="aria_turn_router_output_v1",
    )

    compact_capsule = compact["personal_context_capsule"]
    assert "authority_policy" not in compact_capsule
    assert _expanded_world_rows(compact_capsule["claims"]) == verbose["personal_context_capsule"]["claims"]
    compact_bytes = len(json.dumps(compact_capsule, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    verbose_bytes = len(
        json.dumps(verbose["personal_context_capsule"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    assert compact_bytes < verbose_bytes * 0.7


def test_llm_input_contract_compacts_router_surface_rows_without_losing_authority() -> None:
    compact = build_llm_input_contract(
        message="Was steht in meinen Dokumenten?",
        surface_meta_context={
            "surfaces": [
                {
                    "id": "docs",
                    "type": "local_context",
                    "modes": ["answer", "search", "inventory"],
                    "cost": "cheap",
                    "latency": "medium",
                    "risk": "low",
                    "knows": "Imported documents and indexed document chunks.",
                    "loads": "Relevant document excerpts and source references.",
                    "routing": {"configured": True},
                    "catalog_id": "surface|docs",
                    "score": 0.9,
                }
            ]
        },
        current_date="2026-08-01",
        output_profile="aria_turn_router_output_v1",
    )

    surface_table = compact["world_map"]["surfaces"]
    surface = _expanded_world_rows(surface_table)[0]
    assert surface == {
        "id": "docs",
        "type": "local_context",
        "modes": ["answer", "search", "inventory"],
        "risk": "low",
        "knows": "Imported documents and indexed document chunks.",
        "routing": {"configured": True},
        "catalog_id": "surface|docs",
        "score": 0.9,
    }
    assert compact["requested_output_schema"]["id_sources"]["surface_ids"] == "surfaces[id]"
    compact_bytes = len(json.dumps(surface_table, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    assert list(compact).index("world_map") < list(compact).index("runtime") < list(compact).index("user_prompt")
    diagnostics = llm_input_contract_diagnostics(compact)
    assert diagnostics["llm_input_world_surfaces"] == 1
    assert diagnostics["llm_input_world_surfaces_bytes"] == compact_bytes
    assert diagnostics["llm_input_world_meta_catalog_bytes"] > 0


def test_llm_input_contract_compacts_router_candidates_without_losing_ids() -> None:
    candidates = [
        {
            "catalog_id": f"document|docs|doc-{index}",
            "entity_type": "document",
            "surface_id": "docs",
            "kind": "document_meta",
            "title": f"Document {index}",
            "document_id": f"doc-{index}",
            "document_name": f"Document-{index}.pdf",
            "target_collection": "aria_docs_u1",
            "description": "Indexed document metadata",
            "score": 0.9,
        }
        for index in range(6)
    ]
    contract = build_llm_input_contract(
        message="Welche Dokumente habe ich?",
        surface_meta_context={"surfaces": [{"id": "docs", "type": "local_context", "modes": ["inventory"]}]},
        world_map_extensions={"meta_catalog": candidates},
        current_date="2026-08-01",
        output_profile="aria_turn_router_output_v1",
    )

    table = contract["world_map"]["meta_catalog"]
    expanded = _expanded_world_rows(table)
    assert [row["catalog_id"] for row in expanded] == [row["catalog_id"] for row in candidates]
    assert [row["document_id"] for row in expanded] == [row["document_id"] for row in candidates]
    table_bytes = len(json.dumps(table, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    expanded_bytes = len(json.dumps(candidates, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    assert table_bytes < expanded_bytes * 0.7
    assert "allowed_catalog_ids" not in contract["requested_output_schema"]
    assert contract["requested_output_schema"]["id_sources"]["catalog_ids"].startswith("meta_catalog")
    diagnostics = llm_input_contract_diagnostics(contract)
    assert diagnostics["llm_input_world_meta_catalog"] == 6
    assert diagnostics["llm_input_world_meta_catalog_bytes"] == table_bytes


def test_llm_input_contract_uses_answer_specific_compact_profile() -> None:
    verbose = build_llm_input_contract(
        message="Was steht im Dokument?",
        decision_task="compose_source_bound_answer",
        world_map_extensions={
            "answer_request": {
                "answer_mode": "direct_answer",
                "outcome": {"status": "found", "content": "Belegte Antwort."},
                "evidence": {"local_store_checked": True},
            }
        },
        current_date="2026-08-01",
    )
    compact = build_llm_input_contract(
        message="Was steht im Dokument?",
        decision_task="compose_source_bound_answer",
        world_map_extensions={
            "answer_request": {
                "answer_mode": "direct_answer",
                "outcome": {"status": "found", "content": "Belegte Antwort."},
                "evidence": {"local_store_checked": True},
            }
        },
        current_date="2026-08-01",
        output_profile=ANSWER_COMPOSER_OUTPUT_PROFILE,
    )

    assert compact["global_rules"]["profile"] == "source_bound_answer_v1"
    assert compact["requested_output_schema"] == {
        "profile": ANSWER_COMPOSER_OUTPUT_PROFILE,
        "format": "plain_text",
        "content": "final user-facing answer only",
    }
    assert set(compact["world_map"]) == {"answer_request"}
    assert "conversation_context" not in compact
    assert (
        llm_input_contract_diagnostics(compact)["llm_input_contract_bytes"]
        < llm_input_contract_diagnostics(verbose)["llm_input_contract_bytes"] - 2500
    )


def test_llm_input_contract_can_remove_repeated_world_map_lists() -> None:
    routing_meta = {
        "collections": [{"name": "aria_facts_u1", "kind": "facts"}],
        "actions": [{"name": "personal_memory_capture", "risk": "low"}],
        "contract_version": "routing_meta_v1",
    }
    surface_meta = {
        "surfaces": [{"id": "memory", "type": "memory"}],
        "contract_version": "surface_meta_v1",
    }

    contract = build_llm_input_contract(
        message="Merke dir meine Praeferenz.",
        routing_meta_context=routing_meta,
        surface_meta_context=surface_meta,
        deduplicate_world_map=True,
        current_date="2026-07-24",
    )

    world_map = contract["world_map"]
    assert world_map["surfaces"] == surface_meta["surfaces"]
    assert world_map["collections"] == routing_meta["collections"]
    assert world_map["actions"] == routing_meta["actions"]
    assert world_map["routing_meta"] == {"contract_version": "routing_meta_v1"}
    assert world_map["surface_meta"] == {"contract_version": "surface_meta_v1"}
    assert contract["requested_output_schema"]["allowed_surface_ids"] == ["memory"]
    assert contract["requested_output_schema"]["allowed_collection_names"] == ["aria_facts_u1"]
    assert contract["requested_output_schema"]["allowed_action_names"] == ["personal_memory_capture"]


def test_compact_turn_router_drops_duplicate_surface_contract_but_keeps_authority_rows() -> None:
    contract = build_llm_input_contract(
        message="Welche Quelle passt zu meiner Frage?",
        surface_meta_context={
            "surfaces": [
                {
                    "id": "docs",
                    "type": "local_context",
                    "modes": ["search", "answer"],
                    "knows": "Imported documents and their indexed contents.",
                },
                {
                    "id": "web",
                    "type": "public_web",
                    "modes": ["search", "answer"],
                    "knows": "Current public facts with provider citations.",
                },
            ],
            "contract": {
                "select_registered_surface_ids_only": True,
                "no_trigger_words": True,
                "stage_1_meta_only": True,
                "deep_context_after_selection": True,
                "preserve_user_data": True,
            },
        },
        deduplicate_world_map=True,
        output_profile=TURN_ROUTER_OUTPUT_PROFILE,
        current_date="2026-09-08",
    )

    world_map = contract["world_map"]
    assert "surface_meta" not in world_map
    assert [row[0] for row in world_map["surfaces"]["rows"]] == ["docs", "web"]
    assert contract["requested_output_schema"]["id_sources"]["surface_ids"] == "surfaces[id]"


def test_compact_turn_router_table_encodes_connection_kind_authority() -> None:
    contract = build_llm_input_contract(
        message="Welche administrativen Zugriffe sind verfügbar?",
        routing_meta_context={
            "connection_kinds": ["ssh", "sftp"],
            "connection_kind_options": [
                {
                    "id": "ssh",
                    "label": "SSH",
                    "configured_count": 14,
                    "safe_fields": ["host", "port", "user", "title", "description", "tags"],
                    "capabilities": ["command", "admin_access"],
                },
                {
                    "id": "sftp",
                    "label": "SFTP",
                    "configured_count": 2,
                    "safe_fields": ["host", "port", "path"],
                    "capabilities": ["list", "read", "write"],
                },
            ],
        },
        deduplicate_world_map=True,
        output_profile=TURN_ROUTER_OUTPUT_PROFILE,
        current_date="2026-09-08",
    )

    world_map = contract["world_map"]
    assert "connection_kind_options" not in world_map["routing_meta"]
    assert _expanded_world_rows(world_map["connection_kind_options"]) == [
        {"id": "ssh", "label": "SSH", "configured_count": 14, "capabilities": ["command", "admin_access"]},
        {"id": "sftp", "label": "SFTP", "configured_count": 2, "capabilities": ["list", "read", "write"]},
    ]
    assert contract["requested_output_schema"]["id_sources"]["connection_kinds"] == "connection_kind_options[id]"
    assert llm_input_contract_diagnostics(contract)["llm_input_connection_kind_options_bytes"] > 0


def test_llm_input_contract_keeps_bound_inventory_host_evidence_for_answers() -> None:
    contract = build_llm_input_contract(
        message="was fuer ip adressen haben meine dev-server",
        decision_task="compose_source_bound_answer",
        world_map_extensions={
            "answer_request": {
                "outcome": {
                    "kind": "inventory_list",
                    "status": "found",
                    "scope_contract": "bound",
                    "bound_refs": ["dev-node-02"],
                    "sources": [
                        {
                            "surface": "connections",
                            "kind": "ssh",
                            "refs": ["dev-node-02"],
                            "items": [
                                {
                                    "ref": "dev-node-02",
                                    "title": "Development Server",
                                    "host": "192.0.2.32",
                                    "user": "root",
                                    "password": "must not leak",
                                }
                            ],
                        }
                    ],
                }
            }
        },
        current_date="2026-07-16",
    )

    item = contract["world_map"]["answer_request"]["outcome"]["sources"][0]["items"][0]
    assert item["ref"] == "dev-node-02"
    assert item["host"] == "192.0.2.32"
    assert "user" not in item
    assert "password" not in item


def test_llm_input_contract_redacts_common_secret_key_variants() -> None:
    contract = build_llm_input_contract(
        message="x",
        world_map_extensions={
            "meta_catalog": [
                {
                    "catalog_id": "connection|api|demo",
                    "surface_id": "connections",
                    "access_token": "secret-access",
                    "refreshToken": "secret-refresh",
                    "client_secret": "secret-client",
                    "secret_key": "secret-key",
                    "apiKey": "secret-api",
                    "authorization": "Bearer secret-auth",
                    "nested": {
                        "service_token": "secret-service",
                        "safe_label": "visible",
                    },
                }
            ]
        },
        current_date="2026-07-16",
    )

    row = contract["world_map"]["meta_catalog"][0]
    assert row["catalog_id"] == "connection|api|demo"
    assert row["nested"] == {"safe_label": "visible"}
    serialized = str(row)
    assert "secret-" not in serialized
    assert "access_token" not in row
    assert "refreshToken" not in row
    assert "client_secret" not in row
    assert "secret_key" not in row
    assert "apiKey" not in row
    assert "authorization" not in row


def test_llm_input_contract_bounds_learning_hints_and_validates_reported_usage() -> None:
    hints = [
        {
            "hint_id": f"hint-{index}",
            "text": f"Reviewed hint {index}",
            "version": 2,
            "relevance_score": 0.9,
            "source_candidate_id": f"candidate-{index}",
        }
        for index in range(5)
    ]

    contract = build_llm_input_contract(
        message="route this",
        reviewed_learning_hints=hints,
        current_date="2026-07-23",
    )

    assert [row["hint_id"] for row in contract["reviewed_learning_hints"]] == ["hint-0", "hint-1", "hint-2"]
    assert contract["global_rules"]["learning_hints_are_weak_signals_only"] is True
    assert contract["requested_output_schema"]["allowed_learning_hint_ids"] == ["hint-0", "hint-1", "hint-2"]
    assert validated_used_learning_hint_ids(
        {"used_learning_hint_ids": ["hint-2", "invented", "hint-2"]},
        hints,
    ) == ("hint-2",)
