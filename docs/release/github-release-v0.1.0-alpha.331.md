# ARIA 0.1.0-alpha331

This public alpha rollup promotes the internally tested `alpha299` to `alpha331` line into the public Docker/GitHub channel.

The main theme is a more teachable, more useful ARIA: chat can deliberately create review-only recipe candidates, chats can be archived into Notes, web/current-version questions are less likely to fall back to stale model knowledge, and the UI is calmer and faster while keeping runtime safety bounded.

## Highlights

- Chat Recipe Learn Mode: start a bounded learning run, let ARIA observe following chat turns, and stop it into a review-only Learned Recipe candidate. Nothing is activated automatically.
- Chat-to-Notes archive: save the current chat history as a Markdown Note from the chat toolbox or `/chat note`.
- Notes workspace polish and performance: faster folder/board navigation, lightweight previews, calmer editor styling, mobile-friendly stacking, collapsible folder management, and contained long titles, URLs, tags, and folder labels.
- Stronger source hygiene: general how-to/product/version questions filter weak or mixed local Memory/RAG context unless the user explicitly asks for local notes, documents, or memory.
- Web freshness: current version/release/setup questions and explicit internet research requests can automatically add Web Search context before the final chat answer.
- Clickable `/help` home: Quick Start, Memory, Connections, Recipes, Releases and Upgrades, Pricing, Security, and local help-system docs are linked from the help landing page.
- LLM-first routing improvements: ambiguous operational language can stay in normal chat when it is advice/context, while explicit bounded actions still route to the relevant connection.
- Faster multi-target SSH health checks with bounded parallel execution and better role/group scoping for prompts such as developer-server checks.
- Runtime transparency: `/stats` includes improved Operator Guardrail details, cost/billing-period controls, Runtime Health, and third-party sidecar visibility.
- Refreshed ARIA logo/favicons and a cleaner global busy animation.

## Safety

- Recipe Learn Mode creates review-only candidates. Promotion remains an explicit admin decision.
- Learned candidates remain bounded by runtime policy, confirmations, and active Guardrails.
- Local RAG filtering only applies to general chat. Explicit questions about local notes, documents, or memory still keep local context visible.
- Web freshness does not bypass policy. It only adds source context for the final chat answer.
- Guardrail and policy runtime behavior remains deterministic: LLMs can draft and summarize, but policy/Guardrails decide execution.
- Normal managed updates continue to recreate only the `aria` service and leave Qdrant, SearXNG, Valkey, and volumes untouched.

## Upgrade Notes

- Docker tags:
  - `fischermanch/aria:0.1.0-alpha.331`
  - `fischermanch/aria:alpha`
- Digest: `sha256:6b5980377912788fababc99359e35301fd16ec7af58ba5c85320c836be0f2d16`
- Managed installs should use `/updates` or `./aria-stack.sh update`.
- Fixed-tag installs can use `docker/aria-host-update.sh update --project <name> --target-image fischermanch/aria:0.1.0-alpha.331`.
- No deliberate stack-layout change is required for normal managed installs.
- A hard browser refresh is recommended because this release includes UI, CSS, logo, favicon, help, and chat-toolbox changes.

## What To Test After Upgrade

- `/health` returns `ok`.
- `/stats` shows release metadata, Runtime Health, cost estimates, Operator Guardrail details, and no release errors.
- `/help` home links open Quick Start, Memory, Connections, Recipes, Releases and Upgrades, Pricing, Security, and help-system pages.
- `wie verbinde ich codex von openai mit meinem ssh developement server` answers as normal chat, not as an SSH action, and does not show unrelated local document sources.
- `welche version von claude code ist momentan aktuell`, followed by `suche im internet nach der neusten version`, keeps the web-search topic on Claude Code.
- `ich suche ein cyberdeck zum selbst bauen, kannst du mal im internet recherchieren was es so gibt` triggers Web Search freshness instead of answering only from model memory.
- `was steht in meinen notizen zu ARIA?` still uses local Notes/Memory context and does not route to a connection action.
- `/lernen start`, one successful chat action, then `/lernen stop` creates a review-only Learned Recipe candidate.
- `/lernen abbrechen` discards the explicit learning run without also updating the normal auto-learning path.
- `Chat als Notiz speichern` or `/chat note` creates a Note under `Chats/YYYY-MM`.
- `/notes` folder switching and note opening remain responsive; desktop and mobile layouts stay within the viewport.
- The ARIA header logo/favicons show the refreshed logo, and the busy indicator animates only the logo emblem.
- Calendar, SFTP/SMB list, webhook deny, and HTTP API Guardrail block flows still behave as before.

Full technical details are in `CHANGELOG.md`.
