# Security, Secrets und Guardrails

Stand: 2026-05-12

## Zweck

Diese Seite beschreibt, wie ARIA sensible Werte speichert und wie der aktuelle Alpha-Sicherheitsrahmen funktioniert: Login, Secure Store, CSRF, Guardrails und bestaetigungspflichtige Aktionen.

## Was verschluesselt gespeichert wird

In der Secure-DB (`data/auth/aria_secure.sqlite`) liegen aktuell:

- LLM- und Embedding-API-Keys
- Profil-API-Keys und Tokens fuer Connections
- Benutzer-Credentials mit Passwort-Hash und Rolle
- weitere Runtime-Secrets, wenn sie vom jeweiligen Modul dort abgelegt werden

Passwoerter werden nicht im Klartext gespeichert. Secrets werden AES-256-GCM verschluesselt.

## Wo der Schluessel liegt

Der Master-Key liegt in `config/secrets.env`:

- `ARIA_MASTER_KEY`
- `ARIA_AUTH_SIGNING_SECRET`
- `ARIA_FORGET_SIGNING_SECRET`

Empfohlene Rechte: `600`.

Diese Werte duerfen nicht in Git landen. Wenn sie fehlen, erzeugt ARIA persistente Werte beim ersten Start.

## Migration von Klartext nach Secure-DB

```bash
./aria.sh secure-migrate
```

Dabei werden Secrets aus `config/config.yaml` in die Secure-DB uebernommen, YAML-Felder geleert und ein Backup geschrieben.

## Login und Sessions

- Login-URL: `/login`
- Session-Cookie: signiert
- Benutzernamen sind case-sensitive
- deaktivierte oder entfernte User verlieren ihre Session sofort
- der erste Bootstrap-User wird Admin, solange Bootstrap nicht gesperrt ist
- Admin-Modus und Rolle sind getrennt: nur Admins koennen Admin-Funktionen ueberhaupt nutzen

## CSRF und Browser-Schutz

Zustandsaendernde Browser-Requests werden mit CSRF-Token geschuetzt:

- Cookie: `aria_csrf_token`
- Formulare enthalten das Token automatisch
- Fetch/HTMX sendet `X-CSRF-Token`
- fehlende oder falsche Tokens werden mit `403` abgelehnt

ARIA setzt ausserdem Standard-Security-Header wie CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` und `Permissions-Policy`.

## Guardrails fuer Aktionen

Der Agentic Action Flow trennt:

1. **Draft**: Was koennte der User meinen?
2. **Policy/Guardrail**: Ist das erlaubt, braucht es Bestaetigung oder wird blockiert?
3. **Runtime**: Was wird wirklich ausgefuehrt?

Moegliche Policy-Ergebnisse:

- `allow` - ausfuehren
- `ask_user` - im Chat bestaetigen lassen
- `block` - nicht ausfuehren

Beispiele:

- Read-only SSH wie `df -h` oder Healthchecks: kann erlaubt sein
- Service-Restarts: standardmaessig blocken oder explizite Admin-Policy verlangen
- Discord-/Webhook-Sends: bestaetigen lassen

## One-Click-Bestaetigung

Wenn ARIA eine Aktion nicht direkt ausfuehren soll, zeigt der Chat einen Button wie **Aktion ausfuehren**. Das ersetzt unsichere manuelle Token-Abschreiberei im Normalfall. Der alte Bestaetigungscode-Pfad kann fuer Fallbacks weiter existieren, sollte aber nicht der bevorzugte UX-Weg sein.

## Public-Alpha-Grenze

ARIA ist fuer kontrollierte Umgebungen gedacht:

- LAN/VPN oder Reverse Proxy mit sauberer Auth
- keine Secrets im Image
- keine Secrets in Git
- Volumes fuer persistente Daten
- Updates ueber Managed Helper oder bewusste Host-Kommandos

Direkter Public-Internet-Betrieb ohne Zusatzschutz ist fuer die Alpha nicht empfohlen.

## Troubleshooting

- `ARIA_MASTER_KEY fehlt`: `config/secrets.env` pruefen und ueber den vorgesehenen Startpfad starten.
- Neue Keys wirken nicht: `security.enabled`, Secure-DB-Pfad und Neustart pruefen.
- Aktion wird blockiert: Chat-Details lesen, dort stehen Policy und Guardrail-Reason.
- Button bestaetigt nicht: Browser/CSRF/Session pruefen und den Chat-Detail-Typ `routed_action_pending` beachten.
