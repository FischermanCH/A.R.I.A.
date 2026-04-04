# ARIA — Release-Ready / User-Simulation Plan

Stand: 2026-03-31

## Ziel

ARIA soll so schnell wie möglich **release-ready** werden.

Das bedeutet aktuell **nicht**:
- sofort auf GitHub veröffentlichen
- sofort für offenen Public-Internet-Betrieb freigeben

Das bedeutet aktuell:
- Core härten
- Tests sauber abschließen
- ein echtes Container-Artefakt bauen
- ARIA dann wie ein normaler User betreiben
- Updates über neue Container-Stände simulieren

Wir testen also bewusst nicht nur den Code, sondern die ganze Nutzungskette:

1. Image bauen
2. Container starten
3. konfigurieren
4. produktiv damit arbeiten
5. Änderungen in `dev` machen
6. neues Image erzeugen
7. Update einspielen
8. prüfen, ob Daten, Config und Verhalten stabil bleiben

## Leitprinzip

Vor einer öffentlichen Veröffentlichung gilt:

- **Release-Ready vor Public**
- **User-Simulation vor GitHub**
- **Update-Kette vor Marketing**

ARIA soll zuerst im echten Container-Alltag überzeugen, bevor sie öffentlich verteilt wird.

## Phase A — Core härten

Ziel:
- funktional robuster Kern
- saubere Fehlerrückgaben
- modulare Architektur
- Security im Core mitgedacht

### Pflichtpunkte

1. freie Prompts weiter härten
- natürliche Skill-Auslösung
- stabile Connection-Auflösung
- weniger generische LLM-Antworten bei eigentlich strukturierten Aktionen

2. deterministische Capability-Ausführung stabil halten
- Capability first
- Skill fallback second
- LLM fallback nur eng geführt

3. Fehlerpfade härten
- keine generischen `Internal Server Error` in typischen Flows
- verständliche Nutzermeldungen

4. Security-/Control-Core weiter ausbauen
- Guardrails modular halten
- Confirm-/Pending-Flows stabil halten
- keine stillen riskanten Aktionen

5. Architektur weiter entkoppeln
- `connection_catalog`
- `capability_catalog`
- weniger verstreute Sonderlogik

## Phase B — Großer Testblock

Ziel:
- echter Qualitäts-Gate vor dem ersten Release-Artefakt

### Pflichtumfang

1. Connection-Flows
- anlegen
- bearbeiten
- löschen
- rename
- Tests/Health

2. Chat / Capabilities / Skills
- freie Prompts
- strukturierte Prompts
- Guardrail-verhalten
- Langläufer

3. UI / Browser / Mobile
- Desktop
- iPhone
- Safari
- Firefox

4. Stabilität
- Restart
- Session-Verhalten
- Recovery
- Fehlerpfade

Referenz:
- `project.docu/test-checkliste.md`

## Phase C — Release-Ready Container

Ziel:
- ARIA als verteilbares Container-Artefakt sauber bereitstellen

### Pflichtpunkte

1. Image-Build vereinheitlichen
- reproduzierbarer Build
- klare Versionierung
- saubere Defaults

2. Runtime-Verhalten prüfen
- Volumes
- Persistenz
- Config
- Secrets
- Logs

3. Distribution absichern
- keine unnötig offenen Defaults
- Qdrant-Anbindung absichern
- Fremdabhängigkeiten bewusst prüfen

4. Doku für den Containerbetrieb
- Start
- Volumes
- Upgrade
- bekannte Grenzen

## Phase D — User-Simulation

Ziel:
- ARIA einige Zeit **wie ein Nutzer** betreiben

### Vorgehen

1. Container aus Release-Artefakt starten
2. ARIA normal konfigurieren
3. im Alltag benutzen
4. echte Reibungspunkte sammeln
5. nicht direkt in diesem Container “herumentwickeln”

Wichtig:
- Änderungen passieren weiter in `dev`
- der Simulations-Container bleibt die Nutzersicht

## Phase E — Update-Kette simulieren

Ziel:
- prüfen, ob spätere User-Updates real funktionieren

### Ablauf

1. Problem/Verbesserung in der User-Simulation finden
2. Fix in `dev` umsetzen
3. neues Container-Artefakt bauen
4. Simulations-Instanz aktualisieren
5. prüfen:
  - bleiben Daten erhalten?
  - bleibt die Config gültig?
  - bleiben Connections/Skills/Memories stabil?
  - entstehen Breaking Changes?

Erst wenn diese Kette sauber funktioniert, ist ARIA wirklich release-näher.

## Phase F — GitHub-Ready

Ziel:
- das Repo in einen oeffentlich vertretbaren Zustand bringen
- klare Grenzen und ehrliche ALPHA-Kommunikation
- keine lokalen Altlasten oder irrefuehrenden Defaults veroeffentlichen

### Pflichtpunkte

1. README final schaerfen
- klarer Quickstart
- Docker-/Portainer-Weg sauber erklaeren
- ALPHA-Status klar sagen
- keinen offenen Internetbetrieb empfehlen

2. Repo-Inhalt bewusst schneiden
- nur Dateien ins oeffentliche Repo nehmen, die wirklich produktrelevant sind
- `project.docu/` nur selektiv oder gar nicht veroeffentlichen
- persoenliche Dev-Reste final ausschliessen

3. Privacy-/Clean-Sweep vor Public
- keine privaten Hostnamen, IPs, Usernamen oder Beispielpfade
- keine lokalen Secrets
- keine echten Testdaten in Beispieldateien

4. Rechtliches/Meta
- Lizenz pruefen und klar ablegen
- kurzes ALPHA-Disclaimer-Set vorbereiten
- bekannten Scope und Grenzen klar benennen

## Phase G — Docker-Hub-Ready

Ziel:
- nicht nur lokal baubare, sondern sauber verteilbare Container-Artefakte
- reproduzierbarer, versionierter, oeffentlich nutzbarer Image-Flow

### Pflichtpunkte

1. Image-Versionierung sauberer machen
- nicht nur TAR-Dateinamen hochzaehlen
- auch Image-Tags versionieren
  - z. B. `alpha4`, `alpha5`
- spaeter optional `latest-alpha` zusaetzlich pflegen

2. Registry-Weg festlegen
- Docker-Hub-Namespace festlegen
- spaeter optional GHCR dazu
- finalen Image-Namen in Stack-/Compose-Beispielen nachziehen

3. Release-Artefakte definieren
- was zu jedem Release gehoert:
  - Git-Tag / Release-Notiz
  - Docker-Image
  - Changelog-Eintrag
  - kurze Upgrade-Hinweise

4. Publish-Check vor jedem Push
- Image lokal bauen
- Smoke-Test
- Release-Tag setzen
- erst dann Registry-Push

## Letzter Block vor Public

Bevor ARIA auf GitHub und Docker Hub geht, sollte mindestens gelten:

- Container-Setup laeuft auf einem separaten Host
- Update-Pipe ist real bewiesen
- README ist oeffentlich tragfaehig
- Repo ist privacy-clean
- Docker-/Portainer-Doku ist benutzbar
- ALPHA-Grenzen sind klar kommuniziert

## Offene ALPHA-Grenzen, die bewusst benannt werden sollen

Diese Punkte blockieren eine erste ALPHA-Veroeffentlichung nicht zwingend, muessen aber offen benannt werden:

- ARIA ist aktuell primaer ein persoenliches Single-User-System
- noch kein echtes Multi-User-/RBAC-System
- User-Modus ist eine reduzierte ALPHA-Arbeitsansicht fuer spaetere Einfachheit, nicht vollwertige Mehrbenutzerlogik
- kein offener Public-Internet-Betrieb empfohlen
- noch laufende UI-/Polish-Themen
- spaetere Integrationen und Security-Ausbaustufen sind bewusst nachgelagert

## Was aktuell **nicht** Ziel dieser Phase ist

Diese Punkte bleiben bewusst nachgelagert:

- offener Public-Internet-Betrieb
- GitHub-Veröffentlichung
- `WireGuard / RAS`
- `Multi-User / RBAC`
- `SMTP E2E`
- `IMAP E2E`
- `MQTT E2E`
- `Dokumente / RAG / Knowledge`
- `Theme-/UI-System`

Das sind valide spätere Ausbaustufen, aber kein Blocker für die erste release-nahe Nutzer-Simulation.

## Produktgrenzen für ALPHA

Für den ersten release-nahen Stand gilt bewusst:

- ARIA ist **noch kein Multi-User-System**
- der aktuelle `User-Modus` ist eine reduzierte Betriebsansicht
- `Admin-Modus AUS` soll möglichst nah an dem liegen, was ein späterer normaler User sieht
- das hilft bei UX-Prüfung, Support und der späteren Rollen-/RBAC-Architektur

Für `Skills` bedeutet das in ALPHA:

- keine offene Multi-User-Freigabelogik
- keine Ownership-Engine
- keine geteilten Skill-Berechtigungen
- im `User-Modus` nur reduzierte Sicht
- Skill-Bearbeitung bleibt ein Admin-/Advanced-Thema

Der spätere Ausbau umfasst dann bewusst:

- Skill-Ownership
- Sichtbarkeit/Freigabe
- Ausführungsrechte
- Connection-Scope
- Guardrail-/Policy-Anbindung

## Wichtige Sicherheitsnotiz

Auch wenn der Code später veröffentlicht wird, heißt das **nicht**, dass ARIA schon für offenen Internetbetrieb gedacht ist.

Für die erste reale Nutzung gilt weiterhin:

- LAN
- VPN
- Home-Lab
- kontrollierte Nutzer

Nicht empfohlen in dieser Phase:
- ARIA direkt offen ins Internet hängen

## Aktuelle Prioritätsreihenfolge

1. Core härten
2. großen Testblock sauber fahren
3. Release-Ready-Container bauen
4. User-Simulation starten
5. Update-Kette simulieren
6. erst danach Veröffentlichung breiter denken

## Release-Gate für den ersten Container-Run

Bevor wir die User-Simulation starten, sollte mindestens gelten:

- Kernfunktionen stabil
- bekannte freie Prompt-Kanten nachgetestet
- Guardrails im Core tragfähig
- keine typischen `Internal Server Error`
- Testcheckliste in gutem Zustand
- Doku für Containerstart und Persistenz vorhanden

## Fazit

Wir optimieren jetzt bewusst auf:

- **sauberen modularen Core**
- **kontrollierte Release-Reife**
- **echte Nutzersimulation**
- **funktionierende Update-Kette**

Nicht auf:

- vorschnelle Public-Veröffentlichung
- offenen Internetbetrieb
- neue Nice-to-have-Features vor Kernqualität
