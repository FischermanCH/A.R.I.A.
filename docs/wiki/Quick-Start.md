# Quick Start

ARIA is designed to get from container to usable web UI quickly.

Recommended path:

1. start ARIA with `aria-setup` or manual Docker Compose
2. open the web UI
3. create the first bootstrap user
4. configure:
   - chat LLM
   - embeddings
   - memory
   - first connections under `/connections/types`
5. test the first prompt

Useful first daily-use areas after setup:

- `/notes` for quick Markdown notes
- `/connections/types` for RSS, Watched Websites, or Google Calendar
- `/memories` for semantic memory and documents

Core deployment references:

- [`README.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/README.md)
- [`docs/setup/setup-overview.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/setup/setup-overview.md)

Notes:

- ARIA is currently a personal single-user system
- LAN / VPN is recommended
- public internet exposure is not recommended for the current ALPHA line
