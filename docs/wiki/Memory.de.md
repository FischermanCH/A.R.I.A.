# Memory

ARIA nutzt typisiertes Memory mit Qdrant.

Aktuelle Memory-Ebenen sind:

- Fakten
- Praeferenzen
- Session-Kontext
- verdichtetes Rollup-Wissen
- Dokument-Collections fuer RAG-Uploads

Wichtige aktuelle Punkte:

- Auto-Memory speichert nicht mehr jede fluechtige Frage
- stabile Nutzer-Fakten und Praeferenzen bleiben erhalten
- Capability-Ergebnisse werden nicht standardmaessig ins Memory geschrieben
- Dokument-Uploads liegen unter `/memories`
- die Dokument-Verwaltung liegt unter `/memories/map`
- die Hauptansicht `Memory` gruppiert Eintraege nach Typ und zeigt schnelle Typ-Karten
- Dokument-Recall nutzt zuerst einen internen Guide-Index mit Summary und Stichworten, bevor passende Chunks tief abgefragt werden
- Chat-Details zeigen bei Dokument-Recall Dateiname, Collection und Chunk-Referenz
- unterstuetzte RAG-v1-Formate:
  - `txt`
  - `md`
  - `pdf` mit eingebettetem Text
- Scan-PDFs / OCR sind nicht Teil von v1

Nuetzliche Referenzen:

- [`docs/help/memory.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/help/memory.md)
- [`docs/product/feature-list.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/product/feature-list.md)
- [`docs/product/architecture-summary.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/product/architecture-summary.md)
- [`docs/product/rag-v1-plan.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/product/rag-v1-plan.md)
