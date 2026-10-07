# ARIA Alpha Help

Updated: 2026-07-09 / Public Alpha `0.1.0-alpha437`

This is the practical short help for ARIA Alpha. It reflects the current state after the larger move from legacy skills to recipes, LLM-assisted action planning, and controlled execution.

## What ARIA Alpha is right now

ARIA is a personal self-hosted AI assistant for LAN, VPN, and homelab usage.

Good fit for:

- a browser-based personal AI workspace
- memory and document RAG with Qdrant
- notes as a Markdown workspace
- Chat Prompt Queue with editable and reorderable waiting prompts
- visible Pending Confirmations for confirmation-required actions
- generated section navigation for the header, account menu, Settings, Admin, Memory, Recipes, and Connections
- safe connections to SSH, SFTP, SMB, RSS, Discord, HTTP API, Webhook, Mail, MQTT, and Google Calendar
- recipe-first automation with guardrails
- Agentic Operator Flow: ARIA understands natural prompts, plans bounded steps, lets policy/guardrails decide, executes, and exposes details

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
5. `/recipes` and `/recipes/mine` - import, review, or build recipes

## Admin mode and user mode

ARIA has two working modes:

- **User mode**: reduced daily-use view
- **Admin mode**: additional system, routing, security, workbench, and config pages

If technical configuration pages are missing, check the account menu or `/config/admin-mode` and enable **Extended view**.

## Chat, actions, and details

You can chat normally or give natural work requests, for example:

- `is my dns server ok`
- `check whether my servers still have enough disk space and tell me if action is needed`
- `check whether the api is reachable`
- `show me the folders on the Example Share share`
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

The Chat Prompt Queue lets you keep submitting prompts while ARIA is still working. Waiting prompts stay visible, can be reordered, edited, or removed, and then run sequentially. ARIA does not run multiple runtime requests in parallel and the queue is not persisted across reloads.

## Confirmations

Outgoing or potentially impactful actions can require `ask_user`. ARIA then shows a Pending Confirmation in chat and in the queue.

Examples:

- send a Discord message
- call a webhook
- future non-read-only actions

Pending Confirmations can be run, planned again, or discarded. Expired or invalid confirmations are not executed automatically. Read-only actions such as `df -h`, health checks, or RSS reads can run directly when guardrails allow them.

## Memory

ARIA uses Qdrant for semantic memory.

Important:

- **Facts** and **Preferences** are long-term
- **Session context** and rollups help with work continuity
- **Document collections** power RAG uploads
- **Experience Memory** stores successful safe action patterns as planner context, not as blind executor automation
- transient SSH/RSS/SMB snapshots are not written into Memory by default

On `/memories`, the graphical Memory browser shows collections, documents, entries, chunks, and semantic proximity. `/memories/import` imports documents and memory data; `/memories/maintenance` is for technical maintenance and review artifacts.

## Notes

`/notes` is a standalone Markdown workspace with folder navigation, cards, an editor, and a dense list view. Notes can be moved from cards or the editor into other folders; list view supports multi-select bulk move. Notes are intentionally separate from Memory, but can be indexed for search.

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
- provider-native web search
- Google Calendar read-only
- SMTP / IMAP / MQTT

In the current alpha end-user path, Google Calendar does not use Google Cloud or OAuth sign-in. Copy the `Secret address in iCal format` from Google Calendar under `Settings > Integrate calendar`, paste it into ARIA, and save the connection. The URL is a secret and is stored server-side in the Secure Store. This lets ARIA read events, but not modify calendars.

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

The safe public path is `aria-setup` / managed Compose. The update helper recreates only `aria` while leaving Qdrant and all volumes alone.

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
- inspect the connection inventory and chat details for the resolved target
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
- `/help?doc=chat`
- `/help?doc=navigation`
- `/help?doc=memory`
- `/help?doc=notes`
- `/help?doc=connections`
- `/help?doc=skills`
- `/help?doc=agentic`
- `/help?doc=pricing`
- `/help?doc=security`
- `/help?doc=releases`
