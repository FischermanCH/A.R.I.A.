# ARIA 0.1.0-alpha266

This public alpha rollup promotes the internally tested `alpha252` to `alpha265` line plus the final Learned Recipes UI polish into the public Docker/GitHub channel.

ARIA is now much closer to the intended controlled agentic design: LLMs help interpret natural requests and summarize results, while deterministic policy, guardrails, preflight validation, and bounded runtimes remain the execution gate.

## Highlights

- Stronger LLM-assisted action flow for SSH, HTTP API, RSS, SMB/SFTP, outbound messaging, and learned recipe context.
- Multi-target SSH disk checks now summarize measured read-only results with an LLM-backed operator summary and validate hard thresholds against actual `df -h` output.
- RSS security/news digests honor explicit requested counts more reliably, fetch bounded feed groups concurrently, keep visible links, and explain request/result gaps.
- Blocked SSH/guardrail actions now return a clearer safety answer with the planned command and direct guardrail review path.
- Learned Recipes gained review-only LLM curator metadata, weighted learning evidence, Qdrant cleanup on delete, promotion preview, and a more stable review layout.
- `/connections/status` and `/connections/types` avoid slow page loads by using cached/last-known health unless a live refresh is requested.
- Managed and internal update helpers recreate only `aria`, keep stateful sidecars/volumes untouched, and clean up unused old ARIA images only after a successful health check.
- Docker release builds now pin Python/Docker base image digests and runtime dependency constraints to reduce release drift.
- Browser favicon assets and the update reconnect service worker are bundled and covered by release-hygiene tests.

## Safety

- Learned recipe data remains context-only until an admin explicitly promotes it.
- Side-effect actions such as Discord sends still require confirmation.
- Mutating SSH requests are identified as the intended command and blocked by SSH policy/guardrails unless explicitly allowed by configuration.
- Guardrail links point to `/config/security?guardrail_ref=...` for review.
- Normal updates do not recreate Qdrant, SearXNG, Valkey, or persistent volumes.

## Upgrade Notes

- Docker tags:
  - `fischermanch/aria:0.1.0-alpha.266`
  - `fischermanch/aria:alpha`
- Digest: `sha256:528ea0ef93eb346811542e85b46f671461a0d9b49e32385f48c52b7056c7a45d`
- Managed installs should use `/updates` or `./aria-stack.sh update`.
- Fixed-tag installs can use `docker/aria-host-update.sh update --project <name> --target-image fischermanch/aria:0.1.0-alpha.266`.
- A hard browser refresh is recommended because this release includes UI/CSS, service-worker, and chat-rendering changes.
- No deliberate stack-layout change is required for normal managed installs.
- Docker release builds now use pinned runtime constraints; Debian `apt` packages still come from normal Debian repositories.

## What To Test After Upgrade

- `/health` returns `ok`.
- `/stats` shows release metadata, Operator Guardrail, token/cost status, and Recipe Experience Memory without release errors.
- `/recipes/learned` renders stable review cards and shows file-list learnings as list/browse actions.
- `habe ich auf meinen servern überall mehr als zehn gigabyte reserve auf der festplatte?` reports hosts below the threshold.
- `mach mir eine zusammenfassung der letzten 10 it-security news` returns up to 10 visible linked entries and explains skipped feeds.
- `starte meinen dns server neu` is blocked and shows the guardrail review path.
- `zeige mir die folder auf dem share Ronny Fischer` separates folders from file examples.
- Discord send prompts ask for confirmation and send after the one-click action.

Full technical details are in `CHANGELOG.md`.
