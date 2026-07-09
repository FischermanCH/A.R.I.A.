# Rezepte

Rezepte sind ARIAs sichtbares Automationsmodell. Legacy-Skills bleiben nur als Kompatibilitaetsbruecken erhalten.

Ein Rezept ist ein kuratiertes JSON-Manifest mit:

- Triggern und Beschreibung
- Connection-Referenzen
- geordneten Steps
- optionalen LLM-Transforms
- Guardrail- und Bestaetigungsverhalten

## Capability-Familien

- SSH
- SFTP
- SMB
- RSS
- Discord
- Webhook
- HTTP API
- SMTP / IMAP
- MQTT
- LLM-Transform-Steps

## Wie Rezepte zu Agentic Actions passen

Rezepte sind explizite, reviewbare Workflows. Agentic Action Flow ist die Runtime-Architektur darum herum:

1. Kontext anreichern
2. begrenzten Draft bauen oder auswaehlen
3. Policy/Guardrails anwenden
4. ausfuehren oder fragen/blocken

So bleiben Rezepte kontrolliert, profitieren aber trotzdem vom LLM-Verstaendnis.

## Gelernte Rezepte und Experience Memory

Erfolgreiche sichere Laeufe koennen Learned-Recipe-Kandidaten oder Experience Memory erzeugen. Das ist Planner-Kontext und Review-Material, keine unkontrollierte Selbstprogrammierung.

### Chat Recipe Learn Mode

Die Chat-Toolbox enthaelt einen expliziten Lernmodus fuer Muster, die sich leichter durch Beispielablaeufe als durch Routing-Regeln beschreiben lassen.

Ablauf:

1. Chat-Toolbox oeffnen und Lernmodus mit `/lernen start` oder `/learn start` starten.
2. Die Chat-Schritte ausfuehren, die ARIA spaeter wiedererkennen soll.
3. Mit `/lernen stop` oder `/learn stop` abschliessen.
4. Den erzeugten Kandidaten unter `/recipes/learned` reviewen.

Grenzen:

- Learn Mode ist opt-in fuer die aktuelle Chat-Session.
- Der Ablauf erzeugt nur einen **review-only** Learned-Recipe-Kandidaten.
- Nichts wird automatisch aktiviert.
- Guardrails, Runtime-Policy, Bestaetigungen und Ausfuehrungschecks bleiben vor jeder echten Aktion.
- `/lernen abbrechen` oder `/learn cancel` verwirft den aktuellen Lernlauf.

### Review-Stati fuer gelernte Rezepte

Gelernte Rezepte werden nicht automatisch aktiv. Sie bewegen sich je nach Evidenz durch Review-Stati:

- `observed`: ARIA hat ein erfolgreiches, policy-erlaubtes Muster gesehen.
- `review_ready`: genug Evidenz fuer Admin-Review.
- `eligible`: starke Evidenz, aber weiterhin nur mit bewusster Admin-Entscheidung promotbar.
- `promoted`: bewusst in ein gespeichertes Rezept uebernommen.

Side-Effect-Aktionen bleiben vorsichtig und duerfen Bestaetigung oder Policy nicht umgehen. Multi-Target-Beobachtungen bleiben context-only; fuer echte Ausfuehrung sollte ein explizit reviewtes Rezept erstellt werden.

## Samples

Mitgelieferte Samples sind Templates. Refs, Hosts, URLs, Discord-Ziele und Guardrails muessen an die eigene Umgebung angepasst werden.

Aktuelle Sample-Richtungen:

- read-only SSH Health- und Disk-Checks
- RSS nach Chat oder RSS nach Discord
- SFTP-Lese- und Config-Preview-Beispiele
- SMB-Lese- und Listen-Beispiele

Nuetzliche Referenzen:

- [`samples/recipes/`](https://github.com/FischermanCH/A.R.I.A./tree/main/samples/recipes)
- [`docs/product/feature-list.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/product/feature-list.md)
