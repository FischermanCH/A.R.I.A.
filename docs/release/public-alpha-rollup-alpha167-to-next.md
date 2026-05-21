# ARIA 0.1.0-alpha298 - Public Alpha Rollup since 0.1.0-alpha266

GitHub Release and Docker Hub announcement source for `v0.1.0-alpha.298`.

## Summary

`0.1.0-alpha298` is the current ARIA public alpha rollup since `0.1.0-alpha266`.

This release continues the controlled-agent direction: ARIA gets more flexible in how it understands natural user requests, but runtime execution remains bounded by deterministic policy, Guardrails, confirmation, and clear operator feedback.

The largest user-facing changes are easier Guardrail creation, a much simpler Google Calendar setup, more consistent connection pages, clearer `/stats` cost/log hygiene, and more reliable operational prompts such as `wie fit sind meine server?`.

## What Changed At A Glance

- Guardrail AI drafts turn a plain-language safety intent into a reviewable, editable Guardrail proposal.
- Guardrails can be tested with example requests before being attached to live connections.
- Google Calendar read-only access now uses the secret iCal URL from Google Calendar settings instead of Google Cloud OAuth/device-code setup.
- Connection detail pages now follow the same general edit/create/advanced pattern across SSH, SFTP, SMB, Webhook, HTTP API, Discord, mail, RSS, MQTT, Calendar, SearXNG, and websites.
- Guardrail selection is scoped by compatible connection kind, reducing accidental cross-application of file/web/API policies.
- File, Webhook, and HTTP API Guardrail checks receive structured operation context, making read-only/status policies much more useful.
- Runtime Guardrail blocks are explained as intentional safety decisions with direct Guardrail review links.
- HTTP API 4xx/5xx responses are treated as external endpoint status, not internal recipe failures.
- Multi-server health prompts with natural wording route to the SSH fleet-health path and summarize uptime, disk, RAM, and swap.
- `/stats` clarifies that LLM costs are local estimates, supports billing-period reset, opens detail cards directly, and lists concrete Operator Guardrail review items.
- Token/cost/activity logs and redacted LLM debug logs default to 90-day retention.
- Discord startup events show the configured ARIA URL or detected local address instead of warning about a missing public URL.

## Added

- AI-assisted Guardrail draft flow on `/config/security`.
- Guardrail draft progress indicator so long LLM calls do not look frozen.
- Guardrail-only test box for saved policies.
- Usage/cost reset on `/stats` and `/config/logs`, archiving the current token/run log before starting a new local period.
- Generic content-access and agentic execution contracts for future provider work.
- Provider-manifest validation scaffolding for cleaner connection extensibility.

## Changed

- Google Calendar setup is read-only iCal-first for LAN/IP-only installs.
- Connection pages are more consistent and easier to edit.
- Guardrail-capable connection forms show advanced/security options by default.
- `/stats` is now a stronger operator cockpit for release, pricing, costs, logs, preflight, health, and update path status.
- Discord startup host reporting now uses real configured/detected runtime URLs.
- Documentation, help, and wiki pages were updated to match the iCal Calendar path, Guardrail workflow, cost/log hygiene, and release status.

## Fixed

- Colloquial server-health prompts such as `wie fit sind meine server?` no longer fall back to generic chat/RAG.
- SFTP/SMB read-only Guardrails allow list/read while blocking write/create/delete more reliably.
- Webhook payloads such as `delete user record` are treated as webhook payloads and can be blocked by Guardrails, not misrouted as connection deletion.
- HTTP API single-profile routing handles generic phrases like `meine http api` more reliably.
- Confirmed `ask_user` SSH/HTTP actions pass confirmation into runtime policy instead of failing again.
- Guardrail block fallback text no longer sounds like a broken profile when the action was intentionally blocked.
- Stats detail links open collapsed sections before scrolling.
- Operator Guardrail warnings now name the exact affected checks.
- Google Calendar `next appointment` returns only the next event.

## Security / Safety

- LLM Guardrail drafts are proposals only; users must review and save them.
- Guardrail execution remains deterministic.
- Side effects still require explicit confirmation unless a profile policy intentionally says otherwise.
- Expected policy/Guardrail blocks do not create noisy Discord recipe-error alerts.
- Normal managed updates recreate only `aria` and keep Qdrant/SearXNG/Valkey/volumes untouched.

## Upgrade Notes

- Docker tags:
  - `fischermanch/aria:0.1.0-alpha.298`
  - `fischermanch/aria:alpha`
- Digest: `sha256:7f5a55506d087e0479d0087bb1d9bdfab7706055ba1d21f08d8f6f30ae7db0ad`
- Managed installs should use `/updates` or `./aria-stack.sh update`.
- Fixed-tag installs can use `docker/aria-host-update.sh update --project <name> --target-image fischermanch/aria:0.1.0-alpha.298`.
- No deliberate stack-layout change is required for normal managed installs.
- A hard browser refresh is recommended because this release includes UI, CSS, and form/layout changes.

## What To Test After Upgrade

- `/health` returns `ok`.
- `/stats` shows release metadata, estimated costs, reset controls, Operator Guardrail, and no release errors.
- `/config/security` can create and save a reviewed Guardrail proposal.
- Connection pages can edit an existing profile and attach compatible Guardrails.
- `wie fit sind meine server?` runs the SSH multi-target health path.
- Google Calendar iCal profile answers today/tomorrow/next appointment questions.
- Webhook/HTTP API blocks show the active Guardrail instead of generic execution failure.
- Discord startup alert shows a real configured/detected host.

## Known Limitations

- ARIA is still alpha software for LAN/VPN/homelab use, not direct public internet exposure.
- Full multi-user ownership/RBAC/sharing for Recipes, Connections, and Memories is not complete.
- Pricing remains an estimate based on local usage logs and known model prices.
- Guardrail suggestions are useful starting points, not audited security policies.

## Short Docker Hub Description

Lean, self-hosted AI assistant with memory, recipes, secure connections, Guardrail-aware action planning, and a browser-first UI.

## Longer Docker Hub Intro

ARIA is a compact self-hosted AI assistant for homelabs and private systems. It combines chat, Qdrant-backed memory, recipe-driven automation, modular connections, token/cost visibility, and deterministic Guardrails around LLM-assisted action planning. It is built to stay understandable and operable instead of becoming a giant AI platform.
