# Retrieval-First Planner

Stand: 2026-04-26

## Ziel

ARIA soll sich von keywordlastigem If-Then-Routing zu einem kontrollierten, intelligenten Planner entwickeln:

1. deterministische Schichten sammeln nur den sicheren Handlungsraum
2. Retrieval schlaegt passende Ziele, Rezepte, Templates und Kontexte vor
3. ein bounded Planner-LLM waehlt innerhalb dieses Raums Ziel, Capability und Plan
4. Guardrails validieren den Plan vor der Ausfuehrung

Nicht das LLM soll "alles frei entscheiden". Es soll innerhalb eines sauber eingegrenzten, nachvollziehbaren Kandidatenraums planen.

## Warum

Das aktuelle Muster ist noch zu stark:

- Intent / Routing ueber Keywords und Heuristiken
- spaeter kleine bounded LLM-Korrekturen
- viele Sonderregeln pro Produktpfad

Das fuehrt langfristig zu:

- staendigem Routing-Tuning
- spröder Mixed-Language-Erkennung
- harter Verdrahtung zwischen Triggerwort und Rezept
- zu wenig semantischer Planung bei realen Aufgaben

Beispiel:

`check health auf management server`

Sollte nicht nur auf ein hart verdrahtetes Mapping hinauslaufen, sondern auf einen kleinen, sinnvollen Plan, z. B.:

- `uptime`
- `df -h`
- `systemctl --failed --no-pager`
- optional `docker ps`

## Architektur

### 1. Retrieval Layer

Der Retrieval Layer sammelt bounded Kontext fuer die Planner-Entscheidung:

- passende Connection-Kandidaten
- passende Capability-Kandidaten
- passende Rezept-/Template-Kandidaten
- Qdrant-Routing-Treffer
- Memory-/Kontext-Hinweise
- fruehere aehnliche erfolgreiche Entscheidungen

Output:

- begrenzte Kandidatenliste statt freier Welt
- Scores, Herkunft und Begruendung pro Kandidat

### 2. Planner Layer

Das Planner-LLM bekommt:

- User-Prompt
- Sprache / Session-Kontext
- bounded Connection-Kandidaten
- bounded Capability-Kandidaten
- passende Rezept-/Template-Bausteine
- Safety-/Policy-Hinweise

Output als strukturiertes JSON, z. B.:

```json
{
  "target_kind": "ssh",
  "target_ref": "mgmt-server",
  "capability": "ssh_command_bundle",
  "plan_mode": "template_bundle",
  "steps": [
    {"template_id": "ssh_health_uptime"},
    {"template_id": "ssh_health_disk"},
    {"template_id": "ssh_health_failed_services"}
  ],
  "confidence": "high",
  "ask_user": false,
  "reason": "management server plus health/status intent"
}
```

Wichtig:

- kein freies Werkzeug-Raten
- kein freies Erfinden unbekannter Commands
- nur Auswahl innerhalb des bounded Raums

### 3. Guardrail Layer

Der Guardrail Layer validiert das Planner-Ergebnis:

- ist das Ziel erlaubt?
- ist die Capability in diesem Kontext erlaubt?
- sind alle Step-Templates gueltig?
- braucht der Plan eine Rueckfrage?
- fuehrt ein Plan zu `allow`, `ask_user` oder `block`?

Hier bleibt die eigentliche Sicherheitsgrenze.

### 4. Execution Layer

Erst nach erfolgreicher Validierung:

- konkrete Ausfuehrung
- Logging
- Detail-/Explain-Lines
- Pending Actions / Confirm / Recovery

## Design-Prinzipien

### Deterministisch fuer Begrenzung, nicht fuer die Hauptentscheidung

Deterministik bleibt wichtig fuer:

- Erlaubnisraum
- Kandidatensammlung
- Validation
- Recovery

Aber nicht mehr fuer die eigentliche semantische Ziel-/Planwahl.

### Embeddings fuer Recall, LLM fuer Entscheidung

Embeddings / Qdrant:

- finden relevante Kandidaten
- finden aehnliche fruehere Faelle
- finden passende Rezepte / Templates / Verbindungen

LLM:

- interpretiert Nutzerabsicht
- waehlt bounded Ziele
- baut den Plan

### Explainability bleibt Pflicht

Jede Planner-Entscheidung braucht einen standardisierten Decision Record:

- welche Kandidaten waren im Raum?
- warum wurde Ziel X gewaehlt?
- kam die Auswahl aus:
  - Deterministik
  - Retrieval
  - Planner-LLM
  - Guardrail-Recovery

## Konkrete Produktfolgen

### Routing

Verbindungen werden nicht mehr nur per Alias/Heuristik gemappt, sondern:

- Kandidaten deterministisch eingesammelt
- semantisch ueber Retrieval verdichtet
- final bounded vom Planner-LLM gewaehlt

### Rezepte

Rezepte werden weniger "starre Endpunkte", sondern eher:

- faehige Bausteine
- Templates
- sichere Ausfuehrungspfade
- bounded Operations fuer den Planner

### SSH / Ops

SSH ist der beste Pilotpfad fuer den neuen Planner:

- sehr guter Realnutzen
- heute noch zu keyword- und mappinglastig
- gute Trennung von Ziel, Intent, Plan und Guardrails

## Pilot: SSH Health / Status

Erster bewusst neuer Planner-Pfad:

User:

- `check health auf management server`
- `wie sieht der zustand vom backup host aus`
- `pruef mal ob area41 gesund ist`

Planner-Eingaben:

- bounded SSH-Targets
- bekannte SSH-Health-Templates
- evtl. Host-Metadaten / Tags / Aliases

Planner-Ausgabe:

- SSH-Ziel
- Template-Bundle oder kleiner Health-Plan

Guardrail-Check:

- nur erlaubte Read-only-/Safe-Check-Templates
- keine freien mutierenden Commands

## Umsetzungsphasen

### Phase 1

- Connection-Candidate-Resolver weiterverwenden
- Capability-/Recipe-/Template-Candidates analog aufbauen
- gemeinsames Planner-Input-Schema definieren

### Phase 2

- bounded Planner-LLM als neues Modul
- JSON-Output-Schema fuer Ziel + Capability + Plan
- Decision Record fuer Planner-Auswahl

### Phase 3

- Pilot fuer `ssh health/status`
- Explain-/Debug-Ausgabe sichtbar machen
- Guardrail-/Recovery-Pfad daran haengen

### Phase 4

- Pilot fuer:
  - RSS / Website-Auswahl
  - Calendar
  - Mail

### Phase 5

- alte Heuristiken schrittweise abbauen
- harte Keyword-Mappings nur noch fuer grobe Safety-/Fallback-Faelle behalten

## Nicht-Ziele

- kein ungebundener Agent, der frei Commands erfindet
- keine freie Tool-Wahl ohne bounded Kandidatenraum
- keine Entfernung der Guardrails zugunsten "mehr AI"
- keine komplette Sofortmigration aller Produktpfade in einem Schritt

## Kurzform

Zielbild:

- Retrieval sammelt
- Planner waehlt
- Guardrails pruefen
- Executor fuehrt aus

Damit bleibt ARIA intelligent, aber kontrollierbar.
