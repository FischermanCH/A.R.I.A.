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
- a reachable LLM endpoint
- a Qdrant API key for the bundled Qdrant container

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

Use this minimal `compose.yml`:

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    restart: unless-stopped
    environment:
      QDRANT__SERVICE__API_KEY: ${ARIA_QDRANT_API_KEY}
    volumes:
      - qdrant_storage:/qdrant/storage

  aria:
    image: fischermanch/aria:alpha
    restart: unless-stopped
    depends_on:
      - qdrant
    ports:
      - "${ARIA_HTTP_PORT:-8800}:8800"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      ARIA_QDRANT_URL: http://qdrant:6333
      ARIA_QDRANT_API_KEY: ${ARIA_QDRANT_API_KEY}
      ARIA_LLM_API_BASE: ${ARIA_LLM_API_BASE:-http://host.docker.internal:11434}
      ARIA_LLM_MODEL: ${ARIA_LLM_MODEL:-ollama_chat/qwen3:8b}
      ARIA_EMBEDDINGS_API_BASE: ${ARIA_EMBEDDINGS_API_BASE:-http://host.docker.internal:11434}
      ARIA_EMBEDDINGS_MODEL: ${ARIA_EMBEDDINGS_MODEL:-ollama/nomic-embed-text}
    volumes:
      - aria_config:/app/config
      - aria_prompts:/app/prompts
      - aria_data:/app/data
      - qdrant_storage:/qdrant/storage:ro

volumes:
  qdrant_storage:
  aria_config:
  aria_prompts:
  aria_data:
```

Example `.env` values:

```dotenv
ARIA_QDRANT_API_KEY=replace-with-a-long-random-key
ARIA_HTTP_PORT=8800
ARIA_LLM_API_BASE=http://host.docker.internal:11434
ARIA_LLM_MODEL=ollama_chat/qwen3:8b
ARIA_EMBEDDINGS_API_BASE=http://host.docker.internal:11434
ARIA_EMBEDDINGS_MODEL=ollama/nomic-embed-text
```

Start:

```bash
docker compose up -d
```

## Portainer Stack

Use this stack YAML:

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    restart: unless-stopped
    environment:
      QDRANT__SERVICE__API_KEY: ${ARIA_QDRANT_API_KEY}
    volumes:
      - qdrant_storage:/qdrant/storage

  aria:
    image: fischermanch/aria:alpha
    restart: unless-stopped
    depends_on:
      - qdrant
    ports:
      - "${ARIA_HTTP_PORT:-8800}:8800"
    environment:
      ARIA_QDRANT_URL: http://qdrant:6333
      ARIA_QDRANT_API_KEY: ${ARIA_QDRANT_API_KEY}
      ARIA_PUBLIC_URL: ${ARIA_PUBLIC_URL:-http://localhost:8800}
    volumes:
      - aria_config:/app/config
      - aria_data:/app/data
      - aria_prompts:/app/prompts
      - qdrant_storage:/qdrant/storage:ro
    extra_hosts:
      - "host.docker.internal:host-gateway"

volumes:
  aria_config:
  aria_data:
  aria_prompts:
  qdrant_storage:
```

Recommended Portainer environment variables:

```dotenv
ARIA_QDRANT_API_KEY=replace-with-a-long-random-key
ARIA_HTTP_PORT=8800
ARIA_PUBLIC_URL=http://<your-host>:8800
```

## Notes

- ARIA is currently an ALPHA system
- intended for LAN, VPN, homelab, or trusted internal use
- not recommended for direct public internet exposure

## Full Documentation

For the full product and setup docs, use GitHub:

- Repository: `https://github.com/FischermanCH/A.R.I.A.`
- Wiki: `https://github.com/FischermanCH/A.R.I.A./wiki`
- Setup docs: `https://github.com/FischermanCH/A.R.I.A./tree/main/docs/setup`
- Changelog: `https://github.com/FischermanCH/A.R.I.A./blob/main/CHANGELOG.md`
