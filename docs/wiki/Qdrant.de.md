# Qdrant in ARIA

Stand: 2026-05-12

Qdrant ist ARIAs separater Vector Store. Er bleibt bewusst ein eigener Service im Stack, damit Memory, Dokument-RAG und Routing-Indizes nicht im App-Container verschwinden.

## Was ARIA dort speichert

- Fakten und Praeferenzen
- Session-Kontext und Rollups
- Dokument-Collections fuer RAG
- Notes-Indexe fuer Suche
- Connection-Routing-Indexe
- Experience-Memory-Kontext fuer sichere gelernte Aktionsmuster

## Warum Qdrant separat bleibt

- der ARIA-App-Container kann ersetzt werden
- Volumes bleiben erhalten
- grosse Dokument-/Memory-Daten werden nicht ins Image geschrieben
- Update-Helper koennen ARIA neu erstellen, ohne Qdrant anzufassen

## Routing und Agentic Intelligence

Qdrant ist nicht nur Memory. ARIA nutzt semantische Kandidaten auch fuer Connection-Routing. Wenn deterministische Treffer unsicher sind, kann ARIA Kandidaten aus Qdrant und LLM-Kontext kombinieren.

Wichtig: Qdrant entscheidet nicht allein. Policy, Guardrails und Runtime bleiben getrennte Schichten.

## Alltagchecks

Wenn Memory, RAG oder Routing schwach wirken:

- `/stats` Preflight pruefen
- `/memories/map` oeffnen
- Embedding-Modell und Fingerprint pruefen
- `/config/routing` fuer Connection-Routing testen
- Qdrant-Collections und Storage-Warnungen beachten

## Update-Hinweis

Normale Managed Updates recreaten nur `aria`. Qdrant und sein Volume bleiben bewusst stehen. `repair` oder Full-Stack-Arbeit nur nutzen, wenn Release Notes oder Recovery-Hinweise es verlangen.
