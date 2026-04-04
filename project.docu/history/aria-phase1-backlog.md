# ARIA — Phase 1 Backlog (GUI-First)

## Philosophie

> **Der User öffnet den Browser und chattet. Vom ersten Moment an.**

Kein curl, kein CLI, kein "API first". ARIA ist ein Produkt für Menschen, nicht für Terminals. Das Web-UI entsteht parallel zum Backend — nach jeder Session ist etwas Sichtbares und Benutzbares da.

**Stack Web-UI:** FastAPI + Jinja2 + HTMX + ~200 Zeilen CSS. Kein React, kein Node.js, kein Build-Step, kein npm.

---

## Scope Phase 1

- Web-UI mit Chat-Interface (Dark Mode, responsive, Token-Badge)
- 1 Pipeline-Run pro Request (kein Agent-Loop)
- Router Stufe 1 (Keywords only, 0 Tokens)
- Memory via Qdrant (Store + Recall pro user_id)
- Token-Logging (JSONL)
- OpenAI-kompatibler Endpoint POST /v1/chat/completions (Nebenprodukt)
- GET /health

Hinweis (Strategie-Update 2026-03-24):
- Websuche ist für ARIA wichtig, aber nicht Teil der Phase-1-Pflichtumsetzung.
- Default-Pfad später: provider-native Web-Tooling (ohne SearXNG-Zwang).

---

## Definition of Done (Phase 1)

1. User öffnet `http://localhost:8800` → sieht Chat-UI
2. User tippt Nachricht → bekommt Antwort vom LLM
3. User sieht Token-Verbrauch + Intent-Badge pro Nachricht
4. "Merk dir X" → speichert in Qdrant
5. "Erinnerst du dich an X?" → findet es wieder
6. config.yaml + ENV-Overrides funktionieren
7. Projekt startet mit `uvicorn aria.main:app --host 0.0.0.0 --port 8800`
8. Tests laufen grün (pytest) für Router, Pipeline, Memory

---

## Session-Plan

### Session 1: "Ich kann chatten" 💬

**Ziel:** User öffnet Browser, tippt, bekommt Antwort.

| # | Task | Dateien | Akzeptanzkriterien |
|---|---|---|---|
| 1.1 | Projekt-Scaffold | `pyproject.toml`, `README.md`, `aria/__init__.py` | `pip install -e .` klappt, `python -c "import aria"` klappt |
| 1.2 | Config-System | `aria/core/config.py`, `config/config.yaml`, `config/config.example.yaml` | YAML lädt, ENV überschreibt mit Präfix `ARIA_`, fehlende Pflichtfelder → klare Fehlermeldung |
| 1.3 | LLM Client | `aria/core/llm_client.py` | `chat(messages)` liefert content + usage, Timeout → Exception |
| 1.4 | Prompt Loader | `aria/core/prompt_loader.py`, `prompts/persona.md` | Lädt + cached per mtime, fehlende Datei → kontrollierter Fehler |
| 1.5 | Minimale Pipeline (ohne Skills) | `aria/core/pipeline.py` | Persona laden → User-Message → LLM → Antwort. Ein LLM-Call, fertig |
| 1.6 | **Web-UI: Chat-Interface** | `aria/main.py`, `aria/templates/base.html`, `aria/templates/chat.html`, `aria/static/style.css` | Browser → `http://localhost:8800` → Chat-Fenster → Nachricht senden → Antwort sehen |
| 1.7 | Health Endpoint | in `aria/main.py` | `GET /health` → `{"status": "ok"}` |

**Ergebnis Session 1:** ARIA läuft im Browser. Noch kein Memory, kein Routing — aber man chattet mit dem LLM über ein schönes Interface.

**Technische Details Web-UI:**

```
aria/templates/base.html     ← HTML-Grundgerüst, Dark Mode
aria/templates/chat.html     ← Chat-Bereich, HTMX für Live-Submit
aria/static/style.css        ← ~200 Zeilen, Dark Theme, responsive

POST /chat (HTMX)            ← Sendet Message, bekommt HTML-Fragment zurück
GET /                        ← Rendert chat.html
```

HTMX statt JavaScript: Kein fetch(), kein JSON parsen im Browser. Das Formular postet, der Server gibt ein HTML-Fragment zurück das HTMX in den Chat einfügt. Null Client-Side-Logik.

---

### Session 2: "Ich erinnere mich" 🧠

**Ziel:** Memory funktioniert, Router erkennt Intents, UI zeigt Badges.

| # | Task | Dateien | Akzeptanzkriterien |
|---|---|---|---|
| 2.1 | Router Stufe 1 (Keywords) | `aria/core/router.py` | "merk dir" → `memory_store`, "erinnerst du dich" → `memory_recall`, default → `chat`. Deterministisch, 0 Tokens |
| 2.2 | Skill-Basis | `aria/skills/__init__.py`, `aria/skills/base.py` | `BaseSkill` ABC mit `execute()`, `truncate()`, `max_context_chars` |
| 2.3 | Memory Skill (Qdrant) | `aria/skills/memory.py`, `prompts/skills/memory.md` | Store: Embedding → Qdrant mit user_id + timestamp. Recall: Similarity Search, top_k=3, nur eigener user_id. Qdrant-Fehler → Pipeline läuft ohne Memory weiter |
| 2.4 | Context Assembler | `aria/core/context.py` | System = Persona. User = Skill-Kontext + Frage. Kontext als "untrusted" markiert. Zu lang → abschneiden |
| 2.5 | Token Tracker | `aria/core/token_tracker.py` | JSONL pro Request: request_id, intents, router_level, prompt/completion/total tokens, Dauer. Pfad aus Config |
| 2.6 | Pipeline erweitern | `aria/core/pipeline.py` | Vollständige 6-Schritte-Pipeline: Load → Route → Skills → Context → LLM → Track |
| 2.7 | **Web-UI: Intent-Badge + Token-Count** | `aria/templates/chat.html` | Jede Antwort zeigt: `[🧠 memory_recall · 643 tokens · 1.2s]` |
| 2.8 | **Web-UI: Typing-Indikator** | `aria/templates/chat.html` | Während LLM arbeitet: "ARIA denkt nach..." Animation |

**Ergebnis Session 2:** ARIA erinnert sich an Dinge. User sieht welcher Skill aktiv war und wieviel Tokens verbraucht wurden.

---

### Session 3: "Bereit für die Welt" 🚀

**Ziel:** API-Endpoint, Tests, Hardening, Stats-Seite.

| # | Task | Dateien | Akzeptanzkriterien |
|---|---|---|---|
| 3.1 | OpenAI-kompatibler API-Endpoint | `aria/channels/api.py` | `POST /v1/chat/completions` → OpenAI-Format Response. Optionaler Bearer-Token. Damit funktioniert OpenWebUI-Anbindung |
| 3.2 | **Web-UI: Stats-Seite** | `aria/templates/stats.html` | Token-Verbrauch letzte 7 Tage, Requests pro Intent, Durchschnitt pro Request |
| 3.3 | Tests: Router | `tests/test_router.py` | Store/Recall/Chat-Fallback, Multi-Intent, Edge Cases |
| 3.4 | Tests: Pipeline | `tests/test_pipeline.py` | Reihenfolge bestätigen, Single-LLM-Call, Skill-Fehler → Chat läuft weiter |
| 3.5 | Tests: Memory | `tests/test_memory.py` | user_id Filterung, Store + Recall Happy Path, Qdrant-Down Fallback |
| 3.6 | README finalisieren | `README.md` | Quickstart (3 Schritte), Config-Doku, Screenshots Web-UI |
| 3.7 | Hardening | diverse | Timeouts überall, Input-Sanitierung, Error-Pages im Web-UI statt Stack-Traces |

**Ergebnis Session 3:** ARIA ist produktionsreif für Phase 1. Web-UI, API, Memory, Tests, Doku.

---

## Datei-Scaffold

```
aria/
├── pyproject.toml
├── README.md
├── config/
│   ├── config.yaml
│   └── config.example.yaml
├── prompts/
│   ├── persona.md
│   └── skills/
│       └── memory.md
├── aria/
│   ├── __init__.py
│   ├── main.py                  # FastAPI App + Routes (/, /chat, /health)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Pydantic Settings
│   │   ├── llm_client.py        # LiteLLM Wrapper
│   │   ├── prompt_loader.py     # Prompt-File Cache
│   │   ├── router.py            # Keyword Router
│   │   ├── context.py           # Context Assembler
│   │   ├── token_tracker.py     # JSONL Logger
│   │   └── pipeline.py          # 6-Step Pipeline
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseSkill ABC
│   │   └── memory.py            # Qdrant Memory
│   ├── channels/
│   │   ├── __init__.py
│   │   └── api.py               # OpenAI-kompatibler Endpoint
│   ├── templates/
│   │   ├── base.html            # Layout + Dark Mode
│   │   ├── chat.html            # Chat-Interface
│   │   └── stats.html           # Token-Statistiken
│   └── static/
│       └── style.css            # ~200 Zeilen, Dark Theme
├── data/
│   └── logs/                    # Token JSONL Logs
└── tests/
    ├── test_router.py
    ├── test_pipeline.py
    └── test_memory.py
```

---

## E2E-Referenztest (nach Phase 1)

Alles im Browser:

1. `http://localhost:8800` öffnen → Chat-UI erscheint
2. Tippen: **"Merk dir, dass mein NAS 172.31.10.100 hat."**
   → Antwort: "Gespeichert." · Badge: `[💾 memory_store · 312 tokens]`
3. Tippen: **"Erinnerst du dich an mein NAS?"**
   → Antwort enthält "172.31.10.100" · Badge: `[🧠 memory_recall · 643 tokens]`
4. Stats-Seite öffnen → 2 Requests, Token-Verbrauch sichtbar

Parallel per API testbar:

```bash
curl -X POST http://localhost:8800/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hallo ARIA"}]}'
```

---

## Config-Vorlage (config.yaml)

```yaml
aria:
  host: "0.0.0.0"
  port: 8800
  log_level: "info"

llm:
  model: "ollama_chat/qwen3:8b"
  api_base: "http://localhost:11434"
  temperature: 0.4
  max_tokens: 1024

embeddings:
  model: "nomic-embed-text"
  api_base: "http://localhost:11434"

memory:
  enabled: true
  backend: "qdrant"
  qdrant_url: "http://localhost:6333"
  collection: "aria_memory"
  top_k: 3

channels:
  api:
    enabled: true
    auth_token: ""  # Leer = kein Auth

prompts:
  persona: "prompts/persona.md"
  skills_dir: "prompts/skills/"

token_tracking:
  enabled: true
  log_file: "data/logs/tokens.jsonl"
```

---

## Offene Infos vor dem Start

| Info | Status |
|---|---|
| Mac Ollama IP (qwen3:8b + nomic-embed-text) | 172.31.100.15 ✓ |
| LiteLLM Proxy | 172.31.10.210:4000 ✓ |
| Qdrant IP + Port | Port 6333, **IP?** |
| Wo läuft ARIA? (Docker Host) | **ubnsrv-aiagent?** |

---

## Späterer Produktblock: RAS / WireGuard

- `WireGuard` nicht als normale `Connection` modellieren.
- Stattdessen als eigener Menüpunkt / eigener Produktbereich:
  - `RAS`
  - `Remote Access / Secure Access`

### Zielbild

- ARIA sicher von außen erreichbar machen
- möglichst wenig Einrichtungsaufwand für den User
- keine rohe, verwirrende WireGuard-Oberfläche als erste Version

### MVP-Idee

- Peer-/Client-Verwaltung direkt in ARIA
- Generierung von:
  - Client-Konfig
  - QR-Code für iPhone/iPad
  - kleine Schritt-für-Schritt-Anleitung
- klare Firewall-/Port-Forward-Info:
  - z. B. `UDP 51820 -> ARIA`
- Status-/Health-Anzeige in ARIA

### OPNsense

- nur als Beispiel für typische WireGuard-Komplexität zu verstehen
- kein Pflichtziel für den MVP

---

## Produktlinie ab ALPHA

- ARIA wird zunaechst bewusst als **persoenliches Single-User-System** positioniert
- Personalisierung und Alltagstauglichkeit gehen vor fruehem Multiuser-Ausbau
- `RBAC`, Ownership und Sharing bleiben wichtige spaetere Architekturthemen, aber nicht Kern der fruehen ALPHA

### Frueher nach vorne ziehen

1. Personalisierung / Themes
- Theme-Auswahl in `Settings`
- einige klare Default-Themes
- einfache Dummy-Backgrounds / austauschbare Hintergrundvarianten
- CSS-Variablen statt komplexes Design-System

2. Memory-Export
- persoenliche Memories exportierbar machen
- Zielbild: User kann seine Erinnerungen sichern, mitnehmen und spaeter wieder importieren
- bewusst als persoenliches Feature denken, nicht als Team-/RBAC-Funktion

3. Produktfokus schaerfen
- ARIA als persoenlicher Assistent mit eigenen Memories, eigenen Connections und eigenem Arbeitsraum
- Komplexitaet sichtbar reduzieren, wenn man "einfach mit ARIA arbeiten" will

4. Hilfe-System / Kontext-Hilfe
- kleines Info-Icon an wichtigen UI-Stellen
- kontextbezogene Kurz-Hilfe direkt im jeweiligen Block/Feld/Workflow
- Help-Texte zentral pflegen, damit sie später leicht ersetzt/erweitert werden können
- erster ALPHA-Schritt bewusst klein:
  - statische Kurztexte
  - wichtige Setup-/Connection-/Skill-/Memory-Hinweise
  - mitgeliefertes Hilfe-Dokument als Textgrundlage
- späterer Ausbau:
  - Help-Popover oder Help-Drawer
  - mehr Seiten-/Feld-Kontexte
  - Deep Links in ausführlichere Doku

### Bewusst nach hinten schieben

1. RBAC / Multiuser
- Rollen- und Rechte-Logik
- Ownership / Sharing / Freigaben
- spaetere Mehrbenutzer-Architektur

2. In-App-Update auf Knopfdruck
- vollautomatisches Docker-Update aus dem UI heraus
- wegen Container-/Host-/Portainer-Realitaet deutlich aufwaendiger und fehleranfaelliger

Stattdessen spaeter sinnvoller:
- Version anzeigen
- Hinweis, wenn auf Docker Hub eine neuere Version verfuegbar ist
- Upgrade weiter ueber Host-/Container-Workflow ausfuehren
- Fokus zuerst auf:
  - standalone RAS-Flow in ARIA
  - Export
  - Checkliste
  - klarer Guided Flow

### Architekturhinweis

- so bauen, dass spätere Rechte-/RBAC-Modelle und Multi-User sauber mitziehen können
- RAS ist eher `Secure Access` als klassischer Integrations-Connector

---

## Release ALPHA

Ziel:
- eine stabile, benutzbare Basis mit den wichtigsten Funktionen
- gute Intelligenz und saubere Routing-/Capability-Logik
- ein modularer Core mit vernünftiger Codebasis
- Security von Anfang an mitgedacht
- Distribution über `Docker Hub` und Quellcode über `GitHub`
- echte Update-Kette testen, bevor wir öffentlich breiter gehen

### Produktgrenzen für ALPHA

- `Release ALPHA` ist bewusst **kein Multi-User-System**
- der aktuelle `User-Modus` ist eine reduzierte Arbeitsansicht
- der `User-Modus` soll schon jetzt möglichst nahe an dem liegen, was ein späterer normaler User sieht
- `Admin-Modus AUS` bedeutet:
  - Komplexität ausblenden
  - Systemkonfiguration trennen
  - bewusst in eine einfache Arbeitsansicht wechseln
- Admins sollen den `User-Modus` später auch nutzen können, um die spätere User-Sicht realistisch zu prüfen
- `Skills` im `User-Modus`:
  - nur in sicher reduzierter Form
  - nicht editierbar
  - spätere Freigaben/Ownership nicht in ALPHA vorwegnehmen

### 1. Core-Stabilität und Funktionskern

- freie Prompt-Kanten weiter härten
- Capability-Routing weiter absichern, damit strukturierte Aktionen nicht in generische LLM-Antworten kippen
- Long-Running-Flows sauber führen
  - ehrliche Statusmeldungen
  - keine stillen Hänger
- Preflight-/Runtime-Diagnostik als Release-Gate weiter nutzen
- Qdrant-/Memory-Flow stabil halten
- letzte grobe UI-/Flow-Brüche vor Release entfernen
- Funktion zum Zurücksetzen/Löschen der Statistikdaten einbauen
  - sinnvoll platziert unter `Einstellungen`
  - mit Bestätigungsschutz
  - sauber mehrsprachig
  - so, dass Token-/Kosten-/Request-Statistiken bewusst neu gestartet werden können

### 1b. Hilfe-System für Public ALPHA vorbereiten

- ein mitgeliefertes Hilfe-Dokument für zentrale ARIA-Bereiche anlegen
- technische Grundlage für spätere kontextsensitive UI-Hilfe vorbereiten
- Zielbild:
  - ein kleines Info-Icon neben erklärungsbedürftigen Blöcken/Feldern
  - Klick zeigt kurze, passende Hilfe genau zu diesem Kontext
- wichtige erste Kontexte:
  - First-Run / LLM-Setup
  - Connection-Metadaten
  - RSS-Gruppen / Aliase / Ping-Time
  - Skill Trigger / Step-Reihenfolge
  - Memory Auto-Memory / Forget
  - Statistiken / Kosten / Preflight
- Architekturwunsch:
  - Help-Texte zentral halten
  - später austauschbar und übersetzbar
  - keine hart verstreuten Erklärungstexte in allen Templates

### 2. Architektur und Modularität

- `connection_catalog` weiter als zentrale Quelle nutzen
  - `Config`
  - `Stats`
  - `Toolbox`
  - Chat-Admin
- `capability_catalog` weiter als zentrale Quelle nutzen
  - Badges
  - Detailtexte
  - Executor-Bindings
- Guardrails als generischen Core weiterführen
  - `ssh_command`
  - `http_request`
  - `file_access`
- neue Module so anbinden, dass UI und Runtime möglichst automatisch mitziehen
- alte harte Einzelverdrahtungen weiter reduzieren
- spätere Multi-User-Basis für `Skills` sauber vormerken:
  - Ownership
  - Sichtbarkeit
  - Ausführungsrechte
  - Connection-Scope
  - Guardrail-/Policy-Anbindung

### 3. Security für ALPHA

- sichere Defaults für Distribution
- Guardrail-Bindings auf den relevanten Connection-Typen sauber halten
- Qdrant als Teil der Distribution absichern
  - API-Key verpflichtend dokumentieren
  - keine offene Default-Exponierung
- Secrets sauber über Config/Secure-Store/ENV behandeln
- klare Warnung in Doku:
  - ARIA in ALPHA nicht direkt offen ins Internet hängen
  - VPN/LAN/geschützter Zugriff zuerst

### 4. Pre-Release-Testblock

- manueller Smoke-Test der Kernflächen
  - Chat
  - Connections
  - Memories
  - Security
  - Stats
  - Prompt Studio
  - File Editor
- DE/EN-Sweep der Kernflächen
- Restart-/Recovery-Sweep
- Qdrant-/Memory-Sweep
- Statistik-Reset testen
  - UI
  - Bestätigung
  - Wirkung auf `/stats`
- Connection Save/Test/Delete Sweep
- Chat-Admin-Flow Sweep
- Long-Running-Skill-Sweep
- Docker-/Compose-Smoke-Test erst nach diesem Block

### 5. Docker Packaging

- `docker-compose.yml` für ALPHA sauber halten
  - `aria`
  - `qdrant`
- `.env` / Stack-Variablen sauber dokumentieren
  - besonders `ARIA_QDRANT_API_KEY`
- persistente Volumes klar definieren
- Erststart so bauen, dass möglichst wenig User-Interaktion nötig ist
- Container-Setup in README dokumentieren
- Portainer-Stack-Setup mitdenken

### 6. Release-Kanäle

- GitHub-Repo für ALPHA vorbereiten
  - saubere README
  - Security-Hinweise
  - Betriebsgrenzen klar benennen
- letzten Public-Release-Polish-Block fahren
  - Repo-Inhalt bewusst schneiden
  - `project.docu/` nur selektiv oder gar nicht veroeffentlichen
  - persoenliche/temporäre Dev-Dateien final ausschliessen
- Lizenz und ALPHA-Disclaimer sauber sichtbar machen
- Docker-Hub-Publishing vorbereiten
  - reproduzierbarer Build
  - klare Tags
  - finalen Namespace und finalen Image-Namen festlegen
  - Compose-/Portainer-Beispiele auf den finalen Registry-Namen umstellen
  - echte Image-Tags versionieren, nicht nur TAR-Dateinamen
- Release-Notizen / Changelog-Flow vorbereiten

### 7. Update-Pipe

- lokale Update-Kette bewusst simulieren
  - Dev-Änderung
  - neues Image bauen
  - neues Image ziehen
  - Container ersetzen
- prüfen:
  - Config bleibt gültig
  - Daten bleiben erhalten
  - Qdrant bleibt erreichbar
  - Secrets bleiben intakt
  - keine Breaking Changes in typischen User-Flows
- einfache Release-/Upgrade-Anleitung dokumentieren

### 8. Veröffentlichungsgate

- erst veröffentlichen, wenn:
  - separater Host erfolgreich läuft
  - Update-Pipe real funktioniert
  - README/Doku tragfähig ist
  - Repo privacy-clean ist
  - ALPHA-Grenzen klar benannt sind

### 9. Priorität nach diesem Kapitel

Als Nächstes priorisiert:
1. Core-Härtung abschließen
2. Pre-Release-Testblock vollständig durchziehen
3. Docker-/Compose-ALPHA bauen
4. Update-Kette simulieren
5. erst danach `Docker Hub` + `GitHub` veröffentlichen
