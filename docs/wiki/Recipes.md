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

## Learned recipes and Experience Memory

Successful safe runs can become learned recipe candidates or Experience Memory. They are planner context and review material, not uncontrolled self-modifying automation.

### Chat Recipe Learn Mode

The chat toolbox includes an explicit learn mode for patterns that are easier to teach by example than by editing routing rules.

Flow:

1. Open the chat toolbox and start learn mode with `/lernen start` or `/learn start`.
2. Run the chat steps that show the behavior ARIA should understand later.
3. Finish with `/lernen stop` or `/learn stop`.
4. Review the generated candidate under `/recipes/learned`.

Important boundaries:

- Learn mode is opt-in for the current chat session.
- The captured run creates a **review-only** Learned Recipe candidate.
- Nothing is activated automatically.
- Guardrails, runtime policy, confirmation prompts, and deterministic execution checks stay in front of every real action.
- `/lernen abbrechen` or `/learn cancel` discards the current learn run without creating a candidate.

This is useful for phrasing and routing patterns, for example teaching ARIA which configured targets belong to a personal role such as `dev server`, while keeping the actual promotion step explicit.

### Learned Recipe review states

Learned recipes move through review states based on successful evidence. They do **not** become active automatically.

States:

- `observed`: ARIA has seen at least one successful, policy-allowed pattern, but it is still only observation material.
- `review_ready`: the pattern has enough evidence for an admin review.
- `eligible`: the pattern is strong enough that promotion is due, but still needs an explicit admin decision.
- `promoted`: an admin deliberately promoted the candidate into a stored recipe.

Default thresholds:

- `review_ready`: at least `3` learning-evidence points.
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
