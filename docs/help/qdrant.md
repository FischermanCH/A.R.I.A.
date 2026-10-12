# Qdrant in ARIA

Stand: 2026-06-09

Qdrant ist ARIAs separater Vector Store. Er bleibt bewusst ein eigener Service im Stack, damit Memory, Dokument-RAG und Routing-Indizes nicht im App-Container verschwinden.

## Was ARIA dort speichert

- Fakten und Präferenzen
- Session-Kontext und Rollups
- Dokument-Collections für RAG
- Notes-Indexe für Suche
- Connection-Routing-Indexe
- Experience-Memory-Kontext für sichere gelernte Aktionsmuster

## Warum Qdrant separat bleibt

- der ARIA-App-Container kann ersetzt werden
- Volumes bleiben erhalten
- grosse Dokument-/Memory-Daten werden nicht ins Image geschrieben
- Update-Helper können ARIA neu erstellen, ohne Qdrant anzufassen

## Routing und Agentic Intelligence

Qdrant ist nicht nur Memory. ARIA nutzt semantische Kandidaten auch für Connection-Routing. Wenn deterministische Treffer unsicher sind, kann ARIA Kandidaten aus Qdrant und LLM-Kontext kombinieren.

Wichtig: Qdrant entscheidet nicht allein. Policy, Guardrails und Runtime bleiben getrennte Schichten.

## Qdrant Brain in der Memory Map

`/memories` integriert eine visuelle Qdrant-Brain-Ansicht. ARIA liest dafür read-only eine begrenzte Stichprobe aus Nutzer-Memory und Dokument-Collections, berechnet semantische Kanten serverseitig und rendert daraus einen zoombaren Graphen.

Die Ansicht ist für Beobachtung und Debugging gedacht:

- sie hilft zu sehen, welche Punkte semantisch nahe beieinander liegen
- sie zeigt Cluster, Collection-Herkunft und kurze Payload-Auszüge
- sie exportiert keine Embedding-Vektoren in den Browser
- sie ist bewusst limitiert, damit grosse Qdrant-Instanzen die UI nicht blockieren
- auf Touch-Geräten startet sie im Browse-Modus: normales Scrollen und Tippen bleibt frei; `Graph bewegen` aktiviert gezielt Graph-Pan und Node-Drag

## Alltagchecks

Wenn Memory, RAG oder Routing schwach wirken:

- `/stats` Preflight prüfen
- `/memories` öffnen
- Embedding-Modell und Fingerprint prüfen
- den Routing-Index-Status unter `/stats` prüfen
- Qdrant-Collections und Storage-Warnungen beachten

## Update-Hinweis

Normale Managed Updates recreaten nur `aria`. Qdrant und sein Volume bleiben bewusst stehen. `repair` oder Full-Stack-Arbeit nur nutzen, wenn Release Notes oder Recovery-Hinweise es verlangen.
