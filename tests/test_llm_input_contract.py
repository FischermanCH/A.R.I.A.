from aria.core.llm_input_contract import build_llm_input_contract
from aria.core.llm_input_contract import llm_input_contract_diagnostics


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
                    "base_url": "http://searxng:8080",
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
    assert diagnostics == {
        "llm_input_contract_v1": 1,
        "llm_input_world_surfaces": 1,
        "llm_input_world_collections": 1,
        "llm_input_world_actions": 1,
        "llm_input_world_meta_catalog": 1,
    }


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
