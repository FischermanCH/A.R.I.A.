# Agent und Hintergrund-Jobs

Stand: 2026-07-09

## Zielbild

ARIA arbeitet als kontrollierter persönlicher Agent:

1. Ziel verstehen
2. Kontext laden
3. Schritt planen
4. Sicherheit entscheiden
5. ausführen
6. Ergebnis zusammenfassen
7. das belegte Ergebnis nachvollziehbar anzeigen

LLMs helfen bei Bedeutung, Planung, Zusammenfassung und Review. Sicherheit, Guardrails, Runtime, Validierung, Normalisierung und Fallbacks bleiben kontrollierte Systemschichten.

Längere Abläufe können als Hintergrund-Job weiterlaufen. Im Job-Panel lassen sie
sich an Loop-Grenzen pausieren, fortsetzen, korrigieren oder abbrechen. Eine
Korrektur wird als neue Nutzernachricht nach dem letzten Tool-Ergebnis in den
laufenden Job übernommen. Bestätigungspflichtige Schritte verwenden auch dort
denselben Confirmation-Kernel wie ein kurzer Chat-Turn.

## Details und Trace

In Chat-Details können `operator_trace`-Linien erscheinen. Sie fassen vorhandene Debug-/Runtime-Signale in lesbare Phasen:

- **understanding**: was ARIA aus dem Prompt verstanden hat
- **context**: welche lokalen oder externen Quellen geladen wurden
- **draft/policy**: welche Aktion geplant und welche Sicherheitsentscheidung getroffen wurde
- **runtime**: welche Runtime tatsächlich ausgeführt hat
- **result**: was die Runtime geliefert hat
- **summary**: Antwort- und Laufzeitabschluss
- **job**: Status, Schritte, Token, Kosten und ein begrenztes Ergebnis

Der Trace ist Beobachtung, nicht Freibrief. Er ersetzt keine Guardrails und führt keine Aktion allein aus.

## Aktionen und Guardrails

Read-only Aktionen wie Healthchecks, Disk-Space-Checks, RSS-Lesen oder API-Statusabfragen können direkt laufen, wenn Policy und Guardrails sie erlauben.

Side-Effects wie Nachrichten senden, Webhooks auslösen, Dateien schreiben oder riskante Commands können blockiert werden oder eine Bestätigung brauchen.

## Kontextquellen

ARIA kann je nach Prompt kombinieren:

- Memory und Präferenzen
- Dokumente und Dokument-Inventar
- Notes
- Connections und deren Metadaten
- Rezepte und gelernte Erfahrungen
- Websuche, wenn aktuelle öffentliche Informationen gebraucht werden

Aktuelle Produkt-/Versionsfragen sollen Web-Freshness und offizielle Quellen bevorzugen. Lokale Dokumente bleiben relevant, wenn der Prompt explizit nach dem lokalen Dokumentenspeicher fragt.

MCP-Werkzeuge erscheinen nur für ausdrücklich aktivierte Server. Unvertraute,
verändernde oder nicht als read-only annotierte Werkzeuge laufen über die
Bestätigung. Ein als vertrauenswürdig markierter Server darf Werkzeuge ohne
Bestätigung ausführen; diese Einstellung ist deshalb eine bewusste
Sicherheitsgrenze.

## Gute Tests nach einem Update

- eine read-only Serverfrage stellen und Details auf Kontext, Runtime und Ergebnis prüfen
- eine bestätigungspflichtige Aktion planen und nicht ausführen
- eine aktuelle Produktfrage stellen und Quellen prüfen
- eine lokale Dokument-Inventarfrage stellen und sicherstellen, dass sie nicht ins Web ausweicht
