# ARIA - RAG v1 Plan

Stand: 2026-04-06

## Aktueller Stand

Bereits umgesetzt:

- Upload direkt in `/memories`
- Import in getrennte Dokument-Collections `aria_docs_*`
- `txt`, `md` und `pdf` mit eingebettetem Text
- sichtbarer Ingest-/Chunking-Status im Upload-Flow
- Dokument-Chunks als eigener Typ `document`
- interner Dokument-Guide-Index mit Summary + Stichworten pro Upload
- Recall fragt zuerst den Guide-Index und dann gezielt passende Dokument-Chunks ab
- Dokument-Verwaltung in `/memories/map`
  - gruppiert nach Dokumentname
  - mit Chunk-Anzahl, Vorschau und Collection
  - ganzes Dokument loeschbar

Noch offen:

- spaeter `docx`
- spaeter OCR / Bilder

Ziel:
- ein erstes, nuetzliches Dokument-RAG bauen
- ohne neues Hauptmenue
- ohne neue Top-Level-Seite
- ohne neues grosses Konfig-Modul

Leitidee:
- **RAG lebt in `Memory`**
- Upload und Collection-Auswahl passieren dort, wo User ohnehin nach gespeichertem Wissen suchen
- unter der Haube bleibt der Dokument-Ingest trotzdem ein eigener, sauberer Pfad

## Produkt-Schnitt

RAG v1 soll:
- Textdokumente hochladen koennen
- Text extrahieren
- in Chunks zerlegen
- Embeddings erzeugen
- in Qdrant speichern
- spaeter im Chat mit Quellenhinweisen wiederfinden

RAG v1 soll **noch nicht**:
- eine vollstaendige Knowledge-Base-App sein
- ein neues Produktmodul mit eigener Navigation einfuehren
- OCR/Bildverarbeitung enthalten
- komplexe Dateiformat-Magie abdecken

## V1 Dateiformate

Zuerst:
- `txt`
- `md`
- `pdf`

Spaeter erweiterbar:
- `docx`
- OCR
- Bilder

## Reihenfolge der Umsetzung

### 1. UI in `/memories`

Ziel:
- Dokument-Upload direkt in die bestehende Memory-Oberflaeche integrieren

Vorschlag:
- in `aria/templates/memories.html` eine neue Card:
  - Titel: z. B. `Dokumente importieren`
  - Datei-Upload
  - Auswahl einer bestehenden Qdrant-Collection
  - optional neues Collection-Feld
- keine neue Hauptnavigation
- keine neue Top-Level-Seite

Bestehende Andockpunkte:
- `aria/templates/memories.html`
- `aria/web/memories_routes.py`
- bestehende Collection-Logik aus:
  - `/memories/config/select`
  - `/memories/config/create`
  - `config_memory.html`

Wichtig:
- Upload-Card gehoert in die Memory-Oberflaeche
- die existierende manuelle Memory-Erfassung bleibt daneben bestehen
- Dokumentwissen und manuelle Facts/Preferences werden UI-seitig nah, aber technisch sauber getrennt gehalten

### 2. Upload- und Ingest-Pipeline

Ziel:
- aus einem Upload einen robusten Dokument-Ingest machen

Neuer technischer Block:
- `aria/core/document_ingest.py` oder aehnlich

Verantwortung dieses Blocks:
- Dateityp erkennen
- Text extrahieren
- Text normalisieren
- Chunks bauen
- Metadaten vorbereiten
- Batch-Ingest an Memory/Qdrant uebergeben

Empfohlene Pipeline:
1. Upload annehmen
2. Datei temporär speichern
3. Text extrahieren
4. Dokument in Chunks teilen
5. pro Chunk Embedding erzeugen
6. Chunks in Ziel-Collection schreiben
7. Ergebnis fuer UI zusammenfassen

V1 Metadaten pro Chunk:
- `document_id`
- `document_name`
- `chunk_index`
- `chunk_total`
- `source`
- `source_type`
- `mime_type`
- `uploaded_by`
- `uploaded_at`

Empfohlener `source` fuer RAG:
- `rag_upload`

Wichtig:
- nicht jeden Chunk nur als "normale Fact" tarnen
- Dokument-Chunks brauchen erkennbare Herkunft

### 3. Qdrant-Collection-Logik

Ziel:
- Uploads sauber in Collections steuern, ohne neue Konfig-Seite

V1 Verhalten:
- User kann im Upload:
  - eine bestehende Collection waehlen
  - oder eine neue Collection direkt anlegen

Saubere Produktlogik:
- wir nutzen die bestehende Memory-/Qdrant-Collection-Welt weiter
- aber wir behandeln Dokument-Collections bewusst als Dokumentwissen

Empfehlung:
- User-definierte Dokument-Collections zulassen
- optional spaeter Namenskonvention empfehlen, z. B.:
  - `aria_docs_manuals`
  - `aria_docs_project_x`
  - `aria_docs_fischerman_lab`

Technisch wichtig:
- nicht blind die normalen Facts-/Preferences-/Session-Collections missbrauchen
- Dokument-Collections duerfen eigene Recall-Herkunft behalten

Bestehende Andockpunkte:
- `aria/web/memories_routes.py`
- `aria/templates/config_memory.html`
- Qdrant-Overview / Collection-Listen im Memory-Setup

### 4. Chat-Recall mit Quellen

Ziel:
- hochgeladene Dokumente im Chat nutzbar machen
- mit sichtbarer Herkunft

Wichtige Beobachtung:
- der aktuelle Memory-Recall ist stark auf:
  - Facts
  - Preferences
  - Sessions
  - Knowledge
  zugeschnitten

Deshalb braucht RAG v1 einen bewussten Recall-Schritt fuer Dokument-Collections.

Aktueller Stand:
- pro Dokument wird ein interner Guide-Eintrag erzeugt mit:
  - Dokumentname
  - Kurz-Zusammenfassung
  - Stichworten
  - Ziel-Collection
- der Recall fragt zuerst diesen Guide-Index
- danach werden nur die passendsten Dokumente mit ihren Chunks tief abgefragt
- Antwortkontext enthaelt:
  - Dokumentname
  - Chunk-/Quellenhinweis

Quellenanzeige in V1:
- mindestens:
  - Dokumentname
  - `source=rag_upload`
- spaeter optional:
  - Seitenzahl bei PDF
  - Chunk-Nummer

Technische Andockpunkte:
- `aria/skills/memory.py`
- `aria/core/pipeline.py`
- bestehende Recall-Zusammenstellung erweitern

Wichtig:
- RAG-Recall darf vorhandene Auto-Memory-/Session-Mechanik nicht kaputt machen
- Dokument-Recall sollte modular dazukommen, nicht die alte Memory-Logik ersetzen

## Technische Leitplanken

- kein neues Hauptmenue
- keine neue Top-Level-Seite
- kein neuer grosser Konfig-Bereich
- Upload lebt in `/memories`
- Collection-Wahl nutzt bestehende Memory-/Qdrant-Logik
- Dokument-Ingest bleibt unter der Haube modular

## Sinnvolle erste Implementierungs-Slices

### Slice 1
- Upload-Card in `/memories`
- bestehende Collection waehlen
- `txt` und `md` ingest
- noch ohne Chat-Recall

Status:
- umgesetzt

### Slice 2
- `pdf`-Textextraktion
- bessere Ingest-Zusammenfassung in UI
- erste Dokument-Metadaten sichtbar in Memory-Liste

Status:
- weitgehend umgesetzt
- Dokument-Verwaltung sitzt jetzt bewusst in der `Memory Map`, nicht mitten im normalen `Memory`-Log

### Slice 3
- Dokument-Recall im Chat
- Quellenhinweise in Antworten

### Slice 4
- Collection-Management fuer Dokumente glatter machen
- spaeter `docx` / OCR / Bilder

## Warum dieser Schnitt zu ARIA passt

- `Memory` ist der natuerliche Ort fuer eigenes Wissen
- Dokumente sind gespeichertes Wissen, nicht ein neues Produkt-Silo
- der User findet Upload, Collection und Suche dort, wo er sie erwartet
- wir halten die UI klein, aber die Technik trotzdem modular erweiterbar
