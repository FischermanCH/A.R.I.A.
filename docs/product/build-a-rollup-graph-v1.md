# ARIA - Build A Scope

Stand: 2026-04-07

## Ziel

Der naechste groessere Build soll zwei Dinge zusammenbringen:

1. `Session-Rollup v1`
2. `Memory Map / Graph v1`

Die beiden Themen passen zusammen:
- Rollups geben dem Langzeit-Memory mehr Struktur
- die Graph-/Map-Sicht macht diese Struktur fuer User sichtbar

Wichtig:
- das soll **sichtbar mehr Feature-Substanz** bringen
- aber **nicht** in einen uebergrossen Architektur-Block kippen

## Was in Build A drin ist

### 1. Session-Rollup v1

Ziel:
- Tageskontext nicht nur punktuell komprimieren
- sondern eine klare Hierarchie schaffen:
  - Tag
  - Woche
  - Monat

#### V1 Verhalten

- Tages-Rollups bleiben bestehen
- neue Wochen-Rollups entstehen aus Tages-Rollups
- neue Monats-Rollups entstehen aus Wochen-Rollups
- Rollups werden als eigene Schicht sichtbar und logisch von:
  - Fakten
  - Praeferenzen
  - Dokumenten
  - normalem Wissen
  getrennt

#### Produktziel

ARIA soll nicht nur "letzte Session-Fragmente" behalten, sondern mit der Zeit:
- wiederkehrende Themen
- stabile Muster
- verdichteten Kontext
ueber laengere Zeitfenster aufbauen koennen

#### Minimaler Scope fuer v1

- Tages-Rollup:
  - bestehende Logik weiterverwenden
- Wochen-Rollup:
  - fasst Tages-Rollups einer Kalenderwoche zusammen
- Monats-Rollup:
  - fasst Wochen-Rollups eines Kalendermonats zusammen
- pro Rollup:
  - Text
  - Zeitraum
  - Ursprungsebene
  - User
  - Zeitstempel

#### Nicht in v1

- keine vollautomatische "Wissensbewertung" ueber viele Heuristiken
- keine aggressive Selbst-Ueberschreibung alter Rollups
- keine komplexe Editor-Oberflaeche fuer Rollup-Generationen

## 2. Memory Map / Graph v1

Ziel:
- gespeichertes Wissen sichtbar machen
- einen "Wow"-Effekt schaffen
- aber technisch simpel bleiben

#### V1 Prinzip

- read-only
- einfach
- klar
- spaeter ausbaubar

#### Was sichtbar sein soll

Knoten-Typen:
- User
- Facts
- Preferences
- Session-Rollups
- Knowledge
- Documents
- Collections

Kanten-Typen:
- `belongs_to`
- `stored_in`
- `summarized_into`
- `document_in_collection`

#### V1 Darstellung

- einfache Graph-Ansicht in der bestehenden Memory-Map-Welt
- keine komplexe 3D-/Physics-Spielerei
- lieber:
  - stabil
  - lesbar
  - mobile-tolerant
- aktueller Stand:
  - read-only Graph in `/memories/map`
  - Root-Knoten fuer den User
  - Typ-Knoten fuer Fakten, Praeferenzen, Tages-Kontext, Dokumente und Wissen
  - darunter erste Detail-Knoten fuer Collections, Dokument-Collections und Rollup-Gruppen

#### Produktwirkung

Die Ansicht soll zeigen:
- was ARIA speichert
- wie Dinge zusammenhaengen
- dass Dokumente, Rollups und klassisches Memory nicht nur eine flache Liste sind

#### Nicht in v1

- kein Graph-Editor
- keine frei modellierten semantischen Kanten
- keine LLM-generierten Graphbeziehungen ueber alles
- kein grosses Frontend-Framework nur fuer den Graph

## Warum diese Kombination gut ist

Rollup ohne Sichtbarkeit bleibt abstrakt.

Graph ohne bessere Memory-Struktur bleibt schnell nur eine huebsche Demo.

Zusammen erzeugen sie:
- echten Produktnutzen
- sichtbare Reife
- eine Basis fuer spaetere Ausbauten

## Bewusste Abgrenzung zu Home Assistant

`Home Assistant` gehoert **nicht** in Build A.

Grund:
- HA ist ein eigener Integrationsblock
- Rollup + Graph sind fachlich enger verwandt
- so bleibt Build A fokussiert

Home Assistant ist der geplante **Build B**:
- Connection
- Entities/Geraete sehen
- sichere Grundsteuerung

Spaeteres `HA v2`:
- Verhalten lernen
- Muster erkennen
- "ARIA als Brain von HA"

## Technischer Schnitt fuer Build A

### Session-Rollup

Betroffene Bereiche:
- `aria/skills/memory.py`
- Rollup-/Compression-Logik
- ggf. neue Hilfsfunktionen in `aria/core/`
- `Memory Map`

Noetige Artefakte:
- saubere Rollup-Metadaten
- Zeitfenster-Logik
- Herkunftslogik Tag/Woche/Monat

### Graph v1

Betroffene Bereiche:
- `aria/web/memories_routes.py`
- `aria/templates/memories_map.html`
- `aria/static/style.css`
- ggf. kleines JS fuer read-only Visualisierung

Noetige Artefakte:
- Graph-Datenstruktur aus Memory/Collections
- einfache Knoten-/Kantenliste
- UI fuer Anzeige und ggf. Filter

## Reihenfolge der Umsetzung

### 1. Rollup-Modell klarziehen

- Tag-/Woche-/Monat-Metadaten definieren
- Herkunft und Beziehungen festlegen

Status:
- erledigt
- Wochen- und Monats-Rollups tragen jetzt bereits:
  - `rollup_level`
  - `rollup_bucket`
  - `rollup_period_start`
  - `rollup_period_end`
  - `rollup_source_kind`
  - `rollup_source_count`

### 2. Wochen- und Monats-Rollups bauen

- aus Tages-Rollups
- spaeter aus Wochen-Rollups

### 3. Rollups in Memory Map sichtbar machen

- als klarer eigener Typ
- nicht mit Dokumenten oder normalem Knowledge vermischen

### 4. Graph v1 darueber legen

- read-only
- mit einfachen Knoten und Kanten

## Erfolgsbild fuer Build A

Wenn Build A fertig ist, soll man:

- in ARIA sehen koennen, dass Session-Kontext nicht nur flach gespeichert wird
- Wochen- und Monatsverdichtungen erkennen
- im Graph nachvollziehen koennen,
  - welche Collections es gibt
  - welche Dokumente und Memory-Typen darin leben
  - welche Rollups aus welchen Ebenen entstanden sind

Kurz:

> Build A macht ARIAs gespeichertes Wissen sichtbar und zeitlich strukturierter.
