# Connections

Connections sind explizite Profile zu externen Systemen. Sie sind eine der wichtigsten Grundlagen fuer ARIAs agentisches Routing.

Unterstuetzte Familien:

- SSH
- SFTP
- SMB
- RSS
- Beobachtete Webseiten
- Discord
- HTTP API
- SearXNG
- Google Calendar
- Webhook
- SMTP
- IMAP
- MQTT

## Metadaten sind wichtig

Pflege:

- Titel
- Kurzbeschreibung
- Aliase
- Tags
- Notizen zum Zweck der Verbindung

ARIA nutzt diese Informationen fuer deterministisches Routing, semantisches Routing und LLM-Action-Kontext. Gute Metadaten machen Prompts wie `mein dns server`, `management server` oder `security news` deutlich zuverlaessiger.

## Agentic Action Flow

Bei Action-Prompts kann ARIA Connection-Metadaten, Qdrant-Kandidaten, aktuellen Kontext und LLM-Drafts kombinieren. Policy und Guardrails entscheiden weiterhin, ob die Aktion erlaubt ist, bestaetigt werden muss oder blockiert wird.

## Beispiele

- SSH: read-only Health- und Disk-Checks
- SMB/SFTP: Dateien innerhalb erlaubter Pfade listen oder lesen
- HTTP API: konfigurierte Health-Endpunkte pruefen
- Discord/Webhook: ausgehende Nachrichten mit Bestaetigung
- RSS: Digests mit Titel, Quelle, Datum, Kurztext und Link
- SearXNG: offene Websuche ueber den separaten Stack-Service

Nuetzliche Referenzen:

- [`docs/help/alpha-help-system.de.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/help/alpha-help-system.de.md)
- [`docs/product/feature-list.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/product/feature-list.md)
- [`docs/setup/setup-overview.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/setup/setup-overview.md)
