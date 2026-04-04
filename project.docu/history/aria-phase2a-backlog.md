# ARIA — Phase 2A Backlog: Memory-Architektur 2.0

## Philosophie

> **ARIA erinnert sich wie ein Mensch: Fakten sofort, Kontext bei Bedarf, Altes verblasst.**

Memory ist nicht "alles speichern und Top-3 zurückgeben". Es ist ein System das weiss, WAS wichtig ist, WIE LANGE es relevant bleibt, und WIE es in den aktuellen Kontext passt.

---

## Ist-Zustand (nach Phase 1 + bisherige Arbeit)

- ✅ Memory Store/Recall via Qdrant funktioniert
- ✅ Username-basierte Zuordnung (user_id aus Cookie)
- ✅ Deduplizierung bei Store (Similarity > 0.9 → Update)
- ✅ Tages-Kontext mit Collection-Namensschema `YYMMDD`
- ✅ Auto-Memory konfigurierbar (Ampel im Header)
- ⚠️ Recall ist "flach": Top-K aus einer Collection, keine Gewichtung
- ⚠️ Kein Unterschied zwischen Fakt, Präferenz und Gesprächskontext
- ⚠️ Keine Memory-Hygiene (alte Sessions wachsen unbegrenzt)
- ⚠️ Kein "Vergiss X" mit sauberem Löschen über Collections hinweg

---

## Scope Phase 2A

- Memory-Typen mit unterschiedlichem Verhalten (Facts, Preferences, Sessions, Knowledge)
- Gewichtetes Recall über mehrere Collections
- Memory-Hygiene (Komprimierung, TTL, Vergessen)
- Memory-Management im UI (Anzeigen, Löschen, Suchen)
- Robustes Error-Handling mit verständlichen UI-Meldungen

Abgrenzung:
- Websuche ist als Assistenz-Funktion wichtig, wird aber ausserhalb von Phase 2A umgesetzt.
- Zielbild Websuche: provider-native Tooling first; SearXNG optional.

## Späterer Produktblock: Home Assistant als Hauszustand-Feed

Zielbild:
- ARIA wird nicht nur ein Chat-Frontend, sondern schrittweise das **lernende Hirn der Haussteuerung**
- Home Assistant liefert dafür Device-/Sensor-/Entity-Zustände
- ARIA speichert relevante Zustandsverläufe und Muster in Qdrant und kann daraus adaptive Vorschläge, Routinen und Kontext ableiten

### Kernidee

- Home Assistant als eigene Integration / Connection anbinden
- Zustände einzelner Devices/Entities regelmäßig lesen, z. B.:
  - Lampen / Switches
  - Präsenz
  - Temperatur / Klima
  - Fenster / Türen / Bewegungsmelder
  - Energie- / Verbrauchswerte
- diese Status-Snapshots oder verdichtete Ereignisse strukturiert in Qdrant ablegen
- ARIA kann daraus später beantworten und lernen:
  - `Welche Geräte sind gerade an?`
  - `Ist im Haus gerade etwas ungewöhnlich?`
  - `Welche Routinen wiederholen sich abends/morgens?`
  - `Wann ist das Büro normalerweise belegt?`
  - `Was sollte automatisch passieren, wenn Zustand X eintritt?`

### Wichtiges Design-Prinzip

- nicht blind jeden Rohstatus endlos als Memory speichern
- stattdessen eine **Event-/State-Komprimierung**:
  - relevante Zustandsänderungen erkennen
  - wiederkehrende Muster verdichten
  - zeitliche Fenster zusammenfassen
  - "normales Rauschen" nicht dauerhaft aufblasen

### Denkbares Datenmodell

- `homeassistant_state`:
  - aktueller Entity-Zustand
  - Entity-ID, Area/Room, Device-Klasse, Attribute, `last_changed`
- `homeassistant_event`:
  - relevante Zustandswechsel / Auffälligkeiten
  - z. B. `Fenster Büro 23 Minuten offen`, `Waschmaschine fertig`, `Bewegung Keller nachts`
- `homeassistant_pattern`:
  - von ARIA verdichtete Gewohnheiten / Routinen
  - z. B. `Wohnzimmerlicht meist 19:00-23:30 aktiv`, `Büro werktags ab 08:30 belegt`

### Offene Architekturfragen

- Polling vs. Home-Assistant-Events/Websocket
- welche Entities standardmäßig in Qdrant landen und welche bewusst nicht
- wie viel davon als "harte Fakten" vs. "beobachtete Muster" gespeichert wird
- Datenschutz / lokale Kontrolle:
  - klare Sichtbarkeit, **welche HA-Daten ARIA speichert**
  - einfache Lösch-/Reset-Möglichkeit für HA-Lernhistorie
- ob ARIA später nur Empfehlungen gibt oder auch aktiv Home-Assistant-Services auslöst

### MVP-Vorschlag

1. Home-Assistant-Connection mit API-Token + Base URL
2. auswählbare Entity-/Area-Liste
3. Status-Snapshot abrufen und anzeigen
4. ausgewählte Entity-Zustände in Qdrant speichern
5. einfacher Chat-Readout:
   - `wie ist der Status meiner Wohnung?`
   - `was ist im Wohnzimmer gerade an?`
6. danach erst Pattern-Learning / adaptive Routinen

### Ziel

- Home Assistant bleibt der Aktor-/Device-Layer
- ARIA wird darüber die **kontextuelle, lernende Intelligenzschicht**
- klarer Produktpfad Richtung:
  - `personal assistant`
  - `smart home brain`
  - `lokales, adaptives Zuhause-Gedächtnis`

## Prioritaet morgen (TOP 1)

### Skill-Status Antwort nachschaerfen (`welche Skills sind aktiv?`) ✅ umgesetzt (2026-03-25)

Problem:
- ARIA antwortet aktuell teils generisch/halluziniert ("allgemeine IT-Beratung ..."), statt die real aktivierten Skills zu nennen.
- Teilweise kommt sogar "kein Zugriff auf dein System", obwohl ARIA den Skill-Status intern kennt.

Ziel:
- Bei Fragen wie:
  - `kannst du deine skills überprüfen und mir mitteilen was aktiv ist?`
  - `welche skills sind aktiv?`
  - `was kannst du aktuell ausführen?`
  soll ARIA deterministisch aus der echten Runtime-Konfiguration antworten.

Umsetzung:
1. eigener Intent/Route für `skill_status`
2. Antwortquelle ist **nicht** Freitext-LLM, sondern strukturierte Runtime-Daten:
   - Core Skills (aktiv/aus)
   - Custom Skills (aktiv/aus, Zweck aus `description` + Step-Typen)
3. kompakte Ausgabe mit Zweck je Skill:
   - Name
   - Status (aktiv/aus)
   - Kurz-Zweck
   - ggf. Connection-Hinweis (z.B. `ssh`, `discord`)
4. Fallback nur wenn keine Skilldaten ladbar sind (mit klarer Fehlermeldung)

Akzeptanz:
- Keine generische "ich habe keinen Zugriff" Antwort mehr für Skill-Status-Fragen.
- Antwort basiert auf realen Skills aus `data/skills/*.json` + Core-Konfig.
- Mindestens ein Testfall für Skill-Status-Intent + Ausgabeformat.

## Umsetzungsreihenfolge (angepasst)

Wir starten bewusst mit einem kompatiblen Fundament und reduzieren Risiko:

1. **Task 1 zuerst, kompatibel**  
   Neues `memory.collections`-Schema einführen, ohne bestehende Setups zu brechen.
2. **Task 2 danach**  
   Gewichtetes Recall erst aufbauen, wenn Collection-Layout stabil ist.
3. **Task 3 vor Task 4**  
   Forget-Flow mit Bestätigung zuerst absichern, dann erst zusätzliche Extraction-Logik.
4. **Task 5 erst nach stabilen Kernpfaden**  
   Kontext-Rollup kommt nach Store/Recall/Forget.

### Kompatibilitätsregel

- Bestehende Top-Level-Config (`auto_memory`) bleibt gültig.
- Neues Schema unter `memory.collections` wird parallel eingeführt.
- Keine erzwungene Migration bestehender Daten in Phase 2A-1.

---

## Definition of Done (Phase 2A)

1. Facts, Preferences und Sessions sind getrennte Collections mit eigenem Verhalten
2. Recall kombiniert Treffer aus allen relevanten Collections, gewichtet nach Typ + Zeit
3. "Vergiss mein NAS" löscht den Eintrag sauber aus der richtigen Collection
4. Alte Sessions (>30 Tage) werden automatisch zusammengefasst
5. Memory-Seite im UI zeigt alle Erinnerungen, filterbar nach Typ
6. Tests grün für alle neuen Memory-Operationen

---

## Memory-Typen

### 1. Facts (`aria_facts_{user_id}`)

**Was:** Harte, konkrete Fakten über den User oder seine Umgebung.
**Beispiele:** "Mein NAS ist 172.31.5.230", "Ich arbeite bei Firma X", "Mein Server heisst pve1"
**Verhalten:**
- Deduplizierung: Similarity > 0.85 → Update (überschreiben, nicht doppelt speichern)
- Kein TTL — Fakten bleiben bis explizit gelöscht
- Höchste Priorität beim Recall (Gewicht: 1.0)
- Store-Trigger: Explizit ("merk dir") ODER Auto-Memory erkennt Fakt-Pattern

**Payload:**
```json
{
  "text": "NAS IP ist 172.31.5.230, Modell Synology RS816",
  "user_id": "fischerman",
  "type": "fact",
  "category": "infrastructure",
  "created_at": "2026-02-22T20:26:38Z",
  "updated_at": "2026-03-17T14:30:00Z",
  "source": "explicit"
}
```

### 2. Preferences (`aria_preferences_{user_id}`)

**Was:** Vorlieben, Gewohnheiten, Arbeitsweisen des Users.
**Beispiele:** "Ich bevorzuge Schweizer Hochdeutsch", "Ich mag keine Floskeln", "Ich nutze Docker für alles"
**Verhalten:**
- Deduplizierung: Similarity > 0.80 → Update
- Kein TTL — Präferenzen bleiben
- Mittlere Priorität beim Recall (Gewicht: 0.8)
- Store-Trigger: Primär Auto-Memory (erkennt Präferenz-Pattern)

**Payload:**
```json
{
  "text": "User bevorzugt direkte Antworten ohne Floskeln",
  "user_id": "fischerman",
  "type": "preference",
  "category": "communication",
  "created_at": "2026-03-01T10:00:00Z",
  "confidence": 0.9,
  "source": "auto"
}
```

### 3. Sessions (`aria_sessions_{user_id}_{YYMMDD}`)

**Was:** Tages-Gesprächskontext — was heute besprochen wurde.
**Verhalten:**
- Bereits implementiert (Tages-Collections)
- NEU: Nach 7 Tagen → Zusammenfassung in eine "Wochen-Summary" (1 Eintrag statt 50)
- NEU: Nach 30 Tagen → Wochen-Summaries werden zu Monats-Summary komprimiert
- NEU: Nach 90 Tagen → Monats-Summaries werden gelöscht (oder archiviert)
- Niedrigste Priorität beim Recall (Gewicht: 0.5)
- Store-Trigger: Automatisch nach jedem Chat (wie bisher)

**Komprimierungs-Pipeline:**
```
Tag 1-7:   Einzelne Chat-Einträge (volle Granularität)
Tag 8-30:  Wochen-Summary (LLM fasst 7 Tage zusammen → 1 Eintrag)
Tag 31-90: Monats-Summary (LLM fasst 4 Wochen zusammen → 1 Eintrag)
Tag 91+:   Gelöscht oder in Export-Archiv
```

**Summary-Prompt (für LLM-Komprimierung):**
```
Fasse die folgenden Gesprächsnotizen in maximal 5 Sätzen zusammen.
Behalte nur: konkrete Fakten, Entscheidungen, offene Aufgaben.
Entferne: Smalltalk, Wiederholungen, Debugging-Details.
```

### 4. Knowledge (`aria_knowledge_{user_id}`)

**Was:** Eingespeiste Dokumente, Notizen, Wissensbasen.
**Verhalten:**
- Chunking bei Ingest (kommt in Phase 2B)
- Kein TTL — bleibt bis gelöscht
- Mittlere Priorität beim Recall (Gewicht: 0.7)
- Store-Trigger: Expliziter Upload oder Ingest-Befehl

**Hinweis:** Phase 2A legt die Collection und das Interface an. Die Chunking-Engine (wie Dokumente reinkommen) ist Phase 2B.

---

## Gewichtetes Recall

### Aktuell (flach)
```
User fragt → Embedding → Search in 1 Collection → Top-3 → fertig
```

### Neu (gewichtet, multi-collection)
```
User fragt → Embedding → Parallel Search in allen Collections
  → Facts:       Top-2, Gewicht 1.0, kein Zeitabfall
  → Preferences:  Top-1, Gewicht 0.8, kein Zeitabfall
  → Sessions:    Top-2, Gewicht 0.5, Zeitabfall (neuer = besser)
  → Knowledge:   Top-2, Gewicht 0.7, kein Zeitabfall
  → Merge + Sort nach kombiniertem Score
  → Top-5 gesamt → Context Assembler
```

### Score-Berechnung
```python
def combined_score(hit, memory_type: str) -> float:
    base_score = hit.score  # Qdrant Similarity (0.0 - 1.0)
    
    type_weights = {
        "fact": 1.0,
        "preference": 0.8,
        "knowledge": 0.7,
        "session": 0.5,
    }
    
    weight = type_weights.get(memory_type, 0.5)
    
    # Zeitabfall nur für Sessions
    if memory_type == "session":
        age_days = (now - hit.payload["created_at"]).days
        time_decay = max(0.3, 1.0 - (age_days / 30) * 0.7)
        weight *= time_decay
    
    return base_score * weight
```

### Context-Format für LLM
```
--- erinnerung ---
[FAKT] NAS IP ist 172.31.5.230, Modell Synology RS816
[FAKT] Proxmox Cluster läuft auf pve1
[PRÄFERENZ] User bevorzugt direkte Antworten ohne Floskeln
[KONTEXT/heute] Heute haben wir an ARIA Phase 2A gearbeitet
[WISSEN] Docker Compose unterstützt health checks via test-Direktive
```

Die Typ-Labels helfen dem LLM zu verstehen WOHER die Info kommt und wie verlässlich sie ist.

---

## Memory-Hygiene

### Vergessen ("Vergiss X")

```
User: "Vergiss mein NAS"

1. Router erkennt Intent: memory_forget
2. Embedding von "NAS" erstellen
3. Parallel in allen Collections suchen (Threshold > 0.75)
4. Treffer dem User zeigen: "Ich habe 2 Einträge gefunden:
   - [FAKT] NAS IP ist 172.31.5.230
   - [SESSION] Heute über NAS-Setup gesprochen
   Soll ich beide löschen?"
5. User bestätigt → Löschen aus Qdrant
```

**Wichtig:** Nicht blind löschen. Immer bestätigen lassen — besonders bei Facts.

---

## Zusätzlicher Safety-Backlog

- [ ] **Embedding-Model-Wechsel absichern**
  - Problem: Beim Wechsel des Embedding-Modells können bestehende Vektoren inkompatibel oder semantisch inkonsistent werden.
  - Kurzfristig:
    - UI-Warnung mit expliziter Bestätigung vor dem Speichern
    - Klarer Hinweis auf mögliche Recall-Auswirkungen in bestehenden Collections
  - Mittelfristig:
    - Reindex-/Migrations-Flow (neue Ziel-Collection, Re-Embedding, optionaler atomarer Swap)
    - Fortschrittsanzeige und Rollback-Option

### Auto-Komprimierung (Sessions)

Täglicher Job (oder beim Start):
```python
async def compress_old_sessions(user_id: str):
    # Tages-Kontext älter als 7 Tage → Wochen-Summary
    old_sessions = find_sessions_older_than(user_id, days=7)
    for week_group in group_by_week(old_sessions):
        entries = load_all_entries(week_group)
        summary = await llm.summarize(entries)  # ~150 Tokens
        store_summary(user_id, summary, type="week_summary")
        delete_original_sessions(week_group)
    
    # Wochen-Summaries älter als 30 Tage → Monats-Summary
    old_weeks = find_week_summaries_older_than(user_id, days=30)
    for month_group in group_by_month(old_weeks):
        summary = await llm.summarize(month_group)
        store_summary(user_id, summary, type="month_summary")
        delete_week_summaries(month_group)
```

### Router-Keywords für Memory-Forget

```python
memory_forget_keywords = (
    "vergiss",
    "lösch",
    "entfern",
    "delete",
    "remove",
)
```

---

## Memory-UI

### Neue Seite: `/memories`

```
┌─────────────────────────────────────────────────────┐
│  ARIA          Chat  Memories  Stats  [Fischerman]  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Filter: [Alle ▾]  [Facts] [Preferences] [Sessions]│
│                                                     │
│  Suche: [________________________] [Suchen]         │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │ 🔵 FAKT · infrastructure                    │    │
│  │ NAS IP ist 172.31.5.230, Synology RS816     │    │
│  │ Erstellt: 22.02.2026 · Quelle: explizit     │    │
│  │                              [Löschen]       │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │ 🟢 PRÄFERENZ · communication                │    │
│  │ Bevorzugt direkte Antworten ohne Floskeln   │    │
│  │ Erstellt: 01.03.2026 · Quelle: auto         │    │
│  │                              [Löschen]       │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │ 🟡 SESSION · 17.03.2026                     │    │
│  │ ARIA Phase 2A Backlog besprochen, Memory-   │    │
│  │ Typen definiert, Recall-Strategie geplant   │    │
│  │ Erstellt: 17.03.2026 · Quelle: auto         │    │
│  │                              [Löschen]       │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ─────────────────────────────────────────────────  │
│  Facts: 12 · Preferences: 5 · Sessions: 34         │
│  Qdrant: 172.31.10.220:6334  [Dashboard ↗]         │
│  [Export Memory]                                    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Features:**
- Filter nach Typ (Tabs oder Dropdown)
- Volltextsuche (per Embedding, nicht String-Match)
- Einzelne Einträge löschen (mit Bestätigung)
- Export-Button (Qdrant Snapshot Download)
- Link zum Qdrant Dashboard
- Zähler pro Typ

---

## Auto-Memory Verbesserung

### Aktuell
Auto-Memory speichert alles undifferenziert in eine Collection.

### Neu: Fact-Extraction mit Typ-Erkennung

Am Ende jedes Chat-Turns (wenn Auto-Memory aktiv):

```python
EXTRACTION_PROMPT = """
Analysiere die folgende Nachricht des Users.
Extrahiere NUR relevante Informationen in folgendem JSON-Format:

{
  "facts": ["konkrete Fakten über Personen, Systeme, IPs, Namen, Orte"],
  "preferences": ["Vorlieben, Gewohnheiten, Arbeitsweisen"],
  "skip": true/false  // true wenn nichts Relevantes gefunden
}

Regeln:
- NUR Informationen die der User ÜBER SICH oder SEINE Umgebung mitteilt
- KEINE allgemeinen Fragen oder Wissensfragen extrahieren
- KEINE Informationen die ARIA bereits gespeichert hat
- Kurz und prägnant formulieren
- Bei Unsicherheit: skip: true

User-Nachricht: {message}
ARIA-Antwort: {response}
"""
```

**Token-Budget:** Dieser Extraction-Call kostet ~100-200 Tokens. Nur ausführen wenn Auto-Memory aktiv ist.

**Ablauf:**
```
User sagt: "Ich arbeite bei Swiss Re und mein Laptop ist ein ThinkPad T14"

→ Extraction-LLM:
{
  "facts": [
    "User arbeitet bei Swiss Re",
    "User hat ThinkPad T14 Laptop"
  ],
  "preferences": [],
  "skip": false
}

→ Für jeden Fakt: Dedup-Check → Store in aria_facts_fischerman
→ Für jede Präferenz: Dedup-Check → Store in aria_preferences_fischerman
```

---

## Backlog mit Akzeptanzkriterien

### Task 1: Memory-Typen + Collections
**Dateien:** `memory.py`, `config.py`, `config.yaml`
**Aufgabe:** Facts, Preferences, Knowledge als eigene Collections anlegen. Sessions bleibt wie bisher (Tages-Schema).
**Akzeptanzkriterien:**
- Beim Start werden fehlende Collections automatisch erstellt
- Store-Aufrufe landen in der richtigen Collection basierend auf Typ
- Config hat neue Sektion `memory.collections` mit Namen-Templating
- Bestehende Memories in `aria_memory` bleiben unangetastet (Migration separat)

### Task 2: Gewichtetes Multi-Collection Recall
**Dateien:** `memory.py`, `context.py`
**Aufgabe:** Recall sucht parallel in allen Collections, gewichtet Treffer, gibt Top-N gesamt zurück.
**Akzeptanzkriterien:**
- Recall durchsucht Facts + Preferences + aktuelle Session + Knowledge
- Score-Berechnung mit Typ-Gewichten und Zeitabfall für Sessions
- Context-Format enthält Typ-Labels ([FAKT], [PRÄFERENZ], etc.)
- Konfigurierbar: Gewichte und Top-K pro Typ in config.yaml
- Bei Collection-Fehler: degradieren, nicht abbrechen

### Task 3: Memory-Forget mit Bestätigung
**Dateien:** `router.py`, `memory.py`, `pipeline.py`, `chat.html`
**Aufgabe:** "Vergiss X" sucht über alle Collections, zeigt Treffer, löscht nach Bestätigung.
**Akzeptanzkriterien:**
- Router erkennt forget-Intent ("vergiss", "lösch", "entfern")
- Suche über alle Collections, Threshold > 0.75
- UI zeigt gefundene Einträge mit Typ und Inhalt
- User bestätigt → Einträge werden gelöscht
- Abbrechen möglich → nichts passiert

### Task 4: Auto-Memory mit Typ-Erkennung
**Dateien:** `memory.py`, `pipeline.py`
**Aufgabe:** Auto-Memory extrahiert Fakten und Präferenzen getrennt und speichert in richtiger Collection.
**Akzeptanzkriterien:**
- Extraction-Prompt liefert JSON mit facts[] und preferences[]
- Dedup-Check pro Eintrag vor Store
- Nur bei aktivem Auto-Memory ausgeführt
- Bei skip:true → kein Store, kein Token-Verbrauch für Dedup
- Token-Verbrauch des Extraction-Calls wird separat geloggt

### Task 5: Kontext-Rollup
**Dateien:** `memory.py` (neuer Hintergrund-Task)
**Aufgabe:** Alte Sessions automatisch zusammenfassen (7d → Woche, 30d → Monat).
**Akzeptanzkriterien:**
- Beim Start oder per manuellen Trigger: Sessions > 7 Tage → Wochen-Summary
- Wochen-Summaries > 30 Tage → Monats-Summary
- Originale werden nach Summary gelöscht
- Summary-Prompt ist als Prompt-File konfigurierbar
- Komprimierung wird im Token-Log erfasst

### Task 6: Memory-UI Seite
**Dateien:** `main.py`, `memories.html`, `style.css`
**Aufgabe:** Neue Seite `/memories` mit Übersicht aller Erinnerungen.
**Akzeptanzkriterien:**
- Filter nach Typ (Facts, Preferences, Sessions)
- Suche per Embedding (nicht String-Match)
- Einzelne Einträge löschen mit Bestätigung
- Zähler pro Collection
- Link zum Qdrant Dashboard (aus Config)
- Export-Button (Qdrant Snapshot)

### Task 7: Error-Handling + Meldungen
**Dateien:** `memory.py`, `pipeline.py`, `chat.html`
**Aufgabe:** Verständliche Fehlermeldungen statt `memory_error`.
**Akzeptanzkriterien:**
- Qdrant nicht erreichbar → "Memory-Dienst nicht verfügbar"
- Embedding-Fehler → "Textverarbeitung fehlgeschlagen"
- Collection nicht gefunden → wird automatisch erstellt
- Alle Fehler im Badge sichtbar (Icon + Kurztext)
- Detaillierter Fehler im Token-Log

### Task 8: Tests
**Dateien:** `test_memory.py` (erweitert), `test_recall.py` (neu)
**Aufgabe:** Tests für neue Memory-Operationen.
**Akzeptanzkriterien:**
- Multi-Collection Recall: korrektes Gewichten + Mergen
- Forget: Suche + Löschung über Collections
- Auto-Memory Extraction: JSON-Parsing, Typ-Zuordnung
- Dedup: Similarity > Threshold → Update statt Insert
- Degradation: Collection fehlt → kein Crash

### Task 9 (später): Memory-Map als echte Graph-Visualisierung
**Dateien:** `memories_map.html`, `style.css`, optional `main.py` (Aggregationsdaten)
**Aufgabe:** Native visuelle Graph-Ansicht (Nodes/Edges) statt nur Karten/Tabelle.
**Akzeptanzkriterien:**
- Collections als Nodes mit Grösse nach Point-Anzahl
- Verknüpfungen/Cluster nach Typ oder semantischer Nähe sichtbar
- Zoom/Filter nach Typ (`fact`, `preference`, `session`, `knowledge`)
- Browser-kompatibel ohne iframe/CSP-Abhängigkeit
- Nutztauglich für Debugging und Memory-Hygiene (nicht nur Deko)

---

## Session-Plan

### Session 2A-1: Kompatibles Memory-Schema + Collections
Task 1 (kompatibel)
**Ergebnis:** Typisierte Collections sind eingeführt, bestehende Setups laufen weiter.

### Session 2A-2: Gewichtetes Recall
Task 2
**Ergebnis:** Recall kombiniert Treffer aus mehreren Typ-Collections mit Gewichten.

### Session 2A-3: Forget-Flow + Auto-Memory Typ-Erkennung
Tasks 3 + 4
**Ergebnis:** "Vergiss X" funktioniert sicher, Auto-Memory unterscheidet Fakten und Präferenzen.

### Session 2A-4: Kontext-Rollup + Memory-UI
Tasks 5 + 6
**Ergebnis:** Alte Sessions werden komprimiert, User kann Memories verwalten.

### Session 2A-5: Error-Handling + Tests
Tasks 7 + 8
**Ergebnis:** Robuste Fehlermeldungen, Tests grün.

---

## Config-Erweiterung (config.yaml)

```yaml
memory:
  enabled: true
  backend: "qdrant"
  qdrant_url: "http://localhost:6334"
  
  collections:
    facts:
      prefix: "aria_facts"
      weight: 1.0
      top_k: 2
      dedup_threshold: 0.85
    preferences:
      prefix: "aria_preferences"
      weight: 0.8
      top_k: 1
      dedup_threshold: 0.80
    sessions:
      prefix: "aria_sessions"
      weight: 0.5
      top_k: 2
      time_decay: true
      compress_after_days: 7
      archive_after_days: 90
    knowledge:
      prefix: "aria_knowledge"
      weight: 0.7
      top_k: 2
      dedup_threshold: 0.90

  auto_memory:
    enabled: true
    extraction_model: "ollama_chat/qwen3:8b"  # Kann anderes Modell sein
    max_extraction_tokens: 200

  compression:
    enabled: true
    summary_prompt: "prompts/skills/memory_compress.md"
    run_on_startup: true
```

---

## Migration bestehender Daten

Die aktuelle `aria_memory` Collection und Tages-Collections bleiben zunächst bestehen. Migration ist optional und kann manuell gemacht werden:

1. Bestehende Einträge aus `aria_memory` → `aria_facts_{user_id}` kopieren
2. Tages-Collections → bleiben als Sessions
3. Alte `aria_memory` nach erfolgreicher Migration löschen

Kein automatischer Migrationsschritt — zu riskant. Lieber sauber parallel starten.

---

## Offene Infos vor dem Start

| Info | Status |
|---|---|
| Qdrant eigene Instanz (Port 6334) | Deployen via Portainer ⏳ |
| Aktuelle Collection-Namen | Prüfen was Codex bisher angelegt hat |
| Auto-Memory: Welches Modell für Extraction? | Default qwen3:8b, oder separates kleines Modell? |
