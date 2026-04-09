# ARIA Portainer Deploy Checklist

Updated: 2026-04-09

This guide explains the Portainer path in plain English.

Important first:

- Portainer still works well for ARIA
- Portainer is no longer the recommended default for new installs
- if you want the simplest install and the simplest future updates, use `aria-setup` instead
- use Portainer when you already rely on Portainer and want to stay there on purpose

## 1. What this Portainer stack contains

The public Portainer stack already includes all required runtime services:

- `aria`
- `qdrant`
- `searxng`
- `searxng-valkey`

The SearXNG settings are embedded directly into the stack through Docker `configs`.

That means:

- no separate host-side `searxng.settings.yml` is needed for the normal public Portainer path

## 2. Before you start

Make sure the target host already has:

- Docker
- Portainer
- access to pull these images:
  - `fischermanch/aria:alpha`
  - `qdrant/qdrant:latest`
  - `searxng/searxng:latest`
  - `valkey/valkey:8-alpine`

ARIA is currently best suited for:

- LAN
- VPN
- homelab
- trusted internal environments

It is not the recommended path for direct public internet exposure.

## 3. Which file to use

For the public Portainer path use:

- `docker/portainer-stack.public.yml`

If you are working with internal local TAR builds instead of public registry images, that is a different path and uses:

- `docker/portainer-stack.alpha3.local.yml`

Do not mix the public and internal-local files.

## 4. Environment values to set in Portainer

Set at least these values:

```dotenv
ARIA_QDRANT_API_KEY=replace-with-a-long-random-key
SEARXNG_SECRET=replace-with-a-long-random-key
ARIA_HTTP_PORT=8800
ARIA_PUBLIC_URL=http://your-hostname:8800
```

Generate good secrets on Unix:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Notes:

- `ARIA_QDRANT_API_KEY` must be the same key for both ARIA and Qdrant
- `SEARXNG_SECRET` is for the in-stack SearXNG service
- `ARIA_HTTP_PORT` is the host port for the ARIA web UI
- `ARIA_PUBLIC_URL` should match the real browser URL that users will open

## 5. Deploy the stack in Portainer

Use the content of:

- `docker/portainer-stack.public.yml`

Then:

1. create or open the target stack in Portainer
2. paste the stack YAML
3. set the environment values
4. deploy the stack

After deployment, the browser UI should be available at:

- `http://<host>:<ARIA_HTTP_PORT>`

## 6. First login and first checks

After the stack comes up:

1. open ARIA in the browser
2. create the first user
3. the first user becomes admin
4. configure `LLM`
5. configure `Embeddings`
6. open `/stats`
7. verify the startup preflight
8. run a first chat prompt

## 7. How to update a Portainer install

For a normal update:

1. open the existing stack in Portainer
2. keep the same stack
3. keep the same volume names
4. keep the same network names
5. keep the same public port unless you intentionally change it
6. update the stack

Important:

- do not create a second fresh stack unless that is intentional
- do not rename your data volumes casually
- do not assume a copy/pasted fresh sample will magically reuse old data if the stack name, network, or volume names changed

## 8. Existing Portainer stack delta

If you already have an older ARIA Portainer stack that was created before the SearXNG integration, do not blindly replace it with the fresh public sample if the old stack already has working data.

Keep these parts from the existing stack:

- your current ARIA data volumes
- your current Qdrant storage volume
- your current custom network name
- your current host port
- your current public URL

The actual delta to reach the newer web-search-ready stack is usually only:

1. add `searxng-valkey`
2. add `searxng`
3. add the SearXNG cache volume and Valkey data volume
4. extend `aria.depends_on` with `searxng`
5. keep the embedded `searxng_settings` Docker config
6. add `SEARXNG_SECRET`

That means in practice:

- keep your current ARIA and Qdrant data
- keep your current network
- keep your current port
- add only the missing SearXNG services and settings

## 9. Multi-instance hosts

If the same host already runs another ARIA instance:

- give this stack a different `ARIA_HTTP_PORT`
- keep its volume names separate from the other ARIA instance
- keep its stack name separate from the other ARIA instance

The public Portainer sample intentionally:

- avoids fixed `container_name` values
- does not publish Qdrant on host ports by default

That makes multi-instance hosts much safer.

## 10. What the Portainer path does not do automatically

The normal public Portainer stack does not automatically create a managed install directory like `aria-setup` does.

That means:

- Portainer is a valid runtime path
- but future updates are less controlled than the managed `aria-setup` path
- the browser update button on `/updates` should not be assumed for generic public Portainer installs unless you intentionally wire in a matching helper path

## 11. When should you choose `aria-setup` instead?

Choose `aria-setup` when you want:

- the simplest install path
- visible bind-mounted storage
- a predictable update helper
- an easier future migration path
- the cleanest `/updates` browser update story

Choose Portainer when you already want Portainer specifically.
