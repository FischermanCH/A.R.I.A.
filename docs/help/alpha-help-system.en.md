# ARIA Alpha Help

Updated: 2026-05-15 / Public Alpha `0.1.0-alpha266`

This is the practical short help for ARIA Alpha. It reflects the current state after the larger move from legacy skills to recipes, LLM-assisted action planning, and controlled execution.

## What ARIA Alpha is right now

ARIA is a personal self-hosted AI assistant for LAN, VPN, and homelab usage.

Good fit for:

- a browser-based personal AI workspace
- memory and document RAG with Qdrant
- notes as a Markdown workspace
- safe connections to SSH, SFTP, SMB, RSS, Discord, HTTP API, Webhook, Mail, MQTT, SearXNG, and Google Calendar
- recipe-first automation with guardrails
- LLM-assisted action drafts: ARIA understands natural prompts, proposes bounded actions, and lets policy/guardrails decide

Not the current alpha target:

- direct public internet exposure without a reverse-proxy/auth concept
- a full multi-user/RBAC model
- hands-off enterprise deployment

## First start

On first start, you create the first user. That user automatically becomes admin.

After that, check:

1. `/config/llm` - chat model and API access
2. `/config/embeddings` - embedding model for Memory and routing
3. `/stats` - preflight, Qdrant, model status, tokens/costs, and pricing coverage
4. `/connections/types` - connections to your systems
5. `/recipes` - import, review, or build recipes
6. `/config/routing` and `/config/workbench/routing` - routing dry-runs and debug prompts when ARIA picks the wrong target

## Admin mode and user mode

ARIA has two working modes:

- **User mode**: reduced daily-use view
- **Admin mode**: additional system, routing, security, workbench, and config pages

If config pages are missing, open `/config/users` and check whether **Admin active** is enabled.

## Chat, actions, and details

You can chat normally or give natural work requests, for example:

- `is my dns server ok`
- `check whether my servers still have enough disk space and tell me if action is needed`
- `check whether the api is reachable`
- `show me the folders on the Ronny Fischer share`
- `summarize the latest it-security news`

ARIA tries to:

1. enrich the prompt with context
2. find matching connections, recipes, and previous safe experiences
3. ask an LLM for a bounded action draft when useful
4. let policy and guardrails decide: `allow`, `ask_user`, or `block`
5. execute the action or explain why it was not executed

Under **Details** you can inspect:

- capability, connection, and command/path/message
- routing debug including `agentic_source`, draft/policy/runtime boundaries
- tokens and USD cost when an LLM or embedding call was used
- runtime
- sources for RAG/web/RSS answers

## Confirmations

Outgoing or potentially impactful actions can require `ask_user`. ARIA then shows a chat button such as **Run action**.

Examples:

- send a Discord message
- call a webhook
- future non-read-only actions

Read-only actions such as `df -h`, health checks, or RSS reads can run directly when guardrails allow them.

## Memory

ARIA uses Qdrant for semantic memory.

Important:

- **Facts** and **Preferences** are long-term
- **Session context** and rollups help with work continuity
- **Document collections** power RAG uploads
- **Experience Memory** stores successful safe action patterns as planner context, not as blind executor automation
- transient SSH/RSS/SMB snapshots are not written into Memory by default

On `/memories`, you can inspect, search, edit, delete, and export memories. `/memories/map` shows collections, document groups, rollups, and memory structure.

## Notes

`/notes` is a standalone Markdown workspace with folder navigation, cards, and an editor. Notes are intentionally separate from Memory, but can be indexed for search.

## Connections

Connections are explicit profiles for external systems. Good metadata matters:

- title
- short description
- aliases
- tags
- notes about the purpose of the connection

These fields are not cosmetic. ARIA uses them for routing, semantic target selection, and LLM context.

Current connection families:

- SSH / SFTP / SMB
- RSS and watched websites
- Discord / Webhook / HTTP API
- SearXNG web search
- Google Calendar read-only
- SMTP / IMAP / MQTT

## Recipes

Recipes are the visible automation model. Legacy skills remain only as compatibility bridges.

A recipe is a JSON manifest with:

- triggers and description
- connection refs
- ordered steps
- optional LLM transforms
- guardrail/confirmation logic

Important step types:

- `ssh_run`
- `sftp_read` / `sftp_write`
- `smb_read` / `smb_write`
- `rss_read`
- `llm_transform`
- `discord_send`
- `chat_send`

`llm_transform` turns technical step output into a useful summary. `chat_send` writes output directly back into chat.

## RSS and news digests

RSS answers should not only say that hits exist. For digest prompts, ARIA returns title, source, date, short text, and a link when the feed provides one.

Examples:

- `summarize the latest it-security news`
- `what is new in security news`

## Statistics, tokens, and costs

`/stats` shows:

- total and average costs
- chat/embedding tokens by model
- requests by source
- pricing coverage
- unpriced models
- LiteLLM pricing status
- routing/gateway audit

ARIA uses the LiteLLM GitHub pricing list as the primary source without installing the LiteLLM Python package. The last good pricing list is cached locally. Custom prices and aliases can be managed in the pricing admin UI under `/stats`.

Important: internal LLM calls for routing, RSS summaries, guardrail decisions, and Experience Memory must go through central usage metering. If action details show `0 tokens` even though an LLM was clearly used, that is a bug.

## Updates

The safe public path is `aria-setup` / managed Compose. The update helper refreshes only the `aria` service and intentionally leaves Qdrant, SearXNG, Valkey, and volumes alone.

Before recreating ARIA, the host update helper preflights the intended host port. If another process or container owns the port, the update aborts before changing the running service.

## Security

ARIA is built for controlled environments:

- login and signed sessions
- secure store for API keys and tokens
- CSRF protection for browser requests
- guardrails for SSH/HTTP/File/Messaging actions
- one-click confirmation for outgoing actions
- no direct public-internet recommendation for the alpha

## Troubleshooting

### ARIA chooses the wrong target

- check connection aliases and short description
- use `/config/routing` or `/config/workbench/routing`
- inspect `routing_chain`, `semantic_llm`, `memory_hint`, and `explicit_ref` in chat details

### An action is blocked

- read the guardrail reason in Details
- check whether the action is read-only
- mutating actions intentionally need tighter policies or confirmation

### Costs look wrong

- open `/stats`
- check pricing coverage
- run `Refresh prices`
- add model aliases for provider/proxy names

## Where to read more

- `/help?doc=quick-start`
- `/help?doc=memory`
- `/help?doc=connections`
- `/help?doc=skills`
- `/help?doc=pricing`
- `/help?doc=security`
- `/help?doc=releases`
