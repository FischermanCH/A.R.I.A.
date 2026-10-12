# ARIA-Hilfe: Sicherheit, Zugangsdaten und Schutzregeln

Stand: 2026-05-12

## Zweck

Diese Seite beschreibt, wie ARIA sensible Werte speichert und wie der aktuelle Alpha-Sicherheitsrahmen funktioniert: Login, Secure Store, CSRF, Guardrails und bestätigungspflichtige Aktionen.

## Was verschlüsselt gespeichert wird

In der Secure-DB (`data/auth/aria_secure.sqlite`) liegen aktuell:

- LLM- und Embedding-API-Keys
- Profil-API-Keys und Tokens für Connections
- Benutzer-Credentials mit Passwort-Hash und Rolle
- weitere Runtime-Secrets, wenn sie vom jeweiligen Modul dort abgelegt werden

Passwörter werden nicht im Klartext gespeichert. Secrets werden AES-256-GCM verschlüsselt.

## Wo der Schlüssel liegt

Der Master-Key liegt in `config/secrets.env`:

- `ARIA_MASTER_KEY`
- `ARIA_AUTH_SIGNING_SECRET`
- `ARIA_FORGET_SIGNING_SECRET`

Empfohlene Rechte: `600`.

Diese Werte dürfen nicht in Git landen. Wenn sie fehlen, erzeugt ARIA persistente Werte beim ersten Start.

## Migration von Klartext nach Secure-DB

```bash
./aria.sh secure-migrate
```

Dabei werden Secrets aus `config/config.yaml` in die Secure-DB übernommen, YAML-Felder geleert und ein Backup geschrieben.

## Login und Sessions

- Login-URL: `/login`
- Session-Cookie: signiert
- Benutzernamen sind case-sensitive
- deaktivierte oder entfernte User verlieren ihre Session sofort
- der erste Bootstrap-User wird Admin, solange Bootstrap nicht gesperrt ist
- Admin-Modus und Rolle sind getrennt: nur Admins können Admin-Funktionen überhaupt nutzen

## CSRF und Browser-Schutz

Zustandsändernde Browser-Requests werden mit CSRF-Token geschützt:

- Cookie: `aria_csrf_token`
- Formulare enthalten das Token automatisch
- Fetch/HTMX sendet `X-CSRF-Token`
- fehlende oder falsche Tokens werden mit `403` abgelehnt

ARIA setzt ausserdem Standard-Security-Header wie CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` und `Permissions-Policy`.

## Guardrails für Aktionen

Der Agentic Action Flow trennt:

1. **Draft**: Was könnte der User meinen?
2. **Policy/Guardrail**: Ist das erlaubt, braucht es Bestätigung oder wird blockiert?
3. **Runtime**: Was wird wirklich ausgeführt?

Mögliche Policy-Ergebnisse:

- `allow` - ausführen
- `ask_user` - im Chat bestätigen lassen
- `block` - nicht ausführen

Beispiele:

- Read-only SSH wie `df -h` oder Healthchecks: kann erlaubt sein
- Service-Restarts: standardmäßig blocken oder explizite Admin-Policy verlangen
- Discord-/Webhook-Sends: bestätigen lassen

## One-Click-Bestätigung

Wenn ARIA eine Aktion nicht direkt ausführen soll, zeigt der Chat einen Button wie **Aktion ausführen**. Das ersetzt unsichere manuelle Token-Abschreiberei im Normalfall. Der alte Bestätigungscode-Pfad kann für Fallbacks weiter existieren, sollte aber nicht der bevorzugte UX-Weg sein.

## Public-Alpha-Grenze

ARIA ist für kontrollierte Umgebungen gedacht:

- LAN/VPN oder Reverse Proxy mit sauberer Auth
- keine Secrets im Image
- keine Secrets in Git
- Volumes für persistente Daten
- Updates über Managed Helper oder bewusste Host-Kommandos

Direkter Public-Internet-Betrieb ohne Zusatzschutz ist für die Alpha nicht empfohlen.

## Backups und Diagnose-Traces

Konfigurations-Backups enthalten standardmäßig weder Secrets noch
Passwort-Hashes. Eine Zugangsdaten-Beilage muss ausdrücklich aktiviert und mit
einer Passphrase verschlüsselt werden. Das Manifest weist aus, was enthalten und
nicht enthalten ist.

Native Diagnose-Traces verwenden standardmäßig die Detailtiefe **minimal** und
werden nach sieben Tagen beziehungsweise beim Größenlimit bereinigt. Der Modus
**vollständig** kann redigierte Prompts, Antworten und Tool-Ausgaben enthalten
und wird deshalb in der Oberfläche deutlich gewarnt.

## Troubleshooting

- `ARIA_MASTER_KEY fehlt`: `config/secrets.env` prüfen und über den vorgesehenen Startpfad starten.
- Neue Keys wirken nicht: `security.enabled`, Secure-DB-Pfad und Neustart prüfen.
- Aktion wird blockiert: Chat-Details lesen, dort stehen Policy und Guardrail-Reason.
- Button bestätigt nicht: Browser/CSRF/Session prüfen und den Chat-Detail-Typ `routed_action_pending` beachten.
