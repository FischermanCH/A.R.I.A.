# ARIA - Technische Architektur

Stand: 2026-04-03  
Release-Basis: `0.1.0-alpha21`

Zweck:
- zentrale Architektur-Erklärung für README, Release-Doku und spätere Public Docs
- technisch konkret genug, um ARIA als System zu verstehen
- bewusst release-orientiert statt historischer Bauplan

## Überblick

ARIA ist ein self-hosted AI Assistant mit browser-first UI, deterministischer Pipeline, Memory via Qdrant und modularen Connections/Skills für echte Systeme.

Der zentrale Architekturgedanke ist: **strukturierte Pfade zuerst, LLM erst wenn nötig**.

Das bedeutet:
- Custom Skills und Capability-Routing werden vor dem generischen Chat-LLM geprüft
- Memory-Operationen laufen über explizite Intents
- das LLM bleibt für freie Sprache, Transformation und Zusammenfassung zuständig
- technische Aktionen selbst bleiben in kontrollierten Runtime-Modulen

Der Stack ist bewusst schlank:
- FastAPI
- Jinja2
- LiteLLM
- Qdrant
- SQLite / lokaler Secure Store
- YAML/JSON-Dateien für Config, Skills, Logs und Runtime-State

Kein React-/Node-Frontend-Build, keine zwingende Cloud-Abhängigkeit im Kernbetrieb.

---

## Schichtenarchitektur

![ARIA Schichtenarchitektur](./aria_schichten_architektur.svg)

ARIA ist in vier Hauptschichten organisiert, die vertikal aufeinander aufbauen und jeweils klar getrennte Verantwortlichkeiten haben.

### 1. Web UI / HTTP Layer

Die oberste Schicht besteht aus FastAPI-Routes, Jinja2-Templates und statischem CSS.

Wichtige Eigenschaften:
- serverseitig gerendertes UI
- kein React/Node-Buildprozess
- responsive UI inklusive Theme-/Background-System
- `/` als Chat-UI
- `/stats`, `/skills`, `/memories`, `/config/*`, `/help` als UI-Seiten
- `/health` als Healthcheck
- `POST /v1/chat/completions` als OpenAI-kompatibler API-Endpoint

Wichtige Module:
- `aria/main.py`
- `aria/web/stats_routes.py`
- `aria/web/activities_routes.py`
- `aria/web/skills_routes.py`
- `aria/web/memories_routes.py`
- `aria/web/config_routes.py`
- `aria/templates/*`
- `aria/static/style.css`

### 2. Pipeline / Orchestration Layer

Das Herzstück ist `aria/core/pipeline.py`. Dort wird jede Anfrage in einer festen Reihenfolge verarbeitet.

Aufgaben dieser Schicht:
- Routing-Entscheid
- Custom-Skill-Ausführung
- Capability-Ausführung
- Memory Store / Recall / Forget
- Context Assembly
- LLM-Aufruf
- Token-, Kosten- und Activity-Logging
- optional Auto-Memory nach dem LLM-Call

Wichtige Module:
- `aria/core/pipeline.py`
- `aria/core/capability_router.py`
- `aria/core/capability_catalog.py`
- `aria/core/context.py`
- `aria/core/llm_client.py`
- `aria/core/token_tracker.py`
- `aria/core/pricing_catalog.py`
- `aria/core/auto_memory.py`

### 3. Runtime / Integration Layer

Diese Schicht führt konkrete Aktionen gegen externe Systeme aus und kapselt alle unterstützten Connection-Typen.

Unterstützte Integrationen:
- SSH
- SFTP
- SMB
- Discord
- RSS
- HTTP API
- Webhook
- SMTP
- IMAP
- MQTT

Wichtige Architekturprinzipien:
- Connection-Profile beschreiben technische Zielsysteme
- Runtime-Module führen Aktionen aus
- Health-Checks und CRUD-Verwaltung sind getrennt von der eigentlichen Ausführung
- Guardrails schützen riskantere Aktionen, besonders bei SSH

Wichtige Module:
- `aria/core/connection_catalog.py`
- `aria/core/connection_admin.py`
- `aria/core/connection_health.py`
- `aria/core/connection_runtime.py`
- `aria/core/connection_semantic_resolver.py`
- `aria/core/ssh_runtime.py`
- `aria/core/skill_runtime.py`
- `aria/core/guardrails.py`
- `aria/core/safe_fix.py`

### 4. Memory / State Layer

Persistenz liegt bewusst außerhalb des ersetzbaren ARIA-App-Codes und verteilt sich auf drei Speicherarten.

**Qdrant**
- semantische Memories als Vektor-Collections
- User-bezogene Memory-Trennung
- Recall via Similarity Search
- Forget + Cleanup leerer Collections

**SQLite / Secure Store**
- Auth-/Session-Daten
- Secrets für Connection-Credentials
- keine Klartext-Secrets in `config.yaml`

**YAML / JSON / Textdateien**
- `config/config.yaml` als zentrale Runtime-Konfiguration
- `prompts/` für Persona- und Skill-Prompts
- `data/skills/*.json` für Custom-Skill-Manifeste
- `data/logs/*.jsonl` für Token-/Activity-Logs
- `data/runtime/*.json` für Caches und Runtime-State

Wichtige Module:
- `aria/skills/memory.py`
- `aria/core/qdrant_client.py`
- `aria/core/maintenance.py`
- `aria/core/secure_store.py`
- `aria/core/secure_migrate.py`
- `aria/core/auth.py`
- `aria/core/user_admin.py`

---

## Routing-Architektur

![ARIA Intelligentes Routing](./aria_intelligentes_routing.svg)

Das Routing ist deterministisch priorisiert und bewusst nicht als blindes LLM-Klassifikationsproblem gebaut.

## Routing-Reihenfolge

### 1. Custom Skills

Zuerst prüft ARIA aktive Skill-Manifeste aus `data/skills/`.

Ein klar passender Custom Skill hat Vorrang vor generischem Capability-Routing. Das ist wichtig, damit explizit gebaute Workflows nicht von allgemeineren Connection-Aktionen überfahren werden.

Wichtige Module:
- `aria/core/custom_skills.py`
- `aria/core/skill_runtime.py`

### 2. Capability Routing

Wenn kein Skill gewinnt, prüft `aria/core/capability_router.py` auf strukturierte Capability-Intents wie Datei lesen/schreiben, Feed lesen, Discord senden oder HTTP-Requests.

Die Connection-Auflösung nutzt dabei nicht nur den technischen `ref`, sondern auch:
- Titel
- Kurzbeschreibung
- Aliase
- Tags

Dadurch kann ein Prompt wie `was gibt es auf heise?` oder `schick das in meinen Homelab Discord` natürlicher auf konkrete RSS-/Discord-Profile gemappt werden.

Wichtige Module:
- `aria/core/capability_router.py`
- `aria/core/connection_semantic_resolver.py`

### 3. Memory Intents

Explizite Memory-Operationen werden über eigene Intents verarbeitet:
- `memory_store`
- `memory_recall`
- `memory_forget`

Auto-Memory ist davon getrennt und läuft optional nach normalen Chat-Antworten. Capability-Ergebnisse werden dabei **bewusst nicht pauschal automatisch persistiert**, weil viele davon nur Momentaufnahmen sind und sonst schnell veraltetes Rauschen in Qdrant erzeugen würden. Wenn solche Ergebnisse später dauerhaft lernwirksam werden sollen, dann über explizit modellierte Summary-/State-Memory-Flows, nicht über blindes Mitschreiben jeder Action-Antwort.

Wichtige Module:
- `aria/skills/memory.py`
- `aria/core/auto_memory.py`
- `aria/core/memory_assist.py`

### 4. LLM-Fallback

Wenn kein Skill, keine Capability und kein Memory-Intent greift, geht die Anfrage in den normalen Chat-LLM-Pfad.

`aria/core/llm_client.py` nutzt LiteLLM als Provider-Abstraktion für OpenAI-, Anthropic-, OpenRouter- und Ollama-kompatible Modelle. Der Prompt-Kontext wird in `aria/core/context.py` aus Persona, Chat-History und optionalem Memory-Kontext zusammengesetzt.

## Warum deterministisch vor LLM?

Das Design vermeidet vier typische Probleme eines LLM-First-Routers:
- unnötige Latenz durch Routing-LLM-Calls
- unnötige Kosten pro Routing-Entscheid
- nicht-deterministisches Verhalten bei Systemaktionen
- schlechtere Nachvollziehbarkeit bei Fehlrouting

ARIAs Ansatz ist deshalb: **strukturierte Signale für Routing, LLM für Sprache und Transformation**.

---

## Custom Skills

Custom Skills sind JSON-Manifeste mit einer geordneten Step-Liste. Sie werden im Browser-Wizard erstellt, bearbeitet, exportiert und importiert.

Beispiel:

```json
{
  "id": "homelab-status",
  "name": "Homelab Status",
  "router_keywords": [
    "homelab status",
    "server check"
  ],
  "steps": [
    {
      "id": "s1",
      "type": "ssh_run",
      "connection_ref": "homelab-main",
      "command": "uptime && df -h / && free -m"
    },
    {
      "id": "s2",
      "type": "llm_transform",
      "prompt": "Fasse diesen Server-Status in 2 Sätzen zusammen: {prev_output}"
    },
    {
      "id": "s3",
      "type": "discord_send",
      "connection_ref": "homelab-discord",
      "message": "{prev_output}"
    }
  ]
}
```

Die Skill Runtime führt Steps sequenziell aus und reicht Step-Output an Folgeschritte weiter.

Unterstützte Step-Typen:
- `ssh_run`
- `sftp_read`
- `sftp_write`
- `smb_read`
- `smb_write`
- `rss_read`
- `discord_send`
- `http_request`
- `webhook_send`
- `mqtt_publish`
- `imap_read`
- `smtp_send`
- `llm_transform`
- `chat_send`

Sample-Skills liegen unter `samples/skills/`.

---

## Connection- und Persistenzmodell

![ARIA Modularität und Persistenz](./aria_modularitaet_persistenz.svg)

Ein wichtiger ARIA-Grundsatz ist, dass **der App-Container ersetzbar ist, während Config, Prompts, Skills, Logs und Memories in Volumes erhalten bleiben**.

## Connection-Profile

Jede Connection ist ein Profil mit:
- technischen Parametern
- Credentials im Secure Store
- optionalen Routing-Metadaten
- Health-/Statusinformationen

Die UI trennt bewusst:
- `Neu` für neue Profile
- Klick auf eine bestehende Statuskarte für Edit
- Health-Test / Live-Status
- Löschen erst im Profil selbst

SSH ist ein Sonderfall, weil Key-Erzeugung direkt im Container über `ssh-keygen` unterstützt wird. SFTP kann SSH-Daten aus bestehenden SSH-Profilen übernehmen, um Doppelpflege zu vermeiden.

## Persistente Volumes im Container-Setup

Typisches Compose-/Portainer-Setup:

```text
aria
  /app/config   -> config.yaml, secrets.env
  /app/prompts  -> Persona- und Skill-Prompts
  /app/data     -> Skills, Logs, Chat-History, Runtime-Caches

qdrant
  /qdrant/storage -> Vektor-DB / Collections
```

Der ARIA-Container kann ersetzt werden, ohne diese Volumes zu löschen. Genau darauf basiert der aktuelle sichere Update-Pfad.

Der EntryPoint `docker/entrypoint.sh` initialisiert leere Volumes beim ersten Start aus den Defaults im Image.

---

## Memory-Architektur

Qdrant ist der semantische Memory-Store. ARIA spricht ihn über `aria/core/qdrant_client.py` an.

Aktuell gilt:
- Memory Store / Recall / Forget funktionieren
- Collections sind User-bezogen getrennt
- leere Collections werden nach UI-Löschung und Chat-Forget aufgeräumt
- Recall läuft gewichtet über Facts, Preferences, Knowledge und Session-Collections; Typ-Gewichte und Zeitabfall für Session-Kontext beeinflussen das Ranking
- Auto-Memory für normale Chat-Pfade ist konfigurierbar
- Auto-Memory filtert flüchtige Einmalfragen und reine Tool-/Action-Prompts beim automatischen Persistieren stärker heraus, damit nicht jede Chat-Zeile als neue Erinnerung in Qdrant landet
- Memory-Export ist als JSON-Download aus der Memory-Ansicht verfügbar
- Qdrant-Status und DB-Größe erscheinen in `Statistiken`

Wichtig:
- Embeddings sind getrennt vom Chat-LLM konfiguriert
- beim Recall muss dasselbe Embedding-Modell konsistent zur Index-Erzeugung passen
- ein späterer Reindex-/Migration-Flow bei Embedding-Modellwechsel ist bewusst Roadmap

## Geplanter Memory-Ausbau

Ohne Memory Map / Graph-Visualisierung, aber mit weiterem Ausbau rund um Datenlebenszyklus und Migration:
- typisierte Auto-Memory-Extraktion für Facts / Preferences / Sessions
- Session-Rollups Tag -> Woche -> Monat
- Memory Import / Portabilität
- besserer Reindex-/Warnflow bei Embedding-Modellwechsel

Diese Punkte sind im Main Backlog dokumentiert:
- `docs/backlog/main-backlog.md`

---

## Security-Modell

**Auth**
- erster User wird beim Bootstrap automatisch Admin
- Admin-Modus und User-Modus trennen Alltags-UI und tiefe Konfiguration
- Zugriff auf Config-/User-Seiten ist rollenabhängig begrenzt

**Secrets**
- Credentials werden im lokalen Secure Store gespeichert
- `config/config.yaml` ist nicht der Klartext-Ort für Secrets

**Guardrails**
- Guardrail-Profile können riskante Aktionen, besonders SSH-Kommandos, einschränken
- Ziel ist kontrollierte Ausführung statt blindes Prompt-to-Shell

**Netzwerkmodell im Alpha**
- empfohlen ist LAN/VPN/Homelab-Betrieb
- kein offener Public-Internet-Betrieb ohne zusätzliche Schutzschicht

Wichtige Hilfe dazu:
- `docs/help/security.md`

---

## Observability und Statistiken

ARIA schreibt und zeigt strukturiert:
- Intent / Skill / Capability pro Anfrage
- Token-Anzahl
- USD-Kosten, wenn Pricing für das Modell bekannt ist
- Laufzeit
- Activity-/Run-Status
- Connection-Live-Status
- ARIA-RAM
- Qdrant-DB-Größe
- Startup-Preflight und Systemzustand

Pricing:
- OpenAI/Anthropic über LiteLLM-Preisliste
- OpenRouter über OpenRouter Models API
- lokale Modelle können bewusst unbepreist bleiben

Wichtige Module:
- `aria/core/token_tracker.py`
- `aria/core/pricing_catalog.py`
- `aria/web/stats_routes.py`

---

## Deployment- und Update-Strategie

Aktueller Default-Stack:
- ein `aria`-Container
- ein `qdrant`-Container
- persistente Volumes für Config, Prompts, Data und Qdrant Storage

Wichtiger Architekturpunkt:
- **Updates ersetzen nur den ARIA-Container**
- **Qdrant-Container und Volumes bleiben erhalten**
- dadurch bleiben Config, Secrets, Connections, Skills, Logs, Chat-History und Memories über Updates erhalten

Konfiguration:
- `config/config.yaml`
- ENV-Overrides über `ARIA_*`

Für Setup-Details:
- `docs/setup/setup-overview.md`
- `docs/setup/portainer-deploy-checklist.md`

Für Versionierung und Release-Prozess:
- `docs/release/versioning.md`

---

## Aktuelle bewusste Architekturgrenzen und Designentscheidungen

- ARIA ist aktuell primär ein **Personal Single-User System**
- kein vollständiges Multi-User-/RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse laufen **absichtlich nicht** pauschal durch Auto-Memory; dauerhafte Speicherung solcher Resultate soll später nur über gezielte Summary-/State-Memory-Flows erfolgen
- kein In-App-Container-Self-Updater
- Home Assistant, Websuche, Dokument-Ingest, Streaming/SSE und größere Channel-Adapter sind Roadmap, nicht aktueller Release-Kern

Roadmap-Doku:
- `docs/backlog/alpha-backlog.md`
- `docs/backlog/main-backlog.md`
