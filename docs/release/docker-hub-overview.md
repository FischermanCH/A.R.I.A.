# ARIA on Docker

ARIA is a lean, modular, self-hosted AI assistant with memory, skills, secure connections, and a browser-first UI.

This Docker page is intentionally simple:

- one recommended install path first
- one fully manual Docker Compose path
- clear update rules for both

Repository and full documentation:

- GitHub: `https://github.com/FischermanCH/A.R.I.A.`
- Wiki: `https://github.com/FischermanCH/A.R.I.A./wiki`
- Setup docs: `https://github.com/FischermanCH/A.R.I.A./tree/main/docs/setup`
- Changelog: `https://github.com/FischermanCH/A.R.I.A./blob/main/CHANGELOG.md`
- Product Homepage: `https://fischerman.ch/projects/a-r-i-a-adaptive-reasoning-intelligence-agent/`

## Current alpha highlights

Current public alpha release:

- `0.1.0-alpha167`

- `Notes / Notizen` as a real Markdown-first product path with board view, folders, chat/toolbox entry points, and Qdrant-backed semantic recall
- `Watched Websites / Beobachtete Webseiten` as a new connection type for sources without RSS, including automatic metadata and grouping
- `Google Calendar` as the first personal end-user integration with guided setup and read-only calendar queries
- a more unified routing/planner/guardrail path between live chat and the routing workbench
- calmer domain hubs for `Memories`, `Connections`, and `Skills`, plus broader UI/doc cleanup around the newer product surfaces
- controlled restart actions for `qdrant` and `searxng` from `/config/operations`

## What you need

- Docker
- one long random key for Qdrant
- one long random key for SearXNG

Generate suitable values on Unix:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

## Recommended path: `aria-setup`

If you want the easiest install and the easiest future updates, use:

- `aria-setup`

It:

- asks only for the values it cannot safely guess
- creates one managed ARIA install directory
- writes a ready-to-run `docker-compose.yml`
- writes a matching `.env`
- creates visible persistent storage directories
- adds `aria-stack.sh` for status, logs, health, and updates
- includes `aria-updater`, so admin users can later start a controlled update from `/updates`

Managed installs also support the same controlled update flow from chat for admin users:

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

By default this creates:

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

- normal image refresh:
  - `./aria-stack.sh update`
- stack layout change, for example a new sidecar service:
  - `aria-setup upgrade --install-dir /opt/aria/aria`
- admin-triggered browser update:
  - `/updates`

The same managed update helper can also be used from chat by admin users.

Before larger upgrades, create a configuration snapshot in ARIA under:

- `/config/backup`

## Manual Docker Compose

Use this if you want to manage Compose yourself.

Use:

- `docker-compose.public.yml`

Do not use:

- `docker-compose.yml`

Reason:

- `docker-compose.yml` is the local repo/dev stack
- `docker-compose.public.yml` is the public runtime stack

## Manual Compose setup in 4 steps

### 1. Create a directory

```bash
mkdir -p /opt/aria-manual
cd /opt/aria-manual
```

### 2. Download the official files

```bash
curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docker-compose.public.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/.env.example -o .env
```

### 3. Edit `.env`

Minimum values:

```dotenv
ARIA_QDRANT_API_KEY=replace-with-a-long-random-key
SEARXNG_SECRET=replace-with-a-long-random-key
ARIA_HTTP_PORT=8800
ARIA_PUBLIC_URL=http://localhost:8800
```

Optional LLM / embedding environment overrides should usually stay empty when you manage saved provider profiles inside ARIA. Only set them if you deliberately want Docker to force the live runtime values.

### 4. Start the stack

```bash
docker compose up -d
```

This starts:

- `aria`
- `qdrant`
- `searxng`
- `searxng-valkey`

Qdrant stays internal by default and is not published on host ports in the public sample.

Copy/paste-ready `docker-compose.public.yml`:

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    restart: unless-stopped
    environment:
      QDRANT__SERVICE__API_KEY: ${ARIA_QDRANT_API_KEY}
    volumes:
      - qdrant_storage:/qdrant/storage

  searxng-valkey:
    image: valkey/valkey:8-alpine
    restart: unless-stopped
    volumes:
      - searxng_valkey:/data

  searxng:
    image: searxng/searxng:latest
    restart: unless-stopped
    depends_on:
      - searxng-valkey
    environment:
      FORCE_OWNERSHIP: "false"
      SEARXNG_SECRET: ${SEARXNG_SECRET}
      SEARXNG_LIMITER: "false"
      SEARXNG_VALKEY_URL: "valkey://searxng-valkey:6379/0"
    entrypoint:
      - /bin/sh
      - -lc
      - |
        umask 077
        mkdir -p /etc/searxng
        python - <<'PY'
        import json
        import os
        from pathlib import Path

        secret = os.environ.get("SEARXNG_SECRET", "ultrasecretkey")
        valkey_url = os.environ.get("SEARXNG_VALKEY_URL", "valkey://searxng-valkey:6379/0")
        lines = [
            "use_default_settings: true",
            "",
            "general:",
            '  instance_name: "ARIA Search"',
            "",
            "search:",
            "  safe_search: 1",
            '  autocomplete: ""',
            "  formats:",
            "    - html",
            "    - json",
            "",
            "server:",
            f"  secret_key: {json.dumps(secret)}",
            "  limiter: false",
            "  image_proxy: true",
            "",
            "valkey:",
            f"  url: {json.dumps(valkey_url)}",
            "",
        ]
        Path("/etc/searxng/settings.yml").write_text("\\n".join(lines), encoding="utf-8")
        PY
        exec /usr/local/searxng/entrypoint.sh
    volumes:
      - searxng_cache:/var/cache/searxng

  aria:
    image: fischermanch/aria:alpha
    restart: unless-stopped
    depends_on:
      - qdrant
      - searxng
    ports:
      - "${ARIA_HTTP_PORT:-8800}:8800"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      ARIA_ARIA_HOST: "0.0.0.0"
      ARIA_ARIA_PORT: "8800"
      ARIA_PUBLIC_URL: ${ARIA_PUBLIC_URL:-http://localhost:8800}
      ARIA_QDRANT_URL: http://qdrant:6333
      ARIA_QDRANT_API_KEY: ${ARIA_QDRANT_API_KEY}
    volumes:
      - aria_config:/app/config
      - aria_prompts:/app/prompts
      - aria_data:/app/data
      - qdrant_storage:/qdrant/storage:ro

volumes:
  qdrant_storage:
  searxng_cache:
  searxng_valkey:
  aria_config:
  aria_prompts:
  aria_data:
```

## Manual Compose updates

Before larger upgrades, create a configuration snapshot in ARIA under:

- `/config/backup`

For a normal ARIA release update:

```bash
cd /opt/aria-manual
docker compose pull aria
docker compose up -d --no-deps aria
```

If the release notes say the stack layout changed:

```bash
cd /opt/aria-manual
curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docker-compose.public.yml -o docker-compose.yml
docker compose up -d
```

Important:

- keep the same compose project
- keep the same volumes
- do not rename the stack casually between updates
- use the documented host-side `docker compose` commands for manual installs; the browser `/updates` button and chat-driven update flow are part of the managed install path
- if a managed install ever reports a mount mismatch after an update, `./aria-stack.sh repair` is the supported recovery path

## Backup and recovery

ARIA includes a browser-based configuration backup under:

- `/config/backup`

That backup contains:

- `config.yaml`
- connection profiles and routing metadata
- secure-store secrets and user accounts
- prompt files
- custom skill manifests
- error interpreter rules

It does not contain:

- memories / Qdrant collections
- chat history
- logs, uploads, or Docker stack values
- local SSH key files under `data/ssh_keys`

Useful chat shortcuts after setup:

- `suche im internet nach rabbit r1 neuigkeiten`
- `zeige stats`
- `zeige aktivitäten`
- `exportiere config backup`

## Which path should you use?

- want the easiest install and easiest updates:
  - `aria-setup`
- want full Docker Compose control:
  - `docker-compose.public.yml`

For new public installs, prefer `aria-setup` unless you explicitly want to manage the compose directory yourself.

## Screenshots

<p>
  <a href="https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docs/assets/screenshots/02-aria-main-chat.png"><img src="https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docs/assets/screenshots/02-aria-main-chat.png" alt="ARIA main chat" width="220"></a>
  <a href="https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docs/assets/screenshots/02-aria-main-chat-toolbox.png"><img src="https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docs/assets/screenshots/02-aria-main-chat-toolbox.png" alt="ARIA toolbox in chat" width="220"></a>
  <a href="https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docs/assets/screenshots/03-aria-memories-map.png"><img src="https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docs/assets/screenshots/03-aria-memories-map.png" alt="ARIA memory map" width="220"></a>
</p>

<p>
  <a href="https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docs/assets/screenshots/04-aria-skills.png"><img src="https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docs/assets/screenshots/04-aria-skills.png" alt="ARIA skills overview" width="220"></a>
  <a href="https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docs/assets/screenshots/05-aria-stats.png"><img src="https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docs/assets/screenshots/05-aria-stats.png" alt="ARIA statistics page" width="220"></a>
  <a href="https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docs/assets/screenshots/06-aria-settings-workbench.png"><img src="https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docs/assets/screenshots/06-aria-settings-workbench.png" alt="ARIA workbench settings" width="220"></a>
</p>
