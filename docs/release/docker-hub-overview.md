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

Example `.env` values:

```dotenv
ARIA_QDRANT_API_KEY=replace-with-a-long-random-key
SEARXNG_SECRET=replace-with-a-long-random-key
ARIA_HTTP_PORT=8800
ARIA_PUBLIC_URL=http://localhost:8800
SEARXNG_SETTINGS_FILE=./docker/searxng.settings.yml
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

Recommended Portainer environment variables:

```dotenv
ARIA_QDRANT_API_KEY=replace-with-a-long-random-key
ARIA_PUBLIC_URL=http://<your-host>:8800
SEARXNG_SECRET=replace-with-a-long-random-key
```

If you still need keys:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

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
