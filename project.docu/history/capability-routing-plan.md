# ARIA Capability Routing Plan

Stand: 2026-03-29
Status: Phase 3 begonnen

## Ziel

ARIA soll Nutzerwünsche nicht nur über starre Skill-Keywords erkennen, sondern über fachliche **Capabilities** verstehen und dann den passenden **Executor** und **Connection-Typ** wählen.

Beispiel:

- User: `Schreib mir auf dem Server eine Datei /tmp/info.txt mit Inhalt hallo`
- ARIA erkennt:
  - Capability: `file_write`
  - Zieltyp: `remote_file`
  - bevorzugter Transport: `sftp`
  - passendes Profil: z. B. `ubnsrv-mgmt-master`
- danach führt ARIA deterministisch den passenden Executor aus

Wichtig:

- **Memory wird von Anfang an einbezogen**
- **LLM hilft beim Verstehen**
- **die Ausführung bleibt kontrolliert und validiert**
- **die Architektur bleibt modular und später UI-erweiterbar**

---

## Warum dieser Schritt jetzt sinnvoll ist

Jetzt ist der richtige Zeitpunkt:

- ARIA hat bereits mehrere Connection-Typen
- die Connection-Runtime ist gerade zentralisiert worden
- SFTP/SMB und weitere Verbindungen werden sonst schnell mit Sonderlogik zugepflastert
- spätere user-generierte Erweiterungen brauchen ein sauberes Capability-/Executor-Modell

Wenn wir zu lange warten, entsteht leicht:

- Keyword-Spaghetti
- pro Connection-Typ eigene Sonderpfade
- doppelte Validierung
- schlechtere Erweiterbarkeit im UI

---

## Grundidee

ARIA arbeitet künftig in vier klaren Schichten:

1. **Capability erkennen**
2. **Memory-Assist und Disambiguation**
3. **Executor/Connection auswählen**
4. **Deterministisch validieren und ausführen**

Das trennt sauber:

- fachliche Absicht
- Kontext-/Wissensauflösung
- technische Ausführung

---

## Leitprinzipien

### 1. Capability vor Transport

Nicht zuerst:

- `das klingt nach SFTP`

Sondern zuerst:

- `das ist file_write`

Erst danach wird entschieden:

- `file_write` über `sftp`
- oder später `smb`

### 2. Memory als Assistenz, nicht als Autopilot

Memory darf helfen bei:

- Standardserver
- bevorzugte Verbindungen
- Host-Aliase
- häufig genutzte Pfade
- zuletzt verwendete Ziele

Memory darf **nicht** blind gefährliche Aktionen erzwingen.

### 3. LLM für Verstehen, Code für Ausführung

Das LLM darf:

- Capability vorschlagen
- fehlende Parameter strukturieren
- unklare Sprache interpretieren

Der Code muss:

- Verbindungen validieren
- erlaubte Executor wählen
- Pfade und Parameter prüfen
- Sicherheitsregeln durchsetzen

### 4. User-Erweiterbarkeit mitdenken

Die Architektur soll so gebaut sein, dass später im UI:

- neue Capability-/Executor-Kombinationen ergänzt werden können
- Connection-Typen generisch beschrieben werden können
- user-generierte Erweiterungen nicht an monolithischem Spezialcode scheitern

---

## Zielarchitektur

```text
User Request
   ↓
Capability Router
   ↓
Memory Assist Resolver
   ↓
Action Plan Builder
   ↓
Executor Registry
   ↓
Connection Runtime
   ↓
Result Formatter / Chat
```

### Neue Kernbausteine

- `aria/core/capability_router.py`
- `aria/core/memory_assist.py`
- `aria/core/action_plan.py`
- `aria/core/executor_registry.py`
- bestehend als Basis:
  - `aria/core/connection_runtime.py`

---

## Capability-Schicht

### Erste Capability-Familie

Wir starten bewusst klein:

- `file_read`
- `file_write`
- `file_list`

Später möglich:

- `remote_command`
- `send_notification`
- `fetch_feed`
- `http_call`
- `email_send`

### Ziel

Die Capability-Schicht beantwortet:

- Was will der User fachlich?

Sie beantwortet noch **nicht**:

- Mit welcher Connection?
- Mit welchem konkreten Profil?

### Beispiel-Output

```json
{
  "capability": "file_write",
  "confidence": 0.92,
  "raw_user_goal": "remote file write"
}
```

---

## Memory-Assist-Schicht

### Aufgabe

Memory soll offene Parameter ergänzen oder auflösen.

### Memory darf helfen bei

- bevorzugter `connection_kind`
- bevorzugter `connection_ref`
- Host-/Server-Aliase
- Pfad-Aliase
- zuletzt erfolgreich genutzte Ziele
- Benutzerpräferenzen wie:
  - `für Dateien meist mgmt-master`
  - `bevorzugter Arbeitsordner`

### Memory darf nicht automatisch speichern

- komplette Datei-Inhalte
- Secrets
- Passwörter
- Tokens
- rohe technische Dumps

### Geeignete Memory-Typen

- `preferences`
  - z. B. `Für Dateizugriffe nutzt der User meist ubnsrv-mgmt-master`
- `facts`
  - z. B. `backup-share ist ein SMB-Share`

### Beispiel-Output

```json
{
  "preferred_connection_kind": "sftp",
  "preferred_connection_ref": "ubnsrv-mgmt-master",
  "path_hint": "/home/fischerman/"
}
```

---

## Action-Plan-Schicht

### Aufgabe

Hier entsteht aus Capability + Memory + Usertext ein strukturierter Plan.

### Beispiel

```json
{
  "capability": "file_write",
  "connection_kind": "sftp",
  "connection_ref": "ubnsrv-mgmt-master",
  "path": "/tmp/info.txt",
  "content": "hallo",
  "needs_confirmation": false
}
```

### Regeln

- Wenn zu viele Parameter fehlen:
  - Rückfrage statt Halluzination
- Wenn mehrere Ziele plausibel sind:
  - Memory-Präferenz nutzen oder Rückfrage
- Wenn Aktion riskant ist:
  - `needs_confirmation = true`

---

## Executor-Schicht

### Aufgabe

Die Executor-Schicht mappt Capability + Connection-Typ auf echte Runtime-Aktionen.

### Start-Mapping

- `file_read` + `sftp` -> `sftp_read`
- `file_write` + `sftp` -> `sftp_write`
- `file_list` + `sftp` -> neuer `sftp_list`

Später:

- `file_read` + `smb`
- `file_write` + `smb`
- `file_list` + `smb`

### Ziel

Das Mapping bleibt klein, testbar und explizit.

Keine Magie:

- Capability bestimmt die Aktion
- Executor bestimmt die Implementierung

---

## LLM-Rolle

### LLM darf

- freie Sprache in Capability übersetzen
- unklare Dateiwünsche strukturieren
- Dateiinhalte vorbereiten, wenn der User das will
- Rückfragen natürlicher formulieren

### LLM darf nicht

- direkt Executors aufrufen
- Sicherheitsregeln umgehen
- Connections frei erfinden
- unbestätigte riskante Aktionen ausführen

### Empfehlung

Das LLM liefert strukturierte Vorschläge, z. B.:

```json
{
  "capability": "file_write",
  "path": "/tmp/info.txt",
  "content": "hallo"
}
```

Danach validiert ARIA diese Daten deterministisch.

---

## Sicherheitsmodell

### Immer prüfen

- existiert die `connection_ref`?
- passt die `connection_kind`?
- ist die Capability für diesen Executor erlaubt?
- ist der Pfad plausibel und nicht leer?
- fehlt eine Bestätigung?

### Confirm-Flow für riskante Aktionen

Beispiele:

- Überschreiben bestehender Dateien
- Schreiben in sensible Pfade
- Löschen von Dateien

Diese Punkte sollen nicht “nur weil das LLM es gut gemeint hat” durchlaufen.

---

## Modularität / UI-Erweiterbarkeit

Diese Architektur soll die spätere UI-Erweiterbarkeit vorbereiten.

### Später im UI denkbar

- Capability-Definitionen pflegen
- Executor-Mapping pflegen
- Connection-Typen generisch registrieren
- User-generierte Erweiterungen auf strukturierter Basis erzeugen

### Dafür wichtig

- Capabilities sind Daten, nicht nur Hardcode
- Executors sind registriert, nicht verstreut
- Connection-Typen hängen an gemeinsamer Runtime
- Memory-Assist ist separat, nicht in Skills versteckt

---

## Umsetzung in Phasen

### Phase 1: Architektur-Grundlage

Neue Module:

- `aria/core/capability_router.py`
- `aria/core/memory_assist.py`
- `aria/core/action_plan.py`
- `aria/core/executor_registry.py`

Scope:

- Capability-Familie `file_*`
- erst einmal nur `sftp`

Akzeptanz:

- keine Änderung bestehender SSH-/Discord-/Connection-Health-Flows
- neue Schicht ist additiv

Status:

- begonnen
- erste Basis bereits umgesetzt:
  - `aria/core/capability_router.py`
  - `aria/core/memory_assist.py`
  - `aria/core/action_plan.py`
  - `aria/core/executor_registry.py`
  - additiver Pipeline-Hook für `chat`-Requests ohne Custom-Skill-Treffer
  - erster Executor-Pfad für `SFTP`

### Phase 2: SFTP als erster Capability-Executor

Ziel:

- Chat-Anfrage kann `file_write`, `file_read`, `file_list` als SFTP-Aktion ausführen

Akzeptanz:

- ARIA kann aus natürlicher Sprache Dateiwünsche als SFTP-Aktionen ausführen
- mit Rückfrage wenn Connection/Ziel unklar bleibt

Status:

- teilweise umgesetzt
- aktuell möglich:
  - `file_read`
  - `file_write`
  - `file_list`
  - direkte deterministische Antwort ohne zusätzlichen LLM-Call
  - Auflösung der `connection_ref` via:
    - explizite Erwähnung im Chat
    - einzig vorhandenes SFTP-Profil
    - Memory-Assist über bestehende Memory-Suche
- noch offen:
  - breiterer Sprachraum / robustere Parser
  - optionaler LLM-Planer als zusätzliche Schicht über der Regelbasis

### Phase 3: Memory-Assist aktiv einbinden

Ziel:

- Memory ergänzt bevorzugte Connection und Zielhinweise

Akzeptanz:

- Follow-up-Aktionen wie “wie letztes Mal auf dem Management-Server” werden plausibel aufgelöst

Status:

- begonnen
- operative Kurzzeit-Kontexte werden jetzt file-basiert pro User gespeichert:
  - letzter erfolgreicher `connection_ref`
  - letzter erfolgreicher Pfad
- `MemoryAssistResolver` nutzt diese Daten bereits für Follow-up-Formulierungen wie:
  - `wie letztes Mal`
  - `im gleichen Ordner`
  - `im gleichen Pfad`
- die bestehende semantische Memory-Suche bleibt als zusätzlicher Resolver aktiv

### Phase 4: SMB als zweiter Transport

Ziel:

- dieselben Capabilities laufen auch über `smb`

Akzeptanz:

- Capability-Schicht bleibt gleich
- nur Executor-/Connection-Mapping wächst

Status:

- begonnen
- `file_read`, `file_write`, `file_list` können jetzt neben `SFTP` auch über `SMB` aufgelöst und ausgeführt werden
- Connection-/Executor-Wahl bleibt dabei im selben Capability-Pfad
- explizite SMB-Refs, SMB-/NAS-/Share-Hinweise und Single-Profile-Defaults werden bereits berücksichtigt

### Phase 5: RSS als erste Nicht-Datei-Capability

Ziel:

- ARIA kann RSS-/Atom-Feeds über denselben Capability-Pfad lesen

Akzeptanz:

- natürliche Feed-Anfragen werden als `feed_read` erkannt
- Ausführung bleibt deterministisch
- RSS-Profile werden wie andere Connections über `connection_ref` / Default / Memory-Assist aufgelöst

Status:

- begonnen
- erste Capability `feed_read` ist aktiv
- `RSS` ist damit die erste kleine Nicht-Datei-Capability auf derselben Architektur

---

## Nicht-Ziele am Anfang

Diese Punkte gehören bewusst **nicht** in den ersten Schritt:

- generischer Voll-Autopilot für alle Connections
- user-generierte Executor direkt im ersten Wurf
- unlimitierte LLM-Entscheidung über Ausführung
- komplettes Dokumenten-/RAG-System

---

## Entscheidung

Empfehlung:

- diesen Capability-/Memory-Assist-Pfad als nächsten Architekturblock starten
- klein beginnen mit:
  - `file_read`
  - `file_write`
  - `file_list`
  - `sftp`
- danach `memory_assist`
- danach `smb`

Warum:

- hoher Nutzwert
- geringe spätere Migrationskosten
- saubere Grundlage für modulare und später UI-generierbare Erweiterungen

### Erweiterung: Webhook

- Neue Capability `webhook_send` als eigener Output-Zweig neben `file_*` und `feed_read`.
- Erstes Zielbild: natuerliche Sprache -> Profilaufloesung -> deterministische Ausfuehrung via Webhook-Profil.
- Bewusst klein gehalten: MVP fuer Nachrichtenversand, spaetere Ausbaustufen koennen strukturierte Payloads und Skill-Steps nachziehen.

### Erweiterung: HTTP API

- Neue Capability `api_request` als eigener Integrations-Zweig neben `file_*`, `feed_read` und `webhook_send`.
- Erstes Zielbild: natuerliche Sprache -> Profilaufloesung -> deterministischer HTTP-API-Aufruf.
- MVP bleibt bewusst schlank: Profilmethoden und Pfade werden genutzt, spaetere Ausbaustufen koennen strukturierte Bodies und Antwort-Schemata ergaenzen.

### Erweiterung: Mail-Connections

- Mail wird in den Connections jetzt sauber in `SMTP` und `IMAP` getrennt.
- `SMTP` bleibt der Sendekanal. `IMAP` ist der zukünftige Lese-/Suchkanal.
- Die bestehende Datenbasis fuer SMTP bleibt erhalten; nur die UI-/Route-Struktur wurde konsistent nachgeschärft.

### Erweiterung: Mail-Capabilities

- `email_send` ergänzt den Capability-Pfad als SMTP-basierter Sendekanal.
- `mail_read` und `mail_search` ergänzen den Capability-Pfad für IMAP-Mailboxen.
- Damit ist Mail jetzt architektonisch konsistent getrennt: SMTP für Versand, IMAP für Lesen/Suchen.

### Erweiterung: MQTT

- `mqtt_publish` ergänzt den Capability-Pfad als schlanker Publish-MVP.
- Das Topic kann explizit im Prompt gesetzt oder aus dem Profil übernommen werden.
- Bewusst klein gehalten: erst Publish, keine dauerhafte Subscription-/Listener-Logik.
