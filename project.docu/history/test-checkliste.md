# ARIA Test-Checkliste

Stand: 2026-04-01

## Nutzung

- Diese Liste ist die zentrale Referenz für den kompletten manuellen und operativen Testplan.
- Status pro Punkt setzen: `[ ] offen`, `[x] erledigt`, `[-] bewusst verschoben`.
- Reihenfolge ist wichtig:
  1. Vor `Docker / Compose ALPHA Smoke`
  2. `Docker / Compose ALPHA Smoke`
  3. `Update-Pipe`
  4. bewusst verschobene Tests

## 0. Automatisierte Basis

Aktueller Stand:
- [x] volle Testsuite in der Projekt-Umgebung grün
- [x] `208 passed`
- [x] Qdrant-/Stats-/Token-Tracker-/i18n-/Guardrail-/Routing-/Session-/Capability-Tests grün

Hinweis:
- Diese Checkliste ergänzt die automatisierten Tests um reale E2E-, UI-, Browser-, Container- und Betriebsprüfungen.

---

## 1. Vor Docker / Compose ALPHA Smoke

### 1.1 Start, Betrieb, Restart

- [ ] `./aria.sh start` startet ARIA sauber
- [ ] `./aria.sh status` zeigt laufenden Prozess + korrekte URL
- [ ] `GET /health` liefert `{"status":"ok"}`
- [ ] `./aria.sh restart` funktioniert ohne manuellen Eingriff
- [ ] Restart-UX: offene Unterseite landet nach Restart sauber bei Login statt auf einer kaputten/stalen Seite
- [ ] `/api/system/preflight` liefert plausiblen Gesamtstatus
- [ ] `/stats` zeigt `Startprüfung` und `Systemzustand` ohne Mischsprache

### 1.2 Login, Sessions, Rollen

- [ ] Erstanmeldung: erster User wird automatisch als `admin` angelegt
- [ ] Bei `security.bootstrap_locked: true` ist Auto-Bootstrap gesperrt
- [ ] Login mit gültigen Daten führt auf `/`
- [ ] Logout beendet Session sauber
- [ ] Ungültige/abgelaufene Session leitet auf `/session-expired` und danach Login
- [ ] Deaktivierter User mit altem Cookie verliert Zugriff sofort
- [ ] Case-sensitive Login bleibt korrekt (`fischerman` vs `Fischerman`)
- [ ] `user` sieht kein `Config`-Menü
- [ ] `admin` sieht `Config`-Menü und kann es öffnen
- [ ] `admin` mit `Admin-On/Off = aus`: technische Bereiche ausgeblendet, Benutzerbereich bleibt erreichbar
- [ ] `admin` mit `Admin-On/Off = an`: volle Advanced-Sicht erscheint wieder
- [ ] `user`: direkte Zugriffe auf `LLM`, `Embeddings`, `Routing`, `Skill Routing`, `Security`, `Dateien`, `Logs`, `Error Interpreter` werden blockiert

### 1.3 Sprache / i18n

- [ ] Sprachwechsel `DE -> EN -> DE` wirkt sofort sichtbar im UI
- [ ] Topbar, Menü, Stats, Connections, Memories, Prompt Studio, File Editor bleiben konsistent übersetzt
- [ ] Connection-Testmeldungen folgen ebenfalls der aktiven Sprache
- [ ] keine sichtbaren harten Resttexte in Deutsch/Englisch auf Kernflächen

### 1.4 Chat & allgemeine UX

- [ ] Enter sendet
- [ ] Eingabe ist während Verarbeitung gesperrt
- [ ] Typing-/Working-Indikator sichtbar
- [ ] Long-Running-Flow zeigt ehrliche Zwischenmeldung statt still zu hängen
- [ ] `cls` / `/cls` / `clear` / `/clear` löscht den serverseitigen Chatverlauf wie erwartet
- [ ] Zweiter Browser / zweites Gerät lädt den aktuellen Chat-Verlauf korrekt nach
- [ ] Toolbox bleibt bedienbar auf Desktop und iPhone
- [ ] Toolbox schließt sauber bei Klick ins Leere

### 1.5 Stats, Activities, Logs & Retention

- [ ] `/stats` öffnet korrekt
- [ ] `Systemzustand` und `Startprüfung` bleiben schnell und plausibel
- [ ] keine `unknown`-Artefakte aus Altlogs sichtbar
- [ ] Kostenanzeige wirkt plausibel, wenn Pricing aktiv ist
- [ ] `/activities` zeigt kompakte Übersicht; Details erst nach Aufklappen
- [ ] `/activities` blendet irrelevante Null-/`web`-/`chat`-Infos aus
- [ ] `Einstellungen > Logs & Retention`: Speichern der Aufbewahrungsdauer funktioniert
- [ ] `Einstellungen > Logs & Retention`: Cleanup entfernt alte Einträge gemäß `retention_days`
- [ ] `Einstellungen > Logs & Retention`: leerer Reset zeigt klare Fehlmeldung
- [ ] `Einstellungen > Logs & Retention`: falscher Reset-Text zeigt klare Fehlmeldung
- [ ] `Einstellungen > Logs & Retention`: `RESET` löscht Stats-/Activities-Historie, aber nicht Memories oder Connections
- [ ] Wirkung des Stats-Resets ist auf `/stats` und `/activities` nachvollziehbar

### 1.6 Memory & Qdrant

- [ ] Explizit speichern: `merk dir ...` schreibt in Qdrant
- [ ] Explizit abrufen: `was weisst du ...` nutzt gespeichertes Wissen
- [ ] Kein doppeltes Schreiben bei identischem Fakt
- [ ] Recall kombiniert Facts + Sessions plausibel
- [ ] Auto-Memory `OFF`: normale Aussage erzeugt keinen Auto-Store
- [ ] Auto-Memory `ON`: normale Aussage erzeugt Memory-Eintrag(e)
- [ ] `/memories` zeigt Health-Karten mit plausiblen Werten
- [ ] `/memories` Editieren funktioniert
- [ ] `/memories/map` zeigt Collections/Punktanteile plausibel
- [ ] `/memories/map`: Qdrant-Link korrekt
- [ ] `/memories/map`: Qdrant-Key-Reveal/Copy funktioniert sauber
- [ ] Qdrant-Preflight und `/stats` melden denselben realen Zustand

### 1.7 Security / Guardrails

- [ ] `Config > Security Guardrails` speichert `bootstrap_locked` korrekt
- [ ] Guardrail-Profil anlegen, bearbeiten und löschen funktioniert
- [ ] SSH-Connection kann ein `ssh_command`-Guardrail referenzieren
- [ ] `HTTP API` / `Webhook` können `http_request`-Guardrails referenzieren
- [ ] `SFTP` / `SMB` können `file_access`-Guardrails referenzieren
- [ ] SSH-Guardrail blockiert verbotene SSH-Kommandos zuverlässig
- [ ] HTTP-Guardrail blockiert unerlaubte Methode/URL/Pfad zuverlässig
- [ ] File-Guardrail blockiert unerlaubte Dateioperationen/Pfade zuverlässig

### 1.8 Connections UI / Admin-Flows

- [ ] `Einstellungen > Verbindungen` listet alle Connection-Typen klar getrennt
- [ ] Connection-UI: `Bearbeiten` und `Neu` sind auf allen Seiten klar getrennt
- [ ] neue Profile starten wirklich mit leeren Feldern
- [ ] bestehende Profile lassen sich gezielt laden, bearbeiten und löschen
- [ ] Connection-Edit aktualisiert das bestehende Profil statt still ein neues anzulegen
- [ ] Connection-Rename migriert Secret/Status sauber mit
- [ ] RSS-Dubletten werden verhindert

### 1.9 Connection-Seiten E2E

- [ ] `/config/connections/ssh`
  - öffnen
  - bestehendes Profil laden
  - speichern
  - Guardrail sichtbar und speicherbar
  - löschen
- [ ] `/config/connections/discord`
  - öffnen
  - Profil laden
  - speichern
  - Alert-Kategorien sichtbar und verständlich
- [ ] `/config/connections/sftp`
  - öffnen
  - Profil laden
  - speichern
  - optional SSH-Vorlage übernehmen
- [ ] `/config/connections/smb`
  - öffnen
  - Profil laden
  - speichern
- [ ] `/config/connections/webhook`
  - öffnen
  - Profil laden
  - speichern
- [ ] `/config/connections/smtp`
  - öffnen
  - Profil laden
  - speichern
- [ ] `/config/connections/imap`
  - öffnen
  - Profil laden
  - speichern
- [ ] `/config/connections/http-api`
  - öffnen
  - Profil laden
  - speichern
- [ ] `/config/connections/rss`
  - öffnen
  - Gruppenansicht stabil
  - `Kategorien aktualisieren` funktioniert
- [ ] `/config/connections/mqtt`
  - öffnen
  - Profil laden
  - speichern

### 1.10 Connection Health / Stats-Konsistenz

- [ ] Dieselbe Connection zeigt auf Unterseite und `/stats` denselben Status-/Fehlertext
- [ ] `/stats` verlinkt korrekt auf die jeweilige Connection-Seite
- [ ] `/stats` bleibt trotz Connection-Checks responsiv genug

### 1.11 Chat-Admin-Flow

- [ ] Chat-`create` für `Discord`, `RSS`, `Webhook`, `HTTP API` manuell prüfen
- [ ] Chat-`update` für `Discord`, `RSS`, `Webhook`, `HTTP API` manuell prüfen
- [ ] Chat-`create` für `SSH`, `SFTP`, `SMB`, `SMTP`, `IMAP`, `MQTT` manuell prüfen
- [ ] Chat-`update` für `SSH`, `SFTP`, `SMB`, `SMTP`, `IMAP`, `MQTT` manuell prüfen
- [ ] `delete` per Chat mit Confirm-Step prüfen
- [ ] Titel/Beschreibung/Tags/Aliase aus dem Prompt erscheinen in der Vorschau und werden korrekt gespeichert
- [ ] Fehlermeldungen im Chat sind klar und nicht technisch roh

### 1.12 Capabilities / Routing / freie Prompts

- [ ] freier Prompt `machst du mir ein update auf dem server` trifft robust den richtigen SSH-/Update-Skill
- [ ] freier Prompt `zeige mir die daten aus dem docker verzeichnis von synrs816` trifft robust SMB
- [ ] freier Prompt `schicke eine test nachricht nach discord ...` trifft robust `discord_send`
- [ ] freier Prompt `rufe den inventory endpoint /health auf` trifft robust `api_request`
- [ ] RSS-Prompt wie `was gibts neues auf heise online news` trifft robust RSS
- [ ] `HTTP API` Capability E2E: korrekter Pfad / Health-Pfad / lesbare Antwort / richtige Details
- [ ] `SFTP` Capability E2E: Lesen / Schreiben / Listen + Follow-up (`wie letztes Mal`, `gleicher Pfad`)
- [ ] `SMB` Capability E2E: Lesen / Schreiben / Listen + Follow-up auf gleichem Share/Pfad

### 1.13 Custom Skills / Wizard

- [ ] neuer Skill via `/skills/wizard` anlegen funktioniert
- [ ] Skill erscheint danach automatisch unter `/skills`
- [ ] Skill-ID-Änderung im Wizard migriert die JSON-Datei korrekt
- [ ] Skill-Import legt/aktualisiert Skill korrekt
- [ ] Skill-Export liefert gültiges JSON
- [ ] Wizard: weitere Steps lassen sich dynamisch hinzufügen
- [ ] Wizard: Connection-Auswahl pro Step ist konsistent
- [ ] Wizard: Schedule (`cron/timezone`) speicherbar und sichtbar
- [ ] Step-Skill `ssh_run -> llm_transform -> discord_send` läuft in korrekter Reihenfolge
- [ ] `on_error=continue` funktioniert in Folgeschritten

### 1.14 Prompt Studio / File Editor

- [ ] Prompt Studio: Datei laden, ändern, speichern, zurückändern
- [ ] File Editor: Datei laden, ändern, speichern, zurückändern
- [ ] verständliche Fehlermeldung statt roher Exception
- [ ] Persona-Name aus `persona.md` zieht sichtbar im UI mit

### 1.15 Benutzerverwaltung

- [ ] User-Menü führt zur Benutzerverwaltung
- [ ] neuen `user` anlegen
- [ ] neuen `admin` anlegen
- [ ] Rolle ändern
- [ ] User aktiv/deaktivieren
- [ ] Passwort-Reset über Optional-Feld
- [ ] letzter aktiver Admin kann nicht entfernt/deaktiviert werden
- [ ] eingeloggter Admin kann sich nicht selbst zu `user` machen
- [ ] Username-Umbenennung inkl. Session-Update funktioniert

### 1.16 Browser / Mobile

- [ ] Firefox: Layout ok
- [ ] Safari: Layout ok
- [ ] iPhone: Topbar / Menü / Toolbox / Memories / Stats / Connections bedienbar
- [ ] keine horizontale Überbreite auf Kernseiten

### 1.17 Security Header / CSRF

- [ ] `Content-Security-Policy` vorhanden
- [ ] `X-Frame-Options: DENY` vorhanden
- [ ] `X-Content-Type-Options: nosniff` vorhanden
- [ ] POST ohne CSRF-Token liefert `403`
- [ ] POST mit gültigem CSRF-Token funktioniert

---

## 2. Docker / Compose ALPHA Smoke

### 2.1 Build & Start

- [ ] Docker-Image baut sauber
- [ ] `docker compose up` startet `aria` + `qdrant` sauber
- [ ] Health von ARIA ist grün
- [ ] Qdrant ist erreichbar und authentifiziert
- [ ] Erststart benötigt möglichst wenig User-Interaktion

### 2.2 Config & ENV

- [ ] `ARIA_QDRANT_API_KEY` kann per `.env` / Compose / Portainer-Stack gesetzt werden
- [ ] ARIA und Qdrant verwenden denselben Key korrekt
- [ ] keine verwirrenden Default-Fallen in Compose/README
- [ ] Volumes für Config/Daten/Logs/Qdrant sind korrekt dokumentiert und funktional

### 2.3 Funktion im Container

- [ ] Login funktioniert im Container-Setup
- [ ] Memory/Qdrant funktioniert im Container-Setup
- [ ] `/stats` und Preflight sind im Container plausibel
- [ ] Connections bleiben funktional
- [ ] Logs/Retention/Stats-Reset funktionieren im Container-Setup

### 2.4 Restart & Persistenz

- [ ] `docker compose restart` verliert keine relevanten Daten
- [ ] Config bleibt erhalten
- [ ] Memories bleiben erhalten
- [ ] Chat-History bleibt erhalten
- [ ] Qdrant-Daten bleiben erhalten

---

## 3. Update-Pipe-Simulation

### 3.1 Image-Update

- [ ] Änderung in `dev` umsetzen
- [ ] neues Image bauen
- [ ] neues Image taggen
- [ ] bestehende Instanz per neuem Image aktualisieren

### 3.2 Verifikation nach Update

- [ ] Config bleibt gültig
- [ ] Daten bleiben erhalten
- [ ] Qdrant bleibt erreichbar
- [ ] Secrets bleiben intakt
- [ ] Guardrails bleiben intakt
- [ ] Connections bleiben intakt
- [ ] keine sichtbaren UI-/i18n-Regressions
- [ ] keine Breaking Changes in typischen User-Flows

### 3.3 Dokumentation

- [ ] Update-Anleitung ist für User nachvollziehbar dokumentiert
- [ ] bekannte Breaking-Risiken / Migrationspunkte sind notiert

---

## 4. Vor Veröffentlichung auf GitHub / Docker Hub

- [ ] README vollständig und ehrlich
- [ ] ALPHA-Hinweise klar sichtbar
- [ ] Security-Hinweis klar sichtbar
- [ ] Betriebshinweis klar sichtbar: nicht direkt offen ins Internet hängen
- [ ] Release-Notizen / Changelog vorbereitet
- [ ] Beispieltexte / Platzhalter / interne Reste in distributiven Dateien bereinigt

---

## 5. Bewusst verschobene Tests

Diese Punkte bleiben im Gesamtplan, blockieren aber `Release ALPHA` nicht.

### 5.1 Später nachziehen: Connection E2E mit externer Infrastruktur

- [-] `SMTP` E2E vollständig mit realem Mailversand
- [-] `IMAP` E2E vollständig mit realem Mail-Lesen/Suchen
- [-] `MQTT` E2E vollständig mit realem Broker/Publish

### 5.2 Später nachziehen: Remote Access / Public Exposure

- [-] `WireGuard / RAS` E2E
- [-] öffentlicher Remote-Access-Flow
- [-] Public-Internet-Betrieb als eigener Hardening-Block

### 5.3 Später nachziehen: Produktausbau

- [-] `Multi-User / RBAC` tiefer Testblock
- [-] `Dokumente / RAG / Knowledge` E2E
- [-] `Theme-/UI-System` Testblock
- [-] spätere Integrationen wie `Apple Music`

---

## Nächster Ablauf

1. Abschnitt `1. Vor Docker / Compose ALPHA Smoke` vollständig durchziehen
2. danach Abschnitt `2. Docker / Compose ALPHA Smoke`
3. danach Abschnitt `3. Update-Pipe-Simulation`
4. erst dann Veröffentlichung vorbereiten
