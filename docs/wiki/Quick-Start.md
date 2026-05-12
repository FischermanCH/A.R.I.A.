# Quick Start

ARIA is designed to get from container to usable web UI quickly.

## Recommended path

1. install with `aria-setup` or a deliberate Docker Compose setup
2. open the web UI
3. create the first bootstrap user
4. configure chat LLM and embeddings
5. open `/stats` and check preflight, pricing coverage, and gateway audit
6. create first connections under `/connections/types`
7. test a simple prompt

## Useful first prompts

- `is my dns server ok`
- `check whether my servers still have enough free disk space`
- `check whether the api is reachable`
- `summarize the latest it-security news`

## First daily-use areas

- `/notes` for Markdown notes
- `/memories` and `/memories/map` for memory and documents
- `/connections/types` for external systems
- `/recipes` for automation
- `/config/workbench/routing` for action/routing dry-runs

## Deployment notes

- LAN/VPN is recommended
- direct public internet exposure is not recommended for the alpha
- managed installs should use the update helper instead of manually replacing random containers
- keep volumes and compose project names stable

References:

- [`README.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/README.md)
- [`docs/setup/setup-overview.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/setup/setup-overview.md)
