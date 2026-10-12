# ARIA Hilfe: Memory und Stores

Stand: 2026-07-09

## Zweck

Memory ist ARIAs semantischer Wissensspeicher. Es ist getrennt von Notizen, Logs und reinen Runtime-Ergebnissen.

ARIA nutzt Memory für:

- stabile Fakten über Nutzer und Umgebung
- Präferenzen
- Session-Kontext
- Rollups über längere Zeiträume
- Dokument-RAG
- Experience Memory für sichere gelernte Aktionsmuster

## Was bewusst nicht automatisch ins Memory geht

- jede flüchtige Frage
- komplette SSH-/SMB-/RSS-Momentaufnahmen
- technische Logs ohne dauerhaften Wert
- mutierende Aktionsvorschläge ohne Review

Das reduziert Memory-Rauschen und verhindert, dass ARIA aus zufälligen Einmalereignissen dauerhafte Annahmen baut.

## Store-Typen

### Fakten und Präferenzen

Langfristiges Wissen, das ARIA später wiederverwenden darf.

### Session-Kontext

Arbeitsgedächtnis für laufende Aufgaben und frühere Turns.

### Rollups

Verdichtete Wochen-/Monats- oder Arbeitskontexte. Rollups helfen, ohne alle alten Chatdetails in jeden Prompt zu ziehen.

### Dokument-Collections

RAG-v1 für Uploads unter `/memories`. Unterstützt sind Text, Markdown und PDFs mit eingebettetem Text. OCR/Scan-PDFs sind nicht Teil von v1.

### Experience Memory

Erfolgreiche sichere Recipe-/Guardrail-/Action-Muster können als Planner-Kontext gespeichert werden. Sie helfen ARIA beim Vorschlagen, ersetzen aber nicht Policy oder Guardrails.

## Recall

Recall kombiniert je nach Anfrage:

1. direkte Fakten/Präferenzen
2. Session-Kontext
3. Rollups
4. Dokument-Guides und passende Chunks
5. Experience Memory für Aktionsplanung

Chat-Details zeigen Quellen, Collection und Chunk-Referenzen, wenn Dokument-Recall genutzt wurde.

## UI

- `/memories` für den grafischen Gedächtnis-Browser
- `/memories/import` für neue Dokumente und Memory-Importe
- `/memories/auto-memory` für das persönliche Modell mit wirksamen und historischen Angaben
- `/memories/activity-journal` für kompakte, nutzergetrennte Kurzfassungen abgeschlossener Tool-Aktivitäten und Agent-Jobs
- `/memories/maintenance` für technische Pflege, Reindex und das gezielte Aufräumen alter Lern-Collections
- `/config/embeddings` für Embedding-Modell und Sicherheitsabfrage bei vorhandenem Memory

### Persönliches Modell

ARIA kann eine ausdrückliche Merk-Bitte direkt als persönliche Angabe speichern. Dauerhafte Vorlieben kann der servereigene Lernpfad nach wiederholter Nennung über eine separate Schaltfläche anbieten. ARIA fragt nicht selbst im Antworttext nach dem Speichern.

`/memories/auto-memory` zeigt wirksame und historische persönliche Angaben. Dort lassen sich Werte korrigieren, Angaben aussetzen, reaktivieren oder gezielt löschen. Technische IDs bleiben in einem eingeklappten Expertenbereich.

Strukturierte persönliche Angaben führen Typ, Geltungsbereich, Autorität und Lebenszyklus. Nur wirksame Angaben gelangen in den begrenzten persönlichen Kontext für Planung und Antwort.

Zeitfenster werden automatisch durchgesetzt: geplante und abgelaufene Claims bleiben sichtbar, gelangen aber nicht in ARIAs persönlichen Turn-Kontext.

### Aktivitätsjournal

Das Aktivitätsjournal speichert nur kurze, redigierte Angaben zu abgeschlossenen Tool-Turns und Agent-Jobs: Ziel, verwendete Tools und Verbindungen, Ergebnisstatus und einen kurzen Ergebnissatz. Roh-Ausgaben, Datei- oder Dokumentinhalte, Bilder, Prompts und Zugangsdaten gehören nicht in diesen Speicher. Das Journal wird nie automatisch in einen Modell-Prompt eingefügt; ARIA kann es nur bei Bedarf über das nutzergetrennte Lese-Tool abfragen. Die Aufbewahrung ist standardmäßig 90 Tage, bewusst aufbewahrte und ausdrücklich übernommene Alt-Rollups sind von der automatischen Bereinigung ausgenommen.

Korrekturen ersetzen Claims nachvollziehbar statt sie still zu überschreiben. Ziele und Projekte besitzen eigene Aktionen zum Pausieren, Fortsetzen, Abschließen und Wiederöffnen; Session-Scope bleibt in Session Memory.

### Gedächtnis-Browser

Der Gedächtnis-Browser ist die grafische Pflege- und Debug-Ansicht für ARIAs Qdrant-/Memory-Daten. Er zeigt dieselben Daten in zwei zusammenhängenden Formen:

- Der Graph zeigt Root, Memory-Typen, Collections, Dokumente, Entries und Chunks als navigierbare Struktur.
- Der Inspector zeigt zur aktuellen Ebene die passenden Details und kann wie eine eigene Navigation genutzt werden.
- Auf der Eintrittsseite ist nichts ausgewählt; der Inspector zeigt alle Collections.
- Collection-Ebenen zeigen zuerst darunterliegende Dokumente oder Entries. Erst eine Ebene tiefer werden die zugehörigen Chunks sichtbar.
- Dokument-Collections zeigen Dokumente und danach deren Chunks. Andere Collections zeigen Entries und deren Memory-Punkte.
- Einzelne Chunks, Points und Dokumente können im Browser gelöscht werden. Inhalte werden bewusst nicht inline editiert, weil Änderungen ein Re-Embedding brauchen; sicherer ist löschen und neu erfassen.

### Struktur und semantische Nähe

Der Strukturmodus ist die Standardansicht. Er nutzt Zoom, freies Pan, Panbars, Fullscreen, Inspector-Drilldown und gespeicherte Struktur-Optionen für Abstand, Cluster und Anziehung.

Semantische Nähe erscheint erst auf konkreten Chunk-/Entry-/Point-Ebenen. Dann zeigt der Browser berechnete Nachbarschaften aus Qdrant-Embeddings, ohne Roh-Vektoren an den Browser auszuliefern.

Sichtbar sind nur sichere Metadaten, Textauszüge, Collection, Point-ID und berechnete Kanten. Fullscreen und iOS-/Touch-Bedienung nutzen dieselbe Logik wie der normale Browser.

## Embedding-Fingerprint

Memory- und Dokumenteinträge tragen einen Embedding-Fingerprint. Dadurch mischt ARIA alte und neue Embedding-Generationen nicht still während Recall oder Dokument-Routing.

## Vergessen

Einträge können direkt in `/memories` gelöscht werden. Im Chat kann ARIA explizite Vergessenswünsche erkennen, sollte aber bei destruktiven Operationen bestätigen.

## Warum Antworten manchmal dünn wirken

- Memory ist deaktiviert oder Qdrant nicht erreichbar
- Embedding-Modell wurde gewechselt und alte Einträge passen nicht mehr
- zu wenige oder falsche Erinnerungen existieren
- die Anfrage ist eher ein Action-Prompt und wird vor RAG in den Agentic Action Flow geleitet
- Top-K oder Recall-Grenzen sind zu konservativ

## Test-Hinweise

- `merk dir ...` für explizites Speichern
- später nach demselben Fakt fragen
- `/stats` und Chat-Details für Recall-Quellen prüfen
- `/memories` für Collection-/Dokument-/Chunk-Struktur und semantische Nähe prüfen
