# Qdrant in ARIA

Stand: 2026-04-21

Qdrant ist in ARIA der zentrale Speicher fuer semantisches Wissen.

ARIA nutzt Qdrant vor allem fuer:

- persoenliches Gedaechtnis
- Dokumenten-RAG und Chunks
- Rollups und verdichtetes Wissen
- Routing-Indexe fuer Connections und spaeter weitere Systementscheidungen

## Was dort gespeichert wird

Typische Inhalte in Qdrant:

- Facts und Preferences aus dem Gedaechtnis
- Dokument-Chunks aus importierten Dateien
- verdichtete Rollups
- Routing-Metadaten fuer semantische Auswahl

Wichtig:

- Qdrant ist nicht "der Chat selbst"
- Qdrant ist der Vektor- und Retrieval-Speicher dahinter
- die eigentliche ARIA-Konfiguration lebt weiter in `config/` und anderen App-Daten

## Warum Qdrant separat bleibt

ARIA bindet Qdrant bewusst als eigenen Dienst ein:

- klarere Trennung von App und semantischem Speicher
- leichter zu diagnostizieren
- einfacher zu sichern und zu migrieren
- austauschbarer als eine fest eingebaute In-Process-Loesung

Das ist produktiv sinnvoll:

- ARIA bleibt die Orchestrierungsschicht
- Qdrant bleibt der spezialisierte Retrieval- und Vektor-Dienst

## Was du im Alltag pruefen solltest

Wenn Memory oder Dokumentenwissen schlecht wirken, sind diese Punkte meist zuerst wichtig:

- ist Qdrant erreichbar?
- stimmt das Embedding-Setup?
- ist die richtige Collection aktiv?
- wurden Dokumente wirklich importiert?

Hilfreiche Stellen in ARIA:

- `/memories`
- `/memories/explorer`
- `/memories/config`
- `/stats`

Qdrant ist also kein Nebendetail, sondern ein Kernbaustein von ARIAs Wissensschicht.
