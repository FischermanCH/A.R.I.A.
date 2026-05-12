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
