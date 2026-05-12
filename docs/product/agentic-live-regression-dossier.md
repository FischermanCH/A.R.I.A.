# Agentic Live Regression Dossier

Stand: 2026-05-12

Dieses Dossier sammelt reale Alpha-Ausreisser, die als Architektur-Regressionen behandelt werden. Ziel ist nicht, fuer jede Formulierung einen neuen Spezialfall zu bauen, sondern den gemeinsamen Agentic Action Flow zu schuetzen:

1. Prompt kommt rein.
2. Deterministische Kontextanreicherung sammelt sichere Hinweise: Connection-Kandidaten, Aliase, letzte Ziele, Dossier, vorhandene Guardrails.
3. Ein bounded LLM-Draft darf konkrete Aktionsdetails vorschlagen, aber keine Policy umgehen.
4. Policy/Guardrail entscheidet `allow`, `ask_user` oder `block`.
5. Runtime fuehrt nur erlaubte bzw. bestaetigte Aktionen aus.
6. Kosten, Debug und Ergebnis muessen sichtbar bleiben.

## Aktive Live-Regressions

| Prompt-Familie | Erwarteter Pfad | Wichtige Regression |
| --- | --- | --- |
| `habe ich genuegend freien speicherplatz auf meinen servern?` | Pre-RAG Action Gate -> SSH multi-target -> `df -h` | Darf nicht als `memory_store`, RAG-Chat, RSS oder einzelner alter Server enden. |
| `habe ich auf meinen servern ueberall mehr als 10gb freien festplattenspeicher?` | SSH multi-target -> `df -h` -> bounded LLM Operator-Summary ueber Runtime-Resultate | Darf generische `ok`-Disk-Zusammenfassungen nicht uebernehmen, wenn freie-GiB-Schwelle unterschritten wird; freie Formulierungen wie `zehn Gigabyte Reserve` muessen durch die Summary-Schicht verstanden werden. |
| `wie sieht die hd auf meinem management server aus` | Pre-RAG Action Gate -> SSH single-target -> bounded LLM command draft -> Policy -> Runtime | Darf nicht mit irrelevanten Dokumenten wie Kamera-Handbuechern beantwortet werden. |
| `ist mein dns server ok` | SSH Healthcheck ueber Guardrail-Fallback | Darf keinen blockierten Bare-`uptime`-Fehler produzieren. |
| `starte meinen dns server neu` | LLM erkennt mutierenden Restart-Befehl -> SSH Policy blockiert | Darf nicht in einen harmlosen Healthcheck umgebogen werden. |
| `pruef ob die api erreichbar ist` | HTTP API single-profile health path | Darf `erreichbar` nicht als Profilname interpretieren. |
| `zeige mir die folder auf dem share Ronny Fischer` | SMB root list | Darf nicht nach einem Pfad fragen, wenn der Share-Root gemeint ist. |
| `schick eine testnachricht an discord: ...` | Discord send -> one-click confirmation | Darf nicht von altem SMB/SFTP-Kontext aufgefressen werden. |
| `mach mir eine zusammenfassung der letzten it-security news` | RSS semantic routing -> Digest mit Links | Darf nicht nur eine unbrauchbare Headline-Liste ohne Links liefern. |

## Debug-Kontrakt

`pre_rag_action_gate` muss im Debug sichtbar machen, ob der Agentic-Pfad uebernommen hat oder bewusst nicht:

- `action_path=unified_routing`: Connection-aware Action-Pfad hat uebernommen.
- `action_path=capability_action`: direkte Capability-Aktion hat uebernommen, z. B. Single HTTP API.
- `action_path=missing_capability_target`: Capability erkannt, aber kein passendes Ziel konfiguriert.
- `action_path=no_action`: Gate hat nicht uebernommen; finaler Chat/RAG darf weiterlaufen.

Die Agentic-Boundaries sind maschinenlesbar und muessen zum Prompt-Flow passen:

- `boundary=context_enrichment`: sichere Hinweise sammeln, keine Ausfuehrungsentscheidung.
- `boundary=draft`: LLM oder Resolver hat einen bounded Action-Draft vorgeschlagen.
- `boundary=policy`: Policy/Guardrail hat ohne neuen Draft entschieden.
- `boundary=draft_policy`: Draft plus Policy-Entscheid sind gemeinsam sichtbar.
- `boundary=runtime_execution`: Runtime fuehrt eine bereits erlaubte oder bestaetigte Aktion aus.

Das trennt Kontext, LLM-Vorschlag, Guardrail und Runtime im Debug. Diese Trennung ist absichtlich: Kontext und LLM koennen helfen, aber nur Policy/Guardrails entscheiden ueber Ausfuehrung.

## Testanker

Die wichtigsten Live-Regressions liegen in:

- `tests/test_pipeline.py::test_pipeline_alpha246_live_test_sequence_keeps_agentic_routing_bounded`
- `tests/test_pipeline.py::test_pipeline_plural_server_disk_check_does_not_run_fleet_recipe_or_pick_generic_server_alias`
- `tests/test_pipeline.py::test_pipeline_multi_target_ssh_uses_llm_for_dynamic_operator_summary`
- `tests/test_pipeline.py::test_pipeline_multi_target_ssh_operator_summary_honors_free_disk_threshold`
- `tests/test_pipeline.py::test_pipeline_routes_hd_question_on_management_server_before_rag_chat`
- `tests/test_pipeline.py::test_pipeline_final_chat_keeps_pre_rag_no_action_debug_visible`
- `tests/test_router.py::test_router_speicherplatz_is_not_memory_store`
- `tests/test_capability_router.py::test_capability_router_detects_plural_speicherplatz_server_question`
- `tests/test_agentic_action_resolution.py::test_agentic_debug_boundaries_map_to_prompt_flow_phases`
- `tests/test_agentic_runtime_debug.py::test_runtime_debug_line_exposes_normalized_ssh_execution_boundary`

Neue reale Ausreisser werden zuerst hier klassifiziert: Kontextluecke, Resolverluecke, Policy-/Guardrail-Luecke, Runtime-/Summary-Luecke oder Observability-/Kostenluecke.
