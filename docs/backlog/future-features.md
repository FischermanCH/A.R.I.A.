# ARIA - Future Feature List / Roadmap Input

Stand: 2026-04-03

Zweck:
- technische, nicht-werbliche Zukunftsliste für Release-Kommunikation, Roadmap, Issues und Architekturplanung
- diese Liste beschreibt **geplante/angedachte** Features, nicht aktuelle Release-Fakten

## Near-Term / Post-Alpha

### Memory Export / Import

- Export persönlicher Memories in ein portables Format
- späterer Import derselben Memory-Sets
- Ziel: User behalten ihre Erinnerungen unter eigener Kontrolle und können sie sichern/mitnehmen

### New-Version-Hinweis

- kein riskanter In-App-Container-Updater
- stattdessen UI-Hinweis, wenn auf Docker Hub / GitHub Releases eine neuere ARIA-Version verfügbar ist

### Capability -> Memory Policy

- Produktentscheidung und Implementierung, ob ausgewählte Capability-Ergebnisse automatisch in Memory geschrieben werden sollen
- Ziel: konsistentes Verhalten zwischen Chat, Activities und Memory ohne ungewolltes Memory-Rauschen

### Public Release Hygiene

- README und Setup-Doku finalisieren
- Privacy-/Repo-Sweep
- Lizenz festlegen
- Docker-Image-Tags und Release-Notes stabilisieren

## Smart Home / Home Assistant

### Home Assistant Integration

- Home Assistant als eigene Connection/Integration
- API- oder Event/WebSocket-Anbindung für Entity-/Device-Status
- auswählbare Entities/Areas
- Status-Snapshots, Ereignisse und verdichtete Muster in Qdrant
- ARIA als semantische/intelligente Schicht über Home Assistant

### Adaptive Home Patterns

- wiederkehrende Zustände/Routinen erkennen
- z. B. Anwesenheit, Lichtmuster, Klima-/Energieverhalten, ungewöhnliche Zustände
- aus beobachteten Patterns spätere Empfehlungen oder Automation-Entwürfe ableiten

### Design Guardrail für Smart Home Memory

- nicht jeden Rohzustand endlos speichern
- Event-/State-Komprimierung, Rauschunterdrückung, explizite Löschbarkeit und klare Transparenz, welche Home-Assistant-Daten ARIA behalten hat

## Memory Architecture 2.0

- stärker typisierte Memory-Klassen, z. B.:
  - Facts
  - Preferences
  - Sessions
  - Knowledge
- gewichtetes Recall über mehrere Collections
- bessere Memory-Hygiene:
  - Rollups
  - TTL / Komprimierung
  - gezieltes Forget über mehrere Collections hinweg
- bessere Memory-Transparenz im UI

## Multi-User / Sharing / RBAC

- späteres echtes Multi-User-/Sharing-Modell
- Ownership für:
  - Skills
  - Connections
  - Memories
  - Ressourcen
- Rollenkonzept jenseits des aktuellen Admin-/User-Modes
- bewusst **nicht** aktueller Kernfokus, weil ARIA derzeit klar als Personal Single-User System positioniert ist

## Capability / Plugin Roadmap

- Capability- und Connection-Architektur weiter modularisieren
- Plugin-/Extension-Modell für neue Connection-Typen und Capability-Familien
- strukturierte Skill-/Tool-Definitionen mit stärkerem Manifest-Konzept
- Ziel: neue Integrationen ohne Monolith-Wachstum

## Ingest / Knowledge

- Dokument-/Wissens-Ingest jenseits einzelner Memories
- Chunking-/Indexierungs-Pipeline
- Wissen als eigene Knowledge-Collection
- Quellen-/Provenienz-Metadaten im Recall

## Web / Search / Research

- provider-native Websuche/Web-Tooling first
- optional alternative Suchprovider
- Ergebnisquellen sauberer im UI/Context darstellen
- Ziel: aktuelle Informationen nutzbar machen, ohne den lokalen/self-hosted Fokus zu verlieren

## Smart UI / Personalization

- weitere Themes / Backgrounds
- ggf. importierbare User-Themes
- mehr Personalisierung statt frühem RBAC-Fokus
- kompaktere Statistiken-/Operations-Ansichten

## Help System / Contextual UI Help

- kleines Info-Icon an zentralen Seiten-/Block-/Feldstellen
- Klick zeigt kurze kontextbezogene Hilfe genau zum aktuellen Workflow
- Help-Texte zentral pflegen statt hart in Templates verteilen
- Texte sollen später leicht austauschbar und übersetzbar sein
- erster ALPHA-Schritt:
  - statische Kurztexte für Setup, Connections, RSS, Skills, Memory und Statistiken
  - mitgeliefertes Hilfe-Dokument als Textquelle
- später:
  - Help-Popover oder Help-Drawer
  - mehr Detailseiten/Deep Links
  - ggf. erklärende Hinweise zu Routing-, Memory- und Pricing-Verhalten

## RAS / WireGuard / Remote Access

- eigener Produktbereich für Remote Access / RAS
- WireGuard Peer-/Client-Verwaltung
- QR-Code-/Client-Konfig-Erzeugung
- Status-/Health-Anzeige
- Fokus auf sicheren, verständlichen Remote-Zugriff ohne rohe VPN-Komplexität

## Packaging / Distribution

- Registry-Images mit stabiler Tag-Strategie
- Upgrade-Hinweise pro Release
- optional GHCR zusätzlich zu Docker Hub
- klarer Migrationspfad von lokalem TAR/Portainer-Test hin zu Public Images
