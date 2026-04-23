# ARIA Hilfe: Memory und Stores

Stand: 2026-04-06

## Zweck

Dieses Dokument beschreibt, wie ARIA Wissen speichert, in welche Qdrant-Collections geschrieben wird und wie Antworten später wieder aus diesem Wissen erzeugt werden.

Es ist als Basis für ein späteres Hilfe-System im Web-UI gedacht.

Wichtige Abgrenzung:

- `Memory` ist ARIAs semantischer Wissensspeicher
- `Notizen` unter `/notes` sind ein eigener Markdown-first Arbeitsbereich
- Notizen koennen fuer Suche ebenfalls in Qdrant indiziert werden, gehoeren aber produktisch nicht in den Memory-Bereich

## Was bewusst nicht ins semantische Memory geht

Nicht jede Chat-Nachricht ist Wissen. Operative Skill-Trigger werden deshalb nicht als Tages-Kontext gespeichert.

Beispiele:

- `systemupdate mgmt-master`
- reine Skill-/Tool-Trigger
- technische Bedienbefehle
- reine Ausführungsaufforderungen ohne dauerhaftes Wissen

Ziel:

- Qdrant enthält möglichst stabiles Wissen
- weniger Memory-Rauschen
- besseres Recall-Verhalten mit weniger irrelevanten Treffern

Bereits vorhandene Alt-Eintraege können über die Maintenance bereinigt werden:

`./aria.sh maintenance`

Der Output enthält dafür den Zähler:

`noise=<anzahl>`

## Store-Typen

ARIA arbeitet aktuell mit vier Memory-Ebenen pro Benutzer:

### 1. Nutzer-Speicher

Schema:

`aria_facts_<username>`

Beispiel:

`aria_facts_alice`

Zweck:

- langfristiges Wissen pro Benutzer
- Fakten, die dauerhaft relevant bleiben
- explizite Speicherbefehle wie `merk dir ...` landen hier

### 2. Tages-Kontext (Qdrant)

Schema:

`aria_sessions_<username>_YYMMDD`

Beispiel:

`aria_sessions_alice_260317`

Zweck:

- kurz- bis mittelfristiges Tageswissen
- automatische Memory-Extraktion pro Tag
- besser sortierbar und kontrollierbar als zufaellige Session-IDs

### 3. Kontext-Memory (rollup)

Schema:

`aria_context-mem_<username>`

Beispiel:

`aria_context-mem_alice`

Zweck:

- sammelt komprimierte Inhalte aus alten Qdrant-Tages-Kontext-Collections
- reduziert Collection-Sprawl in Qdrant
- bleibt für Recall als Wissensquelle aktiv

### 4. Dokument-Collections (RAG v1)

Schema:

`aria_docs_<name>`

Beispiele:

- `aria_docs_alice`
- `aria_docs_manuals`
- `aria_docs_fischerman_lab`

Zweck:

- hochgeladene Dokumente für RAG
- Chunk-basierter Import von `txt`, `md` und `pdf` mit eingebettetem Text
- bewusst getrennt von Facts, Preferences und Rollup-Wissen

Wichtig:

- Dokument-Collections sind eigene Wissensquellen
- sie sollen nicht mit normalen Facts-/Preference-/Session-Collections vermischt werden
- wenn nach dem Löschen eines Dokuments keine Chunks mehr übrig sind, räumt ARIA die leere Collection direkt mit auf

Wichtig:

- Der bisherige "Session-Store" ist jetzt tagbasiert.
- Pro Benutzer gibt es damit standardmaessig genau eine Tages-Kontext-Collection pro Kalendertag.
- Eine neue Tages-Kontext-Collection entsteht automatisch am nächsten Tag durch das Namensschema.

Kompatibilitaet:

- Bestehende Alt-Collections (`aria_memory...`) bleiben lesbar und werden nicht automatisch migriert.
- Neues Schreiben läuft über die typisierten Prefixe (`aria_facts`, `aria_sessions`).

## Wann wird wohin geschrieben

### Explizites Speichern

Beispiel:

`Merk dir, dass mein Intranet auf 10.0.0.10 läuft.`

Verhalten:

- ARIA erkennt `memory_store`
- der Inhalt wird in den Nutzer-Speicher geschrieben
- doppelte Fakten werden nach Möglichkeit dedupliziert

### Auto-Memory

Beispiel:

`Hostname: homelab-mgmt-01, IP: 10.0.0.10`

Verhalten bei aktivem Auto-Memory:

- ARIA extrahiert aus der Nachricht ein oder mehrere Fakten
- ARIA trennt dabei jetzt zwischen:
  - Facts -> `aria_facts_<user>`
  - Preferences -> `aria_preferences_<user>`
  - Session-Kontext -> `aria_sessions_<user>_<YYMMDD>`
- flüchtige Einmalfragen und reine Tool-/Action-Prompts werden nicht mehr automatisch als neuer Session-Kontext gespeichert, solange kein klares Fakt- oder Präferenzsignal enthalten ist
- Ziel ist schnelles, kontrolliertes Arbeitsgedaechtnis ohne dauerhaft alles in den Hauptspeicher zu kippen

Verhalten bei deaktiviertem Auto-Memory:

- es wird nichts automatisch gespeichert
- nur explizite Speicherbefehle fuehren zu einem Write

## Wie Recall funktioniert

Bei einer Recall-Frage kombiniert ARIA mehrere Wissensquellen:

1. Nutzer-Speicher
2. Tages-Kontext (Qdrant)
3. Kontext-Memory / Rollup-Wissen
4. einen internen Dokument-Guide-Index pro User
5. passende Dokument-Collections (`aria_docs_*`), wenn Dokumentwissen relevant ist

Praktische Folge:

- Wissen aus `aria_facts_alice`
- plus Wissen aus `aria_sessions_alice_260317`

kann gemeinsam in eine Antwort einfliessen.

Zusätzlich nutzt ARIA dabei Typ-Gewichte und einen Zeitabfall für Tages-Kontext, damit stabilere Facts und Preferences im Ranking nicht unnötig von alten Session-Schnipseln überdeckt werden.

Dokument-Recall läuft jetzt bewusst zweistufig:

1. beim Upload erzeugt ARIA intern pro Dokument einen kompakten Guide-Eintrag mit:
  - Dokumentname
  - Kurz-Zusammenfassung
  - Stichworten
  - Ziel-Collection
2. bei einer Recall-Frage wird zuerst dieser Guide-Index abgefragt
3. nur die passendsten Dokumente werden danach mit ihren Chunks tief abgefragt

Dadurch muss ARIA nicht blind alle Dokument-Collections durchsuchen und vermischt Dokumentwissen auch nicht mit normalen Fakten.

Wenn ein Dokument für die Antwort verwendet wurde, zeigt ARIA in den Chat-Details zusätzlich die verwendeten Quellen an:

- Dokumentname
- Ziel-Collection
- Chunk-Referenz, z. B. `Chunk 12/108`

Dadurch bleibt nachvollziehbar, woher eine Dokument-Antwort stammt.

## Vergessen mit Bestätigung

Beispiel:

`Vergiss mein NAS`

Ablauf:

1. ARIA sucht passende Eintraege über relevante Collections.
2. ARIA zeigt gefundene Treffer (mit Typ-Label).
3. ARIA gibt einen Bestätigungscode aus.
4. Löschen erst nach expliziter Bestätigung:
   `bestätige <code>`

Ohne gültigen Code wird nichts gelöscht.

Sicherheitsdetails:

- Der Pending-Delete-Status im Browser-Cookie ist signiert.
- Wenn der Cookie-Inhalt manipuliert wird, wird der Löschvorgang blockiert.

## Warum Antworten manchmal "duenn" wirken

ARIA ist bewusst tokensparsam gebaut. Deshalb:

- Recall ist auf Top-K und kompakten Kontext begrenzt
- Fakten werden dedupliziert und gekuerzt
- breite Fragen wie `Was weisst du über mein Netzwerk?` nutzen zusätzlich eine keyword-basierte Fallback-Suche

Wenn eine Antwort zu schmal ist, sind typische Ursachen:

- zu wenig Fakten im Nutzer- oder Tages-Kontext
- Fakten liegen nur in einer Collection, die semantisch schlecht zur Anfrage passt
- Top-K oder Auto-Memory-Parameter sind zu konservativ

Wichtig zur Recall-Logik:

- Standard ist semantische (Embedding-)Suche über alle relevanten Collections.
- Die keyword-basierte Suche ist nur Fallback, wenn semantische Suche keine Treffer oder einen technischen Fehler liefert.

## Sichtbarkeit im Chat

Im Chat-Header zeigt ARIA jetzt:

- `Nutzer-Speicher`
- `Tages-Kontext`
- `Auto-Memory` mit roter/gruener Status-Lampe

Damit ist im Alltag sofort sichtbar:

- welcher Haupt-Store aktiv ist
- welcher Tages-Kontext (Qdrant) gerade beschrieben wird
- ob automatische Speicherung läuft

## Fehler-Meldungen (Task 7)

Wenn Memory-Operationen fehlschlagen, zeigt ARIA jetzt klare Hinweise statt generischem `memory_error`:

- `memory_unavailable` -> "Memory-Dienst nicht verfügbar. Ich antworte ohne gespeichertes Wissen."
- `embedding_failed` -> "Textverarbeitung fehlgeschlagen. Bitte Modell/API-Key für Embeddings prüfen."
- sonstiger Memory-Fehler -> "Memory-Verarbeitung fehlgeschlagen. Ich antworte ohne Memory-Kontext."

Diese Meldungen erscheinen im Chat-Hinweis und im Detail-Badge.

## Memory-UI (`/memories`)

Neue Seite für operatives Memory-Management:

- Typ-Filter (`all`, `fact`, `preference`, `session`, `document`, `knowledge`)
- klickbare Typ-Kacheln für schnellere Navigation
- Semantische Suche (Embedding-basiert)
- `Memory exportieren` als JSON-Download für den aktuellen User und den aktuellen Filter/Suchkontext
- Einzelne Eintraege direkt löschbar
- Direkter Link zum Qdrant-Dashboard
- Manueller Button für Kontext-Rollup
- Dokument-Upload direkt im bestehenden Memory-Bereich
- Upload in bestehende oder neue Dokument-Collections
- Embedding-Wechsel werden in `/config/embeddings` jetzt bewusst abgesichert; bei vorhandenem Memory verlangt ARIA eine explizite Bestätigung und empfiehlt vorher den JSON-Export

RAG v1 im Alltag:

- Upload lebt bewusst in `/memories`
- unterstützt aktuell:
  - `txt`
  - `md`
  - `pdf` mit eingebettetem Text
- Scan-/Bild-PDFs und OCR sind in v1 noch nicht enthalten
- Memory- und Dokument-Einträge tragen jetzt einen Embedding-Fingerprint, damit Recall und Dokument-Routing keine alten und neuen Embedding-Generationen still mischen

## Session-Rollups

ARIA verdichtet aelteren Tages-Kontext jetzt stufenweise:

- Tages-Collections bleiben der operative Kurzzeit-Kontext
- aeltere Tages-Collections werden zu Wochen-Rollups verdichtet
- Wochen-Rollups koennen spaeter zu Monats-Rollups verdichtet werden

In der `Memory Map` gibt es dafuer jetzt einen eigenen Bereich:

- `WOCHE`
- `MONAT`

Pro Rollup zeigt ARIA:

- Bucket, z. B. `2026-W15` oder `2026-04`
- Zeitraum
- Anzahl der verdichteten Quellen
- Vorschau des verdichteten Inhalts
- während Chunking und Import zeigt ARIA einen sichtbaren Arbeitszustand im Upload-Block
- Einträge werden in `Alle` zusätzlich nach Typ gruppiert, damit große Mengen nicht wie abgeschnitten oder zufällig gemischt wirken

## Memory Map (`/memories/map`)

Die `Memory Map` ist der Ort für den strukturellen Blick auf gespeichertes Wissen.

Seit RAG v1 zeigt sie zusätzlich:

- importierte Dokumente gesammelt nach Dokumentname
- Chunk-Anzahl pro Dokument
- Ziel-Collection
- kurze Vorschau
- direktes Entfernen eines ganzen Dokuments aus Qdrant
- einen einfachen read-only Graphen für:
  - Memory-Typen
  - Collections
  - Dokument-Collections
  - Session-Rollups

Wichtig:

- `Memory` bleibt der Ort für Upload, Suche und einzelne Einträge
- `Memory Map` ist der passende Ort für Dokument-Verwaltung und Collection-Struktur

Hinweis:

- Das Kontext-Rollup ist manuell über `/memories` triggerbar.
- Zusätzlich gibt es jetzt:
  - Startup-Lauf (automatisch beim ARIA-Start)
  - CLI-Lauf: `./aria.sh maintenance`
  - täglicher Cron-Lauf via `./aria.sh autostart-install` (03:17)
  - Prompt-basiertes Summary-Template aus Datei: [`prompts/skills/memory_compress.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/prompts/skills/memory_compress.md)

Wichtig für den Button im UI:

- `Rollup jetzt starten` verschiebt **nicht blind alles**, sondern nur Tages-Kontext-Collections, die älter als der konfigurierte Grenzwert sind.
- Aktuelle oder noch zu junge Tages-Collections bleiben bestehen.
- Die Rückmeldung im UI nennt jetzt:
  - wie viele Collections verschoben wurden
  - wie viele gelöscht wurden
  - ob Collections bewusst unverändert blieben, weil sie noch zu jung oder noch aktiver Tages-Kontext sind

Konfiguration:

- `memory.compression_summary_prompt` in `config/config.yaml`
- `memory.collections.sessions.compress_after_days` in `config/config.yaml`
- `memory.collections.sessions.monthly_after_days` in `config/config.yaml`
- im UI setzbar unter `Config > Memory > Kontext-Rollup (Qdrant)`
- Platzhalter im Prompt-Template:
  - `{{kind}}` (`week` oder `month`)
  - `{{day}}` (YYMMDD der Tages-Kontext-Collection)
  - `{{entries}}` (extrahierte Stichpunkte)

## Test-Hinweise

### Expliziter Store/Recall

1. `Merk dir, dass mein Intranet auf 10.0.0.10 erreichbar ist.`
2. `Was weisst du über mein Intranet?`

Erwartung:

- Write in den Nutzer-Speicher
- Recall nennt die gespeicherten Fakten

### Auto-Memory

1. Auto-Memory aktivieren
2. `Hostname: homelab-mgmt-01, IP: 10.0.0.10`
3. `Was weisst du über mein Netzwerk?`

Erwartung:

- Write in den Tages-Kontext (Qdrant)
- spätere Recall-Antwort nutzt auch diese Fakten

### Kontrolle

Auto-Memory deaktivieren und denselben Test wiederholen.

Erwartung:

- ohne explizites `merk dir` kein neuer Eintrag im Qdrant-Memory

## Offene Ausbaustufen

Geplant oder sinnvoll:

- Help-Seite im Web-UI
- sichtbarere Herkunft von Fakten in Antworten
- Preislisten für Token- und Embedding-Kosten aus offiziellen Quellen
- feinere Trennung zwischen dauerhaftem Wissen und Tageswissen
