# Connection Action Contract

Stand: 2026-05-12

Dieses Dokument beschreibt den kleinen gemeinsamen Vertrag, den neue Connection-Typen in ARIA einhalten sollen. Ziel: neue Provider duerfen Adapter bekommen, aber keine neue Sonderlogik quer durch `pipeline.py` erzwingen.

## Schichten

1. **Capability Draft**
   - Was meint der User als Aktion?
   - Beispiele: `ssh_command`, `api_request`, `file_list`, `discord_send`, `feed_read`.
   - Quelle kann deterministische Kontextanreicherung oder ein bounded LLM-Draft sein.

2. **Connection Action Contract**
   - Zentrale Metadaten in `aria/core/connection_action_contract.py`.
   - Definiert pro Capability:
     - Runtime-Operation, z. B. `run_command`, `request`, `list`, `send`, `read`.
     - erlaubte Executor-Kinds aus dem Capability-Katalog.
     - benoetigte Felder, z. B. `connection_ref`, `path`, `content`.
     - Policy-Familie, z. B. `ssh_readonly`, `http_api`, `file_access`, `message_confirm`, `read_only`.
     - ob die Aktion einen Side Effect hat.
     - welche `ActionPlan`-Felder im `agentic_runtime` Debug sichtbar werden.

3. **Policy / Guardrail**
   - Entscheidet `allow`, `ask_user` oder `block`.
   - LLM-Drafts duerfen nie selbst autorisieren.

4. **Executor Adapter**
   - Technische Ausfuehrung je Connection-Kind.
   - Wird ueber `ExecutorRegistry` an `(connection_kind, capability)` gebunden.

5. **Runtime Debug / Observability**
   - `agentic_runtime` Debug-Zeilen kommen aus demselben Contract.
   - Kosten/Token bleiben ueber den zentralen LLM-/Embedding-Gateway sichtbar.

## Neue Connection-Typen

Ein neuer Connection-Typ sollte mindestens liefern:

- Eintrag im Connection-Katalog und UI-Konfiguration.
- Capability-Eintrag oder bestehende Capability-Bindung im Capability-Katalog.
- Contract-Eintrag in `connection_action_contract.py`.
- Executor-Adapter in der Runtime, registriert ueber `ExecutorRegistry`.
- Policy/Guardrail-Familie oder bewusste Wiederverwendung einer vorhandenen Familie.
- Regressionstest, dass `capability_executor_bindings()` durch `connection_action_contract()` abgedeckt ist.

## Nicht erlaubt

- Direkte Provider-/Connection-Logik tief im Planner oder RAG-Chat verstecken.
- LLM-Draft als Policy-Entscheid behandeln.
- Secrets in Dossiers, Debug-Zeilen oder Prompt-Kontext geben.
- Neue Action-Pfade ohne `agentic_runtime` Debug und Token-/Kosten-Sichtbarkeit bauen.
