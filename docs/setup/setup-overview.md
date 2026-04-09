# ARIA Setup Overview

Updated: 2026-04-09

This document explains the current ARIA installation and update paths in plain English.

The short version is:

- use `aria-setup` if you want the easiest install and the easiest future updates
- use `docker-compose.public.yml` if you want to manage Docker Compose yourself

## 1. Recommended operating model

For the current alpha stage, ARIA works best like this:

- one Docker host or homelab server
- LAN or VPN access
- persistent storage for config, prompts, data, and Qdrant
- SearXNG included as a separate in-stack search service
- no direct public internet exposure without an additional protection layer

ARIA is still an alpha product. It is best treated as:

- a personal AI workspace
- a trusted internal system
- a self-hosted assistant for one person or a very small trusted setup

## 2. Installation paths

### Option A: managed install with `aria-setup` (recommended)

This is the easiest and safest Docker path.

What it does:

- asks only for the values it cannot safely guess
- creates one managed install directory
- writes a ready-to-use `docker-compose.yml`
- writes a matching `.env`
- creates visible bind-mounted storage folders
- adds `aria-stack.sh` for routine operations
- adds `aria-updater`, so admins can later start a controlled update from `/updates`

Managed installs also support the same controlled update path from chat for admin users:

- `zeige update status`
- `starte update`
- `bestätige update <token>`

Typical usage:

```bash
curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/aria-setup -o aria-setup
chmod +x aria-setup
sudo ./aria-setup
```

Default result:

- `/opt/aria/aria/docker-compose.yml`
- `/opt/aria/aria/.env`
- `/opt/aria/aria/aria-stack.sh`
- `/opt/aria/aria/storage/`

The managed stack includes:

- `aria`
- `qdrant`
- `searxng`
- `searxng-valkey`
- `aria-updater`

Useful commands afterwards:

```bash
cd /opt/aria/aria
./aria-stack.sh ps
./aria-stack.sh logs
./aria-stack.sh health
./aria-stack.sh update
```

### Option B: manual Docker Compose

Use this path if you want Docker Compose, but you do not want the managed `aria-setup` wrapper.

Use:

- `docker-compose.public.yml`

Do not use for public deployment:

- `docker-compose.yml`

Reason:

- `docker-compose.yml` is the local repo/dev stack
- `docker-compose.public.yml` is the public runtime stack

Example setup:

```bash
mkdir -p /opt/aria-manual
cd /opt/aria-manual
curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docker-compose.public.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/.env.example -o .env
```

Minimum `.env` values:

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

## 3. What ARIA stores persistently

No matter which Docker path you choose, these are the important persistent paths:

- ARIA config
- ARIA prompts
- ARIA runtime data
- Qdrant storage
- SearXNG cache
- Valkey data

Managed installs store them as visible bind mounts under:

- `/opt/aria/<stack-name>/storage/`

Manual Compose stores them through named volumes by default unless you intentionally rewrite the compose file.

Important rule:

- updates should replace containers and images
- updates should not delete or rename your existing persistent storage

## 4. First-run flow

After the stack starts:

1. open ARIA in the browser
2. create the first user
3. that first user becomes admin
4. configure `LLM`
5. configure `Embeddings`
6. open `/stats`
7. verify that the startup preflight is clean
8. run the first chat prompt

## 5. SearXNG and web search

ARIA now expects SearXNG inside the stack.

That means:

- ARIA talks to `http://searxng:8080` internally
- both supported Docker paths already include the SearXNG service
- the official stack files write the SearXNG settings inside the container at startup
- you do not need to create a separate host-side `searxng.settings.yml` for the normal public install paths

Inside ARIA, SearXNG profiles only need search behavior and routing metadata, for example:

- engines
- categories
- language
- safe search
- max results
- tags and aliases for routing

## 6. Backups

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

Use it before larger upgrades or before experimenting with a manual configuration import.

## 7. Update paths

### Managed install update

For a normal release update:

```bash
cd /opt/aria/aria
./aria-stack.sh update
```

For a future release that changes the stack layout itself, for example a new sidecar service:

```bash
aria-setup upgrade --install-dir /opt/aria/aria
```

Managed installs also expose a browser update button on:

- `/updates`

Admin users can also drive the same controlled update flow from chat:

- `zeige update status`
- `starte update`

### Manual Docker Compose update

Before larger upgrades:

1. open ARIA
2. go to `/config/backup`
3. export a fresh config snapshot

For a normal ARIA release update:

```bash
cd /opt/aria-manual
docker compose pull aria
docker compose up -d --no-deps aria
```

If the release notes say the compose layout changed:

```bash
cd /opt/aria-manual
curl -fsSL https://raw.githubusercontent.com/FischermanCH/A.R.I.A./main/docker-compose.public.yml -o docker-compose.yml
docker compose up -d
```

Important:

- use the same compose project again
- keep the same volumes
- do not casually rename the stack between updates
- use the documented host-side `docker compose` commands for manual installs; `/updates` and chat-driven updates are part of the managed path

### Internal local TAR update

The internal local alpha path still exists for private testing.

That path uses:

- `aria-pull`
- `docker/update-local-aria.sh`
- the local helper-enabled stack files

It also supports the `/updates` button when the local stack includes the `aria-updater` helper sidecar.

## 8. Useful chat actions

These shortcuts are useful right after setup:

- `suche im internet nach rabbit r1 neuigkeiten`
- `zeige stats`
- `zeige aktivitäten`
- `zeige update status`
- `exportiere config backup`

The config-backup export includes connection profiles and secure-store connection secrets.

It does not include local SSH key files under `data/ssh_keys`.

## 9. Multi-instance rule

If you run more than one ARIA instance on the same host:

- each instance needs its own ARIA port
- each instance must keep its own volume set or storage directory
- public samples intentionally do not publish Qdrant host ports by default
- public samples intentionally avoid fixed `container_name` values

That makes side-by-side stacks much safer.

## 10. Which path should most people choose?

Use:

- `aria-setup`

Use manual Compose only if you explicitly want to manage the files yourself.
