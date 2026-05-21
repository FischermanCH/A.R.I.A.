# ARIA 0.1.0-alpha298

This public alpha rollup promotes the internally tested `alpha267` to `alpha298` line into the public Docker/GitHub channel.

The main theme is controlled usefulness: ARIA got better at understanding natural operational requests, while Guardrails, policy checks, confirmations, and runtime boundaries stay deterministic and inspectable.

## Highlights

- AI-assisted Guardrail drafts: describe a safety intent in everyday language, review/edit the proposal, test examples, then explicitly save it.
- Google Calendar now uses a simple read-only secret iCal URL setup, avoiding Google Cloud OAuth/device-code friction for LAN/IP-only installs.
- Connection detail pages were aligned around the SSH pattern, with clearer edit/create sections and visible Guardrail assignment.
- Scoped Guardrails only show on compatible connection kinds, so SFTP read-only rules do not accidentally appear on SMB profiles.
- File, Webhook, and HTTP API Guardrail evaluation now receives structured operation context such as list/read/write/send/status/health.
- Runtime Guardrail blocks are described as intentional security decisions, with direct review links and without noisy Discord recipe-error alerts.
- Multi-server health prompts such as `wie fit sind meine server?` route to the SSH fleet-health path and summarize uptime, disk, RAM, and swap.
- `/stats` now treats LLM costs as estimates, supports local billing-period reset, opens detail cards directly, and lists concrete Operator Guardrail review items.
- Token/cost/activity logs and redacted LLM debug logs use 90-day retention to reduce disk-fill risk.
- Discord startup events now report a configured ARIA base URL or detected local address, not a confusing missing-public-URL warning.

## Safety

- LLM-generated Guardrails are proposals only. They do not become active until reviewed and saved by the user.
- Guardrail execution remains deterministic; no LLM decision can bypass active policy or Guardrails.
- Side-effect actions such as webhooks and outbound messages still require confirmation unless explicitly configured otherwise.
- Expected Guardrail blocks and expected HTTP endpoint status responses are not treated as internal recipe failures.
- Normal updates continue to recreate only the `aria` service and leave Qdrant, SearXNG, Valkey, and volumes untouched.

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
- `/stats` shows release metadata, cost estimates, reset controls, Operator Guardrail details, and no release errors.
- `/config/security` can create an AI Guardrail draft, show progress while the LLM works, and save only after review.
- Guardrail-capable connection pages show the advanced/security section clearly and only offer compatible Guardrails.
- `wie fit sind meine server?` runs the SSH multi-target health path.
- Google Calendar read-only iCal profile can answer today/tomorrow/next appointment questions.
- Webhook/HTTP API blocked requests explain the active Guardrail instead of reporting a generic execution failure.
- Discord startup alert shows a real configured/detected host.

Full technical details are in `CHANGELOG.md`.
