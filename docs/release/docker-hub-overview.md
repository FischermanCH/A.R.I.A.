# ARIA on Docker

ARIA is a lean, modular, self-hosted AI assistant with memory, skills, secure connections, and a browser-first UI.

This Docker page is intentionally short:

- quick start first
- full docs on GitHub
- practical stack examples for Docker Compose and Portainer

Full repository and documentation:

- GitHub: `https://github.com/FischermanCH/A.R.I.A.`
- Wiki: `https://github.com/FischermanCH/A.R.I.A./wiki`

## Quick Start

What you need:

- Docker
- a Qdrant API key for the bundled Qdrant container
- a SearXNG secret for the bundled web search service

Generate suitable keys on Unix:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Then bring ARIA up with either Docker Compose or Portainer.

Default web UI after startup:

- `http://<host>:8800`

After the first login:

1. create the bootstrap user
2. configure `LLM`
3. configure `Embeddings`
4. open `/stats` and check the preflight
5. run the first prompt

## Docker Compose

Use the included public compose file:

- `docker-compose.public.yml`
- `docker/searxng.settings.yml`

Do not use `docker-compose.yml` for the public quick start.

- `docker-compose.yml` is the local repo/dev build stack
- `docker-compose.public.yml` is the public stack for Docker Hub / registry deploys
- the public stack already contains all four services:
  - `aria`
  - `qdrant`
  - `searxng`
  - `searxng-valkey`

Example `.env` values:

```dotenv
ARIA_QDRANT_API_KEY=replace-with-a-long-random-key
SEARXNG_SECRET=replace-with-a-long-random-key
ARIA_HTTP_PORT=8800
ARIA_PUBLIC_URL=http://localhost:8800
SEARXNG_SETTINGS_FILE=./docker/searxng.settings.yml
```

By default, the public sample does not publish Qdrant on host ports. ARIA talks to Qdrant internally inside the stack, which avoids port conflicts when another ARIA/Qdrant stack already exists on the same host.

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
    volumes:
      - ${SEARXNG_SETTINGS_FILE:-./docker/searxng.settings.yml}:/etc/searxng/settings.yml:ro
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

If you still need a key:

```bash
openssl rand -hex 32
```

Start:

```bash
docker compose -f docker-compose.public.yml up -d
```

This public stack starts:

- `aria`
- `qdrant`
- `searxng`
- `searxng-valkey`

Inside ARIA, web search then talks to the in-stack SearXNG service via:

- `http://searxng:8080`

## Portainer Stack

Use the included Portainer stack file:

- `docker/portainer-stack.public.yml`
- `docker/searxng.settings.yml`

This Portainer stack also already contains:

- `aria`
- `qdrant`
- `searxng`
- `searxng-valkey`

Recommended Portainer environment variables:

```dotenv
ARIA_QDRANT_API_KEY=replace-with-a-long-random-key
ARIA_HTTP_PORT=8800
ARIA_PUBLIC_URL=http://<your-host>:8800
SEARXNG_SECRET=replace-with-a-long-random-key
```

If you already run another ARIA stack on the same host, set a different `ARIA_HTTP_PORT` here. The public Portainer stack intentionally avoids fixed `container_name` values so multiple stacks can coexist cleanly, and it does not publish Qdrant host ports by default.

Copy/paste-ready `docker/portainer-stack.public.yml`:

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    restart: unless-stopped
    environment:
      QDRANT__SERVICE__API_KEY: "${ARIA_QDRANT_API_KEY:-CHANGE-ME-LONG-RANDOM-QDRANT-KEY}"
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
      SEARXNG_SECRET: "${SEARXNG_SECRET:-CHANGE-ME-LONG-RANDOM-SEARXNG-SECRET}"
      SEARXNG_LIMITER: "false"
      SEARXNG_VALKEY_URL: "valkey://searxng-valkey:6379/0"
    volumes:
      - "${SEARXNG_SETTINGS_FILE:-./docker/searxng.settings.yml}:/etc/searxng/settings.yml:ro"
      - searxng_cache:/var/cache/searxng

  aria:
    image: fischermanch/aria:alpha
    restart: unless-stopped
    extra_hosts:
      - "host.docker.internal:host-gateway"
    ports:
      - "${ARIA_HTTP_PORT:-8800}:8800"
    environment:
      ARIA_ARIA_HOST: "0.0.0.0"
      ARIA_ARIA_PORT: "8800"
      ARIA_PUBLIC_URL: "${ARIA_PUBLIC_URL:-http://localhost:8800}"
      ARIA_QDRANT_URL: "http://qdrant:6333"
      ARIA_QDRANT_API_KEY: "${ARIA_QDRANT_API_KEY:-CHANGE-ME-LONG-RANDOM-QDRANT-KEY}"
    volumes:
      - aria_config:/app/config
      - aria_prompts:/app/prompts
      - aria_data:/app/data
      - qdrant_storage:/qdrant/storage:ro
    depends_on:
      - qdrant
      - searxng

volumes:
  qdrant_storage:
  searxng_cache:
  searxng_valkey:
  aria_config:
  aria_prompts:
  aria_data:
```

If you still need keys:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

## Existing Portainer Stack Delta

If you already run an older ARIA Portainer stack from before `alpha69`, do **not** blindly replace it with the fresh public sample if your current stack already has working named volumes and a working custom network.

Keep these parts from your existing stack:

- your current volume names
  - for example `aria2_config`, `aria2_data`, `aria2_prompts`, `aria2_qdrant`
- your current network name
  - for example `aria2-net`
- your current ARIA host port
  - for example `ARIA_HTTP_PORT=8810`
- your current `ARIA_PUBLIC_URL`
- your current Qdrant service + storage volume mapping

The actual delta from an older stack to the new web-search-ready stack is only:

1. add `searxng-valkey`
2. add `searxng`
3. add the new SearXNG cache/Valkey volumes
4. extend `aria.depends_on` with `searxng`
5. mount `searxng.settings.yml`
6. set `SEARXNG_SECRET`

In other words:

- keep your existing ARIA/Qdrant data volumes
- keep your existing network
- keep your existing ARIA port
- only add the SearXNG sidecar services as a delta

For multi-instance hosts, the public sample already avoids fixed `container_name` values and does not publish Qdrant host ports by default. That keeps the default setup much safer for copy/paste deployment.

## Notes

- ARIA is currently an ALPHA system
- intended for LAN, VPN, homelab, or trusted internal use
- not recommended for direct public internet exposure

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

## Full Documentation

For the full product and setup docs, use GitHub:

- Repository: `https://github.com/FischermanCH/A.R.I.A.`
- Wiki: `https://github.com/FischermanCH/A.R.I.A./wiki`
- Setup docs: `https://github.com/FischermanCH/A.R.I.A./tree/main/docs/setup`
- Changelog: `https://github.com/FischermanCH/A.R.I.A./blob/main/CHANGELOG.md`
