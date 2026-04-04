# ARIA

Lean, modular, self-hosted AI assistant with memory, skills, secure connections, and a browser-first interface.

ARIA is built for people who want:

- a clear local AI assistant instead of platform bloat
- modular connections to real systems
- explicit security and role boundaries
- a GUI-first workflow instead of API-first complexity

It is intentionally **not** meant to become a giant OpenWebUI-style suite.  
ARIA aims to stay small, understandable, and extensible.

Current ALPHA boundary:

- ARIA ALPHA is not yet a full multi-user system
- ARIA should currently be understood primarily as a personal single-user system
- the current user mode is a reduced view for everyday work
- advanced configuration stays behind admin mode
- later ownership / sharing / RBAC for skills and resources will come as a separate architecture step
- ARIA ALPHA is intended for LAN / VPN / homelab usage, not open public internet exposure

## Who This ALPHA Is For

ARIA ALPHA is a good fit for:

- people who want a personal AI workspace for themselves
- self-hosters
- homelab users
- tinkerers who are comfortable with Docker / Portainer
- small private tests with 1-2 trusted users

ARIA ALPHA is currently **not** meant for:

- open internet exposure
- production teams
- full multi-user permission setups
- hands-off enterprise deployment

## Overview

- Product overview: `docs/product/overview.md`
- Feature list: `docs/product/feature-list.md`
- Architecture summary: `docs/product/architecture-summary.md`
- Roadmap snapshot: `docs/product/roadmap.md`
- Copy pack for GitHub / releases / landing pages: `docs/product/copy-pack.md`
- Setup overview: `docs/setup/setup-overview.md`
- Portainer deploy checklist: `docs/setup/portainer-deploy-checklist.md`
- Help system: `docs/help/help-system.md`
- Alpha backlog: `docs/backlog/alpha-backlog.md`
- Main backlog: `docs/backlog/main-backlog.md`
- Versioning / release notes plan: `docs/release/versioning.md`
- GitHub release notes template: `docs/release/github-release-notes-template.md`
- Current status: `project.docu/status-aktuell.md`
- Internal notes index: `project.docu/README.md`
- Changelog: `CHANGELOG.md`

## Current implementation snapshot

- Browser chat UI at `/`
- Deterministic routing plus custom-skill and capability execution
- Qdrant-backed memory with typed collections, weighted recall, and JSON export
- Connection pages for SSH, SFTP, SMB, Discord, RSS, HTTP API, Webhook, SMTP, IMAP, and MQTT
- Custom Skills as JSON manifests with a browser wizard, import/export, and sample skills
- `Statistiken` under `/stats` with health, token, cost, preflight, connection status, activities, and reset
- Read-only `/help` and `/product-info`
- OpenAI-compatible endpoint `POST /v1/chat/completions`
- Config from `config/config.yaml` with `ARIA_*` env overrides
- Prompt loader with mtime cache
- Healthcheck under `/health`

## Quickstart

```bash
cd /path/to/ARIA
pip install -e .
cp config/config.example.yaml config/config.yaml
cp config/secrets.env.example config/secrets.env
./aria.sh start
```

Dann Browser öffnen: `http://localhost:8800`
Stats: `http://localhost:8800/stats`

## App-Steuerung

```bash
cd /path/to/ARIA
./aria.sh start
./aria.sh status
./aria.sh logs
./aria.sh stop
./aria.sh maintenance
```

Optional im Vordergrund starten:

```bash
./aria.sh start --foreground
```

`aria.sh` liest Host und Port aus `config/config.yaml`. Falls noetig, koennen beide Werte per `ARIA_ARIA_HOST` und `ARIA_ARIA_PORT` ueberschrieben werden.

## Git / Container Publish Safety

- `config/config.yaml` ist jetzt eine lokale Laufzeitdatei und bleibt aus Git draussen.
- `config/secrets.env` bleibt ebenfalls lokal und wird nicht committed.
- Im Repo gehoeren nur die Beispiele:
  - `config/config.example.yaml`
  - `config/secrets.env.example`
- Laufzeitdaten bleiben lokal:
  - `data/auth/`
  - `data/logs/`
  - `data/skills/`

Fuer Container/Deployment bedeutet das:

```bash
cp config/config.example.yaml config/config.yaml
cp config/secrets.env.example config/secrets.env
cp .env.example .env
```

Dann echte Werte lokal setzen oder per Umgebung ueberschreiben. Direkte `os.environ`-Zugriffe sind auf das zentrale Config-Modul beschraenkt.

## Dauerbetrieb (Autostart)

ARIA kann sich selbst als User-Cronjob verwalten:

```bash
cd /path/to/ARIA
  ./aria.sh autostart-status
  ./aria.sh autostart-install
  ./aria.sh autostart-remove
```

`autostart-install` legt zwei Eintraege an:

- `@reboot`: startet ARIA nach einem Reboot
- `* * * * *`: prueft jede Minute und startet neu, falls ARIA nicht laeuft
- `17 3 * * *`: fuehrt taegliche Memory-Maintenance (Kontext-Rollup) aus

## Docker / Compose

Es gibt jetzt einen container-faehigen Startpfad:

```bash
cd /path/to/ARIA
cp config/config.example.yaml config/config.yaml
cp config/secrets.env.example config/secrets.env
cp .env.example .env
docker compose up -d --build
```

### Eigene ARIA als Container

Wenn du deine eigene ARIA lokal oder im Homelab betreiben willst, ist das der vorgesehene ALPHA-Weg:

```bash
cd /path/to/ARIA
cp config/config.example.yaml config/config.yaml
cp config/secrets.env.example config/secrets.env
cp .env.example .env
```

Dann in `.env` mindestens setzen:

```dotenv
ARIA_QDRANT_API_KEY=hier-einen-langen-zufaelligen-key-setzen
```

Optional anpassen:

```dotenv
ARIA_HTTP_PORT=8800
```

Danach starten:

```bash
docker compose up -d --build
```

Dann im Browser:

- ARIA: `http://localhost:8800`
- Qdrant: `http://localhost:6333`

Beim ersten Start:

1. ersten Benutzer anlegen
2. dieser erste Benutzer wird automatisch Admin
3. Admin-Modus ist direkt aktiv
4. danach LLMs und weitere Verbindungen konfigurieren

### Friend Tester Quickstart

If you want to hand ARIA to 1-2 friends for early feedback, this is the intended ALPHA path:

1. run ARIA on a separate host via Docker or Portainer
2. keep access inside LAN / VPN
3. let the tester create the first user and configure their own LLM
4. collect feedback on:
   - first-run setup
   - chat quality
   - connections
   - memories
   - rough edges in the UI

Recommended framing for early testers:

- this is an **ALPHA**
- ARIA is already usable
- but rough edges, missing polish, and later architecture steps are still expected

### Portainer Stack

Wenn du ARIA spaeter per Portainer betreiben willst, gibt es jetzt zwei sinnvolle Wege:

1. **Jetzt, vor der oeffentlichen Image-Verteilung**
- Repo auf den Zielhost legen
- mit dem normalen `docker-compose.yml` arbeiten
- oder zuerst lokal ein Image bauen und spaeter auf einen Registry-Pfad umstellen

2. **Sobald das verteilbare Image bereitsteht**
- `docker/portainer-stack.example.yml` als Grundlage nehmen
- dort nur noch den finalen Image-Namen einsetzen
- in Portainer die Stack-Variablen setzen:
  - `ARIA_QDRANT_API_KEY`
  - optional `ARIA_HTTP_PORT`
  - optional `ARIA_LLM_API_BASE`
  - optional `ARIA_EMBEDDINGS_API_BASE`

Wichtig fuer den Portainer-Weg:

- das Beispiel nutzt **named volumes**
- leere `config`-/`prompts`-Volumes werden beim ersten Start automatisch aus den eingebauten Defaults befuellt
- `config.yaml` und `secrets.env` werden dadurch beim ersten Start automatisch angelegt, wenn sie im Volume noch fehlen
- danach bleiben diese Daten im Volume erhalten

Enthalten:

- `Dockerfile`
- `docker-compose.yml`
- `docker/entrypoint.sh`
- `docker/portainer-stack.example.yml`
- `.dockerignore`

Wichtig fuer den Container-Betrieb:

- `config/config.yaml` und `config/secrets.env` werden als lokale Laufzeitdateien erwartet
- `.env` ist die einfachste Stelle fuer den Qdrant-Key und optionale Container-Overrides
- falls `config/config.yaml` im Container fehlt, kopiert der Entry-Point automatisch `config/config.example.yaml`
- `config/secrets.env` wird beim Container-Start gesourced, damit `ARIA_MASTER_KEY` und andere Runtime-Secrets verfuegbar sind
- `ARIA_QDRANT_API_KEY` muss vor dem ersten produktiven Start explizit gesetzt werden
- Volumes:
  - `./config -> /app/config`
  - `./prompts -> /app/prompts`
  - `./data -> /app/data`

Beispiel `docker compose` oder Portainer Stack:

```yaml
environment:
  ARIA_QDRANT_API_KEY: "hier-einen-eigenen-langen-key-setzen"
```

Wichtig:

- denselben Wert fuer `aria` und `qdrant` verwenden
- fuer Portainer den Wert als Stack-Env hinterlegen
- fuer Compose den Wert am besten in `.env` oder im Stack-File setzen
- auf Linux ist `host.docker.internal` im Compose-Setup bereits ueber `host-gateway` verdrahtet

## Public Release Status

ARIA is close to a first public ALPHA release, but the intended path remains:

1. stabilize in `dev`
2. test on a separate host like a real user
3. verify the update pipeline
4. only then publish to GitHub and Docker Hub

That means:

- GitHub / Docker Hub are near, but not the very first milestone
- the current focus stays on:
  - release polish
  - documentation quality
  - clean public packaging
  - honest ALPHA boundaries

Before public GitHub / Docker Hub release, the remaining work is mostly release hygiene and end-to-end verification:

- verify Qdrant size reporting and Memory export on a real upgraded deployment
- run a fresh-host smoke test and an upgrade test with existing volumes
- apply real Git/Docker release tags once the public repo exists
- run a final privacy / artifact sweep

## API (OpenAI-kompatibel)

```bash
curl -X POST http://localhost:8800/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hallo ARIA"}]}'
```

Wenn `channels.api.auth_token` gesetzt ist:

```bash
curl -X POST http://localhost:8800/v1/chat/completions \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hallo ARIA"}]}'
```

## ENV-Overrides (Beispiele)

```bash
export ARIA_LLM_MODEL="ollama_chat/qwen3:8b"
export ARIA_LLM_API_BASE="http://localhost:11434"
export ARIA_LLM_TEMPERATURE="0.4"
export ARIA_LLM_MAX_TOKENS="1024"
export ARIA_ARIA_HOST="0.0.0.0"
export ARIA_ARIA_PORT="8800"
```

Wichtig:

- Secrets nie im Code oder in committed YAML-Dateien hinterlegen.
- Secret-bezogene ENV-Werte werden zentral aufgeloest:
  - `ARIA_MASTER_KEY`
  - `ARIA_AUTH_SIGNING_SECRET`
  - `ARIA_FORGET_SIGNING_SECRET`

## Hinweise

- Qdrant muss erreichbar sein, falls `memory.enabled: true`.
- Bei Memory-Fehlern läuft Chat weiter; Badge zeigt `memory_error`.
- Kontext-Rollup nutzt Prompt-Datei aus `memory.compression_summary_prompt` (Default: `prompts/skills/memory_compress.md`).
- Memory-Hilfe: `docs/help/memory.md`
- Pricing/Kosten-Hilfe: `docs/help/pricing.md`
- Security-Hilfe: `docs/help/security.md`
- Zentrale ARIA-Hilfe: `docs/help/help-system.md`
- Fuer ALPHA-Tests gilt:
  - lieber separater Host oder Container
  - lieber LAN / VPN statt offenem Internet
  - echte User-Daten nicht leichtfertig in Testinstanzen mischen

## Tests

```bash
./.venv/bin/pytest -q
```
