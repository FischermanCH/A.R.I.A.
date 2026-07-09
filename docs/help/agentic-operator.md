# Agentic Operator

Stand: 2026-07-09

## Zielbild

ARIA soll weniger wie ein Bot mit Tools und mehr wie ein kontrollierter persoenlicher Operator arbeiten:

1. Ziel verstehen
2. Kontext laden
3. Schritt planen
4. Sicherheit entscheiden
5. ausfuehren
6. Ergebnis zusammenfassen
7. optional aus Review und Feedback lernen

LLMs helfen bei Bedeutung, Planung, Zusammenfassung und Review. Sicherheit, Guardrails, Runtime, Validierung, Normalisierung und Fallbacks bleiben kontrollierte Systemschichten.

## Operator Trace

In Chat-Details koennen `operator_trace`-Linien erscheinen. Sie fassen vorhandene Debug-/Runtime-Signale in lesbare Phasen:

- **understanding**: was ARIA aus dem Prompt verstanden hat
- **context**: welche lokalen oder externen Quellen geladen wurden
- **draft/policy**: welche Aktion geplant und welche Sicherheitsentscheidung getroffen wurde
- **runtime**: welche Runtime tatsaechlich ausgefuehrt hat
- **result**: was die Runtime geliefert hat
- **summary**: Antwort- und Laufzeitabschluss
- **learning**: nur Review-/Kontext-Lernen, keine automatische Policy-Aenderung

Der Trace ist Beobachtung, nicht Freibrief. Er ersetzt keine Guardrails und fuehrt keine Aktion allein aus.

## Aktionen und Guardrails

Read-only Aktionen wie Healthchecks, Disk-Space-Checks, RSS-Lesen oder API-Statusabfragen koennen direkt laufen, wenn Policy und Guardrails sie erlauben.

Side-Effects wie Nachrichten senden, Webhooks ausloesen, Dateien schreiben oder riskante Commands koennen blockiert werden oder eine Bestaetigung brauchen.

## Kontextquellen

ARIA kann je nach Prompt kombinieren:

- Memory und Praeferenzen
- Dokumente und Dokument-Inventar
- Notes
- Connections und deren Metadaten
- Rezepte und gelernte Erfahrungen
- Websuche, wenn aktuelle oeffentliche Informationen gebraucht werden

Aktuelle Produkt-/Versionsfragen sollen Web-Freshness und offizielle Quellen bevorzugen. Lokale Dokumente bleiben relevant, wenn der Prompt explizit nach dem lokalen Dokumentenspeicher fragt.

## Lernen

Gelernte Muster sind Planner-Kontext und Review-Material. Sie duerfen Guardrails nicht umgehen. Multi-Target- oder Side-Effect-Erfahrungen bleiben vorsichtig und muessen bewusst bewertet werden, bevor sie als echtes Rezept dienen.

## Gute Tests nach einem Update

- eine read-only Serverfrage stellen und Details auf Kontext, Runtime und Ergebnis pruefen
- eine bestaetigungspflichtige Aktion planen und nicht ausfuehren
- eine aktuelle Produktfrage stellen und Quellen pruefen
- eine lokale Dokument-Inventarfrage stellen und sicherstellen, dass sie nicht ins Web ausweicht
