# ARIA - Main Backlog

Stand: 2026-04-03

Zweck:
- mittel- und langfristiger Produkt-/Architektur-Backlog nach dem ersten Public Alpha
- enthält die großen ARIA-Ausbaulinien, die nicht mehr in den unmittelbaren Alpha-Release-Block gehören

## Memory 2.0

Ziel:
- Memory stärker strukturieren und adaptiver machen, ohne die Memory Map / Graph-Visualisierung sofort mitzubauen

### Multi-Collection Recall Tuning
- Basis-Variante mit gewichteten Facts/Preferences/Sessions/Knowledge ist im Public-Alpha-Stand vorhanden
- post-alpha weiter abstimmen:
  - Type-Weights und Session-Zeitabfall feinjustieren
  - Kontext-Mix je nach Prompt-Typ dynamischer machen
  - Over-/Under-Retrieval bei sehr breiten Fragen reduzieren
  - Recall-Erklärbarkeit im UI verbessern

### Typed Auto-Memory
- Auto-Memory soll Fakten und Präferenzen stärker unterscheiden
- automatische Extraktion in strukturierte Memory-Typen wie:
  - `fact`
  - `preference`
  - `session`
- Konfidenz / Quelle (`explicit` vs `auto`) sauber speichern
- aggressives Memory-Rauschen vermeiden

### Session Rollup
- Tages-/Session-Memory periodisch komprimieren
  - Tag -> Woche
  - Woche -> Monat
- alte Chat-Granularität kontrolliert verdichten statt endlos wachsen lassen
- Komprimierungs-Prompts und TTL/Retention-Regeln sauber definieren

### Memory Import / Portabilität
- JSON-Export ist im Public-Alpha-Stand vorhanden
- post-alpha Re-Import / Migration sauber vorbereiten
- optional ZIP-Bundles und differenziertere Collection-/Type-Filter
- klare UX, was beim Import ersetzt, ergänzt oder übersprungen wird

### Embedding-Modellwechsel / Reindex
- besser absichern, wenn das Embedding-Modell geändert wird
- UI-Hinweis/Warnung, dass alte und neue Embeddings nicht still vermischt werden sollten
- Reindex-/Neuaufbau-Flow für Memory-Collections vorbereiten
- Fallback-Strategie für bestehende Daten dokumentieren

## Knowledge / Dokumente

- Dokument-Ingest für eigene Dateien/Wissensbestände
- Chunking + Embeddings + Quell-Metadaten
- Knowledge-Collections als separater Memory-Typ
- Zitier-/Quellenmodus für Dokumentantworten
- UI für Upload, Reindex, Löschen und Status

## Websuche / Research

- Websuche als eigener Research-Flow
- bevorzugt provider-native Tooling im Default-Setup
- SearXNG optional als Power-User-Erweiterung
- Ergebnisverdichtung, Quellenanzeige, saubere Kurz-/Langantwort-Modi
- klarer Unterschied zwischen lokalem Wissen, Memory und Live-Web

## Home Assistant / Smart Home Brain

Zielbild:
- Home Assistant bleibt Device-/Aktor-Layer
- ARIA wird darüber die lernende, kontextuelle Intelligenzschicht

### MVP
- Home-Assistant-Connection mit Base URL + API Token
- Entity-/Area-Auswahl
- aktuellen Zustand anzeigen
- ausgewählte Entity-States in Qdrant speichern
- Chat-Fragen wie:
  - `Was ist im Wohnzimmer gerade an?`
  - `Wie ist der Status meiner Wohnung?`

### Danach
- relevante State Changes und Events komprimiert speichern
- wiederkehrende Muster erkennen
- adaptive Routinen / Vorschläge ableiten
- Datenschutz-/Löschkonzept für HA-Lernhistorie
- später optional HA-Services aus ARIA auslösen

## Channels / Realtime

- echte Channel-Adapter jenseits Web/API ausbauen
  - Discord als eigener Channel, nicht nur Webhook-Ziel
  - später weitere Chat-/Messaging-Kanäle
- Streaming/SSE für Live-Antworten im Web-UI und API prüfen
- sauberer Event-/Status-Flow für längere Skill-Runs

## Routing 2.0

- Router Stufe 2/3 weiter ausbauen
  - Embedding-/Similarity-Routing
  - optional LLM-Klassifikation als Fallback
- Overmatching bei generischen Prompts weiter reduzieren
- Skill-/Connection-Routing transparenter erklärbar machen
- Alias-/Beschreibung-/Tag-Qualität stärker nutzbar machen

## Security / Sharing / Multi-User

- echtes Ownership-/Sharing-Modell für:
  - Skills
  - Connections
  - Memories
- Rollen-/RBAC-Ausbau über den aktuellen Admin/User-Modus hinaus
- Tenant-/User-Grenzen klarer modellieren
- sichere Freigabe ausgewählter Ressourcen zwischen Nutzern

## Remote Access / RAS

- WireGuard/RAS als eigener Produktbereich, nicht als normale Connection
- Peer-/Client-Verwaltung
- Client-Konfig/QR-Code erzeugen
- Status-/Health-Anzeige
- klare Port-/Firewall-Hinweise

## UI / Produktpolish

- Help-System schrittweise zu kontextsensitiver Inline-Hilfe ausbauen
- mögliche UI-Update-Aktion später host-/containerbewusst ergänzen, nicht als blinden In-App-Updater
- mehr Guided-Onboarding für First Run und Skill-Bau
- Memory- und Skill-UX weiter vereinfachen
- zusätzliche Themes nur dort ergänzen, wo sie wirklich Qualität bringen
- Accessibility und Mobile/Safari weiter glätten

## Bewusst später / Nice-to-Have

- Memory Map / Graph-Visualisierung
- automatische Agent-Loops
- große Plugin-/Marketplace-Schicht
