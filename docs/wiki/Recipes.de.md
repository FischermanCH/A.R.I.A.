# Rezepte

Rezepte sind ARIAs sichtbares Automationsmodell. Legacy-Skills bleiben nur als Kompatibilitätsbrücken erhalten.

Ein Rezept ist ein kuratiertes JSON-Manifest mit:

- Triggern und Beschreibung
- Connection-Referenzen
- geordneten Steps
- optionalen LLM-Transforms
- Guardrail- und Bestätigungsverhalten

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
2. begrenzten Draft bauen oder auswählen
3. Policy/Guardrails anwenden
4. ausführen oder fragen/blocken

So bleiben Rezepte kontrolliert, profitieren aber trotzdem vom LLM-Verständnis.

## Wiederkehrende Abläufe

Wiederholt beobachtete, vergleichbare Aktionen können als inaktiven Rezeptentwurf angeboten werden. Alternativ legt `recipe_remember` einen ausdrücklich gewünschten Ablauf ab. Beides ersetzt keine Prüfung: Ein Rezept wird erst durch eine bewusste Nutzeraktion gespeichert und bleibt den bestehenden Guardrails und Bestätigungen unterworfen.

Der frühere Chat-Lernmodus mit Start-/Stop-Kommandos ist entfernt. Solche Nachrichten werden heute als normale Chat-Nachrichten behandelt.

## Samples

Mitgelieferte Samples sind Templates. Refs, Hosts, URLs, Discord-Ziele und Guardrails müssen an die eigene Umgebung angepasst werden.

Aktuelle Sample-Richtungen:

- read-only SSH Health- und Disk-Checks
- RSS nach Chat oder RSS nach Discord
- SFTP-Lese- und Config-Preview-Beispiele
- SMB-Lese- und Listen-Beispiele

Nützliche Referenzen:

- [`samples/recipes/`](https://github.com/FischermanCH/A.R.I.A./tree/main/samples/recipes)
- [`docs/product/feature-list.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/product/feature-list.md)
