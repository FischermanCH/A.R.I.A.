# Rezepte

ARIA-Rezepte sind kuratierte JSON-Manifeste mit strukturierten Steps, Routing-Metadaten und guardrail-bewusster Ausfuehrung. Legacy-Skill-Manifeste bleiben fuer Kompatibilitaet lesbar, aber Produktbegriffe und neue Beispiele sind recipe-first.

Aktuelle Capability-Familien umfassen:

- SSH
- SFTP
- SMB
- RSS
- Discord
- Webhook
- HTTP API
- SMTP / IMAP
- MQTT
- LLM-Transform-Steps

Nuetzliche Referenzen:

- [`docs/product/feature-list.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/product/feature-list.md)
- [`samples/recipes/`](https://github.com/FischermanCH/A.R.I.A./tree/main/samples/recipes)
- [`samples/skills/`](https://github.com/FischermanCH/A.R.I.A./tree/main/samples/skills) fuer Legacy-/Backcompat-Beispiele

Gerade fuer Release-Tests sind Sample-Rezepte hilfreich, weil sie wiederholbare Workflows liefern.

Aktuelle Sample-Richtungen:

- read-only SSH-Checks wie Health und Disk-Usage
- RSS nach Chat oder RSS nach Discord
- einfache SFTP-Lese- und Config-Preview-Beispiele
- SMB-Lese- und Listen-Beispiele
