# ARIA 0.1.0-alpha251

This is the largest ARIA alpha rollup since `0.1.0-alpha167`.

ARIA has moved from a mostly deterministic chat/router with legacy Skills toward a recipe-first, LLM-assisted action architecture. Natural-language requests are now treated as bounded action drafts: context is enriched first, an LLM can propose the concrete action, and policy/guardrails decide whether it may run.

## Highlights

- Recipes are now the visible automation model; legacy Skills remain only as compatibility bridges where needed.
- SSH, HTTP API, SFTP/SMB files, outbound messaging, RSS, IMAP, Calendar, and watched websites now share a clearer agentic action flow.
- LLM calls for action planning are routed through the central model gateway and are visible in token/cost tracking.
- Recipe Experience Memory can learn from successful recipe/guardrail runs as planner context without becoming an unsafe executor.
- `/stats` now gives a clearer view of tokens, costs, model pricing, gateway status, and experience memory.
- Pricing uses LiteLLM's public model-pricing JSON as primary source, with cache/fallback/manual overrides.
- Managed Docker updates were hardened so normal updates recreate only the ARIA app container, not Qdrant/SearXNG/Valkey sidecars.
- The host-side update helper checks host-port conflicts before recreating ARIA, so a blocked port aborts safely instead of breaking a running stack halfway through an update.

## Safety

- All agentic action drafts still pass through policy and guardrails before execution.
- SSH read-only policy blocks mutation, shell injection, redirects, background execution, and unsafe command forms.
- Multi-target SSH preflights every target individually against its profile policy and guardrails.
- Side-effect messaging actions still require confirmation, now with one-click UX instead of manual token copying.
- LLM Prompt Debug stores redacted prompt traces and is admin-only.

## Upgrade Notes

- This is a major alpha rollup from `0.1.0-alpha167`; read the notes before updating a system you care about.
- Managed installs should use `/updates` or `./aria-stack.sh update`.
- Older fixed-tag installs can use `docker/aria-host-update.sh update --project <name> --target-image fischermanch/aria:0.1.0-alpha.251`.
- Normal updates should not recreate Qdrant/SearXNG/Valkey sidecars. Use `update-all` or `repair` only when release notes or recovery instructions explicitly say so.
- If a host-side update reports a port conflict, free or change that host port first; do not force a full-stack recreate as a workaround.
- Existing legacy Skills may remain readable for compatibility, but new automation should be created as Recipes.
- After upgrade, check `/stats` for model pricing coverage and unpriced aliases.
- A hard browser refresh is recommended because several UI layouts and route surfaces changed.

## What To Test After Upgrade

- `/health` returns `ok`.
- `/stats` shows tokens, costs, pricing coverage, Model Gateway Audit, and Recipe Experience Memory without layout breakage.
- `/recipes` opens and old `/skills` links redirect or remain compatible where intended.
- A read-only SSH disk check on one server works.
- A fleet disk check over multiple SSH profiles summarizes all-ok results compactly.
- A mutating SSH prompt is blocked and shows the intended blocked command.
- A Discord send asks for one-click confirmation and sends after confirmation.
- An SMB share-root folder list works without asking for a path.
- A normal RAG/document question still goes to chat/RAG and shows sources.

## Docker

- `fischermanch/aria:0.1.0-alpha.251`
- `fischermanch/aria:alpha`
- Digest: `sha256:3aacbe8145da283dddaeb9c8cdef0b56961b05119770df1871570f0e26388321`

Full technical details are in `CHANGELOG.md`.
