# ARIA - Technical Feature List

Stand: 2026-04-03

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
- leere Qdrant-Collections werden nach UI-Löschung und Chat-Forget aufgeräumt
- Qdrant-Status und Qdrant-DB-Größe werden in `Statistiken` angezeigt

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

## Connections

ARIA hat dedizierte Config-Seiten, Health-/Test-Flows, Statusanzeigen und Routing-Metadaten für:

- `SSH`
- `SFTP`
- `SMB`
- `Discord`
- `RSS`
- `HTTP API`
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
