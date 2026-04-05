# Contributing to ARIA

ARIA is still in ALPHA, but contributions, issues, and focused improvements are welcome.

## Best ways to contribute

- report a bug with clear steps, expected behavior, and actual behavior
- suggest a feature with a practical use case
- improve documentation, setup guides, and help texts
- improve tests around routing, memory, skills, and connections

## Before opening a change

Please check:

- `README.md`
- `CHANGELOG.md`
- `docs/product/feature-list.md`
- `docs/product/architecture-summary.md`
- `docs/backlog/alpha-backlog.md`
- `docs/backlog/main-backlog.md`

This helps keep work aligned with the current product direction.

## Issue flow

Use the GitHub issue templates when possible:

- `Bug`
- `Feature`
- `Chore / Release / Docs`

Recommended issue style:

- short title
- clear reproduction or use case
- expected result
- actual result
- screenshots or logs if relevant

Please avoid posting secrets, API keys, private hostnames, internal IPs, or sensitive local paths.

## Pull requests

For code changes, prefer small and focused PRs.

Good PRs usually:

- solve one clear problem
- include or update tests where practical
- update docs if behavior changed
- keep runtime secrets and local config out of Git

## Local safety

Do not commit runtime-specific files such as:

- `config/config.yaml`
- `config/secrets.env`
- `data/auth/`
- `data/chat_history/`
- `data/logs/`
- `data/qdrant/`
- `data/runtime/`
- `data/ssh_keys/`

Use the tracked examples and templates instead:

- `config/config.example.yaml`
- `config/secrets.env.example`
- `.env.example`

## Release notes

Public releases use:

- Git tags
- `CHANGELOG.md`
- Docker Hub image tags
- GitHub Releases

If a change affects users, setup, or behavior, it should be reflected in `CHANGELOG.md`.

## Project style

ARIA aims to stay:

- lean
- understandable
- self-host friendly
- explicit about security boundaries
- practical instead of bloated

If a change adds complexity, it should add clear real value.
