# ARIA Samples

Diese Sammlung enthält kleine Beispiel-Dateien für den ALPHA-Stand.

## Skills

Die Dateien unter `samples/skills/` sind direkte JSON-Manifeste für den Import unter `/skills`.

Aktuelle Beispiele:

- `echo-chat.json`: sicherer Demo-Skill ohne externe Verbindung
- `ssh-healthcheck-template.json`: einfacher SSH-Uptime-/Healthcheck
- `linux-updates-check-template.json`: read-only Linux-Update-Check via SSH
- `linux-fleet-healthcheck-to-discord-template.json`: mehrere Linux-Hosts read-only via SSH pruefen, per LLM bewerten und nur bei echtem Alarm nach Discord senden
- `sftp-read-template.json`: einfacher Datei-Lesezugriff via SFTP
- `smb-share-list-template.json`: SMB-Share lesen und im Chat zusammenfassen
- `discord-broadcast-template.json`: einfache Discord-Nachricht aus einem Skill senden
- `rss-digest-to-discord-template.json`: RSS laden, per LLM kuratieren und nach Discord senden
- `rss-headlines-to-chat-template.json`: einen RSS-Feed lesen und die wichtigsten Headlines direkt in den Chat schreiben
- `ssh-disk-usage-template.json`: Linux-Dateisysteme via SSH pruefen und kompakt zusammenfassen
- `ssh-service-status-template.json`: Status eines Systemd-Dienstes via SSH pruefen und einordnen
- `ssh-memory-pressure-template.json`: RAM-Lage und groesste Prozesse via SSH kompakt zusammenfassen
- `sftp-config-preview-template.json`: eine Konfigurationsdatei via SFTP lesen und die wichtigsten Punkte erklaeren
- `rss-security-watch-template.json`: Security-/Ops-Meldungen aus einem RSS-Feed als kurze Watchlist kuratieren

## Connections

Die Dateien unter `samples/connections/` sind neutrale Vorlagen. Dafür gibt es aktuell noch keinen direkten UI-Import. Sie dienen als Referenz für:

- manuelles Anlegen über die UI
- spätere Import-/Export-Funktionen
- Dokumentation / Demo-Setups

## Security / Guardrails

Die Dateien unter `samples/security/` zeigen das generische Guardrail-Format.

Aktuell enthalten:

- `guardrails.sample.yaml`: kleines Starter-Pack mit SSH-, Datei-, HTTP- und MQTT-Guardrails

Die Guardrail-Samples lassen sich in der Security-Seite direkt aus dem GUI importieren.

Wichtig:

- alle Werte sind Platzhalter
- Secrets / Tokens / Passwörter sind bewusst leer oder neutral
- bei Skills mit `ssh_run`, `sftp_read`, `sftp_write` oder `discord_send` müssen die referenzierten Connections vorher existieren
- bei Skills mit `smb_read`, `smb_write` oder `rss_read` muss der entsprechende Build-Stand diese Step-Typen bereits enthalten
