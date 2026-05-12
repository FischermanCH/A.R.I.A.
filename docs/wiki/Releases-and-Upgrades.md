# Releases and Upgrades

Current public alpha: `0.1.0-alpha251`.

ARIA has three update stories. Keep them separate.

## 1. Managed installs created with `aria-setup`

This is the preferred public path.

Typical commands:

```bash
cd /opt/aria/aria
./aria-stack.sh update
./aria-stack.sh health
./aria-stack.sh logs
```

Normal `aria-stack.sh update` refreshes/recreates only the `aria` service. It intentionally leaves Qdrant, SearXNG, Valkey, and volumes alone.

If a release changes the stack layout itself, use:

```bash
aria-setup upgrade --install-dir /opt/aria/aria
```

Use `update-all` or `repair` only when release notes or recovery guidance explicitly say so.

Managed installs can also expose the browser update page under `/updates`.

## 2. Manual public Docker Compose installs

Normal update:

```bash
docker compose -f docker-compose.public.yml pull aria
docker compose -f docker-compose.public.yml up -d --no-deps --force-recreate aria
```

Rules:

- keep the same compose file
- keep the same compose project name
- keep the same volumes
- use host-side Docker commands unless the stack deliberately includes the managed helper

## 3. Internal local TAR builds

This path is for internal alpha testing:

- `aria-pull`
- `docker/update-local-aria.sh`
- `docker/portainer-stack.alpha3.local.yml`
- local image `aria:alpha-local`

## Host-side upgrade helper

`docker/aria-host-update.sh` can detect and update Compose-based ARIA stacks.

Main commands:

- `docker/aria-host-update.sh detect`
- `docker/aria-host-update.sh update --project <name> --dry-run`
- `docker/aria-host-update.sh update --project <name>`
- `docker/aria-host-update.sh update --project <name> --target-image fischermanch/aria:<version>`

Safety behavior:

- updates only the selected `aria` service
- leaves Qdrant, SearXNG, Valkey, and volumes untouched
- refreshes managed helper files from the target image before recreating ARIA
- preflights the intended host port before recreating ARIA
- aborts safely if another process or container owns that port

## Quick checks

- `aria --version`
- `aria version-check`
- `/stats` preflight
- `/updates` helper status on managed installs
- browser hard reload after large UI/CSS updates

References:

- [`CHANGELOG.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/CHANGELOG.md)
- [`docs/release/versioning.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/release/versioning.md)
- [`docs/setup/setup-overview.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/setup/setup-overview.md)
