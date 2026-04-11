# ARIA - Alpha Backlog

Stand: 2026-04-11

Zweck:
- schlanker Arbeits-Backlog fuer die laufende Alpha-Linie
- hier stehen nur noch echte Restpunkte, Verifikation und direkte Release-Arbeit
- bereits gelieferte Aenderungen stehen im `CHANGELOG.md`
- groessere Zukunftsthemen stehen in `docs/backlog/future-features.md`

Aktueller Release-Stand:
- public: `0.1.0-alpha89`
- lokal / intern: `0.1.0-alpha101`

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
- erste Routing-Entkopplung:
  - zentrale Routing-Lexika in `aria/core/routing_lexicon.py`
  - sprachbewusster `CapabilityRouter`
  - explizite Connection-Capabilities schlagen generische Custom-Skill-Matches
  - englische Prompt-/Capability-/Websearch-Ausgaben im neuen Routing-Pfad

Siehe dafuer:
- `CHANGELOG.md`

## Bewusst spaeter / kein Alpha-Blocker

- Memory-Export einmal live gegen echte `prod`-Qdrant-Daten testen
  - bewusst in den naechsten Alpha-Zyklus verschoben
  - kein Blocker fuer den aktuellen Public-Release
- Home Assistant Integration
- semantischen Graph spaeter aus echten Beziehungen / Qdrant-Daten vertiefen
- Voice Aktivierung
- Streaming / SSE fuer Live-Antworten
- volles Multi-User- / RBAC-Modell

## Naechste Hardening- und Refactor-Reihenfolge

### P0 Security / Safety
- [ ] Login-Rate-Limit fuer `/login`
  - Ziel: Brute-Force-Risiko senken
  - Option: einfacher In-Memory-/TTL-Guard zuerst, spaeter ggf. robuster pro Reverse-Proxy/IP
- [ ] Pending-Action-Secrets trennen
  - `forget`, `safe-fix` und weitere signierte Action-Cookies sollen nicht denselben Secret teilen
- [ ] Signing-Secrets nicht mehr als leere Strings initialisieren
  - stattdessen `None` + expliziter Guard beim Zugriff
- [ ] Cookie-Review abschliessen
  - Auth-/Session-/Pending-Cookies gegen die realen Codepfade pruefen und wo noetig korrigieren
  - klar festhalten, welche Cookies wirklich clientlesbar sein muessen und welche auf `HttpOnly` koennen

### P1 Runtime-Stabilitaet
- [ ] `_reload_runtime()` gegen gleichzeitige Reloads haerten
  - bevorzugter Weg: `asyncio.Lock` + neues Runtime-/Pipeline-Objekt bauen + danach atomar ersetzen
- [ ] Multi-Instanz-/Updater-Regressionstest nachziehen
  - echter Folge-Update-Test mit neuerem Release
  - Fokus: Session-Isolation, `aria-updater`, Managed-Update
- [ ] Qdrant-Migrations-/Upgrade-Validierung weiter haerten
  - Recovery-/Warnpfade fuer teilweise geladene Collections weiter verbessern

### P2 Wartbarkeit / Refactor
- [ ] `aria/main.py` aufteilen
  - bevorzugte Zielstruktur:
    - `aria/web/auth_routes.py`
    - `aria/web/chat_routes.py`
    - `aria/web/admin_routes.py`
  - Ziel: App-Factory, Cookie-/Session-Logik und Route-Handler entflechten
- [ ] `aria/core/skill_runtime.py` nach Connection-Typen schneiden
  - zuerst grob nach:
    - ssh
    - mail
    - file-transfer
    - feeds/http
    - chat/discord
  - `ssh` zuerst herausloesen, weil fachlich am eigenstaendigsten und bereits gut testbar
- [ ] statische Kataloge / groessere UI-Hilfsdaten aus `main.py` auslagern
- [ ] Session-/Cookie-Helfer aus `main.py` in ein eigenes Web-Modul ziehen
  - Ziel: Signieren, Scope, Cookie-Namen, CSRF und Clear-Logik zentral und testbar halten
- [ ] Runtime-Context fuer `settings`, `pipeline`, Secrets und Stores einfuehren
  - Ziel: weniger globale Mutable-States, klarere Reload-Grenze, spaeter leichterer App-Factory-Schnitt
- [ ] `aria/core/connection_catalog.py` datenlastige Katalogteile von Helper-Logik trennen
  - Ziel: statische Connection-Metadaten, Insert-Beispiele und UI-Hinweise getrennt von Resolver-/Helper-Code

### Architekturblock: Routing entkoppeln und `main.py` entlasten

#### Zielbild
- Routing darf nicht primär aus fest verdrahteten deutschen Triggern im Python-Code bestehen
- Sprachlogik soll datengetrieben und pro Sprache konfigurierbar sein
- Chat-/Intent-Logik soll nicht weiter in `aria/main.py` wachsen

#### Phase 1: Routing-Lexikon zentralisieren
- [ ] alle Routing-Trigger inventarisieren
  - Quellen:
    - `aria/core/config.py`
    - `aria/core/capability_router.py`
    - `aria/core/connection_catalog.py`
    - Custom-Skill-`router_keywords`
- [ ] ein zentrales Routing-Lexikon-Modell definieren
  - bevorzugter Schnitt:
    - `memory`
    - `web_search`
    - `capability`
    - `toolbox`
    - `connection_hints`
- [ ] Sprachprofile konsistent aus Config laden
  - Ziel: ein Resolver statt mehrerer verstreuter Default-Listen
- [X] erster Implementierungsschritt
  - bestehende Defaults aus `aria/core/config.py` in `aria/core/routing_lexicon.py` ueberfuehrt
  - doppelte Default-Eintraege dedupliziert, Prefix-Whitespace bewusst erhalten
  - eingebautes `en`-Sprachprofil als erster sauberer Gegenpol zu den deutschlastigen Fallbacks hinterlegt
  - keine harte Verhaltensaenderung fuer bestehende Configs erzwungen, nur Struktur geschaffen
- [X] `KeywordRouter`-Skill-Status-Lexikon aus dem Code gezogen
  - Skill-Status-Keywords, Regexe und Hilfsbegriffe liegen jetzt ebenfalls im Routing-Lexikon
  - `aria/core/router.py` enthaelt damit weniger deutschzentrierte Produktlogik
  - `en` bekommt dafuer ein eigenes eingebautes Skill-Status-Profil

#### Phase 2: Capability-Routing wirklich dynamisch machen
- [ ] `CapabilityRouter` von hart codierten Termlisten loesen
  - statt Tupeln im Code konfigurierbare Sprachdaten verwenden
- [ ] alle `classify(...)`-Aufrufe sprachbewusst machen
  - keine direkten Fallback-Aufrufe mehr ohne explizites Sprachprofil
- [ ] Pending-Action- und Chat-Sonderpfade ueber denselben Routing-Resolver fuehren
  - speziell die Stellen in `main.py`, die aktuell direkt auf `pipeline.router` oder Parser gehen
- [X] erster Umbauschnitt
  - `CapabilityRouter` bekommt Sprachdaten injected
  - Lexikon-Daten liegen jetzt zentral in `aria/core/routing_lexicon.py`
  - `Pipeline` reicht das Sprachprofil jetzt bis in den Capability-Router durch
  - bestehende DE/EN-Begriffe bleiben funktional, liegen aber nicht mehr als Primärlogik im Python-Code
- [X] explizite Connection-Ziele werden strikter behandelt
  - wenn ein Profil wie `alerts-discord` explizit genannt wird, darf Routing nicht still auf ein anderes Profil fallen
  - unbekannte explizite Ziele werden jetzt als fehlendes Wunschprofil behandelt statt als generischer Fallback
- [X] erster Sonderpfad in `main.py` entkoppelt
  - der Forget-/Pending-Action-Pfad ruft nicht mehr direkt `pipeline.router.classify(...)` auf
  - stattdessen laeuft er jetzt ueber einen sprachbewussten Pipeline-Helper

#### Phase 3: `main.py` fachlich zerlegen
- [ ] zuerst den Chat-Block aus `main.py` herausziehen
  - bevorzugte Zielstruktur:
    - `aria/web/chat_routes.py`
    - `aria/web/chat_admin_actions.py`
    - `aria/web/auth_routes.py`
- [ ] Cookie-/Session-Helfer aus dem Route-File herausziehen
  - bevorzugt in einen dedizierten Web-/Session-Helper statt weiter in `main.py`
- [ ] Toolbox-/Chat-Command-Katalog aus `main.py` auslagern
  - eigener Builder statt Route-Logik + UI-Katalog + Admin-Aktionen in einer Datei
- [X] Toolbox-/Chat-Command-Katalog aus `main.py` ausgelagert
  - eigener Builder liegt jetzt in `aria/web/chat_catalog.py`
  - `main.py` haelt nur noch den Aufruf und die Ergebnisverdrahtung fuer das Template
- [X] Pending-/Admin-Parser und Confirm-Flows aus `main.py` ausgelagert
  - Parser, Pending-Cookie-Codecs und Connection-/Update-/Backup-Aktionshelfer liegen jetzt in `aria/web/chat_admin_actions.py`
  - `main.py` verdrahtet nur noch Request-Kontext, Runtime-Abhaengigkeiten und die eigentlichen Aktionen
- [ ] danach nur noch App-Factory und Verdrahtung in `main.py` lassen

#### Empfohlene Reihenfolge
1. Routing-Lexikon zentralisieren
2. `CapabilityRouter` dynamisch machen
3. inkonsistente Direkt-Router-Aufrufe bereinigen
4. erst dann `main.py` in Route-Module schneiden

#### Erfolgskriterien
- neue Sprache darf ohne Codeeingriff ueber Config-/Lexikon-Erweiterung anlernbar sein
- keine deutsch-only Produktlogik mehr als Default-Annahme in zentralen Routern
- `main.py` verliert zuerst den Chat-/Pending-Action-Block
- Routing-Verhalten bleibt durch Tests abgesichert

#### Nach `alpha93` im Routing noch offen
- direkte Router-Aufrufe in `aria/main.py` weiter abbauen
  - besonders weitere Session-/Cookie-Helfer und uebrige Parser-Sonderpfade
- `KeywordRouter` spaeter noch weiter vereinfachen
  - idealerweise nur noch generische Matching-Logik, keine sprachlichen Spezialannahmen mehr im Modul
- Connection-/Toolbox-Hinweise weiter aus Codekonstanten loesen
  - `aria/core/connection_catalog.py` und Teile des Toolbox-Builders in `aria/main.py`
- Chat-Admin-Kommandos und Pending-Actions ueber dieselbe sprachbewusste Resolver-Schicht ziehen
- Feed-Inhalte selbst nicht uebersetzen
  - bewusst okay, solange nur Header und Systemtexte sprachbewusst bleiben

### Skill-Automation strategisch

#### Zielbild
- Skills sollen nicht nur manuell als JSON gepflegt werden
- ARIA soll aus Chat-Anforderungen sichere Skill-Entwuerfe erzeugen koennen
- daraus kann spaeter ein kleiner kuratierter Skill-Shop / Skill-Katalog entstehen

#### Phase 1: Skill-Engine fuer echte Automationen haerten
- [x] konditionale Skill-Schritte einfuehren
  - erster Engine-Schnitt vorhanden: Step-`condition` mit einfachen Operatoren wie `equals`, `not_equals`, `contains`, `regex`, `is_empty`, `not_empty`
  - Beispiel ist damit jetzt direkt moeglich: `discord_send` nur ausfuehren, wenn der LLM-Schritt nicht `NO_ALERT` ergibt
- [ ] Skill-Outputs strukturierter machen
  - Ziel: LLM-/SSH-/Feed-Schritte koennen Status, Severity und Kurzsummary maschinenlesbar weitergeben
- [ ] Skill-Fehler und Skip-Zustaende sauber im UI und in Activities anzeigen
  - Ziel: `skipped`, `no_alert`, `dry_run`, `warn` statt nur `ok/error`

#### Phase 2: Skill-Draft per Chat
- [ ] Chat-zu-Skill-Draft-Flow definieren
  - User beschreibt Ziel in normaler Sprache
  - ARIA baut daraus einen Draft mit:
    - Name
    - Kategorie
    - benoetigte Connections
    - Schritte
    - Schedule
    - offene Platzhalter / Risiken
- [ ] Confirm-/Review-Step fuer Skill-Drafts einfuehren
  - kein direkter Live-Skill ohne Review
  - Draft zuerst deaktiviert speichern
- [ ] Skill-Draft in `/skills` oeffnen und nachbearbeiten koennen
  - Ziel: Chat erzeugt Entwurf, UI macht den letzten sauberen Schliff

#### Phase 3: Skill-Katalog / Skill-Shop
- [ ] kuratierte Sample- und Community-Skills sauber katalogisieren
  - Kategorien, Anforderungen, benoetigte Connections, Schedule-Hinweise
- [ ] Import mit Preview und Kompatibilitaetscheck
  - Ziel: ein Skill zeigt vorher, welche Connections / Refs / Risiken er erwartet
- [ ] spaeter externer Skill-Shop auf Website
  - zuerst nur kuratierte Manifest-Galerie, noch kein unkontrollierter Marketplace

#### Empfohlene Reihenfolge
1. konditionale Skill-Schritte
2. strukturiertere Skill-Outputs / Status
3. Chat-zu-Skill-Draft
4. Review-/Confirm-Flow
5. Skill-Shop / Galerie

### P3 Cleanup / Qualitaet
- [ ] tote `return None`-Zeilen in Decode-Helfern entfernen
- [ ] Routing-Defaults i18n-faehig machen
  - nicht nur deutsche Trigger out of the box
- [ ] doppelte Routing-Keywords deduplizieren
- [ ] `_current_memory_day()` auf timezone-aware UTC ziehen
- [ ] Bare-`except Exception` gezielt reduzieren oder klarer begruenden
- [ ] groessere Kataloge / konstante Daten aus `main.py` weiter abbauen
  - z. B. Produkt-/Editor-Kataloge, damit Route-Dateien weniger Datenballast tragen

### Verifikation offen
- [ ] Back-/Ruecksprung-UX auf Formularseiten fachlich statt per Browser-History loesen
  - aktueller Back-Pfeil nutzt Browser-History und landet nach Save/Redirect oft wieder auf derselben Detailseite
  - loesen ueber `return_to`/`next` plus sinnvolle Fallback-Ziele pro Bereich

- [ ] P1: GUI-Update mit naechstem echten Release erneut testen
- [ ] P2: Public `aria-setup` einmal nochmal komplett frisch gegen Host mit bestehender ARIA gegenpruefen
- [ ] P3: Aktivitaeten-/Runs-Karte spaeter klarer als Historie markieren, damit alte Fehler nicht wie Live-Status wirken

## Naechster groesserer Block nach Alpha-Cleanup

- Home Assistant v1
  - Verbindung
  - Geraete / Entities sehen
  - sichere Grundsteuerung
- spaeter Home Assistant v2
  - Verhalten lernen
  - Muster erkennen
  - Brain-fuer-HA-Richtung
