# ARIA - Technical Feature List

Stand: 2026-04-07

Zweck:
- technische, faktische Feature-Zusammenfassung für GitHub, Releases, README-Überarbeitung und spätere externe Texte
- bewusst **kein Marketingtext**, sondern ein belastbarer Produkt-/Technik-Snapshot

## Produktkern

- Browser-first AI Assistant mit Chat-UI
- lokaler/self-hosted Betrieb im LAN, Homelab oder auf einem separaten Docker-Host
- modularer Zugriff auf echte Systeme über konfigurierte Connections
- Memory mit Qdrant
- Custom Skills als importierbare JSON-Manifeste
- Admin-Modus für Systemkonfiguration, User-Modus als reduzierte Arbeitsansicht
- Statistiken/Health/Token-/Kostenübersicht direkt im UI

## Chat

- Chat-UI unter `/`
- serverseitiges Rendering mit FastAPI + Jinja2
- Message-Details pro Antwort:
  - Intent / Skill / Capability
  - Token-Anzahl
  - Kosten in USD, sofern Modell-Pricing bekannt ist
  - Laufzeit
- Typing-/Thinking-Indikator
- Chat-History persistiert
- Fehlerpfade mit nutzerlesbaren Meldungen statt stiller Fallbacks, z. B. bei leerem LLM-Output

## Routing / Capability Layer

- deterministisches Keyword-/Capability-Routing für zentrale Intents
- Memory-Intents:
  - `memory_store`
  - `memory_recall`
  - `memory_forget`
  - `web_search`
  - `chat`
- Capability-Routing für Verbindungsaktionen wie:
  - Feed lesen
  - Remote Files lesen/schreiben
  - Discord/Webhook senden
  - HTTP API Requests
  - Mail / MQTT
- Custom-Skill-Routing hat Vorrang vor generischem Capability-Fallback, wenn ein klar passender Skill existiert
- Connection-Auflösung nutzt Ref, Titel, Kurzbeschreibung, Aliase und Tags

## Memory

- Qdrant-Backend für semantische Erinnerungssuche
- nutzerbezogene Memory-Trennung über `user_id`
- Memory Store / Recall / Forget
- gewichtetes Multi-Collection-Recall über Facts, Preferences, Sessions und Knowledge mit Typ-Gewichten und Session-Zeitabfall
- Auto-Memory für normale Chat-Pfade konfigurierbar
- Auto-Memory persistiert flüchtige Einmalfragen/Action-Prompts nicht mehr pauschal als neuen Session-Kontext
- Capability-Ergebnisse werden bewusst nicht pauschal automatisch in Memory geschrieben; für dauerhaft relevante Zustände sind später gezielte Summary-/State-Memory-Flows vorgesehen
- Memory-Seite im UI:
  - Memories anzeigen
  - suchen
  - editieren
  - löschen
  - JSON exportieren
  - Maintenance anstoßen
- Dokument-RAG v1 direkt in `Memory`:
  - Upload von `txt`, `md` und `pdf` mit eingebettetem Text
  - Import in separate Dokument-Collections `aria_docs_*`
  - sichtbarer Ingest-/Chunking-Status im Upload-Flow
  - Upload-Hinweis resetet nach erfolgreichem Seiten-Reload sauber
  - Dokument-Chunks als eigener UI-Typ `document`
  - interner Dokument-Guide-Index mit Summary + Stichworten für gezielteren Chat-Recall
  - Chat-Details zeigen die verwendeten Dokument-Quellen mit Collection und Chunk-Referenz
  - Embedding-Wechsel in `/config/embeddings` werden bei vorhandenem Memory bewusst bestätigt statt still übernommen
  - Memory- und Dokumenteinträge tragen einen Embedding-Fingerprint, damit Recall und RAG keine alten und neuen Embedding-Generationen mischen
- `Memory` gruppiert Einträge zusätzlich nach Typ und bietet klickbare Typ-Kacheln für schnellere Navigation bei vielen Einträgen
- `Memory Map` zeigt Dokumente gruppiert nach Dokumentname:
  - Chunk-Anzahl
  - Ziel-Collection
  - Vorschau
  - ganzes Dokument aus Qdrant entfernen
- Session-Rollups werden jetzt mit expliziten Metadaten fuer `week` und `month` erzeugt
- `Memory Map` zeigt diese Rollups als eigene Wochen-/Monats-Sicht mit Zeitraum und Quellenanzahl
- leere Qdrant-Collections werden nach UI-Löschung und Chat-Forget aufgeräumt
- Qdrant-Status und Qdrant-DB-Größe werden in `Statistiken` angezeigt
- Update-Check kann bei GitHub-API-Rate-Limits auf den öffentlichen Changelog als Fallback wechseln, damit `/updates` weiter nutzbar bleibt

## Custom Skills

- Custom Skills als JSON-Manifeste unter `data/skills`
- Skill Wizard im Browser:
  - Skill erstellen/bearbeiten
  - Steps hinzufügen
  - Steps duplizieren
  - Steps verschieben
  - Skill aktivieren/deaktivieren
  - Skill löschen
- Skill Import/Export
- unterstützte Step-Typen u. a.:
  - `ssh_run`
  - `sftp_read`
  - `sftp_write`
  - `smb_read`
  - `smb_write`
  - `rss_read`
  - `discord_send`
  - `http_request`
  - `webhook_send`
  - `mqtt_publish`
  - `imap_read`
  - `smtp_send`
  - `llm_transform`
  - `chat_send`
- Sample-Skills für SSH/SFTP/SMB/Discord/RSS liegen unter `samples/skills`
  - darunter jetzt auch kompakte Vorlagen für RSS-Headlines im Chat, SSH-Disk-Usage und SFTP-Config-Preview

## Connections

ARIA hat dedizierte Config-Seiten, Health-/Test-Flows, Statusanzeigen und Routing-Metadaten für:

- `SSH`
- `SFTP`
- `SMB`
- `Discord`
- `RSS`
- `HTTP API`
- `SearXNG`
- `Webhook`
- `SMTP`
- `IMAP`
- `MQTT`

### Connection UX

- `Neu` für neue Profile
- Klick auf eine bestehende Statuskarte öffnet direkt den Edit-Modus
- Connection-Test/Live-Status pro Profil
- optionale Kontext-Metadaten:
  - Titel
  - Kurzbeschreibung
  - Aliase
  - Tags
- diese Metadaten helfen dem Router bei natürlicherer Connection-Auswahl

## SSH / SFTP / SMB

- SSH-Profilverwaltung mit Host/User/Port/Auth/Timeout
- SSH-Key-Erzeugung im Container über `ssh-keygen`
- SFTP kann SSH-Daten aus bestehenden SSH-Profilen übernehmen
- SFTP Remote-Lesen/Schreiben über Skills/Capabilities
- SMB Share-Zugriff über konfigurierte SMB-Profile
- verständlichere Fehlermeldungen bei fehlender SSH-Keygen-Runtime oder Connection-Problemen

## Discord / Webhook / API

- Discord Webhook-Verbindungen
- Testposts und Skill-Ziel-Freigabe konfigurierbar
- Discord Skill-Error-Alerts mit gekürzten/sanitized Fehlerdetails
- HTTP-API- und Webhook-Connections mit eigenen Profilen
- `ARIA_PUBLIC_URL` / `aria.public_url` für externe Links in Messages statt Docker-Bridge-IP

## Websuche / SearXNG

- dedizierte `SearXNG`-Connection mit eigener Config-Seite
- ARIA nutzt SearXNG bewusst nur ueber die JSON-Search-API
- die Base-URL ist im typischen Stack fest `http://searxng:8080` und muss nicht pro Profil neu eingegeben werden
- sinnvolle Defaults fuer:
  - Sprache
  - SafeSearch
  - Kategorien
  - Engines
  - Zeitbereich
  - Maximalzahl Treffer
- Profil-Metadaten wie Name, Aliase und Tags helfen beim Routing fuer unterschiedliche Suchprofile wie `youtube` fuer Videos oder `startpage` fuer Buecher
- Chat kann explizite Websuche-Anfragen routen, z. B. `websuche ...`
- Chat-Details zeigen Web-Quellen mit Titel, URL und Engine
- Stack-Dateien koennen SearXNG als separaten Dienst neben ARIA und Qdrant mitfuehren

## RSS / OPML

- RSS-Verbindungen einzeln verwaltbar
- OPML Import/Export
- pro Feed:
  - Titel
  - Kurzbeschreibung
  - Aliase
  - Tags
  - Gruppe/Kategorie
  - `Jetzt pingen`
- LLM-gestützte RSS-Metadaten-Vorschläge über `Check mit LLM`
- LLM-gestützte Gruppierung/Kategorisierung für Feeds ohne manuell gesetzte Gruppe
- manuell gesetzte RSS-Gruppen werden von LLM-Gruppierung nicht überschrieben
- globale RSS-Ping-Time für alle Feeds
- Feed-Fälligkeit wird pro Feed stabil per Hash-Offset gestaffelt
- RSS-Statuskarten nutzen Cache/letzten bekannten Stand statt synchronen Live-Ping bei jedem Seitenaufruf
- RSS-Suche über Titel/URL/Ref/Gruppe/Tags
- RSS-Kategorien einklappbar und alphabetisch sortiert
- RSS-URL-Dedupe mit URL-Normalisierung
- bessere Fehlermeldung, wenn eine URL JSON statt RSS/Atom-XML liefert

## Security / Access

- Login-System mit erstem Bootstrap-User als Admin
- Admin-Modus vs User-Modus
- role-/mode-abhängiger Zugriff auf Config-Seiten
- Secrets in lokalem Secure Store
- Guardrail-Profile für riskantere Actions, u. a. SSH-Commands
- Admin-On/Off als UI-Schalter

## Statistiken / Operations

- `Statistiken` unter `/stats`
- Release-/Versionsanzeige
- Token-Statistik
- Kosten-Statistik
- Resource-Status:
  - ARIA RAM
  - Qdrant DB Größe
- Startup Preflight
- Systemzustand
- Live-Status aller konfigurierten Verbindungen
- Aktivitäten & Runs direkt in `Statistiken`
- manuelles Pricing-Refresh für:
  - OpenAI / Anthropic via LiteLLM-Preisliste
  - OpenRouter via OpenRouter Models API

## UI / Personalization

- browser-first UI ohne React/Node-Buildchain
- i18n Deutsch/Englisch
- Prompt Studio
- Theme-Auswahl
- Background-Auswahl
- aktuelle Themes:
  - Matrix Green
  - Sunset Amber
  - Harbor Blue
  - Paper Ink
  - CyberPunk Pulse
  - 8-Bit Arcade
  - Amber CRT
  - Deep Space
- responsive UI, inklusive iPhone-/Safari-Fixes

## API / Runtime / Deployment

- FastAPI-App mit Web-UI und OpenAI-kompatiblem Endpoint `POST /v1/chat/completions`
- `/health` Endpoint
- YAML-Konfiguration über `config/config.yaml`
- ENV-Overrides mit `ARIA_*`
- `aria.sh` für lokale Steuerung:
  - start
  - stop
  - status
  - logs
  - maintenance
  - autostart
- Dockerfile + docker compose + Portainer-Stack-Beispiele
- Container-Volumes für:
  - `config`
  - `prompts`
  - `data`
- EntryPoint initialisiert leere Volumes aus eingebauten Defaults
- bewährter dev -> prod Update-Flow über versioniertes TAR + `aria-pull`

## Aktuelle ALPHA-Grenzen

- ARIA ist aktuell primär ein **Personal Single-User System**
- noch kein vollständiges Multi-User-/RBAC-Modell für geteilte Skills/Connections/Memories
- kein offener Public-Internet-Betrieb empfohlen
- Capability-Ergebnisse laufen bewusst nicht pauschal durch denselben Auto-Memory-Pfad wie normale Chat-/LLM-Antworten
- einige größere Integrationen sind bewusst noch Backlog, nicht aktueller Release-Scope
