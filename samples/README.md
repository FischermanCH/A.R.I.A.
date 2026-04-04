# ARIA Samples

Diese Sammlung enthält kleine Beispiel-Dateien für den ALPHA-Stand.

## Skills

Die Dateien unter `samples/skills/` sind direkte JSON-Manifeste für den Import unter `/skills`.

Aktuelle Beispiele:

- `echo-chat.json`: sicherer Demo-Skill ohne externe Verbindung
- `ssh-healthcheck-template.json`: einfacher SSH-Uptime-/Healthcheck
- `linux-updates-check-template.json`: read-only Linux-Update-Check via SSH
- `sftp-read-template.json`: einfacher Datei-Lesezugriff via SFTP
- `smb-share-list-template.json`: SMB-Share lesen und im Chat zusammenfassen
- `discord-broadcast-template.json`: einfache Discord-Nachricht aus einem Skill senden
- `rss-digest-to-discord-template.json`: RSS laden, per LLM kuratieren und nach Discord senden

## Connections

Die Dateien unter `samples/connections/` sind neutrale Vorlagen. Dafür gibt es aktuell noch keinen direkten UI-Import. Sie dienen als Referenz für:

- manuelles Anlegen über die UI
- spätere Import-/Export-Funktionen
- Dokumentation / Demo-Setups

## Security / Guardrails

Die Dateien unter `samples/security/` zeigen das generische Guardrail-Format.

Wichtig:

- alle Werte sind Platzhalter
- Secrets / Tokens / Passwörter sind bewusst leer oder neutral
- bei Skills mit `ssh_run`, `sftp_read`, `sftp_write` oder `discord_send` müssen die referenzierten Connections vorher existieren
- bei Skills mit `smb_read`, `smb_write` oder `rss_read` muss der entsprechende Build-Stand diese Step-Typen bereits enthalten
