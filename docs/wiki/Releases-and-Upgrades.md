# Releases and Upgrades

ARIA currently has three update stories, and it helps to keep them separate.

## 1. Managed installs created with `aria-setup`

This is the preferred future-facing path.

Managed installs have:

- one install directory
- one `.env`
- one generated `docker-compose.yml`
- visible bind-mounted storage
- `aria-stack.sh`
- `aria-updater`

Typical commands:

```bash
cd /opt/aria/aria
./aria-stack.sh update
./aria-stack.sh health
./aria-stack.sh logs
```

If a release changes the stack layout itself, for example by adding a new sidecar service, use:

```bash
aria-setup upgrade --install-dir /opt/aria/aria
```

Managed installs can also expose a controlled browser update on:

- `/updates`

Admin users can also use the same helper path from chat:

- `zeige update status`
- `starte update`
- `bestätige update <token>`

## 2. Manual public Docker Compose installs

This path uses:

- `docker-compose.public.yml`

Normal update:

```bash
docker compose -f docker-compose.public.yml pull
docker compose -f docker-compose.public.yml up -d
```

Rules:

- keep the same compose file
- keep the same compose project
- keep the same volumes
- use host-side `docker compose` commands for this path; the browser `/updates` button and chat-driven update flow belong to managed installs

## 3. Internal local TAR builds

This path exists for faster internal testing.

It uses:

- `aria-pull`
- `docker/update-local-aria.sh`
- `docker/portainer-stack.alpha3.local.yml`

The local update flow now also supports the `/updates` button when the local stack includes the `aria-updater` helper.

## Release principles

Current release principles:

- public release notes are maintained in `CHANGELOG.md`
- Docker tags follow public alpha tags
- internal TAR delivery can differ from registry installs, but the visible ARIA release label should stay aligned with the same published code line
- `aria-setup` is now the preferred fresh Docker install path
- generic non-managed installs should not be assumed to support the browser update button unless they explicitly include a matching helper path

## Useful references

- [`CHANGELOG.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/CHANGELOG.md)
- [`docs/release/versioning.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/release/versioning.md)
- [`docs/release/github-release-notes-template.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/release/github-release-notes-template.md)
- [`docs/setup/setup-overview.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/setup/setup-overview.md)

## Quick checks

- `aria --version` shows the installed ARIA release label
- `aria version-check` compares the installed version with the latest public release
- after larger UI or CSS changes, a hard browser reload can still be useful if a browser holds old cached assets

## Host-side upgrade helper

The host helper is useful for multi-instance hosts and controlled host-side automation.

Main commands:

- `docker/aria-host-update.sh detect`
- `docker/aria-host-update.sh update --project <name> --dry-run`
- `docker/aria-host-update.sh update --project <name>`

What it does:

- detects Compose-based ARIA stacks on the host
- updates only the `aria` service of the selected project
- intentionally leaves `qdrant`, `searxng`, `valkey`, and volumes alone

For internal local stacks it loads the newest internal TAR.

For registry-based Compose stacks it uses:

- `docker compose pull aria`
- then a targeted ARIA service recreate

Template:

- `docker/aria-host-update.env.example`
