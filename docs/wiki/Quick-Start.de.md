# Quick Start

ARIA ist darauf ausgelegt, schnell vom Container zur nutzbaren Web-Oberflaeche zu kommen.

Empfohlener Weg:

1. ARIA mit `aria-setup` oder manuellem Docker Compose starten
2. die Web-Oberflaeche oeffnen
3. den ersten Bootstrap-Benutzer anlegen
4. konfigurieren:
   - Chat-LLM
   - Embeddings
   - Memory
   - die ersten Connections unter `/connections/types`
5. den ersten Prompt testen

Sinnvolle erste Alltagsbereiche nach dem Setup:

- `/notes` fuer schnelle Markdown-Notizen
- `/connections/types` fuer RSS, Beobachtete Webseiten oder Google Calendar
- `/memories` fuer semantische Erinnerung und Dokumente

Wichtige Deployment-Referenzen:

- [`README.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/README.md)
- [`docs/setup/setup-overview.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/setup/setup-overview.md)

Hinweise:

- ARIA ist aktuell primär ein persoenliches Single-User-System
- LAN / VPN wird empfohlen
- direkter Public-Internet-Betrieb ist fuer die aktuelle ALPHA-Linie nicht empfohlen
