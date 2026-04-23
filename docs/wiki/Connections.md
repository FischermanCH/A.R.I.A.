# Connections

Connections are explicit profiles to external systems.

Supported families currently include:

- SSH
- SFTP
- SMB
- RSS
- Watched Websites
- Discord
- HTTP API
- SearXNG
- Google Calendar
- Webhook
- SMTP
- IMAP
- MQTT

Routing quality improves when connection metadata is maintained:

- title
- short description
- aliases
- tags

`SearXNG` is handled as a separate self-hosted search service in the stack.
ARIA uses only the JSON search API and can surface web sources directly in chat details.

The stack URL is usually fixed for SearXNG profiles in ARIA:

- `http://searxng:8080`

Per profile, you mainly manage:

- profile name
- title / short description / aliases / tags for routing
- language
- SafeSearch
- a few sensible categories
- a few preferred engines
- result count and time range

Newer personal / knowledge-oriented connection types:

- `Watched Websites`
  - for individual sources without an RSS feed
  - URL-first setup
  - title, short description, tags, and group can be suggested automatically
- `Google Calendar`
  - intentionally read-only for now
  - guided setup flow via Google Cloud + OAuth Playground
  - meant for questions like `what is on my calendar today?`

Useful references:

- [`docs/help/help-system.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/help/help-system.md)
- [`docs/product/feature-list.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/product/feature-list.md)
- [`docs/setup/setup-overview.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/setup/setup-overview.md)
