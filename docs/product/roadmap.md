# ARIA - Roadmap Snapshot

Stand: 2026-04-03

Zweck:
- GitHub-taugliche Übersicht, was im aktuellen Public-Alpha-Stand schon da ist
- klar zeigen, was bereits auf `dev` vorbereitet ist
- nachvollziehbar machen, was als nächstes geplant ist

## Bereits im aktuellen Alpha-Kern vorhanden

### Modular Connections
- SSH
- SFTP
- SMB
- Discord Webhooks
- RSS
- HTTP API
- Webhook
- SMTP
- IMAP
- MQTT

### Custom Skills
- JSON-basierte Skill-Manifeste
- Browser-Wizard zum Erstellen/Bearbeiten
- Steps duplizieren und sortieren
- Import/Export
- Sample-Skills unter `samples/skills/`

### Memory
- Qdrant als semantischer Memory-Store
- typisierte Collections für Facts / Preferences / Sessions / Knowledge
- gewichtetes Multi-Collection-Recall
- Auto-Memory mit stärkerem Filter gegen flüchtiges Prompt-Rauschen
- Forget + Cleanup leerer Collections
- Memory JSON Export

### UI / Ops
- Browser-first UI
- Admin-/User-Modus
- `Statistiken` mit Health, Tokens, Kosten, Preflight, Connection-Status und Activities
- `/help` und `/product-info`
- Themes, Backgrounds, i18n DE/EN

## Auf `dev` bereits für den nächsten Build vorbereitet

- Qdrant-DB-Größenanzeige robuster für separates Compose-/Portainer-Qdrant-Volume
- `/stats` Reset mit bewusster `RESET`-Bestätigung
- First-Run-/Admin-/User-Hinweise in Login-, Benutzer- und Security-UI
- iPhone-Fix für lange Debug-Session-IDs im Chat-Header
- CyberPunk Theme stärker Richtung Hot-Pink/Magenta
- Help-/Produktinfo-Doku direkt im UI angebunden
- `LICENSE` und `THIRD_PARTY_NOTICES.md`

## Geplant nach Public Alpha

### Memory 2.0
- Typed Auto-Memory weiter verfeinern
- Session Rollup Tag -> Woche -> Monat
- Memory Import / Migration
- Embedding-Modellwechsel / Reindex-Flow

### Knowledge / Research
- Dokument-Ingest eigener Dateien
- Websuche / Research-Flow mit Quellenanzeige

### Smart Home / Integrationen
- Home Assistant Integration
- State-/Event-Kompression in Qdrant
- ARIA als lernende Logikschicht über Home Assistant

### Channels / Realtime
- Discord als echter Channel, nicht nur Webhook-Ziel
- Streaming/SSE für Live-Antworten
- bessere Progress-/Event-Flows für lange Skill-Runs

### Routing 2.0
- Embedding-/Similarity-Routing
- optional LLM-Klassifikation als Fallback
- Routing-Erklärbarkeit im UI verbessern
- Alias-/Beschreibung-/Tag-Qualität noch stärker ausnutzen

### Security / Sharing
- echtes Ownership-/Sharing-Modell für Skills, Connections und Memories
- RBAC-Ausbau über den aktuellen Admin/User-Schalter hinaus

## Nicht-Ziel des aktuellen Alpha

- kein Public-Internet-Standardbetrieb
- kein Full-Enterprise-RBAC
- kein automatischer Container-Self-Updater
- keine Memory-Map als Pflichtbestandteil
