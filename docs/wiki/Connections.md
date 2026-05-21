# Connections

Connections are explicit profiles to external systems. They are one of the most important inputs for ARIA's agentic routing.

Supported families include:

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

## Metadata matters

Maintain:

- title
- short description
- aliases
- tags
- notes about what the connection is for

ARIA uses this information for deterministic routing, semantic routing, and LLM action context. Good metadata makes prompts like `my dns server`, `management server`, or `security news` much more reliable.

## Agentic Action Flow

For action prompts, ARIA can combine connection metadata, Qdrant candidates, recent context, and LLM drafts. Policy and guardrails still decide whether the action is allowed, asks for confirmation, or is blocked.

## Examples

- SSH: read-only health and disk checks
- SMB/SFTP: list or read files within allowed paths
- HTTP API: configured health endpoint checks
- Discord/Webhook: outgoing messages with confirmation
- RSS: digests with title, source, date, summary, and link
- SearXNG: open web search via the separate stack service
- Google Calendar: read-only event queries via the secret iCal address from Google Calendar; no Google Cloud/OAuth setup in the current alpha end-user path

Useful references:

- [`docs/help/alpha-help-system.en.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/help/alpha-help-system.en.md)
- [`docs/product/feature-list.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/product/feature-list.md)
- [`docs/setup/setup-overview.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/setup/setup-overview.md)
