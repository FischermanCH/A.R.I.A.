# ARIA – Technische Architektur

Stand: 2026-04-03 · Version 0.1.0-alpha.21

---

## Überblick

ARIA ist ein self-hosted AI Assistant, der auf einem deterministischen Pipeline-Modell aufbaut. Statt jede Anfrage blind an ein LLM weiterzuleiten, analysiert ARIA den Intent zuerst strukturiert – und ruft das LLM nur dann auf, wenn kein spezifischerer Pfad greift. Das erlaubt vorhersehbares Verhalten bei Systemintegrationen und vermeidet unnötige LLM-Kosten für Anfragen, die sich deterministisch beantworten lassen.

Der Stack ist bewusst schlank: FastAPI, Jinja2, LiteLLM, Qdrant, SQLite. Kein Frontend-Framework, keine Buildchain, keine externen Cloud-Abhängigkeiten im Kernbetrieb.

---

## Schichtenarchitektur

ARIA ist in vier klar getrennte Schichten gegliedert, die vertikal gestapelt sind und nur mit ihren direkten Nachbarn kommunizieren.

### Web UI / HTTP Layer

Die oberste Schicht besteht aus FastAPI-Routes und Jinja2-Templates. Das UI wird vollständig serverseitig gerendert – kein React, kein Node-Buildprozess, keine JavaScript-Bundles. Statisches CSS deckt Theming und Responsivität ab.

FastAPI stellt neben der Web-UI auch einen OpenAI-kompatiblen Endpoint unter `POST /v1/chat/completions` bereit. Das erlaubt es, ARIA als Drop-in-Backend für Tools zu verwenden, die den OpenAI-Standard erwarten. Der `/health`-Endpoint dient Container-Orchestratoren und Monitoring.

Die Route-Registrierung erfolgt modular über separate Route-Module:
- `aria/web/stats_routes.py`
- `aria/web/activities_routes.py`
- `aria/web/skills_routes.py`
- `aria/web/memories_routes.py`
- `aria/web/config_routes.py`

### Pipeline / Orchestration Layer

Das Herzstück ist `aria/core/pipeline.py`. Jede eingehende Anfrage – egal ob aus dem Browser-Chat, der API oder einem Skill-Trigger – läuft durch diese zentrale Orchestrierung. Die Pipeline entscheidet in fester Reihenfolge:

1. Ist ein passender Custom Skill vorhanden? → Skill Runtime
2. Trifft ein strukturierter Capability-Pfad zu? → Capability Router
3. Ist es ein Memory-Intent? → Memory-Modul
4. Kein Treffer → LLM-Aufruf via LiteLLM

Parallel dazu laufen Token-Tracking, Kosten-Logging und Activity-Recording für jede Anfrage durch `aria/core/token_tracker.py` und `aria/core/pricing_catalog.py`.

### Runtime / Integration Layer

Diese Schicht enthält alle Verbindungstypen als eigenständige Runtime-Module:

- `aria/core/ssh_runtime.py` – SSH-Befehlsausführung, Key-Verwaltung
- `aria/core/connection_runtime.py` – generische Verbindungsausführung
- `aria/core/connection_health.py` – Live-Statusprüfung aller Profile
- `aria/core/guardrails.py` – Absicherung riskanter Aktionen, z. B. SSH-Commands
- `aria/core/safe_fix.py` – Fehlerkorrektur auf Runtime-Ebene

Unterstützte Verbindungstypen: SSH, SFTP, SMB, Discord, RSS, HTTP API, Webhook, SMTP, IMAP, MQTT.

Jede Verbindung wird als Profil in der Config verwaltet und trägt optionale Kontext-Metadaten: Titel, Kurzbeschreibung, Aliase, Tags. Diese Metadaten sind kein Komfort-Feature – sie sind aktiv Teil der Verbindungsauflösung im Router.

### Memory / State Layer

Persistenz läuft auf drei parallelen Wegen:

**Qdrant** speichert semantische Memories als Vektoren. Collections sind pro User und Memory-Typ getrennt. Recall funktioniert über Cosine-Similarity-Suche; Forget löscht gezielt Einträge und räumt leere Collections auf.

**SQLite / Secure Store** hält Auth-Daten, User-Sessions und Verbindungs-Credentials. Secrets werden nicht im Klartext in der Config gespeichert, sondern im lokalen Secure Store verwaltet (`aria/core/secure_store.py`, `aria/core/secure_migrate.py`).

**JSON/YAML-Dateien** decken alles Restliche ab: Skill-Manifeste in `data/skills/*.json`, Token-Logs als JSONL in `data/logs/`, Runtime-Caches in `data/runtime/`, zentrale Konfiguration in `config/config.yaml`.

---

## Intelligentes Routing im Detail

Das Routing-Modell ist der architektonisch entscheidende Teil von ARIA. Es ist kein Klassifikator, der LLM-Ausgaben interpretiert – es ist ein deterministischer Entscheidungsbaum, der strukturelle Signale auswertet.

### Routing-Reihenfolge

**Schritt 1: Custom Skill Match**

Der Router prüft zuerst alle aktiven Skill-Manifeste in `data/skills/`. Ein Skill-Manifest definiert Trigger-Begriffe, die mit dem eingehenden Prompt verglichen werden. Custom Skills haben explizit höchste Priorität – ein Prompt, der einem Skill eindeutig zugeordnet werden kann, erreicht die generische Capability-Ebene gar nicht.

**Schritt 2: Capability-Routing**

Wenn kein Skill trifft, wertet `aria/core/capability_router.py` den Prompt gegen den Capability-Katalog aus. Der Katalog beschreibt strukturierte Aktionen wie «Feed lesen», «Datei auf SMB-Share schreiben», «Discord-Nachricht senden». Die Auflösung bezieht die Verbindungsmetadaten (Titel, Aliase, Tags) aktiv ein: Ein Prompt wie «schick das an meinen Homelab-Discord» wird gegen die Discord-Verbindungsprofile aufgelöst, nicht gegen einen fest kodierten Bezeichner.

`aria/core/connection_semantic_resolver.py` übernimmt das Mapping zwischen freiem Prompt-Text und konkretem Verbindungsprofil. Das erlaubt natürliche Sprache bei der Verbindungsauswahl, ohne dass der User den exakten Profilnamen kennen muss.

**Schritt 3: Memory-Intents**

Vor dem LLM-Fallback prüft die Pipeline Memory-spezifische Intents:
- `memory_store` – explizites Speichern einer Information
- `memory_recall` – Abfrage aus dem Qdrant-Index
- `memory_forget` – gezieltes Löschen

Memory-Recall geschieht nicht automatisch bei jeder Anfrage. Auto-Memory ist konfigurierbar und läuft als separater Pfad nach dem LLM-Aufruf (`aria/core/auto_memory.py`).

**Schritt 4: LLM-Fallback**

Erst hier kommt das LLM zum Einsatz. `aria/core/llm_client.py` spricht LLMs über LiteLLM an, das OpenAI-, Anthropic-, OpenRouter- und Ollama-kompatible Endpunkte abstrahiert. Der Context Assembly (`aria/core/context.py`) baut den Prompt zusammen aus: aktuellem Prompt, Chat-History, optionalem Memory-Recall und Persona-Prompt.

### Warum deterministisch vor LLM?

Ein LLM-Router hätte mehrere Nachteile in diesem Kontext:
- Nicht-deterministisches Verhalten bei gleichem Input
- Latenz durch den LLM-Aufruf vor der eigentlichen Aktion
- Kosten für jeden Routing-Entscheid
- Schwierigere Nachvollziehbarkeit im Fehlerfall

ARIAs Ansatz ist: strukturelle Signale (Skill-Manifeste, Capability-Katalog, Intent-Keywords) sind billiger, schneller und vorhersehbarer als LLM-Klassifikation. Das LLM bleibt für das, was es gut kann – freier Text, Transformation, Analyse.

---

## Custom Skills

Skills sind JSON-Manifeste, die einen Automatisierungsablauf als geordnete Liste von Steps beschreiben. Jeder Step hat einen Typ, eine Verbindungsreferenz und typspezifische Parameter.

```json
{
  "id": "homelab-status",
  "name": "Homelab Status",
  "trigger": ["homelab status", "server check"],
  "steps": [
    {
      "type": "ssh_run",
      "connection": "homelab-main",
      "command": "uptime && df -h / && free -m"
    },
    {
      "type": "llm_transform",
      "prompt": "Fasse diesen Server-Status in 2 Sätzen zusammen: {{previous_output}}"
    },
    {
      "type": "discord_send",
      "connection": "homelab-discord",
      "message": "{{previous_output}}"
    }
  ]
}
```

Die Skill Runtime (`aria/core/skill_runtime.py`) führt Steps sequenziell aus und leitet den Output eines Steps als `{{previous_output}}` in den nächsten weiter. Steps können also aufeinander aufbauen: SSH-Ausgabe lesen → LLM transformieren → Ergebnis senden.

Unterstützte Step-Typen: `ssh_run`, `sftp_read`, `sftp_write`, `smb_read`, `smb_write`, `rss_read`, `discord_send`, `http_request`, `webhook_send`, `mqtt_publish`, `imap_read`, `smtp_send`, `llm_transform`, `chat_send`.

Skills werden im Browser-Wizard erstellt und bearbeitet. Import/Export funktioniert als JSON-Datei. Sample-Skills für gängige Patterns liegen unter `samples/skills/`.

---

## Verbindungsarchitektur

Jede Verbindung wird als Profil in der Config verwaltet. Ein Profil enthält Zugangsdaten (via Secure Store), technische Parameter und optionale Routing-Metadaten.

Die Trennung zwischen **Profilverwaltung** (was existiert), **Health-Check** (ist es erreichbar) und **Runtime-Ausführung** (führe Aktion aus) ist explizit in separate Module aufgeteilt:

- `aria/core/connection_catalog.py` – verfügbare Profile
- `aria/core/connection_health.py` – Live-Status
- `aria/core/connection_runtime.py` – Ausführung
- `aria/core/connection_admin.py` – CRUD-Operationen aus der UI

SSH verdient einen gesonderten Hinweis: `aria/core/ssh_runtime.py` verwaltet SSH-Keys direkt im Container. Key-Erzeugung läuft über `ssh-keygen` im Container-Kontext. SFTP-Profile können SSH-Zugangsdaten aus bestehenden SSH-Profilen übernehmen, um Doppelkonfiguration zu vermeiden.

---

## Memory-Architektur

Qdrant wird als externer Service im selben Container-Stack betrieben. ARIA spricht Qdrant über `aria/core/qdrant_client.py` an.

Collections sind nach `user_id` und Memory-Typ getrennt. Das erlaubt in Zukunft nutzerspezifische Memory-Isolation, ohne die Indexstruktur zu ändern. Aktuell ist ARIA primär Single-User, aber die Datenstruktur antizipiert Multi-User.

Der Recall-Pfad in `aria/skills/memory.py`:
1. Prompt wird mit demselben Embedding-Modell enkodiert wie beim Speichern
2. Cosine-Similarity-Suche gegen die User-Collection
3. Top-K-Ergebnisse werden in den Context Assembly übergeben
4. LLM erhält Memories als Teil des Kontexts

`aria/core/maintenance.py` deckt Memory-Hygiene ab: Deduplizierung, Aufräumen leerer Collections, manuelle Maintenance-Trigger aus der UI.

Embeddings sind separat vom LLM konfiguriert – das erlaubt z. B. ein lokales Ollama-Embedding-Modell bei gleichzeitiger Nutzung eines Remote-LLM für Chat.

---

## Deployment und Update-Strategie

ARIA läuft als Docker-Container neben einem Qdrant-Container. Persistenz liegt ausschliesslich in Volumes:

```
aria/          → Web UI + Pipeline + Runtime (ersetzbar)
qdrant/        → Vector Store (bleibt)

Volumes:
  /app/config  → config.yaml, secrets.env
  /app/prompts → Persona- und Skill-Prompts
  /app/data    → Skills, Logs, Chat-History, Runtime-Caches
  qdrant_storage
```

Der EntryPoint (`docker/entrypoint.sh`) initialisiert leere Volumes beim ersten Start aus eingebauten Defaults. Das macht das erste Setup friktionslos: Volume mounten, Container starten, Browser öffnen.

Update-Ablauf: nur der ARIA-Container wird ersetzt. Qdrant-Container und alle Volumes bleiben unangetastet. Connections, Skills, Memories, Logs und Chat-History überleben den Update ohne Migrationsskript – weil sie in Volumes liegen, nicht im Container.

Konfiguration läuft über `config/config.yaml` mit `ARIA_*`-ENV-Overrides. Das erlaubt sowohl dateibasierte Konfiguration für lokale Instanzen als auch reine ENV-Konfiguration für automatisierte Deployments.

---

## Security-Modell

**Auth:** Login-System mit Bootstrap-Admin beim ersten Start. Der erste angelegte User wird automatisch Admin. Admin-Modus und User-Modus sind getrennte Ansichten mit unterschiedlichem Zugriff auf Config-Seiten.

**Secrets:** Verbindungs-Credentials werden nicht in `config.yaml` im Klartext gespeichert. Sie landen im lokalen Secure Store (`aria/core/secure_store.py`). Migration zwischen Store-Versionen übernimmt `aria/core/secure_migrate.py`.

**Guardrails:** `aria/core/guardrails.py` definiert Profile für riskante Aktionen. SSH-Command-Ausführung ist das prominenteste Beispiel – Guardrail-Profile können Commands einschränken, Preflight-Checks erzwingen oder bestimmte Patterns blockieren.

**Netzwerk:** Für den Alpha-Betrieb ist LAN- oder VPN-Zugang empfohlen. Kein offener Public-Internet-Betrieb ohne vorgeschaltete Schutzschicht.

---

## Observability

Jede Pipeline-Ausführung schreibt strukturiertes Logging:

- **Token-Tracking:** Prompt-Tokens, Completion-Tokens, Gesamtkosten in USD pro Request – als JSONL in `data/logs/`
- **Activity-Log:** welcher Skill/Capability/Intent wurde ausgeführt, mit Laufzeit und Ergebnis-Status
- **Pricing-Catalog:** Modellpreise werden manuell oder automatisch über die LiteLLM-Preisliste (OpenAI/Anthropic) und die OpenRouter-Models-API aktualisiert

Die `/stats`-Seite aggregiert diese Daten direkt im UI: Token-Verbrauch über Zeit, Kosten, RAM-Auslastung des ARIA-Prozesses, Qdrant-DB-Grösse, Connection-Live-Status aller Profile.

---

## Aktuelle Architekturgrenzen

**Single-User-Optimierung:** Die aktuelle Architektur ist für persönlichen Gebrauch ausgelegt. User-Trennung in Qdrant ist vorbereitet, aber RBAC für geteilte Skills, Connections und Memories existiert noch nicht.

**Capability → Memory:** Capability-Ergebnisse laufen aktuell nicht automatisch durch den Auto-Memory-Pfad. Chat-Antworten können automatisch in Memory geschrieben werden, Capability-Outputs noch nicht. Das ist eine offene Produktentscheidung, keine technische Einschränkung.

**Keine Container-Selbstaktualisierung:** Update-Hinweise auf neue Versionen sind geplant (UI-Hinweis bei verfügbarer neuerer Version), aber kein In-App-Container-Updater. Updates laufen manuell über den definierten Volume-sicheren Prozess.

---

## Roadmap-Architektur (Auswahl)

**Memory Architecture 2.0:** Typisierte Memory-Klassen (Facts, Preferences, Sessions, Knowledge), gewichtetes Recall über mehrere Collections, TTL und Rollups für Memory-Hygiene.

**Home Assistant Integration:** HA als eigene Connection mit API/WebSocket-Anbindung, Entity-/Device-Status in Qdrant, ARIA als semantische Schicht über Smart-Home-Zustand.

**Plugin-/Extension-Modell:** Capability- und Connection-Architektur weiter modularisieren, neue Verbindungstypen ohne Monolith-Wachstum ermöglichen.

**Ingest / Knowledge:** Dokument-Ingest mit Chunking-Pipeline als eigenständige Knowledge-Collection in Qdrant, getrennt von persönlichen Memories.
