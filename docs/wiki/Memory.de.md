# ARIA Hilfe: Memory und Stores

Stand: 2026-06-09

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

- `/memories` fuer Eintraege, Suche, Bearbeitung, Loeschen und JSON-Export
- `/memories/map` fuer Collections, Dokumentgruppen, Rollups, Struktur und Qdrant-Brain-Graph
- `/config/embeddings` fuer Embedding-Modell und Sicherheitsabfrage bei vorhandenem Memory

### Memory Map und Qdrant Brain

Die Memory Map zeigt zuerst die logische Struktur: Nutzer, Memory-Typen, Collections, Dokumentgruppen, Rollups, Notes, Routing und System-Collections.

Wenn Qdrant erreichbar ist und ausreichend Punkte mit Embeddings vorhanden sind, zeigt dieselbe Seite zusaetzlich den **Qdrant Brain**. Dieser Graph startet mit Collections und erlaubt den Drilldown in die enthaltenen Qdrant-Punkte:

- Knoten sind Memory-/Dokument-/Notes-/Rollup-Punkte.
- Kanten zeigen berechnete semantische Naehe zwischen Embeddings innerhalb der ausgewaehlten Collection.
- Zoom, Pan und Detailauswahl helfen beim Verstehen von Clustern und Relevanzen.
- Roh-Vektoren werden nicht an den Browser ausgeliefert; sichtbar sind nur sichere Metadaten, Textauszuege, Collection und Point-ID.

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
- `/memories/map` fuer Collection-/Rollup-Struktur pruefen
