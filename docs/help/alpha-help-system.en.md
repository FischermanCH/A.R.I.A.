# ARIA Alpha Help

Updated: 2026-04-07

This page is the practical short help for ARIA Alpha. It explains the main areas in a way that should let you start working directly.

## What ARIA Alpha is right now

ARIA is currently a personal self-hosted AI assistant for LAN, VPN, and homelab usage.

Good fit for:

- a browser-based personal AI workspace
- Memory with Qdrant
- Notes as a separate Markdown workspace
- SSH / SFTP / SMB / RSS / Discord / HTTP API / Webhook / Mail / MQTT
- Custom Skills that automate multi-step flows

Not the current target:

- direct public internet exposure
- a full multi-user / RBAC system
- hands-off enterprise deployment

## First start

On first start, you create the first user. That user automatically becomes admin.

After that, check these areas first:

1. `/config/llm` - chat model and API access
2. `/config/embeddings` - embedding model for Memory
3. `/stats` - preflight, Qdrant, model status, logs
4. `/config` - connections to your systems
5. `/skills` - import Custom Skills or build them in the wizard

## Admin mode and user mode

ARIA has two working modes:

- **User mode**: reduced daily working view
- **Admin mode**: additional system, routing, security, and config pages

If config pages seem missing, open `/config/users` and check whether **Admin active** is enabled.

## Chat and message details

You can chat normally, or trigger connections and skills through natural prompts.

Under **Details** for each response, you can see:

- which intent / skill / capability was used
- token count
- USD cost, if ARIA knows pricing for that model
- runtime

If cost shows `n/a`, you are either using a local model without pricing, or the exact model name is not in the pricing catalog yet.

## Memory

ARIA uses Qdrant for semantic memory.

Important:

- **Facts** and **Preferences** are more long-term
- **Context / Session** is more like day-level working memory
- transient one-off questions should ideally **not** be stored as memory noise
- raw capability snapshots from RSS / SMB / SSH are **not automatically** written to Memory by default

On `/memories`, you can:

- inspect memories
- search
- edit
- delete
- export as JSON

If you explicitly want something forgotten, you can ask in chat with phrasing like `forget ...`, or delete it directly on `/memories`.

Important distinction:

- `Memory` is ARIA's semantic recall layer
- `Notes` are your intentionally written Markdown workspace under `/notes`
- notes are indexed in Qdrant for search, but product-wise they are **not** part of the Memory area

## Notes

Under `/notes`, you get a standalone workspace:

- folder navigation on the left, like a small explorer
- a note board with previews on the right
- the editor below for the selected note

Notes are intentionally:

- editable
- exportable as Markdown
- separate from Memory

ARIA can also create notes from chat, for example with prompts like:

- `note down ...`
- `keep this note ...`

## Connections

You manage external connections under `/config`.

Basic flow:

- **New** creates a new profile
- clicking an existing status card opens that profile in edit mode
- title, short description, aliases, and tags help ARIA route free-form requests

The better your titles / aliases / tags are, the more reliably ARIA can pick the right connection from natural chat prompts.

### SSH / SFTP / SMB

- SSH defines how ARIA reaches a server
- SFTP can reuse connection data from an existing SSH profile
- SMB connects ARIA to a share
- Guardrails can restrict allowed actions or paths

### Discord / Webhook / HTTP API

- Discord is currently mainly a webhook target and skill output channel
- on Discord connections, you can enable test posts and `Allow as skill target`
- HTTP API and Webhook profiles are meant for targeted request/send flows

### SearXNG / Web Search

- for ARIA, SearXNG is a separate search service in the stack, similar to how Qdrant stays separate
- ARIA only uses the SearXNG JSON search API, not SearXNG code inside ARIA itself
- ARIA now uses the in-stack URL as a fixed default:
  - `http://searxng:8080`
- per profile you mainly configure:
  - language
  - SafeSearch
  - a few categories
  - a few preferred engines
  - result count
  - time range
- clear profile names and tags help routing, for example `youtube` for videos or `startpage` for books
- in chat you can then use explicit prompts like `search the web ...` or `web search ...`

### Watched Websites

- for pages without an RSS feed
- you mainly provide the URL
- ARIA can suggest title, short description, tags, and a group automatically
- later these sources combine well with web search and notes

### Google Calendar

- the first personal `read-only` daily-use path
- own setup flow on the connection page with Google links per step
- meant for everyday questions like:
  - `what is on my calendar today?`
  - `when is my next event?`

### RSS

RSS is especially useful in ARIA if you want to curate many feeds and let an LLM summarize or filter them.

On the RSS page, you can:

- add feeds one by one
- import / export OPML
- organize feeds by groups/categories
- run `Ping now` for one feed
- use `Check with LLM` to suggest title, short description, aliases, and tags
- use `Refresh categories with LLM` to auto-group feeds that do not have a manually set category

Notes:

- the global ping interval applies to all RSS feeds
- ARIA staggers feed due-times internally so they do not all ping at once
- the RSS overview mainly shows the last known cached status
- if a URL returns JSON instead of RSS/Atom XML, add it as an HTTP API connection instead

## Skills

Custom Skills are JSON manifests with an ordered list of steps.

In the Skill Wizard, you can:

- create / edit skills
- add, duplicate, reorder, and remove steps
- enable / disable skills
- import / delete skills

Important step types:

- `ssh_run`
- `sftp_read` / `sftp_write`
- `smb_read` / `smb_write`
- `rss_read`
- `llm_transform`
- `discord_send`
- `chat_send`

### `llm_transform` vs `chat_send`

- `llm_transform` takes technical step output and asks an LLM to turn it into a cleaner summary or selection
- `chat_send` writes output directly back into the chat

Useful placeholders in skill prompts:

- `{prev_output}` = output of the immediately previous step
- `{s1_output}`, `{s2_output}`, ... = targeted access to earlier step outputs
- `{query}` = the original chat request

That means you can fetch several RSS feeds in multiple `rss_read` steps and then build one curated morning briefing in a single `llm_transform` step.

## Bundled samples

ARIA ships sample skills and sample connections.

- on `/skills`, you can import bundled sample skills directly
- on `/config`, you can import bundled sample connections directly

These samples are templates on purpose. In real use, you usually need to adjust refs, hosts, URLs, or Discord webhooks to your own environment.

## Statistics

On `/stats`, you can see:

- current ARIA release/version
- token and cost statistics
- ARIA RAM and Qdrant DB size
- Startup Preflight
- System Health
- live status of all configured connections
- Activities & Runs

The green/yellow/red lamps should quickly tell you what is healthy and where to investigate.

### Refresh pricing

If you use OpenAI / Anthropic / OpenRouter and want cost numbers, run **Refresh pricing** on `/stats`.

Local models like Ollama may intentionally show no USD pricing.

### Reset statistics

Stats reset clears token/cost/activity data. It does **not** delete your Memories, Skills, or Connections.

## Security

For Public Alpha, the rule is simple:

- do **not** expose ARIA directly to the open internet
- use LAN or VPN / WireGuard instead
- keep Admin mode enabled only when you actually need configuration access
- use guardrails and least-privilege accounts for SSH / SMB / SFTP
- API keys and secrets belong in the Secure Store / local secret config, not in public docs or Git

## Troubleshooting

### Chat responses are broken or not useful

Check:

- `/config/llm`
- `/config/embeddings`
- `/stats` -> Preflight and System Health

If responses fail with `finish_reason=length`, your `Max Tokens` value is probably too low.

### Memory feels empty or weak

Check:

- is Qdrant reachable?
- is the embedding model configured correctly?
- is Auto-Memory enabled?
- do matching facts/preferences actually exist in `/memories`?

### A skill does not trigger

Check:

- is the skill enabled?
- are trigger phrases / description / aliases specific enough?
- is a generic prompt causing routing ambiguity?
- do the connection refs in the skill match real connections?

### A connection test is red

Check:

- host / URL / port / credentials
- network reachability from inside the ARIA container
- guardrails / allowed actions
- for RSS: is it really RSS/Atom XML, not JSON?

## Where to read more

`/help` shows this short help.

`/product-info` adds:

- product overview
- feature list
- architecture
