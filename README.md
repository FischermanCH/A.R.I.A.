<p align="center">
  <img src="aria/static/logo-aria-v01.png" alt="ARIA logo" width="180">
</p>

# ARIA

Lean, modular, self-hosted AI assistant with memory, skills, secure connections, and a browser-first UI.

**GitHub:** [FischermanCH/A.R.I.A.](https://github.com/FischermanCH/A.R.I.A.)  
**Docker Hub:** [fischermanch/aria](https://hub.docker.com/r/fischermanch/aria)  
**Wiki:** [GitHub Wiki](https://github.com/FischermanCH/A.R.I.A./wiki)  
**Product Homepage:** [Fischerman.ch]([https://github.com/FischermanCH/A.R.I.A./wiki](https://fischerman.ch/projects/a-r-i-a-adaptive-reasoning-intelligence-agent/)

**Languages:** [English](#english) · [Deutsch](#deutsch)


---
## Screenshots

<table>
  <tr>
    <td align="center" width="33%">
      <a href="https://github.com/user-attachments/assets/bca9df58-f65e-4fba-a42b-00d8d2f87223">
        <img src="https://github.com/user-attachments/assets/bca9df58-f65e-4fba-a42b-00d8d2f87223" alt="ARIA chat running a Linux update skill" height="220">
      </a>
      <br>
      <sub><strong>Chat + Skills:</strong> ARIA running a Linux server update workflow.</sub>
    </td>
    <td align="center" width="33%">
      <a href="https://github.com/user-attachments/assets/1810671e-5452-4255-8165-f1f2f10072e2">
        <img src="https://github.com/user-attachments/assets/1810671e-5452-4255-8165-f1f2f10072e2" alt="ARIA memory map" height="220">
      </a>
      <br>
      <sub><strong>Memory Map:</strong> visual view into ARIA's stored memory structure.</sub>
    </td>
    <td align="center" width="33%">
      <a href="https://github.com/user-attachments/assets/2ed2281e-6fff-448c-af94-2e6262b26e84">
        <img src="https://github.com/user-attachments/assets/2ed2281e-6fff-448c-af94-2e6262b26e84" alt="ARIA theme variant one" height="220">
      </a>
      <br>
      <sub><strong>Themes:</strong> different looks and color directions are built in.</sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="33%">
      <a href="https://github.com/user-attachments/assets/804e6584-2447-4901-a006-9543e8c0c275">
        <img src="https://github.com/user-attachments/assets/804e6584-2447-4901-a006-9543e8c0c275" alt="ARIA configuration screen" height="220">
      </a>
      <br>
      <sub><strong>Configuration:</strong> browser-based setup for system and provider settings.</sub>
    </td>
    <td align="center" width="33%">
      <a href="https://github.com/user-attachments/assets/e583d84d-52a8-4a60-9279-a6b214bb5732">
        <img src="https://github.com/user-attachments/assets/e583d84d-52a8-4a60-9279-a6b214bb5732" alt="ARIA skill configuration screen" height="220">
      </a>
      <br>
      <sub><strong>Skill Builder:</strong> UI for editing and wiring custom skills.</sub>
    </td>
    <td align="center" width="33%">
      <a href="https://github.com/user-attachments/assets/434a28c2-f7bd-447b-8218-d848a1d1f0e9">
        <img src="https://github.com/user-attachments/assets/434a28c2-f7bd-447b-8218-d848a1d1f0e9" alt="ARIA statistics page" height="220">
      </a>
      <br>
      <sub><strong>Statistics:</strong> runtime health, usage, costs, and system status.</sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="33%">
      <a href="https://github.com/user-attachments/assets/eae1715d-4272-46e3-bf67-cddc37890b32">
        <img src="https://github.com/user-attachments/assets/eae1715d-4272-46e3-bf67-cddc37890b32" alt="ARIA theme variant two" height="220">
      </a>
      <br>
      <sub><strong>Theme Variant:</strong> another UI style from the same system.</sub>
    </td>
    <td align="center" width="33%">
      &nbsp;
    </td>
    <td align="center" width="33%">
      &nbsp;
    </td>
  </tr>
</table>


# English
## What ARIA is

ARIA is a small, modular AI assistant for people who want control instead of platform sprawl.

It combines:

- a browser-first chat UI
- structured memory with Qdrant
- configurable skills and automations
- modular connections to real systems
- explicit security and role boundaries

ARIA is intentionally **not** trying to become a giant OpenWebUI-style suite.  
The goal is to stay lean, understandable, and extensible.

## Built With Human + AI Collaboration

ARIA was not created by a human alone, and not by AI alone.

It was built through a real long-form collaboration between **Fischerman** and **AI coding/research systems**:

- **Codex** played a major role in implementation, debugging, refactoring, release preparation, and day-to-day product iteration
- the broader **masterplan and architectural direction** were shaped in collaboration between **Fischerman** and **Claude.ai**

That means ARIA is itself a product of the workflow it represents:
human direction, AI acceleration, shared iteration, and a lot of stubborn refinement.

## Current ALPHA boundary

- ARIA ALPHA is currently **primarily a personal single-user system**
- User mode is a reduced everyday working view
- Advanced configuration stays behind Admin mode
- Full ownership / sharing / RBAC for skills, connections, and memories is planned as a later architecture step
- ARIA ALPHA is intended for **LAN / VPN / homelab**, not direct public internet exposure

## Who this ALPHA is for

Good fit:

- people who want a personal AI workspace
- self-hosters and homelab users
- tinkerers comfortable with Docker and self-hosting basics
- small private tests with 1-2 trusted users

Not the current target:

- open internet exposure
- production teams
- full multi-user permission setups
- hands-off enterprise deployment

## Current implementation snapshot

- Chat UI at `/`
- Deterministic routing plus custom-skill and capability execution
- Qdrant-backed memory with typed collections, weighted recall, and JSON export
- RAG v1 in `Memory` with document upload for `txt`, `md`, and `pdf` with embedded text
- Document-RAG uses an internal guide index with summary + keywords so ARIA can route chat recall to relevant uploaded documents
- Chat details now show document recall sources with file name, collection, and chunk reference
- pre-alpha web search via self-hosted `SearXNG`, with a fixed in-stack target URL, slim search profiles, and source lines in chat details
- Chat toolbox includes direct phrases for web search, stats, activities, controlled updates, and config-backup helpers; the same actions can now also be triggered from chat instead of only through the respective pages
- Embedding changes are now guarded by explicit confirmation plus Memory fingerprinting, so existing Memory/RAG is less likely to be mixed with a different embedding generation by accident
- `Memory Map` groups imported documents by name and can remove a whole document from Qdrant in one step
- Connection pages for SSH, SFTP, SMB, Discord, RSS, HTTP API, SearXNG, Webhook, SMTP, IMAP, and MQTT
- Custom Skills as JSON manifests with a browser wizard, import/export, and bundled sample skills
- `Statistics` under `/stats` with health, token/cost stats, connection status, activities, and reset
- Read-only `/help` and `/product-info`
- OpenAI-compatible endpoint `POST /v1/chat/completions`
- Config via `config/config.yaml` plus `ARIA_*` environment overrides
- `/health` endpoint

## Architecture at a glance

### Layered architecture

![ARIA layered architecture](docs/product/aria_schichten_architektur.svg)

### Intelligent routing

![ARIA intelligent routing](docs/product/aria_intelligentes_routing.svg)

### Modularity and persistence

![ARIA modularity and persistence](docs/product/aria_modularitaet_persistenz.svg)

## Documentation

- GitHub Wiki: `https://github.com/FischermanCH/A.R.I.A./wiki`
- Product overview: `docs/product/overview.md`
- Feature list: `docs/product/feature-list.md`
- Architecture summary: `docs/product/architecture-summary.md`
- Roadmap: `docs/product/roadmap.md`
- Contributing guide: `CONTRIBUTING.md`
- Setup overview: `docs/setup/setup-overview.md`
- Alpha help (DE): `docs/help/alpha-help-system.de.md`
- Alpha help (EN): `docs/help/alpha-help-system.en.md`
- Memory help: `docs/help/memory.md`
- Pricing help: `docs/help/pricing.md`
- Security help: `docs/help/security.md`
- Changelog: `CHANGELOG.md`

## Docker Install and Update Paths

ARIA supports two main Docker paths:

1. `aria-setup`  
   Best choice for most people. One command, one managed directory, predictable updates later.
2. `docker-compose.public.yml`  
   Good if you want a manual Docker Compose setup but still want the official public sample.

The recommended path is still:

- `aria-setup`

### Option 1: `aria-setup` (recommended)

`aria-setup` is the easiest controlled install path.

It:

- asks only for the few values it cannot safely guess
- creates one managed install directory
- writes a ready-to-use `docker-compose.yml`
- writes a matching `.env`
- creates persistent bind-mounted storage folders
- adds `aria-stack.sh` for status, logs, updates, and health checks

Managed installs also include the internal `aria-updater` helper. That means admins can later start a controlled update directly from `/updates` in the browser.

Admins can also use the same helper path from chat, for example:

- `zeige update status`
- `starte update`
- `bestätige update <token>`

Install:

```bash
curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/aria-setup -o aria-setup
chmod +x aria-setup
sudo ./aria-setup
```

If you already know the target values and want a fully unattended run:

```bash
sudo ./aria-setup \
  --stack-name aria-main \
  --install-dir /opt/aria/aria-main \
  --http-port 8800 \
  --public-url http://localhost:8800 \
  --non-interactive
```

Default result:

- `/opt/aria/aria/docker-compose.yml`
- `/opt/aria/aria/.env`
- `/opt/aria/aria/aria-stack.sh`
- `/opt/aria/aria/storage/`

Useful commands afterwards:

```bash
cd /opt/aria/aria
./aria-stack.sh ps
./aria-stack.sh logs
./aria-stack.sh health
./aria-stack.sh update
```

Managed update rules:

- normal image update:
  - `./aria-stack.sh update`
- stack layout change, for example a new sidecar service:
  - `aria-setup upgrade --install-dir /opt/aria/aria`
- admin-triggered browser update:
  - `/updates`

If a managed ARIA install already exists, `aria-setup` detects that and upgrades it instead of creating an accidental second install.

### Option 2: manual Docker Compose

Use this when you want the public sample but prefer to manage the compose directory yourself.

Use:

- `docker-compose.public.yml`

Do not use:

- `docker-compose.yml`

Reason:

- `docker-compose.yml` is the local repo/dev stack
- `docker-compose.public.yml` is the public runtime stack

Example manual setup:

```bash
mkdir -p /opt/aria-manual
cd /opt/aria-manual
curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docker-compose.public.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/.env.example -o .env
```

Minimal `.env`:

```dotenv
ARIA_QDRANT_API_KEY=replace-with-a-long-random-key
SEARXNG_SECRET=replace-with-a-long-random-key
ARIA_HTTP_PORT=8800
ARIA_PUBLIC_URL=http://localhost:8800
```

Start:

```bash
docker compose up -d
```

This starts:

- `aria`
- `qdrant`
- `searxng`
- `searxng-valkey`

Manual Compose update rules:

- before larger upgrades, export a config snapshot from `/config/backup`
- normal ARIA release update:

  ```bash
  docker compose pull aria
  docker compose up -d --no-deps aria
  ```

- if the release notes say the compose file changed:

  ```bash
  curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docker-compose.public.yml -o docker-compose.yml
  docker compose up -d
  ```

Important:

- keep the same compose project
- keep the same volumes
- do not rename the stack casually between updates
- the browser `/updates` button and chat-driven update flow are designed for managed installs; for a plain manual Compose install, use the documented host-side `docker compose` commands

### Which update path should you use?

- managed install from `aria-setup`:
  - `./aria-stack.sh update`
  - or `/updates` in the UI
  - or a controlled update directly from chat for admin users
- manual `docker-compose.public.yml`:
  - `docker compose pull aria`
  - `docker compose up -d --no-deps aria`
  - replace the compose file only when the release notes say the stack layout changed

### Helpful chat shortcuts

Recent admin and operator shortcuts that now work directly from chat:

- `suche im internet nach <topic>`
- `zeige stats`
- `zeige aktivitäten`
- `zeige update status`
- `starte update`
- `exportiere config backup`

The backup export includes:

- connection profiles from `config.yaml`
- connection secrets from the secure store

It does not include local SSH key files under `data/ssh_keys`.

### Internal local TAR builds

Internal local TAR builds still exist for faster private testing.

That path uses:

- `aria-pull`
- `docker/update-local-aria.sh`
- the local helper-enabled stack files

It is useful for internal testing, but it is not the preferred public install path.

If you want the cleanest public setup and the easiest future updates, use `aria-setup`.

## Quickstart

```bash
cd /path/to/ARIA
pip install -e .
cp config/config.example.yaml config/config.yaml
cp config/secrets.env.example config/secrets.env
./aria.sh start
```

Then open:

- ARIA: `http://localhost:8800`
- Stats: `http://localhost:8800/stats`

## App control

```bash
cd /path/to/ARIA
./aria.sh start
./aria.sh status
./aria.sh logs
./aria.sh stop
./aria.sh maintenance
```

Foreground mode:

```bash
./aria.sh start --foreground
```

`aria.sh` reads host and port from `config/config.yaml`. If needed, override them with `ARIA_ARIA_HOST` and `ARIA_ARIA_PORT`.

## Git / container publish safety

Local runtime config and secrets should stay out of Git.

Ignored runtime files/directories include:

- `config/config.yaml`
- `config/secrets.env`
- `data/auth/`
- `data/logs/`
- `data/skills/`
- `data/chat_history/`
- `data/qdrant/`
- `data/runtime/`
- `data/ssh_keys/`

Tracked examples/templates:

- `config/config.example.yaml`
- `config/secrets.env.example`
- `.env.example`

For a new local/container setup:

```bash
cp config/config.example.yaml config/config.yaml
cp config/secrets.env.example config/secrets.env
cp .env.example .env
```

## Autostart

ARIA can manage its own user-level cron autostart:

```bash
cd /path/to/ARIA
./aria.sh autostart-status
./aria.sh autostart-install
./aria.sh autostart-remove
```

`autostart-install` creates:

- `@reboot` startup
- a one-minute watchdog restart check
- daily memory maintenance at `03:17`

## Docker / Compose

```bash
cd /path/to/ARIA
cp .env.example .env
```

For the public/registry path, use `docker-compose.public.yml`.

- `docker-compose.yml` is the repo-local build/dev stack
- `docker-compose.public.yml` is the public quick-start stack
- the public stack already contains:
  - `aria`
  - `qdrant`
  - `searxng`
  - `searxng-valkey`

Set at least this in `.env`:

```dotenv
ARIA_QDRANT_API_KEY=replace-with-a-long-random-key
SEARXNG_SECRET=replace-with-a-long-random-key
```

Optional:

```dotenv
ARIA_HTTP_PORT=8800
ARIA_PUBLIC_URL=http://localhost:8800
```

One simple manual setup path:

```bash
mkdir -p /opt/aria-manual
cd /opt/aria-manual
curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docker-compose.public.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/.env.example -o .env
```

Start:

```bash
docker compose up -d
```

Open:

- ARIA: `http://localhost:8800`
- SearXNG is internal in the stack and is used from ARIA via `http://searxng:8080`
- Qdrant is internal in the stack by default and is not published to a host port in the public sample

First start flow:

1. create the first user
2. that first user becomes Admin automatically
3. Admin mode is active
4. configure LLMs, embeddings, connections, and skills

Update:

```bash
docker compose pull aria
docker compose up -d --no-deps aria
```

Before larger upgrades, create a config snapshot in ARIA under:

- `/config/backup`

If a future release changes the compose layout itself, download the latest `docker-compose.public.yml` again and then run:

```bash
docker compose up -d
```

## Friend tester quickstart

If you want 1-2 trusted people to test ARIA:

1. run ARIA on a separate host via Docker
2. keep access inside LAN / VPN
3. let the tester create the first user and configure their own LLM
4. collect feedback on first-run setup, chat quality, connections, memories, and rough UI edges

Please frame it clearly as an **ALPHA**.

## OpenAI-compatible API

```bash
curl -X POST http://localhost:8800/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello ARIA"}]}'
```

If `channels.api.auth_token` is configured:

```bash
curl -X POST http://localhost:8800/v1/chat/completions \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello ARIA"}]}'
```

## Environment override examples

```bash
export ARIA_LLM_MODEL="ollama_chat/qwen3:8b"
export ARIA_LLM_API_BASE="http://localhost:11434"
export ARIA_LLM_TEMPERATURE="0.4"
export ARIA_LLM_MAX_TOKENS="4096"
export ARIA_ARIA_HOST="0.0.0.0"
export ARIA_ARIA_PORT="8800"
```

Secret-related environment variables are resolved centrally:

- `ARIA_MASTER_KEY`
- `ARIA_AUTH_SIGNING_SECRET`
- `ARIA_FORGET_SIGNING_SECRET`

Never commit real secrets into code or YAML.

## Operational notes

- Qdrant must be reachable if `memory.enabled: true`
- if Memory fails, chat should still continue and message details show `memory_error`
- context rollup uses `memory.compression_summary_prompt` (default: `prompts/skills/memory_compress.md`)
- for ALPHA testing, prefer a separate host/container, LAN/VPN access, and avoid mixing highly sensitive real user data into throwaway test instances

## Tests

```bash
./.venv/bin/pytest -q
```

## Public release status

ARIA is close to a first public ALPHA release. The remaining work is mostly release hygiene and end-to-end verification.

## One-line summary

**ARIA is a lean, modular, self-hosted AI assistant with memory, skills, secure connections, and a browser-first interface built for real control instead of platform bloat.**

---

# Deutsch

## Was ARIA ist

ARIA ist ein kleiner, modularer, selbst gehosteter AI-Assistent für Menschen, die Kontrolle statt Plattform-Bloat wollen.

ARIA verbindet:

- eine browser-first Chat-UI
- strukturiertes Memory mit Qdrant
- konfigurierbare Skills und Automationen
- modulare Connections zu echten Systemen
- klare Security- und Rollen-Grenzen

ARIA soll bewusst **keine riesige OpenWebUI-artige Alles-in-einem-Suite** werden.  
Das Ziel ist, klein, verständlich und erweiterbar zu bleiben.

## Entstanden Aus Mensch + KI Zusammenarbeit

ARIA wurde weder allein von einem Menschen noch allein von einer KI gebaut.

Das Projekt ist aus einer echten, langen Zusammenarbeit zwischen **Fischerman** und **KI-gestützten Entwicklungs- und Research-Systemen** entstanden:

- **Codex** war maßgeblich an Implementierung, Debugging, Refactoring, Release-Vorbereitung und der täglichen Produktentwicklung beteiligt
- der größere **Masterplan und die architektonische Leitlinie** entstanden in Zusammenarbeit zwischen **Fischerman** und **Claude.ai**

ARIA ist damit selbst ein Ergebnis genau der Arbeitsweise, die es unterstützen soll:
menschliche Richtung, KI als Beschleuniger, gemeinsame Iteration und sehr viel hartnäckige Feinarbeit.

## Aktuelle ALPHA-Grenze

- ARIA ALPHA ist aktuell **primär ein persönliches Single-User-System**
- der User-Modus ist eine reduzierte Arbeitsansicht für den Alltag
- erweiterte Konfiguration bleibt hinter dem Admin-Modus
- Ownership / Sharing / RBAC für Skills, Connections und Memories ist als späterer Architektur-Schritt geplant
- ARIA ALPHA ist für **LAN / VPN / Homelab** gedacht, nicht für direkte offene Internet-Exponierung

## Für wen diese ALPHA gedacht ist

Gut geeignet für:

- Menschen, die einen eigenen AI-Workspace wollen
- Self-Hoster und Homelab-User
- Bastler, die mit Docker und Self-Hosting-Grundlagen umgehen können
- kleine private Tests mit 1-2 vertrauenswürdigen Personen

Aktuell **nicht** gedacht für:

- offene Internet-Exponierung
- produktive Teams
- vollständige Multi-User-Berechtigungsmodelle
- hands-off Enterprise-Deployment

## Aktueller Implementierungsstand

- Chat-UI unter `/`
- deterministisches Routing plus Custom-Skill- und Capability-Ausführung
- Qdrant-Memory mit typisierten Collections, gewichtetem Recall und JSON-Export
- Connection-Seiten für SSH, SFTP, SMB, Discord, RSS, HTTP API, Webhook, SMTP, IMAP und MQTT
- Custom Skills als JSON-Manifeste mit Wizard, Import/Export und mitgelieferten Sample-Skills
- `Statistiken` unter `/stats` mit Health, Token-/Kosten-Stats, Connection-Status, Aktivitäten und Reset
- Read-only `/help` und `/product-info`
- CLI-Schnellcheck via `aria --version` und `aria version-check`
- OpenAI-kompatibler Endpoint `POST /v1/chat/completions`
- Konfiguration über `config/config.yaml` plus `ARIA_*` ENV-Overrides
- `/health` Endpoint

## Architektur auf einen Blick

### Schichtenarchitektur

![ARIA Schichtenarchitektur](docs/product/aria_schichten_architektur.svg)

### Intelligentes Routing

![ARIA Intelligentes Routing](docs/product/aria_intelligentes_routing.svg)

### Modularität und Persistenz

![ARIA Modularität und Persistenz](docs/product/aria_modularitaet_persistenz.svg)

## Dokumentation

- Produktüberblick: `docs/product/overview.md`
- Feature-Liste: `docs/product/feature-list.md`
- Architektur: `docs/product/architecture-summary.md`
- Roadmap: `docs/product/roadmap.md`
- Setup-Überblick: `docs/setup/setup-overview.md`
- Alpha-Hilfe DE: `docs/help/alpha-help-system.de.md`
- Alpha-Hilfe EN: `docs/help/alpha-help-system.en.md`
- Memory-Hilfe: `docs/help/memory.md`
- Pricing-Hilfe: `docs/help/pricing.md`
- Security-Hilfe: `docs/help/security.md`
- Changelog: `CHANGELOG.md`

## Quickstart

```bash
cd /path/to/ARIA
pip install -e .
cp config/config.example.yaml config/config.yaml
cp config/secrets.env.example config/secrets.env
./aria.sh start
```

Danach öffnen:

- ARIA: `http://localhost:8800`
- Statistiken: `http://localhost:8800/stats`

## App-Steuerung

```bash
cd /path/to/ARIA
./aria.sh start
./aria.sh status
./aria.sh logs
./aria.sh stop
./aria.sh maintenance
```

Im Vordergrund starten:

```bash
./aria.sh start --foreground
```

`aria.sh` liest Host und Port aus `config/config.yaml`. Falls nötig, kannst du beides mit `ARIA_ARIA_HOST` und `ARIA_ARIA_PORT` überschreiben.

## Git-/Container-Publish-Sicherheit

Lokale Runtime-Config und Secrets sollen nicht in Git landen.

Ignorierte Runtime-Dateien/-Ordner:

- `config/config.yaml`
- `config/secrets.env`
- `data/auth/`
- `data/logs/`
- `data/skills/`
- `data/chat_history/`
- `data/qdrant/`
- `data/runtime/`
- `data/ssh_keys/`

Getrackte Beispiele/Templates:

- `config/config.example.yaml`
- `config/secrets.env.example`
- `.env.example`

Für ein neues lokales/containerisiertes Setup:

```bash
cp config/config.example.yaml config/config.yaml
cp config/secrets.env.example config/secrets.env
cp .env.example .env
```

## Autostart

ARIA kann seinen eigenen User-Cron-Autostart verwalten:

```bash
cd /path/to/ARIA
./aria.sh autostart-status
./aria.sh autostart-install
./aria.sh autostart-remove
```

`autostart-install` legt an:

- Start bei Reboot über `@reboot`
- einen Watchdog-Check jede Minute
- tägliche Memory-Maintenance um `03:17`

## Docker / Compose

```bash
cd /path/to/ARIA
cp .env.example .env
```

Für den Public-/Registry-Weg nutzt du `docker-compose.public.yml`.

- `docker-compose.yml` ist der lokale Repo-/Build-Stack
- `docker-compose.public.yml` ist der Public-Quickstart-Stack
- im Public-Stack sind bereits enthalten:
  - `aria`
  - `qdrant`
  - `searxng`
  - `searxng-valkey`

In `.env` mindestens setzen:

```dotenv
ARIA_QDRANT_API_KEY=hier-einen-langen-zufaelligen-key-setzen
SEARXNG_SECRET=hier-einen-langen-zufaelligen-searxng-key-setzen
```

Optional:

```dotenv
ARIA_HTTP_PORT=8800
ARIA_PUBLIC_URL=http://localhost:8800
```

Ein einfacher manueller Setup-Weg:

```bash
mkdir -p /opt/aria-manual
cd /opt/aria-manual
curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docker-compose.public.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/.env.example -o .env
```

Starten:

```bash
docker compose up -d
```

Im Browser öffnen:

- ARIA: `http://localhost:8800`
- SearXNG läuft intern im Stack und wird in ARIA über `http://searxng:8080` genutzt
- Qdrant bleibt im Public-Sample standardmäßig intern und wird nicht auf einen Host-Port veröffentlicht

First-Run-Flow:

1. ersten Benutzer anlegen
2. dieser erste Benutzer wird automatisch Admin
3. Admin-Modus ist aktiv
4. danach LLMs, Embeddings, Connections und Skills konfigurieren

Update:

```bash
docker compose pull aria
docker compose up -d --no-deps aria
```

Vor groesseren Upgrades zuerst in ARIA unter `/config/backup` einen Konfig-Snapshot ziehen.

Wenn ein spaeteres Release das Compose-Layout selbst aendert, die aktuelle `docker-compose.public.yml` erneut herunterladen und danach ausfuehren:

```bash
docker compose up -d
```

## Friend-Tester-Quickstart

Wenn du ARIA an 1-2 vertraute Tester geben willst:

1. ARIA auf einem separaten Host über Docker betreiben
2. Zugriff auf LAN / VPN beschränken
3. Tester den ersten User selbst anlegen und das eigene LLM konfigurieren lassen
4. Feedback zu First-Run, Chatqualität, Connections, Memories und UI-Reibung sammeln

Bitte klar als **ALPHA** framen.

## OpenAI-kompatible API

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

## ENV-Override-Beispiele

```bash
export ARIA_LLM_MODEL="ollama_chat/qwen3:8b"
export ARIA_LLM_API_BASE="http://localhost:11434"
export ARIA_LLM_TEMPERATURE="0.4"
export ARIA_LLM_MAX_TOKENS="4096"
export ARIA_ARIA_HOST="0.0.0.0"
export ARIA_ARIA_PORT="8800"
```

Secret-ENV-Variablen werden zentral aufgelöst:

- `ARIA_MASTER_KEY`
- `ARIA_AUTH_SIGNING_SECRET`
- `ARIA_FORGET_SIGNING_SECRET`

Echte Secrets bitte nie in Code oder YAML committen.

## Betriebshinweise

- Qdrant muss erreichbar sein, wenn `memory.enabled: true`
- bei Memory-Fehlern läuft der Chat weiter, Message-Details zeigen dann `memory_error`
- Kontext-Rollup nutzt `memory.compression_summary_prompt` (Default: `prompts/skills/memory_compress.md`)
- für ALPHA-Tests besser separater Host/Container, LAN/VPN-Zugriff und keine hochsensiblen Echtdaten in Wegwerf-Testinstanzen

## Tests

```bash
./.venv/bin/pytest -q
```

## Public-Release-Status

ARIA ist nah an einem ersten Public-ALPHA-Release. Der Rest ist vor allem Release-Hygiene und End-to-End-Verifikation.

## Ein-Satz-Zusammenfassung

**ARIA ist ein schlanker, modularer, selbst gehosteter AI-Assistent mit Memory, Skills, sicheren Connections und browser-first UI für echte Kontrolle statt Plattform-Bloat.**
