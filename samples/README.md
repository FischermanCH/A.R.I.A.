# ARIA Samples

Diese Sammlung enthaelt kleine Beispiel-Dateien fuer den Alpha-Stand.

## Recipes

Die Dateien unter `samples/recipes/` sind recipe-first JSON-Manifeste fuer den Import unter `/recipes`.

Aktuelle Beispiele:

- `discord-broadcast-template.json`: einfache Discord-Nachricht aus einem Rezept senden
- `linux-fleet-healthcheck-to-discord-template.json`: mehrere Linux-Hosts read-only via SSH pruefen, per LLM bewerten und nur bei echtem Alarm nach Discord senden
- `linux-updates-check-template.json`: read-only Linux-Update-Check via SSH
- `smb-share-list-template.json`: SMB-Share lesen und im Chat zusammenfassen

## Legacy Skill Samples

Die Dateien unter `samples/skills/` bleiben vorerst als Legacy-/Backcompat-Referenz erhalten. Neue Tests, neue Doku und neue Produkttexte sollen `samples/recipes/` und `/recipes` verwenden.

## Connections

Die Dateien unter `samples/connections/` sind neutrale Vorlagen. Dafuer gibt es aktuell noch keinen direkten UI-Import. Sie dienen als Referenz fuer:

- manuelles Anlegen ueber die UI
- spaetere Import-/Export-Funktionen
- Dokumentation / Demo-Setups

## Security / Guardrails

Die Dateien unter `samples/security/` zeigen das generische Guardrail-Format.

Aktuell enthalten:

- `guardrails.sample.yaml`: kleines Starter-Pack mit SSH-, Datei-, HTTP- und MQTT-Guardrails

Die Guardrail-Samples lassen sich in der Security-Seite direkt aus dem GUI importieren.

Wichtig:

- alle Werte sind Platzhalter
- Secrets / Tokens / Passwoerter sind bewusst leer oder neutral
- bei Rezepten mit `ssh_run`, `sftp_read`, `sftp_write` oder `discord_send` muessen die referenzierten Connections vorher existieren
- bei Rezepten mit `smb_read`, `smb_write` oder `rss_read` muss der entsprechende Build-Stand diese Step-Typen bereits enthalten
