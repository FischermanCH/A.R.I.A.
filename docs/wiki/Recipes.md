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
