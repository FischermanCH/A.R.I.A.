# I18N Code Literal Audit

Stand: 2026-05-06

Ziel:
- Python-Code soll langfristig keine deutschen UI-/Antworttexte als Produktwahrheit enthalten.
- Runtime-Code soll Text-Keys und strukturierte Daten liefern.
- Sprachdateien (`aria/i18n/*.json`) halten die sichtbaren Texte.
- Deutsche Eingabe-Erkennung bleibt fachlich erlaubt, soll mittelfristig aber ebenfalls aus Python-Konstanten in Lexikon-/Config-Dateien wandern.

Audit-Befehl:

```bash
scripts/audit_i18n_code_literals.py
scripts/audit_i18n_code_literals.py --strict
```

Aktueller Stand nach erstem deklarativen Input-Lexikon-Nachzug:

| Kategorie | Treffer | Bedeutung |
| --- | ---: | --- |
| `raw_runtime_literal` | 0 | harte deutsche Runtime-/UI-/Fehlertexte in Python |
| `inline_localized` | 0 | zweisprachige Inline-Texte via `_msg`, `localized_text`, `translate` usw. |
| `input_lexicon` | 0 | deutsche Eingabe-Erkennung, Regexe, Routing-Wortlisten |
| `llm_prompt` | 0 | deutsche Prompt-/Instruktionsfragmente |

Wichtig:
- `raw_runtime_literal` ist die harte Restschuld und steht jetzt bei 0.
- `inline_localized` steht jetzt bei 0; sichtbare zweisprachige Fallbacks liegen in Sprachdateien.
- `input_lexicon` steht jetzt bei 0; deutsche Eingabe-Erkennung liegt in deklarativen Lexikon-Dateien.
- Tests duerfen deutsche Erwartungswerte behalten, solange sie i18n-Ausgabe pruefen.

Erledigte Nachzuege:
- SSH-Healthcheck-Summary-Texte und Health-State-Labels aus `aria/core/result_summarizers/ssh.py` entfernt.
- Texte liegen jetzt unter `result_ssh.*` in `aria/i18n/de.json` und `aria/i18n/en.json`.
- `ssh.py` nutzt nur noch `result_ssh`-Keys.
- Connection-Admin- und Chat-Admin-Nachzug:
  - `aria/core/connection_admin.py` nutzt Fehlercodes und `connection_admin.*` i18n-Keys.
  - `aria/web/connection_admin_helpers.py` nutzt ebenfalls Message-Keys statt deutschen Fallbacks.
  - `aria/web/chat_admin_flows.py` nutzt `chat_admin.*` i18n-Keys fuer sichtbare Chat-Antworten.
- Connection-Mutation-Nachzug:
  - `aria/web/connection_mutation_handlers.py` nutzt `connection_mutation.*` i18n-Keys fuer harte Formular-/Redirect-Fehler.
  - rohe deutsche Runtime-Literale in dieser Datei sind entfernt; vorhandene `_msg(de,en)`-Inline-Texte bleiben als naechster Cleanup-Typ sichtbar.
- Connection-Catalog-Nachzug:
  - sichtbare Field-Labels, Discord-UI-Texte und Chat-Insert-Beispiele aus `aria/core/connection_catalog.py` liegen jetzt in `connection_catalog.*` bzw. vorhandenen `config_conn.*` i18n-Keys.
  - deutsche Eingabe-/Routing-Begriffe aus `connection_catalog.py` wurden spaeter in deklarative Lexikon-Dateien verschoben.
- Recipe-Runtime-Nachzug:
  - Statusausgabe, Step-Fehler-Marker, Recipe-Step-Zusammenfassung, SMB-Verbindungsfehler und Recipe-Auswahl-Prompt aus `aria/core/recipe_runtime.py` liegen jetzt in `recipe_runtime.*` i18n-Keys.
  - rohe Runtime-Literale in dieser Datei sind entfernt; verbleibende Treffer sind Inline-Lokalisierungen und Eingabelexikon.
- Chat-Catalog-Nachzug:
  - alte Deutsch-zu-Englisch-Ersetzungsbruecke fuer Connection-Insert-Beispiele wurde entfernt.
  - Delete-Connection-Insert nutzt jetzt `chat.tool_delete_connection_insert`.
  - rohe Runtime-Literale in `aria/web/chat_catalog.py` sind entfernt; verbleibende Treffer sind Inline-Lokalisierungen.
- Recipes-Routes-Nachzug:
  - Wizard-Presets, Follow-up-Step-Vorschlaege, Connection-Choice-Hints und Import-/Wizard-Fehler aus `aria/web/recipes_routes.py` liegen jetzt in `recipes_routes.*` i18n-Keys.
  - rohe Runtime-Literale in dieser Datei sind entfernt; verbleibende Treffer sind Inline-Lokalisierungen.
- Memories-Routes-Nachzug:
  - Memory-Graph-Labels, manuelle Memory-Typen, Dokument-Delete-/Import-Fehler, Backend-Fehler und Komprimierungsstatus aus `aria/web/memories_routes.py` liegen jetzt in `memories_routes.*` i18n-Keys.
  - rohe Runtime-Literale in dieser Datei sind entfernt; verbleibende Treffer sind Inline-Lokalisierungen.
- Chat-Pending-Flow-Nachzug:
  - Bestätigungs-, Safe-Fix-, Memory-Forget- und Alias-Follow-up-Texte aus `aria/web/chat_pending_flows.py` liegen jetzt in `chat_pending.*` i18n-Keys.
  - deutsche Fallback-Texte wurden in diesem Modul entfernt; `chat_pending_flows.py` hat keine deutschen Marker mehr im Python-Code.
- Config-Workbench-Nachzug:
  - LLM-/Embedding-Profilvalidierung, Modell-API-Validierung, Datei-Editor-Fehler und Error-Interpreter-Regelfehler aus `aria/web/config_intelligence_workbench_routes.py` liegen jetzt in `config_workbench.*` i18n-Keys.
  - der Workbench-Routenblock hat keine deutschen Marker mehr im Python-Code.
- Main-App-Nachzug:
  - Doku-Katalog-Defaults, Runtime-Reload-Fehler, Startup-Discord-Alert und unerwartete Fehlerantwort aus `aria/main.py` nutzen jetzt englische Defaults oder `app.*` i18n-Keys.
  - `aria/main.py` hat keine deutschen Marker mehr im Python-Code.
- Planner-/Notes-Store-Nachzug:
  - Planner-Reason-, Dry-run- und bounded-Recovery-Texte aus `aria/core/action_planner.py` liegen jetzt in `action_planner.*` i18n-Keys.
  - Notes-Store-Validierungs- und Dateiaktionsfehler aus `aria/core/notes_store.py` liegen jetzt in `notes_store.*` i18n-Keys.
  - beide Core-Dateien haben nur noch Eingabe-Lexikon-Treffer, keine rohen Runtime-Literale.
- Document-Ingest-/Safe-Fix-Nachzug:
  - Dokumentimport-Validierung, PDF-Fehler und lokale Dokument-Stopwords aus `aria/core/document_ingest.py` liegen jetzt in `document_ingest.*` i18n-Keys.
  - Safe-Fix-Held-Package-Erkennung, Summary-Text und Ausführungs-/Fehlertexte aus `aria/core/safe_fix.py` liegen jetzt in `safe_fix.*` i18n-Keys.
  - `Pipeline._format_held_packages_summary` nutzt jetzt die zentrale Safe-Fix-Formatierung statt einer zweiten deutschen Kopie.
  - `document_ingest.py` und `safe_fix.py` haben keine deutschen Marker mehr im Python-Code.
- Config-Surface-/Notes-Routes-Nachzug:
  - Config-Seitenueberschriften, Admin-Fehler und Service-Restart-Texte aus `aria/web/config_surface_routes.py` liegen jetzt in `config_surface.*` i18n-Keys.
  - Notes-Folder-Labels und Save/Delete/Folder-Redirect-Statusmeldungen aus `aria/web/notes_routes.py` liegen jetzt in `notes_routes.*` i18n-Keys.
  - beide Web-Dateien haben keine deutschen Marker mehr im Python-Code.
- Routing-Config-/Main-UI-Nachzug:
  - Routing-Config-/Workbench-Ueberschriften, Qdrant-Routing-Validierung, Routing-Scope-Fehler und Rezept-Routing-Fehler aus `aria/web/config_routing_routes.py` und `aria/web/config_routing_detail_routes.py` liegen jetzt in `config_routing_routes.*` i18n-Keys.
  - Die geteilte Routing-i18n-Schicht liegt in `aria/web/config_routing_i18n.py`, damit beide Legacy-/Detail-Routen denselben Textvertrag nutzen.
  - Zeitvalidierung, freundliche Fehlertexte und HTML-Fallbackfehler aus `aria/web/main_ui_helpers.py` liegen jetzt in `main_ui.*` i18n-Keys.
  - die drei Zielmodule haben keine deutschen Marker mehr im Python-Code.
- Config-Profile-/Stats-Routes-Nachzug:
  - Connection-Test-Info, Profiltest-Resultate, Embedding-Switch-Guard und Sample-Connection-Importfehler aus `aria/web/config_profile_helpers.py` liegen jetzt in `config_profile_helpers.*` i18n-Keys.
  - Stats-Verbindungszusammenfassungen, Preflight-Prompt-Checks, Log-/Update-Helper-Status und Reset-Bestaetigung aus `aria/web/stats_routes.py` liegen jetzt in `stats_routes.*` i18n-Keys.
  - beide Zielmodule haben keine deutschen Marker mehr im Python-Code.
- Planner-Candidate-/SSH-Agentic-Nachzug:
  - Kalender-Vorschau-Labels, Website-Capability-Labels und SSH-Healthcheck-Lexikon aus `aria/core/action_planner_candidate_details.py` liegen jetzt in `action_planner_candidate_details.*` i18n-Keys.
  - Agentic-SSH-Rueckfragen, Confirmation-Labels und Healthcheck-Lexikon aus `aria/core/ssh_agentic_resolution.py` liegen jetzt in `ssh_agentic_resolution.*` i18n-Keys.
  - beide Core-Dateien haben keine deutschen Marker mehr im Python-Code.
- Operations-/Connection-Context-/Taxonomy-/IMAP-Nachzug:
  - Backup-/Log-/Factory-Reset-Fehler und Bestaetigungen aus `aria/web/config_operations_detail_routes.py` liegen jetzt in `config_operations_detail_routes.*` i18n-Keys.
  - SFTP-, Google-Calendar- und SearXNG-Hilfstexte aus `aria/web/connection_context_helpers.py` liegen jetzt in `connection_context_helpers.*` i18n-Keys.
  - Recipe-Candidate-Taxonomy-Labels aus `aria/core/action_candidate_taxonomy.py` liegen jetzt in `action_candidate_taxonomy.*` i18n-Keys.
  - IMAP-Result-Summary-Texte und Mailbox-Splitmarker aus `aria/core/result_summarizers/imap.py` liegen jetzt in `result_imap.*` i18n-Keys.
  - alle vier Zielmodule haben keine deutschen Marker mehr im Python-Code.
- Auth-/Main-Config-/Notes-Magic-/HTTP-API-/Website-Runtime-Nachzug:
  - Login-/Bootstrap-Fehler aus `aria/web/auth_surface_routes.py` liegen jetzt in `auth_surface_routes.*` i18n-Keys.
  - Datei-Editor-, Config- und Modell-API-Fehler aus `aria/web/main_config_helpers.py` liegen jetzt in `main_config_helpers.*` i18n-Keys.
  - Notes-Magic-Defaulttitel, Folder-Labels, Stopwords und Folder-Erkennungslexikon aus `aria/core/notes_magic.py` liegen jetzt in `notes_magic.*` i18n-Keys.
  - HTTP-API-Statuszusammenfassungen aus `aria/core/result_summarizers/http_api.py` liegen jetzt in `result_http_api.*` i18n-Keys.
  - Website-Read-/List-Antworten aus `aria/core/website_runtime.py` liegen jetzt in `website_runtime.*` i18n-Keys.
  - alle fuenf Zielmodule haben keine deutschen Marker mehr im Python-Code.
- Google-Calendar-/Web-Search-/Config-Surface-/Chat-Execution-Nachzug:
  - Google-Calendar-Supportfehler, Timeout-Erkennung und OAuth-/API-Hinweise aus `aria/core/google_calendar_support.py` liegen jetzt in `google_calendar_support.*` i18n-Keys.
  - Web-Search-Stopwords, Recency-Begriffe, Detailzeilen und Ergebnis-/Fehlertexte aus `aria/skills/web_search.py` liegen jetzt in `web_search.*` i18n-Keys.
  - Config-Overview-Importmeldungen und Statuskarten aus `aria/web/config_surface_helpers.py` liegen jetzt in `config_surface_helpers.*` i18n-Keys.
  - Chat-Execution-Fallbackantworten, Warnpraefixe und Discord-Error-Titel aus `aria/web/chat_execution_flow.py` liegen jetzt in `chat_execution_flow.*` i18n-Keys.
  - alle vier Zielmodule haben keine deutschen Marker mehr im Python-Code.
- Capability-/Planner-State-/RSS-/File-Summary-Nachzug:
  - Capability-Detailzeilen und Detail-Labels aus `aria/core/capability_catalog.py` liegen jetzt in `capability_catalog.*` i18n-Keys.
  - Planner-State-, Confidence- und Source-Labels aus `aria/core/action_planner_result_state.py` liegen jetzt in `action_planner_result_state.*` i18n-Keys.
  - RSS-Digest-Ausgaben und RSS-Parser-Labels aus `aria/core/result_summarizers/rss.py` liegen jetzt in `result_rss.*` i18n-Keys.
  - File-List-/File-Write-Summaries und Parser-Terme aus `aria/core/result_summarizers/file_operation.py` liegen jetzt in `result_file_operation.*` i18n-Keys.
  - alle vier Zielmodule haben keine deutschen Marker mehr im Python-Code.
- Connections-Surface-/Notes-Context-/Notes-Index-Nachzug:
  - Connections-Hub-Ueberschriften aus `aria/web/connections_surface_routes.py` liegen jetzt in `connections_surface_routes.*` i18n-Keys.
  - Connections-Overview-Statuskarten, Admin-Fehler, SearXNG-Badges und Next-Step-Texte aus `aria/web/connections_surface_helpers.py` liegen jetzt in `connections_surface_helpers.*` i18n-Keys.
  - Notes-Kontext-Detailzeilen und Suchkontext-Header aus `aria/core/notes_context.py` liegen jetzt in `notes_context.*` i18n-Keys.
  - Notes-Index-Embeddingfehler und Fallbacktitel aus `aria/core/notes_index.py` liegen jetzt in `notes_index.*` i18n-Keys.
  - alle vier Zielmodule haben keine deutschen Marker mehr im Python-Code.
- LLM-/Executor-/Recipe-Promotion-/Recipe-Manifest-Nachzug:
  - LLM-Client-Fehler aus `aria/core/llm_client.py` liegen jetzt in `llm_client.*` i18n-Keys.
  - Executor-Registry-Fehler aus `aria/core/executor_registry.py` liegen jetzt in `executor_registry.*` i18n-Keys.
  - Learned-Recipe-Promotion-Validierungen aus `aria/core/learned_recipe_promotion.py` liegen jetzt in `learned_recipe_promotion.*` i18n-Keys.
  - Stored-Recipe-Manifest-Validierungen aus `aria/core/recipe_manifests.py` liegen jetzt in `recipe_manifests.*` i18n-Keys.
  - alle vier Zielmodule haben keine deutschen Marker mehr im Python-Code.
- Config-Access-/Persona-/Support-/Connection-Helper-Nachzug:
  - Guardrail-Save-/Delete-Fehler aus `aria/web/config_access_detail_routes.py` liegen jetzt in `config_access_detail_routes.*` i18n-Keys.
  - Language-File-Validierung aus `aria/web/config_persona_routes.py` liegt jetzt in `config_persona_routes.*` i18n-Keys.
  - Datei-Speichern-mit-Runtime-Reload-Warnung aus `aria/web/config_support_helpers.py` liegt jetzt in `config_support_helpers.*` i18n-Keys.
  - OPML-RSS-Import-Ref-Fehler aus `aria/web/connection_reader_helpers.py` liegt jetzt in `connection_reader_helpers.*` i18n-Keys.
  - SSH-authorized_keys-Remote-Fehler aus `aria/web/connection_support_helpers.py` liegt jetzt in `connection_support_helpers.*` i18n-Keys.
  - alle fuenf Zielmodule haben keine deutschen Marker mehr im Python-Code.
- Security-/Admin-/Planner-Template-Nachzug:
  - User-Admin-CLI-Texte aus `aria/core/user_admin.py` liegen jetzt in `user_admin.*` i18n-Keys.
  - Secure-Store- und Secure-Migrate-Fehler-/CLI-Texte aus `aria/core/secure_store.py` und `aria/core/secure_migrate.py` liegen jetzt in `secure_store.*` und `secure_migrate.*` i18n-Keys.
  - Source-Lookup-Preview-Texte und Suchbegriffe aus `aria/core/behavior_families.py` liegen jetzt in `behavior_families.*` i18n-Keys.
  - SSH-Template-Default-Begriffe und HTTP-API-Status-Begriffe aus `aria/core/execution_dry_run_template_payloads.py` und `aria/core/http_api_agentic_resolution.py` liegen jetzt in i18n-Keys.
  - alle sechs Zielmodule haben keine deutschen Marker mehr im Python-Code.
- Harte-Restliteral-Nachzug:
  - Config-, Connection-Health-, Pipeline-, Learned-Recipe-UI- und Runtime-Diagnostics-Texte liegen jetzt in eigenen i18n-Keys.
  - Maintenance-, Router-, Routing-Hints-, RSS-Grouping- und Memory-Skill-Reste wurden aus Python-Konstanten in i18n-Keys verschoben.
  - `raw_runtime_literal` und `llm_prompt` stehen im Audit jetzt bei 0.
- Inline-Localized-Grossblock-Nachzug:
  - `aria/core/connection_runtime.py` nutzt jetzt `connection_runtime.*` i18n-Keys statt `_msg(de,en)`-Inline-Texten.
  - `aria/core/recipe_runtime.py` nutzt fuer sichtbare Runtime-Texte jetzt `recipe_runtime.message_*` i18n-Keys; verbleibende Treffer dort sind Eingabelexikon.
  - `aria/web/chat_catalog.py` nutzt englische Fallbacks und deutsche/englische `chat.*` i18n-Keys fuer Toolbox-Labels.
  - `inline_localized` ist dadurch von 252 auf 93 gefallen.
- Zweiter Inline-Localized-Grossblock-Nachzug:
  - Capability-Missing-/Execution-Texte aus `aria/core/pipeline_capability_messages.py` liegen jetzt in `pipeline_capability_messages.*` i18n-Keys.
  - Recipe-Overview-/Wizard-Fallbacks aus `aria/web/recipes_routes.py` nutzen englische Code-Fallbacks und deutsche/englische `skills.*` i18n-Keys.
  - Memory-Hub-Next-Steps und Upload-Fehler aus `aria/web/memories_routes.py` liegen jetzt in `memories_routes.*` i18n-Keys.
  - `inline_localized` ist dadurch von 93 auf 50 gefallen.
- Finaler Inline-Localized-Nachzug:
  - Execution-Dry-Run-Texte aus `aria/core/execution_dry_run.py` und `aria/core/execution_dry_run_text.py` liegen jetzt in `execution_dry_run.*` und `execution_dry_run_text.*` i18n-Keys.
  - Learned-/Stored-Recipe-Kandidatenansichten und Planner-Follow-up-Texte aus `aria/core/learned_recipe_candidate_view.py`, `aria/core/action_planner_skill_candidates.py` und `aria/core/action_planner_followups.py` liegen jetzt in eigenen i18n-Keys.
  - Connection-Mutation-Statusmeldungen, Pipeline-Capability-Details, Capability-Execution-Texte, Auth-JSON-Fallbacks und License-Summaries liegen jetzt in `connection_mutation.*`, `pipeline_capability_details.*`, `pipeline_capability_execution.*`, `auth.*` und `licenses.*` i18n-Keys.
  - `inline_localized` ist dadurch von 50 auf 0 gefallen.
- Deklarativer Input-Lexikon-Nachzug:
  - Routing-Profile und Capability-Routing-Begriffe aus `aria/core/routing_lexicon.py` liegen jetzt in `aria/lexicons/routing.json`.
  - Chat-Notes-Patterns liegen jetzt in `aria/lexicons/chat_notes.json`; sichtbare Chat-Notes-Antworten nutzen `chat_notes.*` i18n-Keys.
  - Chat-Admin-Kommandopatterns und Phrase-Listen liegen jetzt in `aria/lexicons/chat_admin_actions.json`.
  - Action-Planner-Scoring-Hints liegen jetzt in `aria/lexicons/action_planner_scoring.json`.
  - Auto-Memory-Regeln, Routing-Resolver-Scoring, Website-Chat-Patterns, Capability-Router-Patterns, Recipe-Runtime-Matching und Action-Planner-Extractor-Hints liegen jetzt ebenfalls in `aria/lexicons/*.json`.
  - Connection-Catalog-Extras, Action-Planner-Template-Overrides, Connection-Semantic-Resolver-Prompts, Pipeline-Missing-Input-Patterns, Notes-Tag-Normalisierung und Update-Helper-Fehlererkennung liegen jetzt ebenfalls in `aria/lexicons/*.json`.
  - `input_lexicon` ist dadurch von 142 auf 0 gefallen.

Prioritaet fuer Abbau:
1. CI-Integration vorbereiten
   - `scripts/audit_i18n_code_literals.py --strict` liefert Exitcode 1 bei neuen Treffern
   - Contract-Test `tests/test_i18n_code_literal_audit.py` prueft den aktuellen Null-Stand und die Klassifikation
   - sobald ein CI-Workflow existiert, `--strict` dort als Pflichtschritt aufnehmen
2. Katalog-/Template-Schnitt stabilisieren
   - `connection_catalog.py` und `action_planner_templates.py` enthalten weiter strukturierte Python-Kataloge, aber keine deutschen Code-Literal-Treffer mehr
   - ein spaeterer Umbau kann ganze Kataloge nach `aria/catalogs/*.json` verschieben, wenn wir Erweiterbarkeit statt Audit-Abbau priorisieren

Zielzustand:
- neue sichtbare Texte nicht mehr direkt in Python einfuehren
- keine neuen deutschen Runtime-Literale ausserhalb von Tests/i18n-/Lexikon-Dateien
- keine deutschen Eingabe-Lexikon-Literale mehr in Python einfuehren
- Audit-Script dauerhaft als lokale/CI-Guardrail aktiv halten
