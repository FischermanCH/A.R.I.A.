# ARIA 0.1.0-alpha266 - Public Alpha Rollup since 0.1.0-alpha167

GitHub Release and Docker Hub announcement source for `v0.1.0-alpha.266`.

## Summary

`0.1.0-alpha266` is the current ARIA public alpha rollup since `0.1.0-alpha167`.

ARIA has moved from a mostly deterministic chat/router with legacy Skills toward a recipe-first, LLM-assisted action architecture. The visible product language is now `Recipes`, while legacy Skill compatibility remains only where it is still needed for old data and routes.

The biggest change is architectural: ARIA now treats natural-language requests as bounded action drafts. Context is enriched first, an LLM can propose the concrete action, and policy/guardrails decide whether it may run. This makes ARIA more useful as an assistant that can operate real connections without turning every new phrase into hard-coded routing logic.

## What Changed At A Glance

- Skills are no longer the primary product concept; Recipes are now the visible automation model.
- SSH, HTTP API, SFTP/SMB files, outbound messaging, RSS, IMAP, Calendar, and watched websites now share a clearer agentic action flow.
- LLM calls for action planning are routed through the central model gateway and are visible in token/cost tracking.
- Recipe Experience Memory can learn from successful recipe/guardrail runs as planner context without becoming an unsafe executor.
- `/stats` now gives a much clearer view of tokens, costs, model pricing, gateway status, and experience memory.
- Pricing uses LiteLLM's public model-pricing JSON as primary source, with cache/fallback/manual overrides.
- Managed Docker updates were hardened so normal updates recreate only the ARIA app container, not Qdrant/SearXNG sidecars.
- The host-side update helper now checks host-port conflicts before recreating ARIA, so a blocked port aborts safely instead of breaking a running stack halfway through an update.
- The UI, docs, routes, tests, and i18n surfaces were cleaned up heavily around the new recipe-first model.
- RSS digests now honor explicit requested counts more reliably, fetch bounded feed groups concurrently, and keep visible links even for bracketed titles.
- Learned Recipes now include LLM curator metadata, weighted evidence, promotion preview, Qdrant cleanup on delete, and a calmer review layout.
- Docker release builds now pin base-image digests and runtime dependencies through `constraints/runtime.txt`.
- The update reconnect service worker gives browsers a small waiting shell during brief ARIA container recreates.

## Added

- Recipe-first UI under `/recipes`, including templates, imported recipes, user recipes, learned recipe review, and wizard flows.
- Recipe Experience Memory backed by Qdrant, used as planner context only.
- Agentic action draft contracts for SSH, HTTP API, file operations, messaging, read-only source lookups, and runtime debug output.
- LLM Prompt Debug page for inspecting redacted prompts, responses, model, source, operation, duration, and token usage.
- Model Gateway Audit and Recipe Experience Memory cards on `/stats`.
- One-click confirmation buttons for side-effect actions such as Discord sends.
- Multi-target SSH execution for bounded read-only checks such as fleet disk-space checks.
- Public host-side update helper support for `--target-image`, useful for safely moving fixed-tag installs to a newer ARIA image.
- Admin Pricing Overrides UI for model aliases and local/manual prices.
- Package-data regression coverage for i18n, lexicons, templates, static assets, recipe prompts, and sample recipes.

## Changed

- Product language changed from Skills-first to Recipes-first. Old Skill names remain only as compatibility bridges where needed.
- Natural action requests now follow the intended architecture: context enrichment, LLM action proposal, policy/guardrail decision, runtime execution.
- Deterministic logic is now treated as boundaries, hints, policies, normalizers, and runtime helpers, not as the main source of product intelligence.
- SSH health and disk checks now produce operator-level summaries instead of raw command dumps when possible.
- Fleet-style SSH checks summarize all-ok results compactly and keep per-host detail in the technical trace.
- `/stats` pricing and token cards were rearranged to avoid layout breakage and make cost coverage visible.
- LiteLLM is no longer a hard runtime dependency of the base Python package; model calls load the gateway adapter lazily, while Docker installs the model-gateway extra explicitly.
- The active alpha backlog was compacted; old build history lives in `project.docu/alpha-build-log.md`, while public-facing changes live in `CHANGELOG.md` and release docs.

## Fixed

- Natural prompts like `wie sieht die hd auf meinem management server aus` now route to bounded SSH disk checks instead of drifting into unrelated document RAG.
- Mutating SSH requests such as restarting a DNS server now surface the real mutating command and are blocked by policy instead of being silently converted into a safe healthcheck.
- Plural SSH prompts like `meine server` can fan out safely for read-only checks instead of choosing one stale memory target.
- Discord send prompts no longer fall through into stale SMB/file context.
- SMB root folder listing now defaults to the share root instead of asking for an unnecessary path.
- HTTP API reachability prompts can use the only configured API profile instead of treating words like `reachable` as a profile name.
- LLM usage in agentic routing is now counted in visible token/cost stats instead of showing misleading `0 tokens`.
- Unpriced model warnings now show exact model aliases and no longer break the `/stats` layout.
- Managed public updates no longer recreate stateful sidecars during normal `aria-stack.sh update`.
- Host-side update helper lock cleanup and root-owned managed file refresh issues were fixed.
- Host-side updates now preflight published Compose ports before `up --force-recreate`, preventing a port conflict from removing/recreating the ARIA container and then failing after the old service is already gone.

## Security / Safety

- All agentic action drafts still pass through policy and guardrails before execution.
- SSH read-only policy blocks mutation, shell injection, redirects, background execution, and unsafe command forms.
- Multi-target SSH preflights every target individually against its profile policy and guardrails.
- Side-effect messaging actions still require confirmation, now with one-click UX instead of manual token copying.
- LLM Prompt Debug stores redacted prompt traces and is admin-only.
- Managed updates deliberately keep Qdrant/SearXNG/Valkey and volumes untouched on normal updates.
- Update helpers fail closed when the target host port is already occupied by another process/container.

## Upgrade Notes

- This is a major alpha rollup from `0.1.0-alpha167`; read the notes before updating a system you care about.
- Managed installs should use `/updates` or `./aria-stack.sh update` after this release is installed.
- Older fixed-tag installs can use the host helper with `--target-image` to move to the new image while recreating only the ARIA service.
- Normal updates should not recreate Qdrant/SearXNG sidecars. Use `update-all` or `repair` only when release notes or recovery instructions explicitly say so.
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
- Managed update path: normal update recreates only `aria`, not Qdrant/SearXNG/Valkey.
- Host update helper: dry-run/update should abort before recreate when the intended ARIA host port is already occupied by another process.

## Known Limitations

- ARIA is still alpha software for LAN/VPN/homelab use, not direct public internet exposure.
- Full multi-user ownership/RBAC/sharing for Recipes, Connections, and Memories is not complete.
- Some internal compatibility modules still use Skill names to preserve old data/routes; these are not the visible product direction.
- Agentic intelligence is improving but still bounded deliberately by policies and guardrails.
- Pricing depends on provider naming and aliases; manual overrides may still be needed for custom deployments.

## Short Docker Hub Description

Lean, self-hosted AI assistant with memory, recipes, secure connections, LLM-assisted action planning, and a browser-first UI.

## Longer Docker Hub Intro

ARIA is a compact self-hosted AI assistant for homelabs and private systems. It combines chat, Qdrant-backed memory, recipe-driven automation, modular connections, token/cost visibility, and guardrail-aware LLM action planning. It is built to stay understandable and operable instead of becoming a giant AI platform.
