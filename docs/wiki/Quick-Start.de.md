# Quick Start

ARIA ist darauf ausgelegt, schnell vom Container zur nutzbaren Web-Oberfläche zu kommen.

## Empfohlener Weg

1. mit `aria-setup` oder bewusstem Docker Compose Setup installieren
2. Web-UI öffnen
3. ersten Bootstrap-User anlegen
4. Chat-LLM und Embeddings konfigurieren
5. `/stats` öffnen und Preflight, Pricing Coverage und Gateway Audit prüfen
6. erste Connections unter `/connections/types` anlegen
7. einen einfachen Prompt testen
8. `/help?doc=chat`, `/help?doc=navigation` und `/help?doc=agentic` öffnen, wenn du Queue, Menüs, Bestätigungen und Details verstehen willst

## Sinnvolle erste Prompts

- `ist mein dns server ok`
- `check mal ob meine server noch genug freien festplatten platz haben`
- `prüf ob die api erreichbar ist`
- `fass mir die neuesten IT-Sicherheitsnachrichten zusammen`

## Erste Alltagsbereiche

- `/notes` für Markdown-Notizen
- `/memories` für den grafischen Gedächtnis-Browser und `/memories/import` für Dokumentimporte
- `/connections/types` für externe Systeme
- `/recipes` für den Rezepte-Hub und `/recipes/mine` für gespeicherte Rezepte
- [LLM-Diagnose öffnen](/config/llm/debug) für Action-/Routing-Dry-runs

## Deployment-Hinweise

- LAN/VPN wird empfohlen
- direkter Public-Internet-Betrieb ist für die Alpha nicht empfohlen
- Managed Installs sollten den Update-Helper nutzen statt beliebige Container manuell zu ersetzen
- Volumes und Compose-Projektnamen stabil halten

Referenzen:

- [`README.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/README.md)
- [`docs/setup/setup-overview.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/setup/setup-overview.md)
