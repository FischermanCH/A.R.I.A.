# Quick Start

ARIA ist darauf ausgelegt, schnell vom Container zur nutzbaren Web-Oberflaeche zu kommen.

## Empfohlener Weg

1. mit `aria-setup` oder bewusstem Docker Compose Setup installieren
2. Web-UI oeffnen
3. ersten Bootstrap-User anlegen
4. Chat-LLM und Embeddings konfigurieren
5. `/stats` oeffnen und Preflight, Pricing Coverage und Gateway Audit pruefen
6. erste Connections unter `/connections/types` anlegen
7. einen einfachen Prompt testen

## Sinnvolle erste Prompts

- `ist mein dns server ok`
- `check mal ob meine server noch genug freien festplatten platz haben`
- `pruef ob die api erreichbar ist`
- `mach mir eine zusammenfassung der letzten it-security news`

## Erste Alltagsbereiche

- `/notes` fuer Markdown-Notizen
- `/memories` und `/memories/map` fuer Memory und Dokumente
- `/connections/types` fuer externe Systeme
- `/recipes` fuer Automationen
- `/config/workbench/routing` fuer Action-/Routing-Dry-runs

## Deployment-Hinweise

- LAN/VPN wird empfohlen
- direkter Public-Internet-Betrieb ist fuer die Alpha nicht empfohlen
- Managed Installs sollten den Update-Helper nutzen statt beliebige Container manuell zu ersetzen
- Volumes und Compose-Projektnamen stabil halten

Referenzen:

- [`README.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/README.md)
- [`docs/setup/setup-overview.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/setup/setup-overview.md)
