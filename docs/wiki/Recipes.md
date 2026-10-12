# Recipes

Recipes are ARIA's visible automation model. Legacy Skills remain only as compatibility bridges.

A recipe is a curated JSON manifest with:

- triggers and description
- connection references
- ordered steps
- optional LLM transforms
- guardrail and confirmation behavior

## Capability families

- SSH
- SFTP
- SMB
- RSS
- Discord
- Webhook
- HTTP API
- SMTP / IMAP
- MQTT
- LLM transform steps

## How recipes relate to Agentic Actions

Recipes are explicit, reviewable workflows. Agentic Action Flow is the runtime architecture around them:

1. enrich context
2. build or select a bounded draft
3. apply policy/guardrails
4. execute or ask/block

Recipes can therefore stay controlled while still benefiting from LLM understanding.

## Recurring workflows

Repeated comparable actions can be offered as an inactive recipe draft. A user can also explicitly preserve a workflow through `recipe_remember`. Neither path bypasses review: a recipe is stored only after a deliberate user action and remains subject to the existing guardrails and confirmations.

The former start/stop chat learning mode has been removed. Those command-like messages are now handled as ordinary chat messages.
- `eligible`: at least `5` learning-evidence points.
- Side-effect actions: at least `5` learning-evidence points for `review_ready`; they still remain review-only and must not bypass confirmation or policy.
- Multi-target observations: stay context-only. Create an explicit reviewed recipe for the target set instead of promoting the observation directly.

Evidence is weighted:

- New successful pattern: `+1.0`.
- Same pattern with another user wording: `+0.75`.
- Same pattern with another target/scope: `+0.75`.
- Same pattern with another safe action shape: `+0.5`.
- Exact repeat of the same target, action and wording: `+0.25`.
- Risky action deviation: `+0`; kept for review only.

The UI may also show a maturity hint such as "keep observing" or "strong evidence". The actual lifecycle state is still the stored `promotion_state` (`observed`, `review_ready`, `eligible`, `promoted`).

## Samples

Bundled samples are templates. Adjust refs, hosts, URLs, Discord targets, and guardrails for your environment.

Current sample directions:

- read-only SSH health and disk checks
- RSS to chat or RSS to Discord digests
- SFTP read/config-preview examples
- SMB read/list examples

Useful references:

- [`samples/recipes/`](https://github.com/FischermanCH/A.R.I.A./tree/main/samples/recipes)
- [`docs/product/feature-list.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/product/feature-list.md)
