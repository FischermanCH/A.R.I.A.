# ARIA Hilfe: Memory und Stores

Stand: 2026-07-09

## Zweck

Memory ist ARIAs semantischer Wissensspeicher. Es ist getrennt von Notizen, Logs und reinen Runtime-Ergebnissen.

ARIA nutzt Memory fuer:

- stabile Fakten ueber Nutzer und Umgebung
- Praeferenzen
- Session-Kontext
- Rollups ueber laengere Zeitraeume
- Dokument-RAG
- Experience Memory fuer sichere gelernte Aktionsmuster

## Was bewusst nicht automatisch ins Memory geht

- jede fluechtige Frage
- komplette SSH-/SMB-/RSS-Momentaufnahmen
- technische Logs ohne dauerhaften Wert
- mutierende Aktionsvorschlaege ohne Review

Das reduziert Memory-Rauschen und verhindert, dass ARIA aus zufaelligen Einmalereignissen dauerhafte Annahmen baut.

## Store-Typen

### Fakten und Praeferenzen

Langfristiges Wissen, das ARIA spaeter wiederverwenden darf.

### Session-Kontext

Arbeitsgedaechtnis fuer laufende Aufgaben und fruehere Turns.

### Rollups

Verdichtete Wochen-/Monats- oder Arbeitskontexte. Rollups helfen, ohne alle alten Chatdetails in jeden Prompt zu ziehen.

### Dokument-Collections

RAG-v1 fuer Uploads unter `/memories`. Unterstuetzt sind Text, Markdown und PDFs mit eingebettetem Text. OCR/Scan-PDFs sind nicht Teil von v1.

### Experience Memory

Erfolgreiche sichere Recipe-/Guardrail-/Action-Muster koennen als Planner-Kontext gespeichert werden. Sie helfen ARIA beim Vorschlagen, ersetzen aber nicht Policy oder Guardrails.

## Recall

Recall kombiniert je nach Anfrage:

1. direkte Fakten/Praeferenzen
2. Session-Kontext
3. Rollups
4. Dokument-Guides und passende Chunks
5. Experience Memory fuer Aktionsplanung

Chat-Details zeigen Quellen, Collection und Chunk-Referenzen, wenn Dokument-Recall genutzt wurde.

## UI

- `/memories` fuer den grafischen Gedaechtnis-Browser
- `/memories/import` fuer neue Dokumente und Memory-Importe
- `/memories/auto-memory` fuer Auto-Memory und agentisches Lernen
- `/memories/maintenance` fuer technische Pflege, Rebuilds und interne Lernartefakte
- `/config/embeddings` fuer Embedding-Modell und Sicherheitsabfrage bei vorhandenem Memory

### Auto-Memory und Lernen

Auto-Memory kann dauerhafte Fakten und Praeferenzen speichern, wenn ARIA genug Sicherheit hat. Agentisches Lernen kann ausserdem reviewbare Konventionen aus User-Feedback und erfolgreichen sicheren Laeufen extrahieren. Lernartefakte sind Kontext und Review-Material; sie umgehen keine Policy, Guardrails oder Bestaetigungen.

### Gedaechtnis-Browser

Der Gedaechtnis-Browser ist die grafische Pflege- und Debug-Ansicht fuer ARIAs Qdrant-/Memory-Daten. Er zeigt dieselben Daten in zwei zusammenhaengenden Formen:

- Der Graph zeigt Root, Memory-Typen, Collections, Dokumente, Entries und Chunks als navigierbare Struktur.
- Der Inspector zeigt zur aktuellen Ebene die passenden Details und kann wie eine eigene Navigation genutzt werden.
- Auf der Eintrittsseite ist nichts ausgewaehlt; der Inspector zeigt alle Collections.
- Collection-Ebenen zeigen zuerst darunterliegende Dokumente oder Entries. Erst eine Ebene tiefer werden die zugehoerigen Chunks sichtbar.
- Dokument-Collections zeigen Dokumente und danach deren Chunks. Andere Collections zeigen Entries und deren Memory-Punkte.
- Einzelne Chunks, Points und Dokumente koennen im Browser geloescht werden. Inhalte werden bewusst nicht inline editiert, weil Aenderungen ein Re-Embedding brauchen; sicherer ist loeschen und neu erfassen.

### Struktur und semantische Naehe

Der Strukturmodus ist die Standardansicht. Er nutzt Zoom, freies Pan, Panbars, Fullscreen, Inspector-Drilldown und gespeicherte Struktur-Optionen fuer Abstand, Cluster und Anziehung.

Semantische Naehe erscheint erst auf konkreten Chunk-/Entry-/Point-Ebenen. Dann zeigt der Browser berechnete Nachbarschaften aus Qdrant-Embeddings, ohne Roh-Vektoren an den Browser auszuliefern.

Sichtbar sind nur sichere Metadaten, Textauszuege, Collection, Point-ID und berechnete Kanten. Fullscreen und iOS-/Touch-Bedienung nutzen dieselbe Logik wie der normale Browser.

## Embedding-Fingerprint

Memory- und Dokumenteintraege tragen einen Embedding-Fingerprint. Dadurch mischt ARIA alte und neue Embedding-Generationen nicht still waehrend Recall oder Dokument-Routing.

## Vergessen

Eintraege koennen direkt in `/memories` geloescht werden. Im Chat kann ARIA explizite Vergessenswuensche erkennen, sollte aber bei destruktiven Operationen bestaetigen.

## Warum Antworten manchmal duenn wirken

- Memory ist deaktiviert oder Qdrant nicht erreichbar
- Embedding-Modell wurde gewechselt und alte Eintraege passen nicht mehr
- zu wenige oder falsche Erinnerungen existieren
- die Anfrage ist eher ein Action-Prompt und wird vor RAG in den Agentic Action Flow geleitet
- Top-K oder Recall-Grenzen sind zu konservativ

## Test-Hinweise

- `merk dir ...` fuer explizites Speichern
- spaeter nach demselben Fakt fragen
- `/stats` und Chat-Details fuer Recall-Quellen pruefen
- `/memories` fuer Collection-/Dokument-/Chunk-Struktur und semantische Naehe pruefen
