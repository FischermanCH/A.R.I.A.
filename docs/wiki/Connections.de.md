# Connections

Connections sind explizite Profile zu externen Systemen.

Aktuell unterstuetzte Familien sind:

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

Die Routing-Qualitaet steigt, wenn Connection-Metadaten gepflegt sind:

- Titel
- Kurzbeschreibung
- Aliase
- Tags

`SearXNG` wird als eigener self-hosted Suchdienst im Stack behandelt.
ARIA nutzt bewusst nur die JSON-Search-API und kann Web-Quellen direkt in den Chat-Details ausweisen.

Die Stack-URL ist fuer SearXNG-Profile in ARIA normalerweise fest:

- `http://searxng:8080`

Pro Profil pflegst du vor allem:

- Profilname
- Titel / Kurzbeschreibung / Aliase / Tags fuer Routing
- Sprache
- SafeSearch
- wenige sinnvolle Kategorien
- wenige bevorzugte Engines
- Trefferzahl und Zeitbereich

Neuere persoenliche / wissensnahe Verbindungstypen:

- `Beobachtete Webseiten`
  - fuer einzelne Quellen ohne RSS-Feed
  - URL-first anlegen
  - Titel, Kurzbeschreibung, Tags und Gruppe koennen automatisch vorgeschlagen werden
- `Google Calendar`
  - read-only ausgelegt
  - eigener gefuehrter Setup-Flow ueber Google Cloud + OAuth Playground
  - gedacht fuer Fragen wie `was steht heute an?`

Nuetzliche Referenzen:

- [`docs/help/help-system.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/help/help-system.md)
- [`docs/product/feature-list.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/product/feature-list.md)
- [`docs/setup/setup-overview.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/setup/setup-overview.md)
