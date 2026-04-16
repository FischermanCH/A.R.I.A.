# ARIA - Alpha Backlog

Stand: 2026-04-16

Zweck:
- schlanker Arbeits-Backlog fuer die laufende Alpha-Linie
- hier stehen nur noch echte Restpunkte, Verifikation und direkte Release-Arbeit
- bereits gelieferte Aenderungen stehen im `CHANGELOG.md`
- groessere Zukunftsthemen stehen in `docs/backlog/future-features.md`

Aktueller Release-Stand:
- public: `0.1.0-alpha110`
- lokal / intern: `0.1.0-alpha121` · intern end-to-end verifiziert
- naechster vorbereiteter Public-Kandidat: `0.1.0-alpha121` · Changelog/Git-/Docker-Doku nachgezogen

## Offene Alpha-Punkte

### Jetzt

- Managed-GUI-Update-Ende-zu-Ende absichern
  - `P0`: Mount-/Config-/Prompt-/Data-Konsistenz nie wieder verlieren
  - `P2`: `aria-setup` frisch gegen Host mit bestehender ARIA gegenpruefen
- Runtime-Stabilitaet haerten
  - `_reload_runtime()` gegen parallele Reloads absichern: erledigt (`RLock` + atomarer Runtime-Bundle-Swap)
  - danach Runtime-Context als sauberer Zielzustand einfuehren
- groesste Monolithen mit dem hoechsten Hebel zuerst schneiden
  - zuerst Connection-Routen aus `aria/web/config_routes.py` ziehen
  - danach Session-/Cookie-Helfer und weitere Chat-/Route-Logik aus `aria/main.py`
- Routing-Produktpfad weiter sauberziehen
  - LLM-gestuetztes Routing ueber begrenzte Kandidatenraeume als naechsten Schritt angehen
    - deterministische Treffer + Qdrant-Kandidaten bleiben Vorstufe
    - kleine Router-LLM entscheidet anschliessend innerhalb des erlaubten Kandidatensets
    - Ziel: weniger Keyword-Pflege, bessere DE/EN-/Mixed-Language-Abdeckung, keine freie Tool-Wahl ohne Guardrails
  - Debug-Ausgabe im Chat fuer Qdrant-/Routing-Entscheidungen
  - direkte Router-Aufrufe in `aria/main.py` weiter abbauen
  - Pending-/Admin-Sonderpfade auf dieselbe sprachbewusste Resolver-Schicht ziehen

### Danach

- restliche P0-/P1-Hardening-Punkte abschliessen
  - Login-Rate-Limit
  - getrennte Pending-Action-Secrets
  - Signing-Secrets nicht mehr leer initialisieren
  - Cookie-Review abschliessen
  - Qdrant-Migrations-/Upgrade-Validierung weiter haerten
- Routing weiter datengetrieben und mehrsprachig machen
  - Routing-Trigger komplett inventarisieren
  - zentrales Routing-Lexikon-Modell finalisieren
  - `CapabilityRouter` weiter von hart codierten Listen loesen
  - LLM-unterstuetzte Routing-Entscheidung ueber Top-K-Kandidaten konzipieren und in den Produktpfad ueberfuehren
- Core-Architektur weiter modularisieren
  - `skill_runtime.py` nach Executor-Domaenen schneiden
  - `Pipeline` als Orchestrator schlanker machen
  - gemeinsame Helper statt Copy-Paste schrittweise konsolidieren
- Skill-Automation auf die naechste Reifestufe bringen
  - strukturierte Skill-Outputs
  - sauberere Skill-Fehler-/Skip-Zustaende im UI und in Activities
  - Chat-zu-Skill-Draft-Flow vorbereiten

### Spaeter

- P3-Cleanup und breite Restpflege
  - tote `return None`-Zeilen
  - timezone-aware UTC fuer `_current_memory_day()`
  - doppelte Routing-Keywords deduplizieren
  - breite `except Exception` weiter reduzieren oder sauber begruenden
- groessere Produktausbauten nach dem Alpha-Cleanup
  - Skill-Shop / kuratierter Katalog
  - Home Assistant v1/v2
  - weitere groessere Agent-/Graph-/Voice-Themen

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

- [x] `_reload_runtime()` gegen gleichzeitige Reloads haerten
  - umgesetzt in `aria/main.py` mit `threading.RLock` + Runtime-Bundle + atomarem Swap
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

### Architekturblock: Clean-Code- und Modularitaetsplan

#### Ausgangslage

- `aria/web/config_routes.py` ist mit ca. 7k Zeilen aktuell der groesste Monolith
- `aria/main.py` ist trotz erster Schnitte weiter zu gross und enthaelt noch Runtime-/Cookie-/Route-Verdrahtung
- `aria/core/skill_runtime.py` ist ein zweiter Core-Monolith fuer viele Connection-Typen
- Review-Findings zeigen wiederkehrende Muster:
  - zu viele breite `except Exception`-Faelle ohne einheitliche Logging-Policy
  - doppelte Helper wie `_msg`, `_sanitize*`, `_is_english`
  - globale Mutable-Runtime-States
  - zu enge Kopplung im `Pipeline`-Orchestrator
  - Sicherheits-/Robustheitsluecken bei SSH-Command-Templates und Guardrail-Matching

#### Zielbild

- ARIA soll weiter modular wachsen koennen, ohne dass neue Features immer mehr Code in einzelne Mega-Dateien druecken
- Web-Routen, Runtime-State, Connection-Ausfuehrung, Routing und Skill-Engine sollen klarere Verantwortlichkeiten bekommen
- Refactors muessen inkrementell und releasefaehig bleiben:
  - kleine Schnitte
  - Tests pro Schnitt
  - keine Big-Bang-Umbauten

#### Phase 1: Observability statt Silent Failures

- [ ] Logging-Policy fuer breite `except Exception` definieren
  - Kategorien:
    - best-effort Fallbacks: `debug`
    - Benutzer-/Config-Fehler: `warning`
    - Runtime-/Storage-/Update-Fehler: `error`
  - jeder Log soll Operation/Route/Kontext nennen, aber keine Secrets ausgeben
- [ ] kritische Pfade zuerst instrumentieren
  - Managed-Update / Repair
  - Config Save/Load
  - LLM-/Embedding-Profiltests
  - Qdrant-/Memory-Checks
  - Connection-Tests
- [ ] danach erst breite Reststellen anfassen
  - Ziel: weniger stille Fehler, aber kein Log-Spam

#### Phase 2: Gemeinsame Helper statt Copy-Paste

- [ ] kein grosses unspezifisches `utils.py` bauen
  - lieber fachliche Helper-Module:
    - `aria/core/text_utils.py` fuer Normalize/Sanitize
    - `aria/core/i18n_helpers.py` oder Erweiterung von `aria/core/i18n.py` fuer `_msg` / Sprachchecks
    - `aria/core/http_fetch.py` fuer sichere URL-Fetches
    - `aria/web/url_helpers.py` fuer `return_to`, Redirects, Web-spezifische Sanitizer
- [ ] doppelte `_msg`, `_sanitize*`, `_is_english` schrittweise ersetzen
  - nicht in einem riesigen Sweep
  - pro Modul mit Tests nachziehen
- [ ] zentraler HTTP-Fetcher
  - einheitlich:
    - erlaubte Schemes `http/https`
    - Timeout
    - Max-Bytes
    - User-Agent
    - klare Fehlerobjekte
  - spaeter optional SSRF-Schutz / private-IP-Regeln

#### Phase 3: `config_routes.py` nach Domaenen schneiden

- [ ] zuerst Connection-Routen auslagern
  - groesster Hebel, weil Connections aktuell stark wachsen
  - bevorzugte Zielmodule:
    - `aria/web/config_connections_routes.py`
    - `aria/web/config_connection_context.py`
    - `aria/web/config_connection_metadata.py`
  - umfasst:
    - SSH/SFTP/RSS/SMB/Discord/API/Mail/MQTT-Seiten
    - Metadaten-Helfer
    - Save-/Test-/Delete-Pfade
- [ ] danach LLM-/Embedding-Profile auslagern
  - bevorzugt:
    - `aria/web/config_llm_routes.py`
    - `aria/web/config_embedding_routes.py`
  - Ziel:
    - Profil laden/speichern/testen klar getrennt
    - weniger Risiko bei Provider-Preset-Aenderungen
- [ ] danach Admin-/System-Config trennen
  - Kandidaten:
    - Appearance
    - Language
    - Users/Security
    - Backup/Logs/Debug
    - Routing/Skill-Routing
- [ ] `config_routes.py` am Ende nur noch als Aggregator/Register-Modul verwenden
  - Route-Registrierung und gemeinsame Dependencies ja
  - keine grosse Fachlogik mehr

#### Phase 4: RuntimeContext und Dependency Injection

- [ ] Runtime-Context einfuehren
  - kapselt:
    - `settings`
    - `pipeline`
    - Secure Store
    - Signing-Secrets
    - Paths
    - Reload-Lock
- [ ] `_reload_runtime()` final ueber RuntimeContext abschliessen
  - aktueller Zwischenstand: Runtime-Bundle in `aria/main.py` + atomarer Swap vorhanden
  - Zielzustand: Reload komplett ueber dedizierten RuntimeContext tragen
- [ ] Web-Routen ueber Context statt modulglobale Variablen versorgen
  - Ziel: testbarer, weniger Race-/Reload-Risiko

#### Phase 5: `skill_runtime.py` und `pipeline.py` entkoppeln

- [ ] `skill_runtime.py` nach Executor-Domaenen schneiden
  - Reihenfolge:
    1. SSH
    2. HTTP/Webhook/API
    3. RSS/Feeds
    4. Mail
    5. Discord/MQTT
  - Ziel: Custom-Skill-Orchestrierung bleibt, konkrete Providerlogik wandert raus
- [ ] `Pipeline` als Orchestrator schlanker machen
  - keine Big-Bang-Zerlegung
  - erst Services/Registries einfuehren:
    - `SkillService`
    - `MemoryService`
    - `ConnectionExecutionRegistry`
    - `RoutingService`
  - danach direkte Imports/Kopplung reduzieren

#### Erfolgskriterien

- keine neue Feature-Arbeit muss mehr direkt in `config_routes.py` oder `main.py` landen, wenn es ein passendes Modul gibt
- neue Connection-Typen koennen mit kleinen, isolierten Dateien wachsen
- Update-/Config-/Connection-Fehler sind im Log nachvollziehbar
- SSH-/Guardrail-Sicherheitsregressionen sind mit Tests abgesichert
- Modulgrenzen sind so klein, dass Reviews wieder gezielt moeglich sind

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

#### Phase 2: Capability-Routing wirklich dynamisch machen

- [ ] `CapabilityRouter` von hart codierten Termlisten loesen
  - statt Tupeln im Code konfigurierbare Sprachdaten verwenden
- [ ] alle `classify(...)`-Aufrufe sprachbewusst machen
  - keine direkten Fallback-Aufrufe mehr ohne explizites Sprachprofil
- [ ] Pending-Action- und Chat-Sonderpfade ueber denselben Routing-Resolver fuehren
  - speziell die Stellen in `main.py`, die aktuell direkt auf `pipeline.router` oder Parser gehen

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

#### P1: Hybrid-Routing mit Qdrant als naechster Produkthebel

- Ziel: ARIA soll sich mehr wie ein persoenlicher Agent anfuehlen, ohne das bestehende Sicherheitsmodell zu verlassen
  - kein Redesign weg von Skills/Connections/Guardrails
  - Qdrant-Routing wird als emotionale/produktive Schicht darueber gebaut
  - User formuliert natuerlich, ARIA findet kontrolliert passende Ziele und erklaert die Entscheidung
- [ ] Routing nicht komplett in Vektor-Suche verlagern, sondern als Hybrid-System schneiden
  - Stufe 1 bleibt regelbasiert und deterministisch:
    - exakte `ref`-Treffer
    - explizite Alias-Treffer
    - Guardrails / Capability-Sperren / sichere Prioritaeten
  - Stufe 2 liefert semantische Kandidaten:
    - Connections
    - Skills
    - RSS-Feeds
    - spaeter evtl. Toolbox-/Service-Ziele
  - finale Entscheidung bleibt im Code:
    - Schwellwerte
    - Typpruefung
    - Sicherheitslogik
- [ ] eigene Qdrant-Routing-Collections vorsehen
  - bewusst getrennt von normalem Memory/RAG
  - keine Dokumente, Sessions, Facts oder Prompt-Kontexte in denselben Index mischen
  - bevorzugte Struktur:
    - `aria_routing_connections_<instance>`
    - `aria_routing_skills_<instance>`
    - optional spaeter `aria_routing_feeds_<instance>`
- [ ] Routing-Dokumente klein und gezielt halten
  - pro Eintrag z. B.:
    - `kind`
    - `ref`
    - `title`
    - `description`
    - `aliases`
    - `tags`
    - `supported_actions`
    - optionale Beispiel-Prompts
- [ ] Resolver-Schnitt definieren
  - bevorzugter Ablauf:
    1. exakte Regeln
    2. Qdrant-Kandidaten mit Score
    3. Code entscheidet final
  - Ziel: natuerliche Formulierungen besser treffen, ohne harte Routing-Grenzen aufzugeben
- [ ] Mehrsprachigkeit dadurch robuster machen
  - Routing-Dokumente koennen gemischte DE/EN-Aliase und Tags tragen
  - semantische Kandidatensuche soll sprachuebergreifend helfen, nicht nur ueber starre Trigger
- [ ] zuerst nur fuer Connection-Zielauflosung pilotieren
  - SSH/SFTP/RSS/Discord/API als erster Testbereich
  - noch kein globaler Ersatz fuer `KeywordRouter` oder Guardrail-Checks
- [ ] Erfolgskriterien fuer den Pilot festhalten
  - bessere Zieltreffer bei natuerlichen User-Formulierungen
  - weniger Sprachabhaengigkeit bei vielen aehnlichen Connections
  - keine Regression bei expliziten Profilnamen / exakten Alias-Treffern

#### Konkreter Pilotplan Qdrant-Routing

1. Routing-Dokument-Modell definieren
   - `kind`, `ref`, `title`, `description`, `aliases`, `tags`, `supported_actions`, `example_prompts`, `language_hints`
   - bewusst ohne Secrets und ohne volatile Runtime-Daten
2. Index-Builder fuer Connections bauen
   - liest SSH/SFTP/RSS/Discord/API-Profile aus `settings.connections`
   - schreibt pro Profil ein kleines Dokument in `aria_routing_connections_<instance>`
   - Rebuild bei Profil-Save und zusaetzlich Admin-Button "Routing-Index neu bauen"
3. Resolver-Schicht einfuehren
   - erst deterministische Treffer pruefen
   - dann Qdrant-Kandidaten holen
   - dann Typ-/Score-/Guardrail-Pruefung im Code
   - LLM nur optional zur Auswahl zwischen wenigen Kandidaten nutzen
4. Pilot nur fuer Connection-Zielauflosung aktivieren
   - zuerst SSH/SFTP/RSS/Discord/API
   - keine Ablösung von `KeywordRouter`
   - keine Vermischung mit normalem Memory/RAG
5. Tests und UI-Transparenz
   - Routing-Testseite oder Debug-Details: Kandidaten, Scores, gewaehltes Profil
   - Regressionstests fuer exakte Profilnamen, Aliase, mehrsprachige Begriffe und falsch-positive Treffer
   - Erfolgskriterium: explizite Profile bleiben deterministisch, natuerliche Formulierungen werden robuster

#### Umsetzungsplan Richtung "Agent, der Dinge tut" ohne Redesign

1. Routing-Index zuerst bauen
   - kleinster wirksamer Schritt Richtung OpenClaw-Gefuehl
   - ARIA kann damit viele aehnliche Connections/Skills natuerlicher finden
   - bestehende Config-Pflege bleibt die Quelle der Wahrheit
2. Skill-/Connection-Details emotionaler machen
   - `title`, `description`, `aliases`, `tags`, `service_url`, Beispiel-Prompts bewusst als "Agent versteht dieses Ziel"-Metadaten behandeln
   - UI soll klar zeigen: "So erkennt ARIA dieses Profil"
3. Routing-Entscheidung transparent machen
   - Chat-Details/Debug zeigen:
     - deterministischer Treffer oder Qdrant-Kandidat
     - Kandidatenliste + Score
     - gewaehlte Capability
     - aktive Guardrail
   - Ziel: Magie ja, Blackbox nein
4. Skill-Draft danach anschliessen
   - Chat-zu-Skill-Draft nutzt denselben Routing-Index fuer vorhandene Connections und passende Capabilities
   - Draft bleibt deaktiviert bis Admin bestaetigt
   - Guardrail-/Risk-Preview ist Pflicht
5. Proaktive Aufgaben kontrolliert ausbauen
   - Cron/Schedules fuer Skills first-class machen
   - Lauf-Status, letzte Entscheidung, naechster Lauf und Benachrichtigungsgrund im UI zeigen
   - Beispiel-Ziel: "alle 4 Stunden Linux HealthCheck und nur relevante Findings nach Discord"

#### Sofort naechste Arbeitspakete fuer Qdrant-Routing

- [ ] Debug-Ausgabe im Chat
  - zunaechst nur im Debug/Admin-Modus
  - zeigt Routing-Kandidaten ohne Secrets

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

1. Qdrant-Routing-Index fuer Connections/Skills
   - damit ARIA vorhandene Ziele natuerlich und mehrsprachig findet
2. konditionale Skill-Schritte
   - erledigt als Grundlage fuer echte Automationen
3. strukturiertere Skill-Outputs / Status
   - damit Schedules und LLM-Entscheidungen maschinenlesbar weiterarbeiten koennen
4. Chat-zu-Skill-Draft
   - nutzt Routing-Index, vorhandene Connections und Guardrails
5. Review-/Confirm-Flow
   - keine Live-Automation ohne Admin-Bestaetigung
6. Skill-Shop / Galerie
   - erst wenn Draft/Review/Guardrail-Pruefung stabil sind

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

- [ ] P0: Managed GUI-Update darf Config-/Prompt-/Data-Mounts nie wieder implizit verdrehen oder entkoppeln
  - Befund aus `white`/`neo`-Mehrinstanz-Host: Nach GUI-Update wirkte eine Instanz wie frisch/default, obwohl `config.yaml` auf dem Host die Profile noch enthielt
  - Symptom: Host-`config.yaml` enthielt LLM-/Embedding-Profile, im laufenden Container war `/app/config/config.yaml` davon abweichend
  - Sofort-Fix/Recovery: `setup-compose-stack.sh --upgrade-existing --force --no-start` erneut gegen das Install-Verzeichnis laufen lassen und danach `aria` + `aria-updater` recreaten
  - lokaler Produkt-Fix vorbereitet:
    - `./aria-stack.sh repair` als offizieller Recovery-Befehl
    - Managed-Post-Validation vergleicht Host-`config.yaml` gegen Container-`/app/config/config.yaml`
    - GUI-Update-Refresh laeuft ueber das Ziel-Image statt ueber das ggf. veraltete Updater-Bundle
  - Produkt-Fix absichern:
    - Compose-/Mount-Refresh im Managed-Update als Regressionstest absichern
    - nach Managed-Update serverseitig pruefen, dass Container-`/app/config/config.yaml` denselben Profilstand wie `storage/aria-config/config.yaml` sieht
    - dieselbe Konsistenzpruefung auch fuer `/app/prompts` und `/app/data` vorsehen
    - im Fehlerfall Update nicht still als "ok" melden, sondern klar auf Mount-/Persistenzproblem gehen

- [ ] P2: Public `aria-setup` einmal nochmal komplett frisch gegen Host mit bestehender ARIA gegenpruefen
- [ ] P3: Aktivitaeten-/Runs-Karte spaeter klarer als Historie markieren, damit alte Fehler nicht wie Live-Status wirken

## Bewusst spaeter / kein Alpha-Blocker

- Memory-Export einmal live gegen echte `prod`-Qdrant-Daten testen
  - bewusst in den naechsten Alpha-Zyklus verschoben
  - kein Blocker fuer den aktuellen Public-Release
- Home Assistant Integration
- semantischen Graph spaeter aus echten Beziehungen / Qdrant-Daten vertiefen
- Voice Aktivierung
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

## Erledigt / Archiv

### alpha121 intern verifiziert

- [X] interner Update-Button erfolgreich gegen echtes Folge-Release getestet
  - interner GUI-Update-Flow zog `aria-alpha121-local.tar` sauber vom NAS
  - `aria` wurde erfolgreich recreatet, Qdrant/Volumes blieben unberuehrt
  - Healthcheck nach dem Recreate war erfolgreich
- [X] Persistenz nach internem GUI-Update verifiziert
  - Version, Profile, Memory und Theme blieben erhalten
- [X] Routing-/SSH-Fix auf der echten internen ARIA verifiziert
  - `Wie lange ist mein DNS Server schon online?` routed korrekt auf SSH `uptime`
  - Ausfuehrung lief direkt auf `pihole1` und kam ohne generische LLM-Antwort zurueck
  - Reaktionszeit fuehlbar schnell

### alpha119 intern verifiziert

- [X] interner Update-Button erfolgreich gegen echtes Folge-Release getestet
  - interner GUI-Update-Flow zog `aria-alpha119-local.tar` sauber vom NAS
  - `aria` wurde erfolgreich recreatet, Qdrant/Volumes blieben unberuehrt
  - Healthcheck nach dem Recreate war erfolgreich
- [X] Persistenz nach internem GUI-Update verifiziert
  - Config / LLM-Profile / Embeddings / Memory blieben erhalten
- [X] Routing-Fixes auf der echten internen ARIA verifiziert
  - Routing-Collection ist im Memory-Graph sichtbar
  - `Wie lange laeuft mein DNS Server schon?` routed korrekt auf SSH `uptime`

### Bewusst nicht mehr hier doppelt pflegen

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

### Offene Alpha-Punkte

#### Alpha65 Verifikation

- [X] SearXNG startet im internen Stack sauber als separater Dienst neben ARIA und Qdrant

- [X] `/config/connections/searxng` speichert und testet eine Connection gegen `http://searxng:8080`

- [X] explizite Websuche im Chat liefert Treffer mit Quellen in den Details

#### Alpha64 Verifikation

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

#### Echte Restarbeiten in der Alpha-Linie

- [X] `alpha64` geht als naechster Public-Release raus

#### Connection-UX Follow-up

- [X] Sammelkarten fuer Connections mit 4+ Profilen besser aufklappbar machen
  - betrifft SSH und alle anderen Connection-Typen mit zusammengefassten Profilen
  - Ziel: geschlossene Kachel oeffnet sich beim Klick irgendwo auf der Kachel, nicht nur auf dem kleinen Link / der Count-Zeile
  - sichtbar z. B. auf `/config/connections/ssh`

### Naechste Hardening- und Refactor-Reihenfolge

#### Architekturblock: Clean-Code- und Modularitaetsplan

##### Phase 0: Sicherheitsnahe Quick-Wins zuerst

- [X] SSH-Custom-Command-Safety haerten
  - Problem: `{query}` in Shell-Templates kann trotz aeusserem `shlex.quote(command)` riskant bleiben, weil remote `bash -lc` laeuft
  - Ziel:
    - rohe User-Inputs nicht unquoted in Shell-Templates einsetzen
    - optional explizite Platzhalter wie `{query:q}` einfuehren
    - klare Tests fuer `$()`, Backticks, Semikolon-/Pipe-/Newline-Faelle
  - Umgesetzt:
    - `{query}` und `{query:q}` werden shell-gequotet gerendert
    - Backtick-/Newline-Blockade bleibt als zusaetzliche Sicherheitsgrenze bestehen
    - Regressionstests fuer `$()`, Semikolon/Pipe und Backticks ergaenzt
  - Datei-Fokus:
    - `aria/core/ssh_runtime.py`
    - Skill-Sample-/Runtime-Tests

- [X] Guardrail-Matching von Substring auf Token-/Pattern-Matching umstellen
  - Problem: `rm` darf nicht zufaellig `berm.sh` matchen
  - Ziel:
    - Word-Boundary-/Token-Matching fuer einfache Begriffe
    - optional explizite Regex-/Glob-Modi spaeter
    - Tests fuer False Positives und echte Deny-Treffer
  - Umgesetzt:
    - einfache Begriffe matchen token-/boundary-bewusst
    - Pfad-Guardrails behalten bewusst Prefix-/Substring-Matching fuer Unterpfade
    - Regressionstests fuer `rm` vs. `berm.sh`, echte `rm`-Treffer und Pfad-Allowlists ergaenzt
  - Datei-Fokus:
    - `aria/core/guardrails.py`

- [X] Regex-Quick-Wins sammeln und precompilen
  - nicht als Top-Risiko, aber einfacher Cleanup
  - zuerst heisse Pfade in `skill_runtime.py`
  - Umgesetzt:
    - konstante Skill-/JSON-/HTML-/Token-Regexes in `aria/core/skill_runtime.py` vor-kompiliert
    - dynamische Condition-Regexes ueber kleinen LRU-Cache kompiliert
    - Verhalten bleibt unveraendert, Cleanup ist durch Skill-/Pipeline-Tests abgesichert

#### Architekturblock: Routing entkoppeln und `main.py` entlasten

##### Phase 1: Routing-Lexikon zentralisieren

- [X] erster Implementierungsschritt
  - bestehende Defaults aus `aria/core/config.py` in `aria/core/routing_lexicon.py` ueberfuehrt
  - doppelte Default-Eintraege dedupliziert, Prefix-Whitespace bewusst erhalten
  - eingebautes `en`-Sprachprofil als erster sauberer Gegenpol zu den deutschlastigen Fallbacks hinterlegt
  - keine harte Verhaltensaenderung fuer bestehende Configs erzwungen, nur Struktur geschaffen

- [X] `KeywordRouter`-Skill-Status-Lexikon aus dem Code gezogen
  - Skill-Status-Keywords, Regexe und Hilfsbegriffe liegen jetzt ebenfalls im Routing-Lexikon
  - `aria/core/router.py` enthaelt damit weniger deutschzentrierte Produktlogik
  - `en` bekommt dafuer ein eigenes eingebautes Skill-Status-Profil

##### Phase 2: Capability-Routing wirklich dynamisch machen

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

##### Phase 3: `main.py` fachlich zerlegen

- [X] Toolbox-/Chat-Command-Katalog aus `main.py` ausgelagert
  - eigener Builder liegt jetzt in `aria/web/chat_catalog.py`
  - `main.py` haelt nur noch den Aufruf und die Ergebnisverdrahtung fuer das Template

- [X] Pending-/Admin-Parser und Confirm-Flows aus `main.py` ausgelagert
  - Parser, Pending-Cookie-Codecs und Connection-/Update-/Backup-Aktionshelfer liegen jetzt in `aria/web/chat_admin_actions.py`
  - `main.py` verdrahtet nur noch Request-Kontext, Runtime-Abhaengigkeiten und die eigentlichen Aktionen

##### P1: Hybrid-Routing mit Qdrant als naechster Produkthebel

- [X] Vorlaeufer-Fix: direkte SSH-Kommandos vor Chat/RAG routen
  - `Run uptime on pihole1` wird als `capability:ssh_command` erkannt
  - exakte SSH-Profiltreffer werden getrimmt und vor normalem Chat-/Memory-Kontext behandelt
  - Guardrails und `allow_commands` bleiben im SSH-Runtime-Pfad aktiv

##### Sofort naechste Arbeitspakete fuer Qdrant-Routing

- [X] `aria/core/routing_index.py` einfuehren
  - RoutingDocument-Dataclass / Pydantic-Modell
  - Builder fuer Connection-Dokumente aus `settings.connections`
  - Text-Renderer fuer Embeddings ohne Secrets

- [X] `aria/core/routing_resolver.py` einfuehren
  - deterministische Exact-/Alias-Treffer behalten
  - Qdrant-Kandidaten optional nachladen
  - finaler Resolver gibt `kind`, `ref`, `capability`, `source`, `score`, `reason` zurueck

- [X] Kernlogik mit Tests absichern
  - exakter Profilname gewinnt vor Qdrant
  - Alias gewinnt vor Qdrant
  - Qdrant-Kandidat wird nur akzeptiert, wenn `kind/ref` in der aktuellen Config existieren
  - falscher Connection-Typ wird verworfen
  - Secret-Felder/Webhook-URLs landen nicht im Routing-Text

- [X] Admin-Rebuild fuer Routing-Index
  - `aria/core/routing_admin.py` als getrennte Admin-/Debug-Schicht
  - Button auf `/config/routing` fuer manuellen Rebuild
  - JSON-Status unter `/config/routing-index/status`
  - Stats-/Config-Hinweis, wenn Index leer, unvollstaendig oder bereit ist
  - Rebuild nach Connection-Save bleibt als spaeterer Komfort offen

- [X] Routing-Testbench vor Live-Schaltung
  - Dry-run-Formular auf `/config/routing`
  - JSON-Test unter `/config/routing-index/test`
  - zeigt deterministischen Treffer, Qdrant-Kandidaten, akzeptiert/verworfen und finale Entscheidung
  - fuehrt bewusst keine Skills, SSH-Kommandos, Discord-Nachrichten oder Dateiaktionen aus

- [X] Stale-Erkennung fuer Routing-Index
  - aktueller Fingerprint aus routbaren Connection-Metadaten
  - Rebuild schreibt Fingerprint in die Qdrant-Payload der Routing-Punkte
  - Status/Stats zeigen `current_config_hash`, `indexed_config_hash` und `stale`
  - alte Indexe ohne Fingerprint werden gelb markiert und empfehlen Rebuild

- [X] Qdrant-Live-Routing als Feature-Flag vorbereiten
  - `routing.qdrant_connection_routing_enabled` default `false`
  - `routing.qdrant_score_threshold`, `routing.qdrant_candidate_limit`, `routing.qdrant_ask_on_low_confidence`
  - Pipeline nutzt Qdrant nur zwischen deterministischem Matching und LLM-Fallback
  - stale/nicht bereiter Index blockiert Qdrant und verhindert heimlichen LLM-Fallback
  - Debug-Details zeigen Qdrant-Quelle, Score oder Skip-Grund

- [X] Tests fuer Pilot
  - exakter Profilname gewinnt immer
  - Alias gewinnt vor Qdrant
  - Admin-Status/Rebuild ist ohne Live-Pipeline-Schaltung testbar
  - Qdrant hilft bei natuerlicher Umschreibung
  - falscher Connection-Typ wird nicht ausgefuehrt
  - fehlende/unklare Kandidaten fuehren zu Rueckfrage statt falscher Aktion

#### Skill-Automation strategisch

##### Phase 1: Skill-Engine fuer echte Automationen haerten

- [x] konditionale Skill-Schritte einfuehren
  - erster Engine-Schnitt vorhanden: Step-`condition` mit einfachen Operatoren wie `equals`, `not_equals`, `contains`, `regex`, `is_empty`, `not_empty`
  - Beispiel ist damit jetzt direkt moeglich: `discord_send` nur ausfuehren, wenn der LLM-Schritt nicht `NO_ALERT` ergibt

#### Verifikation offen

- [X] Back-/Ruecksprung-UX auf Formularseiten fachlich statt per Browser-History loesen
  - aktueller Back-Pfeil nutzt Browser-History und landet nach Save/Redirect oft wieder auf derselben Detailseite
  - loesen ueber `return_to`/`next` plus sinnvolle Fallback-Ziele pro Bereich
