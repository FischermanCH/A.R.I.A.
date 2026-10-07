# ARIA Samples

Diese Sammlung enthaelt kleine Beispiel-Dateien fuer den Alpha-Stand.

## Recipes

Die Dateien unter `samples/recipes/` sind recipe-first JSON-Manifeste fuer den Import unter `/recipes`.

Aktuelle Beispiele:

- `ssh-uptime-all-hosts.json`: Uptime auf allen konfigurierten SSH-Verbindungen lesen
- `ssh-disk-usage-all-hosts.json`: Dateisystembelegung auf allen konfigurierten SSH-Verbindungen lesen
- `ssh-updates-check-all-hosts.json`: Debian-/Ubuntu-Updates auf allen konfigurierten SSH-Verbindungen pruefen

Alle drei Templates sind adaptiv: `connection_kind=ssh` und `binding=all` werden beim Lauf in konkrete konfigurierte Profile expandiert. Sie enthalten keine fixe Demo-Ref.

## Legacy Skill Samples

Unter `samples/skills/` werden keine Legacy-Demo-Rezepte mehr ausgeliefert. Der Loader-Fallback bleibt fuer externe Alt-Pakete kompatibel; shipped Beispiele liegen ausschliesslich unter `samples/recipes/`.

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
- bei den adaptiven `ssh_run`-Beispielen muss mindestens eine SSH-Connection konfiguriert sein
- bei Rezepten mit `smb_read`, `smb_write` oder `rss_read` muss der entsprechende Build-Stand diese Step-Typen bereits enthalten
