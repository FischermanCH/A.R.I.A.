# ARIA - Alpha Backlog

Stand: 2026-04-07

Zweck:
- schlanker Arbeits-Backlog fuer die laufende Alpha-Linie
- hier stehen nur noch echte Restpunkte, Verifikation und direkte Release-Arbeit
- bereits gelieferte Aenderungen stehen im `CHANGELOG.md`
- groessere Zukunftsthemen stehen in `docs/backlog/future-features.md`

Aktueller Release-Stand:
- public: `0.1.0-alpha64`
- lokal / intern: `0.1.0-alpha65`

## Offene Alpha-Punkte

### Alpha65 Verifikation
- [ ] SearXNG startet im internen Stack sauber als separater Dienst neben ARIA und Qdrant
- [ ] `/config/connections/searxng` speichert und testet eine Connection gegen `http://searxng:8080`
- [ ] explizite Websuche im Chat liefert Treffer mit Quellen in den Details

### Alpha64 Verifikation
- [X] `/stats` zeigt den aktuellen internen Build korrekt
- [X] `aria --version` funktioniert lokal und im Container sauber
- [X] `aria version-check` zeigt den installierten und den neuesten oeffentlichen Stand korrekt
- [X] `/stats` zeigt Modellnutzung plausibel auch nach Quellen wie `chat`, `rss_metadata`, `rss_grouping`, `rag_ingest` und `memory`
- [X] RSS-Metadaten- und RSS-Gruppierungs-LLM-Aufrufe landen sichtbar in Kosten- und Token-Logs
- [X] Dokument-Upload (`txt` / `md` / `pdf` mit eingebettetem Text) funktioniert weiterhin stabil
- [X] Chat-Recall auf hochgeladene Dokumente funktioniert weiterhin stabil
- [X] Chat-Details zeigen die Quelle mit Dokumentname / Collection / Chunk sauber an
- [X] RSS-Verbindungen zeigen konsistent die Anzeigenamen statt alter `ref`-Profilnamen
- [X] `Memory`, `Memory Map` und RSS-Seiten bleiben auf iPhone / Mobile lesbar

### Echte Restarbeiten in der Alpha-Linie
- [X] `alpha64` geht als naechster Public-Release raus

## Bewusst nicht mehr hier doppelt pflegen

Bereits lokal geliefert oder im aktuellen Unreleased-Stand enthalten und deshalb nicht mehr als offene Backlog-Punkte hier fuehren:
- RAG v1 in `Memory` inklusive Dokument-Upload, Dokument-Guide, Recall und Quellenanzeige
- `Memory Map` mit Dokumentverwaltung, Collection-Kacheln, Rollups und Graph-Sicht
- Update-Anzeige in `/stats` und verbesserter `/updates`-Fallback
- Session-, Cookie- und Multi-Instanz-Logout-Fixes
- RSS-UX- und Anzeigenamen-Fixes
- pre-alpha Websuche via SearXNG als separatem Stack-Dienst, eigener Connection und Chat-Quellenanzeige
- konfigurierbarer Embedding-Schutz fuer bestehendes Memory
- zentrales Metering fuer alle LLM- und Embedding-Aufrufe
- `aria --version`, `aria version-check`, Kontext-Hilfen und neue Sample-Skills

Siehe dafuer:
- `CHANGELOG.md`

## Bewusst spaeter / kein Alpha-Blocker

- Memory-Export einmal live gegen echte `prod`-Qdrant-Daten testen
  - bewusst in den naechsten Alpha-Zyklus verschoben
  - kein Blocker fuer den aktuellen Public-Release
- Home Assistant Integration
- semantischen Graph spaeter aus echten Beziehungen / Qdrant-Daten vertiefen
- Streaming / SSE fuer Live-Antworten
- volles Multi-User- / RBAC-Modell

## Naechster groesserer Block nach Alpha-Cleanup

- Home Assistant v1
  - Verbindung
  - Geraete / Entities sehen
  - sichere Grundsteuerung
- spaeter Home Assistant v2
  - Verhalten lernen
  - Muster erkennen
  - Brain-fuer-HA-Richtung
