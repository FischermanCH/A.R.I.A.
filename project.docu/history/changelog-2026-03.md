# ARIA Changelog — 2026-03

## 2026-03-31

### Update Skill Polish
- `server-update-2nodes` liefert jetzt einen zusätzlichen technischen Laufblock:
  - pro Server Status/Exit
  - Dauer
  - Anzahl gehaltener Pakete
  - typische Warnhinweise wie `apt-key/GPG`, `Fetch`, `DNS/Netz`, `dpkg/Lock`
- `SSHRuntime.execute_custom_ssh_command(...)` liefert dafür jetzt strukturiertere Metadaten:
  - `custom_duration_seconds`
  - `custom_timeout_seconds`
  - `custom_warning_hints`
- `ssh_run`-Steps unterstützen jetzt optionale `timeout_seconds`
- `data/skills/server-update-2nodes.json` setzt jetzt `180s` pro SSH-Step, damit der Skill nicht unkontrolliert an der sehr hohen SSH-Connection-Timeout-Grenze hängt
- Neue Tests:
  - Warnhinweis-Erkennung in `SSHRuntime`
  - Formatierung der technischen SSH-Laufzusammenfassung
- Verifikation:
  - `48 passed`
  - `py_compile`: ok
  - ARIA neu gestartet
  - `/health`: ok

### Routing / Fehlerpfade
- Freie Prompt-Kanten im Core weiter gehärtet:
  - `CustomSkill`-Matching berücksichtigt jetzt zusätzlich `skill_id`-Tokens
  - generische Aktionsprompts mit ausreichender Token-Überlappung greifen robuster
- SMB-/NAS-Aliasauflösung verbessert:
  - nummerierte Refs wie `synrs816-01-docker` erzeugen jetzt natürliche Kurz-Aliase wie `synrs816`
  - dadurch funktionieren alltagssprachliche NAS-Prompts auch näher am echten Config-Stil
- Capability-Ausführungen sind jetzt defensiver:
  - Runtime-Fehler werden in der Pipeline abgefangen
  - Nutzer bekommen eine verständliche Capability-Fehlermeldung statt eines unkontrollierten Serverfehlers
  - Chat-Friendly-Errors kennen jetzt auch Capability-Fehler
- Neue Regressionstests:
  - realitätsnaher `server-update-2nodes`-Prompt
  - SMB-Routing mit echtem Ref-Stil `synrs816-01-docker`
  - freundlicher Fehlerpfad bei Capability-Ausnahmen
- Verifikation:
  - `54 passed`
  - `py_compile`: ok
  - ARIA neu gestartet
  - `/health`: ok

### Generic Guardrails
- SSH-spezifische Guardrails in ein generisches Core-Modell überführt:
  - `security.guardrails`
  - neue Profilfelder:
    - `kind`
    - `title`
    - `description`
    - `allow_terms`
    - `deny_terms`
- neue zentrale Guardrail-Schicht:
  - `aria/core/guardrails.py`
  - Katalog für Guardrail-Typen
  - Kompatibilitätsprüfung pro Connection-Typ
  - neutrale Evaluierung via `GuardrailDecision`
- `SSHRuntime` nutzt jetzt die generische Guardrail-Engine statt SSH-Sonderlogik
- zweiter echter Guardrail-Verbraucher ergänzt:
  - `Webhook`
  - `HTTP API`
  - beide über `kind=http_request`
- dritter echter Guardrail-Verbraucher ergänzt:
  - `SFTP`
  - `SMB`
  - beide über `kind=file_access`
- `SFTP`- und `SMB`-Verbindungen können jetzt Guardrail-Profile direkt tragen
- Save-Flow validiert Guardrails jetzt auch dort gegen Typ-Kompatibilität
- `CustomSkillRuntime` erzwingt Datei-Guardrails vor Dateioperationen
  - geprüft werden Operation (`read`, `write`, `list`) und Zielpfad
  - bei Schreiboperationen zusätzlich der Content-Kontext
- `Webhook`- und `HTTP API`-Verbindungen können jetzt Guardrail-Profile direkt tragen
- Save-Flow validiert Guardrails jetzt auch dort gegen Typ-Kompatibilität
- `CustomSkillRuntime` erzwingt HTTP-Guardrails vor dem eigentlichen Request
  - geprüft werden u. a. Methode, Ziel-URL, Pfad und relevante Request-Fragmente
- `/config/security` ist auf das neue Modell migriert:
  - generische Guardrail-Profile
  - Typ-Auswahl im UI
  - Security-Texte neutralisiert
- `SSH`-Connection-Save validiert Guardrails jetzt gegen das generische Modell inkl. Kompatibilitätscheck
- Guardrail-Delete räumt Bindings jetzt neutraler über die vorhandenen Connection-Dictionaries auf
- gezielte Regressionstests ergänzt:
  - `tests/test_guardrails.py`
  - `tests/test_ssh_runtime.py`
  - `tests/test_http_guardrails.py`
  - `tests/test_file_guardrails.py`
- Verifikation:
  - `12 passed`
  - `py_compile`: ok
  - Templates: ok
  - ARIA neu gestartet
  - `/health`: ok

## 2026-03-30

### Schema-Config UI / Connection-Katalog
- erste größere Welle der schema-gerenderten Connection-Formulare fertiggezogen
- gemeinsame Formularbasis jetzt auch auf komplexeren Seiten hybrid eingebunden:
  - `SSH`
  - `SFTP`
  - `SMB`
  - `Discord` (Basisfelder)
- neuer gemeinsamer Partial:
  - `aria/templates/_connection_schema_fields.html`
- der Schema-Renderer unterstützt jetzt zusätzlich:
  - `select`
  - `checkbox`
  - `textarea`
  - Feld-Hinweise
- Spezialblöcke bleiben absichtlich separat:
  - SSH Key-Exchange / Key-Management
  - SFTP-Import aus SSH
  - Discord Alerting & Verhalten
- Discord-Alerting ist intern weiter modularisiert:
  - neue Toggle-Sektionen/Karten werden aus dem Connection-Katalog aufgebaut
  - neuer Partial:
    - `aria/templates/_connection_toggle_sections.html`
- Connection-Katalog ist jetzt stärker an die UI angeschlossen:
  - `config.html` baut die Verbindungsnavigation aus dem Katalog
  - Chat-Toolbox nutzt Katalog-Icons für Connection-Admin-Hilfen
- `Stats` zeigt Connection-Typen jetzt mit Katalog-Metadaten:
  - Icon
  - Alpha-Status
  - konsistente Reihenfolge
- neue Capability-Metadaten-Registry:
  - `aria/core/capability_catalog.py`
  - Badges und Detailzeilen für Capability-Antworten sind jetzt zentraler gepflegt
- Ziel:
  - weniger Copy/Paste in der Config-UI
  - gemeinsame Feldbasis für spätere noch stärker registry-/schema-getriebene Formulargenerierung

### Backlog / RAS
- WireGuard strategisch als eigener späterer Produktblock festgehalten:
  - nicht als normale Connection
  - sondern als eigener Menüpunkt `RAS`
  - Fokus auf sicheren Remote-Zugriff mit möglichst wenig Einrichtungsaufwand
  - OPNsense war nur ein Beispiel für WireGuard-Komplexität; der MVP bleibt standalone und ohne Pflicht-Integration in fremde Firewalls

## 2026-03-28

### RSS / Testsession-Hotfix
- natürlicher RSS-Prompt nachgeschärft:
  - Formulierungen wie `was gibts neues auf heise online news` werden jetzt als `feed_read` erkannt
- Feed-Erkennung weiter gelockert:
  - offene News-/Feed-Fragen mit klarem Betreff wie `was gibts neues bei heise` können jetzt in den RSS-Pfad fallen, wenn RSS-Profile vorhanden sind
- Erkennung von Connection-Refs erweitert:
  - RSS-/Connection-Refs mit `-` oder `_` werden jetzt auch in gesprochener Schreibweise mit Leerzeichen erkannt
  - Beispiel:
    - Profil `heise-online-news`
    - Prompt `heise online news`
- neue semantische RSS-Auflösung ergänzt:
  - `aria/core/connection_semantic_resolver.py`
  - wenn mehrere RSS-Profile vorhanden sind und kein eindeutiger Ref im Prompt steht, kann ARIA per LLM zwischen den Feed-Profilen auswaehlen
  - dabei werden Ref, URL-Host und einfache Aliasformen als Kontext verwendet
- Regressionstests ergänzt:
  - Router-Test für natürliche RSS-Formulierung
  - Pipeline-Test für `feed_read` via `heise-online-news`
  - Pipeline-Test für semantische Feed-Auswahl bei mehreren RSS-Profilen

### Testsession 2026-03-29
- SSH manuell geprüft:
  - Connection-Seite, Speichern, `/stats` und Skill-Status ok
  - offen:
    - `/stats` bei vielen Connections noch etwas träge
    - natürlicher Update-Prompt greift bestehenden SSH-/Update-Skill noch nicht
- Discord manuell geprüft:
  - Connection-Seite, Speichern, `/stats`, Testpost und freier Chat-Prompt ok
- SFTP manuell geprüft:
  - Connection-Seite, Speichern, `/stats` und echter `file_read` ok
  - offener Polishing-Punkt:
    - Connection-Details im Chat für alle Capability-Typen vereinheitlichen
- SMB manuell geprüft:
  - Connection-Seite, Speichern und `/stats` ok
  - Routing-Finding:
    - freier SMB-/NAS-Prompt braucht noch bessere Kontextauflösung
- RSS manuell geprüft:
  - UI-Gruppierung und kompakte Stats-Summary ok
  - natürlicher Heise-Prompt war das gefundene Routing-Finding und ist jetzt nachgearbeitet
- Webhook manuell geprüft:
  - Connection-Seite, Anlegen, Bearbeiten und Auto-Test ok
  - Fehlerfall mit falscher URL liefert verständlichen Verbindungsfehler
  - Chat-E2E gegen das echte Zielsystem (`n8n`) ok
  - Hotfix:
    - Prompts mit explizitem Webhook-Ref wie `schicke per n8n-test-webhook ...` triggern jetzt zuverlässig `webhook_send`
- HTTP API manuell geprüft:
  - Connection-Seite, Speichern und `/stats` ok
  - Chat-E2E gegen echten `n8n`-Health-Endpoint ok
  - Hotfix:
    - ähnliche Refnamen wie `n8n-test-web-api` und `n8n-test-webhook` werden jetzt sauber auseinandergehalten
    - Chat-Fehlerpfad ist gehärtet und stolpert im Exception-Fall nicht mehr über fehlende `result`-Details
### Connections / Runtime-Refactor
- Connection-Test- und Statuslogik zentralisiert in:
  - `aria/core/connection_runtime.py`
- dieselbe Runtime wird jetzt von beiden Seiten genutzt:
  - Connection-Unterseiten unter `Einstellungen > Verbindungen`
  - `/stats`
- bisher doppelte Prüfpfade in `aria/web/config_routes.py` und `aria/web/stats_routes.py` wurden entfernt
- Ziel:
  - weniger Doppelpflege
  - weniger Inkonsistenzen zwischen Config und Stats
  - bessere Grundlage für später auto-generierte bzw. benutzerdefinierte Connection-Typen
- Discord-Probes auf Übersichtsseiten laufen damit jetzt ebenfalls über denselben zentralen Prüfpfad; sichtbare Testposts bleiben auf explizite Save-/Test-Flows beschränkt
- Regressionstest für SFTP-Key-Profile auf der neuen zentralen Runtime nachgezogen
- Hotfix nach dem Refactor:
  - `/stats` lief kurzzeitig auf `500`, weil beim Aufräumen von `aria/web/stats_routes.py` Hilfsfunktionen für Pricing-/Health-Meta mit entfernt wurden
  - fehlende Helper (`_build_pricing_meta`, `_build_health_meta`) wieder sauber eingesetzt
  - `/stats` läuft damit wieder normal

### Navigation / Back-Button
- Zurück-Pfeil in der Topbar nachgeschärft:
  - Browser-Back bleibt erhalten
  - nach dem Zurückspringen wird die Zielseite jetzt einmalig frisch neu geladen
  - damit kommen Unterseiten nicht mehr stale aus dem Browser-Back-Cache zurück
  - wichtig z. B. nach Änderungen an Connection-Profilen, damit Listen/Status sofort konsistent wirken

### Architektur / Planung
- neuer Architekturplan ergänzt:
  - `project.docu/capability-routing-plan.md`
- Zielbild festgehalten:
  - Capability Routing statt reiner Keyword-/Connection-Logik
  - Memory Assist als eigene Auflösungsschicht
  - modulare Executor-Auswahl
  - vorbereitet für spätere UI-generierte Erweiterungen
- Startpfad festgelegt:
  - `file_read`
  - `file_write`
  - `file_list`
  - zuerst über `SFTP`, später `SMB`

### Capability Routing / Phase 1
- neue Kernmodule ergänzt:
  - `aria/core/capability_router.py`
  - `aria/core/memory_assist.py`
  - `aria/core/action_plan.py`
  - `aria/core/executor_registry.py`
- Pipeline additiv erweitert:
  - nur für normale `chat`-Anfragen ohne Custom-Skill-Treffer
  - bestehende Skill-/Connection-/Health-Pfade bleiben unverändert
- erster nutzbarer Capability-Pfad aktiv:
  - `file_read`
  - `file_write`
  - `file_list`
  - jeweils über `SFTP`
- Verbindungsauswahl aktuell in dieser Reihenfolge:
  - explizites SFTP-Profil im Usertext
  - einzig vorhandenes SFTP-Profil
  - Memory-Assist über bestehende Memory-Suche
- Ergebnis wird derzeit deterministisch direkt beantwortet, ohne zusätzlichen LLM-Call
- `CustomSkillRuntime` erweitert um öffentliche SFTP-Helfer:
  - `execute_sftp_read`
  - `execute_sftp_write`
  - `execute_sftp_list`
- neue Pipeline-Tests decken den Capability-Pfad ab:
  - direkter `SFTP`-Write aus Chat
  - Default auf einziges SFTP-Profil
  - Memory-Hinweis bei mehreren SFTP-Profilen

## 2026-03-27

### Access / Admin Mode
- Admin-/Rechtemodell gehaertet und sauber getrennt:
  - `admin` bleibt Rechte-Rolle
  - `Admin-On/Off` ist jetzt klar als Sichtbarkeits-/Power-Modus für Admins zu verstehen
- neue zentrale Zugriffsschicht:
  - `aria/core/access.py`
  - zentrale Regeln für:
    - allgemeine Einstellungen
    - Benutzerverwaltung
    - technische Advanced-Config-Bereiche
- harte Route-Sperren statt nur Menue-Ausblendung:
  - `user` hat keinen Zugriff auf:
    - `/config/llm`
    - `/config/embeddings`
    - `/config/routing`
    - `/config/skill-routing`
    - `/config/security`
    - `/config/files`
    - `/config/logs`
    - `/config/error-interpreter`
  - Admins erreichen diese Bereiche nur mit aktivem Admin-Modus
  - `/config/users` bleibt für Admins immer erreichbar, auch bei deaktiviertem Admin-Modus
- UI an die gleiche Matrix angepasst:
  - `Einstellungen` jetzt für eingeloggte User sichtbar
  - `Benutzer` nur für Admins sichtbar
  - Config-Hub blendet Advanced-Karten aus, wenn Admin-Modus aus ist
  - Sprachdatei-Editor unter `/config/language` wird nur noch im Admin-Modus angezeigt

### Roadmap / Priorisierung
- Roadmap nachgeschaerft:
  - Connections-Ausbau ist der nächste priorisierte Block vor Dokumenten/RAG
  - Reihenfolge festgehalten:
    1. `Discord`
    2. `SFTP / SMB`
    3. `Webhook`
    4. `Email`
    5. `HTTP API`
    6. `RSS`
    7. `MQTT`
- Dokumente/RAG explizit als eigenes Feature markiert:
  - nicht als normaler Skill
  - eigener Ingest-/Chunking-/Collection-Flow

### Connections / Discord
- Discord als erster neuer Connection-Typ aufgebaut:
  - Konfiguration unter `/config/connections`
  - gleicher Grundstil wie bei `SSH`
  - Save-Flow mit automatischem Verbindungstest
  - eigene Live-Statusliste mit rot/gruenen Lampen
- Discord-UX nachgeschaerft:
  - klarerer Hinweis, dass der Webhook zuerst auf Discord angelegt werden muss
  - bestehende Profile sind sichtbarer ladbar/bearbeitbar
  - `403`, `401` und `404` werden beim Discord-Test verständlicher erklärt
  - Root Cause für valide, aber abgewiesene Webhooks gefixt: Discord-POSTs senden jetzt einen expliziten `User-Agent`
- `/stats` nutzt für Discord jetzt denselben gefixten Prüfpfad wie die Config-Seite, damit funktionierende Webhooks dort nicht mehr fälschlich rot bleiben
- Discord-Alerting ausgebaut:
  - Connection-Tests können optional eine nerdige A.R.I.A-Handshake-Nachricht posten
  - alternativ ist eine stille Webhook-Prüfung ohne Testpost möglich
  - pro Discord-Profil kann `discord_send` für Skills explizit erlaubt/gesperrt werden
  - pro Discord-Profil sind jetzt selektive ARIA-Event-Kategorien konfigurierbar:
    - Skill-Fehler
    - Safe-Fix
    - Verbindungsstatus-Änderungen
    - System-Events
  - dafür gibt es einen zentralen Discord-Alert-Helfer unter `aria/core/discord_alerts.py`
- `/stats` Connection-Block textlich generalisiert:
  - zeigt jetzt klar, dass dort alle konfigurierten Verbindungen geprüft werden, nicht nur SSH
- Security:
  - Discord-Webhook-URL wird nicht in `config.yaml` gespeichert
  - Ablage im Secure Store unter `connections.discord.<ref>.webhook_url`
- Runtime:
  - `discord_send` kann jetzt eine `connection_ref` nutzen
  - bestehende direkte `webhook_url`-Steps bleiben kompatibel
- Stats:
  - `/stats` zeigt jetzt SSH- und Discord-Connections gemeinsam im Health-/Connections-Bereich
  - pro Eintrag mit Typ-Hinweis (`SSH`, `Discord`) und `Letzter Erfolg`

### Connections / SFTP
- SFTP als nächster Connection-Typ aufgebaut:
  - Konfiguration unter `/config/connections`
  - gleicher Grundstil wie bei `SSH` und `Discord`
  - Save-Flow mit automatischem Verbindungstest
  - eigene Live-Statusliste mit rot/gruenen Lampen
- SFTP-Ausbau nachgezogen:
  - SFTP kann jetzt mit Passwort **oder** SSH-Key arbeiten
  - bestehende SSH-Profile lassen sich als Vorlage in SFTP uebernehmen
  - dabei werden Host, User, Port und Key-Pfad ins SFTP-Formular kopiert, ohne harte Kopplung der Profile
- Security:
  - SFTP-Passwort wird nicht in `config.yaml` gespeichert
  - Ablage im Secure Store unter `connections.sftp.<ref>.password`
- Runtime / Stats:
  - `/stats` zeigt jetzt SSH-, Discord- und SFTP-Connections gemeinsam im Health-/Connections-Bereich
  - pro Eintrag mit Typ-Hinweis (`SSH`, `Discord`, `SFTP`) und persistentem `Letzter Erfolg`
- Scope:
  - SFTP ist aktiv umgesetzt
  - SMB bleibt als nächster Connection-Unterpunkt offen und folgt später als eigener Schritt
- SFTP-Runtime erweitert:
  - neue Skill-Step-Typen `sftp_read` und `sftp_write`
  - Skill-Wizard unterstützt SFTP-Profil, Remote-Pfad und Schreib-Template
  - erster E2E-Test für `sftp_write -> sftp_read -> chat_send` ergänzt

### Connections / Erweiterte Typen
- weitere Connection-Typen im gleichen Schema wie `SSH` / `Discord` / `SFTP` aufgebaut:
  - `SMB`
  - `Webhook`
  - `Email`
  - `HTTP API`
  - `RSS`
  - `MQTT`

### Connections / Delete-Flow
- einheitlicher Lösch-Flow für alle Connection-Typen ergänzt:
  - `SSH`
  - `Discord`
  - `SFTP`
  - `SMB`
  - `Webhook`
  - `Email`
  - `HTTP API`
  - `RSS`
  - `MQTT`
- Löschen entfernt jetzt konsistent:
  - Config-Eintrag
  - Secure-Store-Secret(s)
  - Connection-Health-Cache
- Sonderfall `SSH`:
  - lokale Key-Dateien bleiben bewusst erhalten und werden nicht automatisch gelöscht
- jede Connection-Art hat jetzt eine eigene fokussierte Unterseite:
  - `/config/connections/smb`
  - `/config/connections/webhook`
  - `/config/connections/email`
  - `/config/connections/http-api`
  - `/config/connections/rss`
  - `/config/connections/mqtt`
- alle neuen Connection-Seiten folgen demselben Muster:
  - Profil speichern
  - Auto-Test direkt nach Save
  - eigener Live-Status-Block mit rot/gruenen Lampen
  - persistenter `Letzter Erfolg`
- Security:
  - Secrets liegen nicht in `config.yaml`
  - Secure-Store-Ablage für:
    - `connections.smb.<ref>.password`
    - `connections.webhook.<ref>.url`
    - `connections.email.<ref>.password`
    - `connections.http_api.<ref>.auth_token`
    - `connections.mqtt.<ref>.password`
- Stats:
  - `/stats` zeigt jetzt auch `SMB`, `Webhook`, `Email`, `HTTP API`, `RSS` und `MQTT` im Connection-/Health-Bereich
  - gleiche Health-Kartenlogik wie auf den Connection-Unterseiten
- Dependencies erweitert:
  - `pysmb`
  - `paho-mqtt`
  - dadurch sind `SMB` und `MQTT` nicht nur konfigurierbar, sondern für die grosse Test-Session lauffähig vorbereitet

### Connections / Modularisierung
- Connections-Config in Hub + Unterseiten zerlegt:
  - `/config/connections/ssh`
  - `/config/connections/discord`
  - `/config/connections/sftp`
- Ziel:
  - jede Connection-Art direkt aus `Einstellungen > Verbindungen` auf eigener, deutlich fokussierter Seite
  - weniger Komplexitaet pro Screen
  - bessere Basis für spätere weitere Connection-Typen und später mögliche Power-User-Erweiterbarkeit
- Save-/Test-/Key-Management-Redirects zeigen jetzt wieder direkt auf die passende Unterseite zurück
- die alte Zwischen-Seite `/config/connections` wurde wieder entfernt, damit keine vergessene Legacy-Navigation liegenbleibt

### UI / Sprache
- deutsche UI-Texte für `Aktivitäten` auf Umlaut-Schreibweise umgestellt:
  - Navigation
  - Activities-Seite
- breiter Text-/i18n-Nachlauf für sichtbare deutsche UI- und Doku-Texte:
  - `ae/oe/ue` in sichtbaren deutschen Texten auf echte Umlaute umgestellt
  - Schweizer Schreibweise beibehalten (`ss` statt `ß`)
  - Connection-Intro auf `Alles für externe Systeme und Zugriffe.` gekürzt

### Stats / Health
- `/stats` um neue sichtbare Health-Sektion erweitert:
  - Kern-Dienste im Überblick:
    - `ARIA Runtime`
    - `Model Stack`
    - `Memory / Qdrant`
    - `Security Store`
    - `Activities / Logs`
  - pro Dienst:
    - Status-Badge (`OK`, `Warnung`, `Fehler`)
    - Kurzbeschreibung
    - technischer Detailhinweis
- Stats-Health ist bewusst leichtgewichtig:
  - Qdrant wird mit kurzem Timeout geprüft
  - verhindert, dass `/stats` bei einem traegen Memory-Backend lange blockiert
- UI konsistent im Stats-Stil erweitert:
  - neue Health-Karten + Status-Pills
  - DE/EN Labels nachgezogen
- Visual-Nachschliff:
  - Status-Pills durch deutlichere Health-Lampen ersetzt
  - neue Gesamtstatus-Karte oben in der Sektion
  - Health-Karten visuell ruhiger und klarer gestaltet
- SSH-Verbindungen jetzt auch auf `/stats` sichtbar:
  - eigener Block direkt unterhalb von `Health`
  - nutzt denselben Kartenstil wie `/config/connections`
  - zeigt rote/gruene Lampen, Zielhost und Detailmeldung für alle konfigurierten SSH-Profile
  - Probe-Timeouts bleiben kurz, damit die Stats-Seite nicht unnötig blockiert
- letzter erfolgreicher Verbindungscheck jetzt persistent:
  - file-basiert unter `data/runtime/connection_health.json`
  - wird auf `/config/connections` und `/stats` pro Profil als `Letzter Erfolg` angezeigt
  - bleibt erhalten, auch wenn der aktuelle Check gerade fehlschlaegt
- Verifikation:
  - JSON Language-Files valide
  - `py_compile`: OK (`aria/web/stats_routes.py`)
  - Vollsuite: `37 passed`

### Skills / Rename
- Skill-ID-Änderung im Wizard als echter Rename-Flow gehaertet:
  - alte Skill-Datei wird beim ID-Wechsel entfernt statt als zweite Skill-Datei liegenzubleiben
  - `skills.custom.<alte_id>` in `config.yaml` wird auf die neue ID migriert
  - Default-`prompt_file` (`prompts/skills/<id>.md`) wird bei passender Konstellation mit umbenannt
- Hintergrund:
  - vorher war eine ID-Änderung faktisch eher ein "neuen Skill anlegen" als ein echtes Umbenennen
  - dadurch konnten Alt-Datei, Alt-Trigger und verwaiste Config-Eintraege parallel bestehen bleiben
- Verifikation:
  - neue Regressionstests für Skill-Rename + Config-Migration

### Skills / Routing
- Skill-Status-Routing nachgeschaerft:
  - natuerliche Formulierungen wie `Was sind deine aktuellen Skills?` werden jetzt ebenfalls sicher als `skill_status` erkannt
  - dadurch liefert ARIA für diese Fragen wieder deterministisch die installierten/aktiven Skills aus der Runtime statt generischer LLM-Freitext-Antworten
- Verifikation:
  - `tests/test_router.py` + `tests/test_pipeline.py` -> `21 passed`

### Memories / UI
- Statistik-/Health-Block aufgeraeumt:
  - der Block mit `Memory-Punkte`, Typ-Verteilung, grösster Collection, Komprimierungsstatus und `Empty-Cleanup` wurde von `/memories` nach `/memories/map` verschoben
  - `/memories` ist dadurch stärker auf Suche, Filter, Liste und Bearbeiten fokussiert
  - `/memories/map` kombiniert nun Visualisierung + Gesundheits-/Maintenance-Überblick an einem Ort
- kleine UX-Nachbesserungen:
  - Memory-Zeitstempel zeigen Leerzeichen statt `T` zwischen Datum und Uhrzeit
  - globaler Zurück-Pfeil in der Topbar für schnellere Navigation zwischen Unterseiten
  - Zurück-Pfeil nachgeschliffen:
    - weiter nach unten unter den User-Bereich gesetzt
    - sichtbareres Gruen (`#00ff00`)
    - leicht vergrössert
    - auf der Chat-Startseite bewusst ausgeblendet
  - Username als Menuepunkt durch `Mehr` ersetzt
  - Username/Rolle nur noch klein im Dropdown sichtbar
  - `ADMIN` im Dropdown nur noch sichtbar, wenn der Admin-Modus aktiv ist
  - `Config` im Menue sprachlich zu `Einstellungen` / `Settings` umbenannt

### Chat / Verlauf
- letzter Chat ist jetzt browserübergreifend pro User verfügbar:
  - einfacher file-basierter Store unter `data/chat_history/`
  - keine zusätzliche SQLite-/DB-Schicht
  - Chat-Seite lädt den letzten Verlauf direkt vom Server
  - nach jeder erfolgreichen Chat-Antwort wird der Verlauf serverseitig aktualisiert
- `cls` / `/cls` / `clear` / `/clear` löschen jetzt nicht mehr nur lokalen Browserzustand, sondern auch die serverseitige Chat-History für diesen User
- Draft bleibt bewusst lokal im Browser, damit angefangene Eingaben weiter leichtgewichtig bleiben
- Verifikation:
  - `py_compile`: OK (`aria/main.py`, `aria/core/chat_history.py`)
  - Tests: `tests/test_chat_history.py` + `tests/test_pipeline.py` -> `13 passed`

### Config / Connections
- `/config/connections` auf Auto-Test-Flow umgestellt:
  - Speichern eines SSH-Profils fuehrt jetzt automatisch einen Verbindungstest aus
  - kein manueller Test-Schritt mehr nötig, um direktes Feedback zu bekommen
  - bei Erfolg: gruene Rückmeldung
  - bei Fehler: rote Rückmeldung plus Fehlermeldung
- neue Live-Statusliste für alle SSH-Profile:
  - Seite prüft beim Aufruf alle vorhandenen SSH-Verbindungen mit kurzem Probe-Timeout
  - jedes Profil zeigt jetzt roten/gruenen Statuspunkt, Zielhost und Detailmeldung
  - aktuell ausgewähltes Profil wird in der Liste zusätzlich markiert
- UI-Texte und Flow angepasst:
  - Empfehlungen und Hilfetexte sprechen jetzt von automatischem Test statt manuellem Klick
  - Statuszusammenfassung zeigt `Profiles`, `Healthy`, `Issues`, `Active`
  - Live-Status sitzt jetzt als eigener optischer Block unterhalb der Summary
  - die Summary wurde auf vier Karten reduziert; die separate `Active`-Box wurde entfernt

- `/config/connections` UX-seitig neu strukturiert:
  - kompakter Status-/Profil-Überblick oben
  - Profil laden und Verbindung testen als klarer Einstieg
  - Profil + Key-Exchange als eigentlicher Hauptflow
  - manuelle Key-Tools nur noch als Fallback darunter
- doppelten `Test connection`-Button im Save-Form entfernt, damit kein falsches/alt geladenes Profil getestet wird
- restliche Feldlabels auf der Seite i18n-konsistent gemacht
- Verbindungstest-Feedback im UI sichtbarer:
  - gruene Status-Karte bei Erfolg
  - rote Status-Karte bei Fehler
  - technischer Detailtext direkt darunter
- Responsive Layout für die neue Übersicht nachgezogen
- Verifikation:
  - Jinja-Template kompiliert
  - DE/EN Language-Files valide
  - Neustart + `/health`: OK

## 2026-03-26

### Projektstruktur / Umbau
- Neuer schrittweiser Architektur-Refactor-Plan angelegt:
  - `project.docu/umbau-plan.md`
  - Ziel: `main.py` und `pipeline.py` kontrolliert modularisieren, ohne bestehende Funktionalitaet zu brechen
  - Umbau wird explizit inkrementell dokumentiert und pro Phase validiert
- Phase 1 gestartet:
  - Backup erstellt: `/home/fischerman/ARIA_backup_2026-03-26`
  - Skill-Manifest- und Trigger-Index-Logik aus `main.py` in neues Modul `aria/core/custom_skills.py` verschoben
  - `main.py` damit erstmals sichtbar entlastet, ohne Skill-Verhalten zu ändern
  - Verifikation: `37 passed`, Neustart + `/health` erfolgreich
- Phase 2 abgeschlossen:
  - neue Route-Module:
    - `aria/web/stats_routes.py`
    - `aria/web/activities_routes.py`
  - `/stats` und `/activities` aus `aria/main.py` in eigene Registrierer ausgelagert
  - `main.py` dient für diese Seiten jetzt nur noch als Registrierungsort
  - Verifikation:
    - `py_compile`: OK
    - `pytest`: `37 passed`
    - Neustart + `/health`: OK
    - `/stats` und `/activities` redirecten im nicht eingeloggten Zustand weiterhin korrekt auf `/login`
- Phase 3 abgeschlossen:
  - neues Route-Modul:
    - `aria/web/skills_routes.py`
  - `/skills`, `/skills/save`, `/skills/wizard`, `/skills/wizard/save`, `/skills/import` und `/skills/export/{skill_id}` aus `aria/main.py` ausgelagert
  - `main.py` dient für die Skills-Seiten jetzt nur noch als Registrierungsort
  - Runtime-Schutz nachgezogen:
    - ausgelagerte Route-Module beziehen `settings`/`pipeline` über Getter, damit `reload_runtime()` keine stale Referenzen hinterlaesst
  - Verifikation:
    - `py_compile`: OK
    - `pytest`: `37 passed`
    - Neustart + `/health`: OK
    - `/skills` und `/skills/wizard` redirecten im nicht eingeloggten Zustand weiterhin korrekt auf `/login`
- Phase 4 abgeschlossen:
  - neue Runtime-Module:
    - `aria/core/safe_fix.py`
    - `aria/core/ssh_runtime.py`
    - `aria/core/skill_runtime.py`
  - Safe-Fix, SSH-Command-Ausführung und Custom-Skill-Runtime aus `aria/core/pipeline.py` ausgelagert
  - `Pipeline` delegiert diese Bereiche jetzt an die neuen Module; `process()` bleibt Orchestrator
  - interne Pipeline-Methoden bleiben als schmale Wrapper erhalten, damit Tests und bestehende Aufrufer stabil bleiben
  - Verifikation:
    - `py_compile`: OK
    - `pytest`: `37 passed`
    - Neustart + `/health`: OK
    - Login-Redirects für `/skills` und `/activities` weiterhin korrekt
  - manueller Runtime-Check:
    - Skill-Status-Intent antwortet korrekt und sehr schnell
    - Upgrade-Skill für beide `ubnsrv`-Server läuft erfolgreich
    - Hold-Detection + Safe-Fix-Vorschlag erscheinen korrekt
- Phase 5 abgeschlossen:
  - neues Route-Modul:
    - `aria/web/memories_routes.py`
  - `/memories`, `/memories/map`, `/memories/delete`, `/memories/edit`, `/memories/maintenance`, `/memories/config` und Alias `/config/memory` aus `aria/main.py` ausgelagert
  - `main.py` registriert die Memory-Seiten jetzt nur noch über `register_memories_routes(...)`
  - Getter-/Callback-Muster wie bei `skills` übernommen, damit `reload_runtime()` weiterhin aktuelle `settings`/`pipeline` nutzt
  - Verifikation:
    - `py_compile`: OK
    - `pytest`: `37 passed`
    - Neustart + `/health`: OK
    - Login-Redirects für `/memories`, `/memories/map`, `/memories/config` und `/config/memory` korrekt
- Phase 6 abgeschlossen:
  - neues Route-Modul:
    - `aria/web/config_routes.py`
  - Config-Seiten aus `aria/main.py` ausgelagert:
    - `/config`
    - `/config/language`
    - `/config/debug`
    - `/config/security`
    - `/config/logs`
    - `/config/connections`
    - `/config/users`
    - `/config/prompts`
    - `/config/routing`
    - `/config/skill-routing`
    - `/config/llm`
    - `/config/embeddings`
    - `/config/files`
    - `/config/error-interpreter`
  - `main.py` registriert die Config-Seiten jetzt nur noch über `register_config_routes(...)`
  - Getter-/Proxy-Muster auch für `config` umgesetzt, damit `reload_runtime()` aktuelle `settings`/`pipeline` beibehaelt
  - Verifikation:
    - `py_compile`: OK
    - `tests/test_router.py`: `8 passed`
    - `tests/test_memory.py`: `4 passed`
    - `tests/test_error_handling.py`: `4 passed`
    - Neustart + `/health`: OK
    - Route-Registry: `50` `/config*`-Routen vorhanden
  - nachtraeglicher Follow-up-Fix:
    - der späte `tests/test_pipeline.py`-Haenger wurde isoliert und behoben
    - Ursache:
      - `CustomSkillRuntime` hielt nach Phase 4 noch eine stale `memory_skill`-Referenz fest
      - wenn `pipeline.memory_skill` später ersetzt wurde, lief die Runtime intern weiter mit der alten Instanz
    - Loesung:
      - `CustomSkillRuntime` nutzt jetzt einen Getter auf `pipeline.memory_skill`
      - damit bleiben Tests und Runtime auch nach späteren Austausch-/Mocking-Schritten konsistent
    - Verifikation:
      - gezielter Regressionstest: `1 passed`
      - `tests/test_pipeline.py`: `11 passed`
      - Vollsuite: `37 passed`

### Memory Rollup UX
- Rollup-/Komprimierungsfeedback auf `/memories/config` verbessert:
  - Button-Text praezisiert (`Rollup jetzt starten`)
  - direkter Hinweis ergänzt, dass nur Tages-Kontext-Collections oberhalb des Alters-Grenzwerts verarbeitet werden
  - Redirect springt nach manueller Ausführung direkt zur Rollup-Sektion (`#rollup`)
  - Ergebnistext nennt jetzt nicht nur Zähler, sondern auch verschobene/entfernte bzw. bewusst unveränderte Collections
- `MemorySkill.compress_old_sessions(...)` liefert dafür erweiterte Rückgabedaten:
  - `compressed_collections`
  - `removed_collections`
  - `skipped_recent`
  - `skipped_empty`
  - `failed_delete`
- Verifikation:
  - `py_compile`: OK (`aria/web/memories_routes.py`, `aria/skills/memory.py`)
  - gezielter Test: `tests/test_memory_compression.py` -> `3 passed`
  - Neustart + `/health`: OK

### Security / Publish Hardening
- Secret- und ENV-Auflösung zentralisiert:
  - direkte `os.getenv`/`os.environ`-Zugriffe aus `aria/main.py`, `aria/core/user_admin.py` und `aria/core/secure_migrate.py` entfernt
  - zentrale Helper in `aria/core/config.py` für:
    - `read_secrets_env`
    - `get_secret_value`
    - `ensure_secret_value`
    - `get_master_key`
    - `get_or_create_runtime_secret`
- Runtime-Signing-Secrets für Web-Sessions/Forget-Flow gehaertet:
  - `ARIA_AUTH_SIGNING_SECRET`
  - `ARIA_FORGET_SIGNING_SECRET`
  - wenn nicht gesetzt, erzeugt ARIA beim ersten Start persistente Werte in `config/secrets.env`
  - dadurch keine hartcodierten oder ad-hoc prozesslokalen Fallback-Secrets mehr
- Repo-/Container-Publish-Workflow gestrafft:
  - `.gitignore` erweitert für lokale Laufzeitdateien:
    - `config/config.yaml`
    - `config/*.bak.*`
    - `config/secrets.env`
    - `data/auth/`
    - `data/logs/`
    - `data/skills/`
  - neue Vorlage `config/secrets.env.example`
  - README um Publish-Safety / Beispiel-Dateien / lokales Runtime-Setup erweitert
- Container-Ready-Grundlage hinzugefuegt:
  - neue Dateien:
    - `Dockerfile`
    - `.dockerignore`
    - `docker/entrypoint.sh`
    - `docker-compose.yml`
  - Container erwartet lokale Runtime-Volumes für `config`, `prompts`, `data`
  - `config/secrets.env` wird im Entry-Point geladen
  - falls `config/config.yaml` fehlt, wird automatisch `config/config.example.yaml` kopiert
  - Healthcheck auf `/health` integriert
  - Container-Build und Container-Health lokal verifiziert
  - `numpy<2` explizit in `pyproject.toml` gepinnt, damit Qdrant/Numpy im Container auch auf älterer CPU-Hardware sauber startet
- Auto-Memory für operative Skill-Trigger geschaerft:
  - Prompts, die einen Custom Skill oder `skill_status` ausloesen, werden nicht mehr als `auto_session` in Tages-Collections geschrieben
  - verhindert semantisches Memory-Rauschen wie `systemupdate mgmt-master`
  - explizite Memory-Befehle (`memory_store`) bleiben davon unberuehrt
- Memory-Maintenance bereinigt jetzt auch bestehende operative Alt-Eintraege aus Session-Collections
  - Cleanup basiert auf bekannten Skill-Triggern und Skill-Status-Phrasen
- Neue Seite `/activities` eingefuehrt:
  - operative Skill-Läufe, Memory-Aktionen und Systemaktionen werden aus dem Token-Log als getrennte Aktivitaetenansicht dargestellt
  - bewusst getrennt vom semantischen Memory
  - Fehlerdetails pro Aktivitaet aufklappbar
  - UI-Filter für `Alle`, `Skills`, `Memory`, `System` ergänzt
  - Status-Filter für `Alle`, `OK`, `Fehler` ergänzt
- Skill-Wizard Bugfix:
  - Skill-Namen bleiben beim Speichern/Editieren erhalten
  - ein Variablen-Konflikt im Manifest-Validator hat vorher den Namen durch eine abgeleitete Connection (`llm`, `ssh`, `chat`) ersetzt
  - Regression-Test hinzugefuegt
- Interne Code-Haertung nach Variablen-Audit:
  - im Skill-/SSH-Pfad wurden mehrdeutige lokale Variablennamen bereinigt (`connection_ref`, Paketnamen), um stille Überschreibungen künftig unwahrscheinlicher zu machen
- Activities-Ansicht und Navigation für DE/EN ergänzt.
- Token-Tracker-Test für Aktivitaeten-Auswertung hinzugefuegt.
- Log-Retention eingefuehrt:
  - neues Feld `token_tracking.retention_days` (Default: 30)
  - Startup-Maintenance und `./aria.sh maintenance` prune alte Eintraege aus `data/logs/tokens.jsonl`
  - neue Admin-Seite `/config/logs` für Status, Retention und manuellen Cleanup
  - eigener Test für Log-Pruning hinzugefuegt
  - Token-Tracker intern vereinfacht:
    - gemeinsame JSONL-/Timestamp-Helfer statt mehrfacher Copy/Paste-Logik
    - Activity-Filterlogik zentral in `TokenTracker`
    - `get_log_health` bestimmt ältesten/neuesten Eintrag jetzt robust per Zeitwert statt nur per Dateireihenfolge

## 2026-03-25

### Skills / SSH Runtime
- SSH-Timeout-Verhalten in der Step-Runtime verbessert (`aria/core/pipeline.py`):
  - `connections.ssh.<ref>.timeout_seconds` steuert weiterhin die maximal erlaubte Command-Laufzeit.
  - Der SSH-`ConnectTimeout` wird jetzt getrennt und kurz gehalten (max. 20s), damit Down-Hosts schnell fehlschlagen.
  - Ergebnis: lange Jobs wie `apt update/upgrade` können laufen, ohne dass Verbindungsfehler unnötig lange blockieren.
- 2-Node-Update-Skill für laengere Wartungsjobs vorbereitet:
  - in `config/config.yaml` für `ubnsrv-mgmt-master` und `ubnsrv-netalert` auf `timeout_seconds: 1800` angehoben.
- Universelle APT-Hold-Detection in der Skill-Runtime:
  - gilt für alle Custom Skills mit `ssh_run` (nicht nur Server-Update-Skill)
  - erkennt zurückgehaltene Pakete aus SSH-Output (`kept back`)
  - aggregiert Treffer pro Connection/Host
  - fuegt automatische Safe-Fix-Empfehlung hinzu:
    - `sudo apt install --only-upgrade <pakete>`
  - bei direkter Chat-Antwort (`chat_send`) wird die Hold-Zusammenfassung automatisch an den Skill-Output angehängt
- Safe-Fix Confirm-Flow:
    - bei erkanntem Hold erstellt ARIA einen bestätigungspflichtigen Fix-Plan (Cookie-basiert, user-gebunden, signiert)
    - Ausführung erst nach explizitem Chat-Command:
    - `bestätige fix <token>` (alternativ `confirm fix <token>`)
    - verhindert unbestätigte, automatische apt-Upgrade-Schritte
- Fehler-Dolmetscher eingefuehrt:
  - neues Modul `aria/core/error_interpreter.py`
  - interpretiert SSH-/apt-/sudo-/Netzwerkfehler über YAML-Regeln statt über eine harte Fehlerliste im Code
  - neue Regeldatei: `config/error_interpreter.yaml`
  - neue Config-Seite: `/config/error-interpreter`
  - Safe-Fix-Fehler zeigen jetzt zusätzlich menschlichere Ursache- und Next-Step-Texte
- Skill-Status-Intent umgesetzt (deterministisch, ohne LLM):
  - neuer Router-Intent `skill_status` für Fragen wie `welche skills sind aktiv?`
  - Pipeline antwortet direkt aus Runtime-Daten (Core + Custom Skills, inkl. Status/Zweck/Connections)
  - verhindert generische/halluzinierte Skill-Antworten
  - Chat-Badge für diesen Pfad: `🧩 skill_status`
  - Erkennung erweitert für natuerliche Formulierungen wie `was für skills hast du aktiv?`
- Chat-UI erweitert:
  - lokaler Chat-Reset per Nerd-Commands im Eingabefeld:
    - `cls`, `/cls`, `clear`, `/clear`
  - löscht lokalen Chatverlauf + Draft aus Browser-`localStorage`
  - Memory/Qdrant bleibt unverändert
  - Chat-Reset-Button wurde wieder entfernt (cleaneres UI)
  - neues Slash-Menue wie bei Discord:
    - bei Eingabe von `/` erscheinen Chat-Tools als Auswahlliste
    - enthält `cls/clear` plus Toolbox-Aktionen für `Lesen`/`Merken`
    - enthält jetzt auch `/skill` Vorschlaege aus den vorhandenen Skill-Triggern (automatisch generiert)
    - gruppiert nach `Commands`, `Memory lesen`, `Memory speichern`
    - mit Icons für schnellere Orientierung
  - sichtbares Laufzeit-Feedback bei Chat-Requests:
    - waehrend der Verarbeitung wird eine temporaere Assistant-Statusnachricht eingeblendet
    - bei erkanntem Skill-Trigger: `Skill wird ausgefuehrt...`
    - sonst: `Nachricht wird verarbeitet...`
    - Status verschwindet automatisch, sobald die echte Antwort vorliegt

### Skills Wizard
- Neuer Step-Typ `chat_send` eingefuehrt:
  - interne Default-Connection `chat` (kein Setup nötig)
  - Message-Template wird direkt als Chat-Antwort genutzt
  - kein zusätzlicher LLM-Rewrite für reine Custom-Skill-Chatantworten
- Wizard erweitert:
  - Typ-Auswahl enthält `chat_send`
  - Feld `Chat Message Template (für chat_send)` hinzugefuegt
  - Hinweistext im Wizard erklaert die interne `chat`-Connection

### Internationalisierung (MVP Fundament)
- Neues i18n-System eingefuehrt:
  - Language-Files unter `aria/i18n/de.json` und `aria/i18n/en.json`
  - neuer Loader `aria/core/i18n.py` mit Fallback-Logik (`de` als Default)
  - Sprachwahl via `?lang=de|en` + Persistenz im Cookie `aria_lang`
  - konfigurierbare Standardsprache via `ui.language` (ENV: `ARIA_UI_LANGUAGE`)
- Template-Integration:
  - globaler Translator `tr(request, key, default)` in Jinja
  - Basis-Navigation (`base.html`) auf i18n umgestellt inkl. DE/EN-Umschalter
  - `login.html` auf i18n umgestellt
  - `chat.html` auf i18n umgestellt (Labels + JS-UI-Texte inkl. Slash-Menue-Gruppen)
- Architektur bleibt erweiterbar:
  - neue Sprache = neues JSON-File in `aria/i18n/`
- Sprachsteuerung erweitert:
  - Flaggen-Dropdown statt Text-Links (automatisch aus vorhandenen Language-Files)
  - sichtbar in der Topbar und explizit auf der Login-Seite
  - neue Config-Seite `/config/language`:
    - Standardsprache setzen (`ui.language`)
    - optionaler Sprachdatei-Editor unter `Erweitert`
- i18n-Audit nachgezogen:
  - verbleibende harte DE-Texte in `base/chat/login/config_language` auf `tr(...)` umgestellt
  - Debug-Header im Chat ebenfalls sprachfähig (Day Context / Login Session / Role etc.)
- i18n-Welle 2 umgesetzt:
  - `/memories` und `/skills` auf `tr(...)` umgestellt (Labels, Buttons, Filter, Status-/Hilfstexte)
  - neue i18n-Keys unter `memories.*` und `skills.*` in `de.json` + `en.json`
  - Core-Skill-Beschreibungen (`Memory`, `Auto-Memory`) sind jetzt sprachabhängig
  - bekannte Default-Custom-Beschreibung für `Server Update (2 Nodes)` bekommt EN-Fallback im UI
- i18n-Welle 3 umgesetzt:
  - `/memories/config` vollständig auf `tr(...)` umgestellt
  - neue Keygruppe `config_memory.*` in `aria/i18n/de.json` und `aria/i18n/en.json`
  - statische DE-Texte auf der Memory-Config-Seite entfernt
- i18n-Welle 4 umgesetzt:
  - `/config` (Config-Hub) vollständig auf `tr(...)` umgestellt
  - neue Keygruppe `config.*` in `aria/i18n/de.json` und `aria/i18n/en.json`
  - statische DE-Texte auf der Config-Übersichtsseite entfernt
- i18n-Welle 5 umgesetzt:
  - folgende Seiten vollständig auf `tr(...)` umgestellt:
    - `/config/llm`
    - `/config/embeddings`
    - `/config/routing`
    - `/config/prompts`
    - `/config/connections`
    - `/config/security`
    - `/config/files`
    - `/config/users`
    - `/stats`
  - neue Keygruppen ergänzt: `config_llm.*`, `config_embed.*`, `config_routing.*`, `config_prompts.*`, `config_conn.*`, `config_security.*`, `config_files.*`, `config_users.*`, `stats.*`
  - Model-Loader-JS-Texte in LLM/Embeddings ebenfalls i18n-fähig gemacht
- Chat Slash-Menü i18n erweitert:
  - sprachabhängige Slash-Labels für Memory-Aktionen:
    - DE: `/lesen`, `/merken`
    - EN: `/read`, `/store`
  - umgesetzt über neue Keys `chat.slash_read_cmd` und `chat.slash_store_cmd`
- Mehrsprachiges Routing umgesetzt:
  - `routing` unterstützt jetzt Sprach-Scope mit Fallback:
    - `routing.default` = Basis-Regeln
    - `routing.languages.<lang>` = sprachspezifische Overrides
  - effektives Routing wird pro Request nach aktiver UI-Sprache geladen
  - Router + Store/Recall-Text-Extraktion nutzen das sprachspezifische Profil
  - Routing-Config-UI (`/config/routing`) erweitert:
    - Scope-Auswahl (`default`, `de`, `en`, weitere Sprachdateien automatisch)
    - Speichern schreibt in den gewählten Scope
- Memory-Rollup / Maintenance verbessert:
  - Legacy-Session-Collections im Format `aria_memory_<user>_session_<id>` werden bei der Komprimierung jetzt ebenfalls berücksichtigt
  - Altersermittlung für Legacy-Collections erfolgt über Payload-Timestamps (statt Namensdatum)
  - CLI-Maintenance nutzt jetzt `monthly_after_days` aus `config.yaml` (vorher fest auf 30)
- Custom-Skill `server-update-2nodes` verbessert:
  - Router-Keywords erweitert (u. a. `update der zwei server`, `update die zwei server`)
  - Zusammenfassungs-Step verwendet jetzt beide Server-Outputs (`{s1_output}` + `{s2_output}`) statt nur den letzten Step
- Skill-Routing erweitert:
  - neue Admin-Seite `/config/skill-routing`:
    - zentrale Trigger-Übersicht über alle Custom Skills
    - Trigger pro Skill direkt editierbar
    - Trigger-Index-Vorschau inkl. Kollisionen
    - manueller Rebuild-Button
  - Trigger-Index als Datei: `data/skills/_trigger_index.json` (auto-generiert)
  - Skill-Loader ignorieren interne JSON-Dateien mit Prefix `_` (z. B. Trigger-Index)
- Skill-Wizard erweitert:
  - zusätzliche editierbare Manifest-Felder:
    - `connections`
    - `prompt_file`
    - `schema_version`
  - `connections` aus Wizard werden mit step-abgeleiteten Connections zusammengeführt
  - Trigger-Automation ergänzt:
    - im Wizard kann `router_keywords` bei leerem Feld automatisch über das aktive Chat-LLM erzeugt werden
    - neue Option im Wizard: automatische Trigger-Generierung (default an)
  - Skill-Routing-UI erweitert:
    - pro Skill Button `Keywords via LLM vorschlagen`
    - globaler Button `Keywords für alle Skills via LLM vorschlagen`
    - Routen: `POST /config/skill-routing/suggest` und `POST /config/skill-routing/suggest-all`
  - UX-Verbesserung für LLM-Triggervorschlaege:
    - interne Info-Codes wie `suggest-all:1:12` werden im UI in lesbare Texte umgewandelt
    - gilt für `/config/skill-routing` und Wizard-Save-Infos

## 2026-03-24

### Skills (MVP 1)
- Skill-Manifeste eingefuehrt als JSON-Quelle der Wahrheit:
  - Speicherort: `data/skills/*.json`
  - Validierung + Normalisierung beim Laden/Speichern
- Skills-UI dynamisch erweitert:
  - Core Skills + Custom Skills werden gemeinsam angezeigt
  - Custom Skills erscheinen automatisch im Menu `Skills`
  - Aktiv/aus-Status für Custom Skills wird in `config.yaml` unter `skills.custom.<id>.enabled` gespeichert
  - Platzhalter-Core-Skills `Websuche`, `Dokumente`, `Home` aus der festen Liste entfernt (künftig via Skill-Editor)
- Skill Wizard eingefuehrt:
  - Seite: `/skills/wizard`
  - Felder für ID, Name, Version, Kategorie, Beschreibung, Prompt-Datei, Keywords, Connections, UI-Link/Hinweis
  - dient für Erstellen und Bearbeiten
- Import/Export:
  - Import: `POST /skills/import` (JSON)
  - Export: `GET /skills/export/{skill_id}` (JSON-Download)
- Runtime MVP erweitert:
  - Custom-Skills werden in der Pipeline geladen und per Router-Keywords erkannt
  - erkannte Skills erzeugen als `llm_task` Skill-Kontext (ohne zusätzlichen LLM-Call)
  - Intents enthalten jetzt auch `custom_skill:<id>` bei Treffer
- `ssh_command` Execution MVP hinzugefuegt:
  - `execution.type: ssh_command`
  - `execution.connection_ref` verweist auf `connections.ssh.<name>` aus `config.yaml`
  - `execution.command` unterstützt `{query}` Platzhalter
  - Guardrails aktiv: Allowlist, Timeout, Host-Key-Checking, Output-Truncation
- Neue Verbindungsseite in der Config:
  - Route: `/config/connections`
  - SSH-Verbindungsprofile im UI speichern (Host, Port, User, Key-Pfad, Timeout, Host-Key-Mode, Allowlist)
  - Key-Management im UI:
    - ED25519-Keypair erzeugen (`data/ssh_keys/<ref>_ed25519`)
    - optionales Overwrite
    - Public-Key direkt im UI anzeigen
  - Config-Menue unter `Werkbank (Advanced)` um `Verbindungen (SSH)` erweitert
  - Key-Exchange-Flow hinzugefuegt:
  - Route: `POST /config/connections/key-exchange`
  - einmaliger Passwort-Login auf Zielhost und automatisches Schreiben des Public Keys in `~/.ssh/authorized_keys`
  - Passwort wird nicht persistiert
  - UX-Update: Key-Exchange als Default direkt in `POST /config/connections/save` integriert (Checkbox standardmaessig aktiv)
  - UX-Update: Verbindungstest hinzugefuegt:
    - Route: `POST /config/connections/test`
    - testet key-basierten SSH-Login und zeigt klare Erfolg-/Fehlermeldung
    - Status-Badges für private/public Key-Verfügbarkeit auf der Seite
- Wizard-Felder erweitert:
  - `execution.type` (aktuell `llm_task`)
  - `execution.instruction` (freie Anweisung für Skill-Output)
- Wizard UX überarbeitet (guided input):
  - Skill-ID optional (auto aus Name), weiterhin editierbar
  - Kategorien als Dropdown (Default + bestehende Kategorien)
  - Prompt-Datei nur noch als Read-only Summary (auto)
  - Execution-Typ gefuehrt auswählbar (`llm_task`, `ssh_command`)
  - Connections als gefuehrte Presets + optionales Zusatzfeld
  - Inline-Hilfe (`i`) an Eingabefeldern für spätere Live-Help vorbereitet
  - optionale Felder (`UI-Konfig-Link`, `UI-Hinweis`) unter „Erweitert“
  - SSH-spezifische Felder: Connection-Ref (Dropdown) + Command-Template
- Neuer Step-Builder (MVP):
  - dynamische Anzahl Schritte pro Skill im Wizard (Hinzufügen/Entfernen im UI)
  - Step-Typen: `ssh_run`, `llm_transform`, `discord_send`
  - pro Step eigene Parameter und `on_error` Verhalten
  - `steps[]` wird in Skill-JSON gespeichert (Schema 1.1)
  - Runtime fuehrt Step-Ketten sequentiell aus
  - Legacy-`execution` wurde entfernt; `steps[]` ist Pflicht
  - Connection-Auswahl nur noch im jeweiligen Step (kein separater Connections-Block mehr)
  - Direktlink im Step auf `/config/connections`
  - Skill-Scheduling (MVP, Konfig-Ebene) ergänzt:
    - `schedule.enabled`
    - `schedule.cron` (intern)
    - `schedule.timezone`
    - `schedule.run_on_startup`
  - Wizard-UX für Zeitplan vereinfacht:
    - User gibt Uhrzeit im 24h-Format (`HH:MM`) ein
    - Backend übersetzt automatisch nach Cron
- Websuche-Strategie nachgeschaerft:
  - Websuche bleibt Pflichtfunktion
  - provider-native Tooling ist der Standardpfad
  - SearXNG nur noch optional (kein Pflicht-Container im Default-Setup)
- Skills-UI Layout auf "schwebende Karten" umgestellt (analog Memories).
- Neues CSS-Pattern `floating-card` eingefuehrt und als Default für neue Seitenlayout-Bloecke festgelegt.
- `Config` und `Benutzer` ebenfalls auf Floating-Layout angehoben (mehrere getrennte Karten statt monolithischer Block).
- `Config` Intro-Claim entfernt für konsistenteres Seitenlayout.
- Benutzer-Seite mobil überarbeitet:
  - Tabelle durch responsive User-Karten ersetzt
  - iPhone-Overflow am rechten Rand behoben

### Auth / Userverwaltung
- Userverwaltung auf case-sensitive Benutzernamen umgestellt:
  - `fischerman` und `Fischerman` sind getrennte Accounts
  - Secure-Store normalisiert Usernamen nicht mehr auf lowercase
- Login setzt Session/Cookies mit dem kanonischen Username aus dem Security-Store.
- Login-UI zeigt Hinweis, dass Benutzernamen gross/klein-sensitiv sind.
- Benutzerverwaltung erweitert:
  - Username kann unter `/config/users` direkt umbenannt werden
  - Duplikat-Check für Zielnamen aktiv
  - bei eigener Umbenennung wird die aktive Session sofort auf den neuen Namen aktualisiert
- Navigation vereinfacht:
  - Top-Menue zeigt nur noch `Memories`, `Skills` und Username-Menue
  - bisherige Punkte aus `Mehr` sind ins Username-Menue verschoben (`Stats`, für Admin zusätzlich `Config` und `Benutzer`)

### Memory
- User-Filter in Memory wieder strikt auf exakte `user_id` gesetzt (kein Alias-Match).
- Dedup/Update-Checks respektieren jetzt ebenfalls exakte `user_id` (case-sensitive).

## 2026-03-23

### UX & Navigation
- Restart-Watchdog im Basis-Template eingefuehrt:
  - erkennt, wenn ARIA waehrend offener Seite kurz nicht erreichbar ist
  - leitet nach Wiederverfügbarkeit automatisch auf `/login` (mit `next`) um
  - verhindert "stale" Unterseiten nach Restart
- Navigation verschlankt und mobilfreundlich gemacht:
  - `Chat` aus Topnav entfernt (Home via Logo/Name)
  - neue Hauptnavigation: `Memories`, `Skills`, `Mehr`
  - `Mehr` buendelt `Stats` + admin-spezifisch `Config` und `Benutzer`
- `Admin ON` Badge aus rechter Leiste in den linken Brand-Bereich verlegt.
- `Admin-On/Off` Schalter in die Benutzerverwaltung verlegt (`/config/users`).

### Betrieb / Startscript
- `aria.sh` gehaertet:
  - robustere Prozess-Erkennung (keine Abhaengigkeit von potenziell abgeschnittenen `ps`-Zeilen)
  - stabileres Background-Detach via `setsid` + `nohup` (falls `setsid` verfügbar)
  - `status` nutzt Health-Fallback, falls PID nicht sauber ermittelbar ist

### Memory-UI Struktur
- Qdrant/Collection-Setup thematisch unter `Memories` gebuendelt:
  - neue Zielseite: `/memories/config`
  - Einstieg direkt auf `/memories` als `Memory-Setup` (Admin)
- `Config` zeigt bei Memory nur noch Trigger/Routing (`/config/routing`).
- Legacy-Routen `/config/memory*` bleiben vorerst als Backward-Compatibility erhalten (späterer Release-Cleanup geplant).

### Skills-UI
- Neue Seite `/skills` mit Skill-Karten und Aktiv/aus-Status.
- Admin kann zentrale Skill-Toggles speichern (`memory`, `auto_memory`, `web_search`, `documents`, `home`).
- Pro Skill aufklappbare `Details` mit Quick-Links zu relevanten Konfig-Bereichen.

## 2026-03-22

### Security & Secrets
- Secure-Store eingefuehrt (verschlüsselte SQLite) für API-Keys/Tokens.
- Migration von Klartext-Secrets nach Secure-Store integriert (`secure-migrate`).
- `secrets.env`-Handling im Startscript verbessert.

### Auth & Rollen
- Login-Flow mit Session-Cookie eingefuehrt.
- Rollenmodell (`admin` / `user`) aktiv.
- Zugriffsschutz:
  - Config nur für `admin`
  - Chat/Memories/Stats nur mit Login
- Bootstrap-Flow:
  - erster Login erstellt automatisch den ersten `admin`.
- Passwort-Mindestlaenge auf 8 gesetzt.

### User-Verwaltung
- UI-Seite für Benutzerverwaltung umgesetzt (`/config/users`):
  - User erstellen
  - Rolle ändern
  - aktiv/deaktiviert setzen
  - Passwort aktualisieren
- Schutzregeln:
  - letzter aktiver Admin kann nicht entfernt/deaktiviert werden
  - eingeloggter Admin kann sich nicht selbst degradieren/deaktivieren
- Zugriff auf Benutzerverwaltung über User-Menue (oben rechts).

### UI/UX
- Topbar aufgeraeumt:
  - `ADMIN`-Badge entfernt
  - User-Menue mit Logout/Benutzerverwaltung
  - Session-Badge nur bei Debug-Modus
- Doppelter Login-Flow bereinigt (nur noch `/login`).
- Login-Feld verbessert:
  - kombiniertes Username-Input mit Vorschlagsliste (datalist)
  - kein separates old-school Dropdown mehr
- Nicht eingeloggt:
  - nur `Login` in der Navigation sichtbar.
- Model-Loader für `/config/llm` und `/config/embeddings` nachgeschaerft:
  - Browser-Fetch sendet jetzt den CSRF-Token korrekt mit
  - Embeddings nutzt jetzt den eigenen Endpoint `/config/embeddings/models`
  - Fehlerausgabe im Browser ist robuster und zeigt nicht mehr nur `JSON.parse`-Fehler bei HTML-/Text-Antworten

### Debug
- Debug-Modus als Config-Schalter (`/config/debug`) eingefuehrt.
- Technische Chat-Metadaten (u.a. Session-ID) nur sichtbar, wenn Debug aktiv ist.

### Dokumentation
- `status-aktuell.md` mehrfach aktualisiert.
- `help-security.md` um Auth-/Rollen- und UI-Infos erweitert.
- `test-checkliste.md` erweitert (Debug ON/OFF, User-Verwaltung etc.).

### Capability Routing
- Capability-Antworten für `file_read`, `file_write` und `file_list` halten den Chattext jetzt bewusst sauber.
- verwendetes Connection-Profil und Zielpfad werden stattdessen im bestehenden aufklappbaren `Details`-Bereich der Assistant-Nachricht angezeigt und auch in der file-basierten Chat-History mitgespeichert.
- Capability-Aktionen bekommen im `Details`-Badge jetzt eigene Icons/Labels statt wie normale Chat-Antworten als `💬 chat` zu erscheinen:
  - `📄 file_read`
  - `📝 file_write`
  - `🗂 file_list`
- Capability Routing erkennt jetzt deutlich mehr natürliche Datei-Formulierungen:
  - `Inhalt von /etc/hosts auf <server> zeigen`
  - `Datei ... erstellen`
  - `welche Dateien liegen in /tmp`
  - `öffne /etc/hosts auf <server>`
- `file_list` wird dabei bewusst vor allgemeinen `zeige`-/`show`-Formulierungen priorisiert, damit Listen nicht fälschlich als `file_read` laufen.
- Phase 3 gestartet:
  - neuer file-basierter `CapabilityContextStore` für operativen Kurzzeit-Kontext pro User
  - letzter erfolgreicher Server/Pfad wird nach erfolgreichen Capability-Aktionen mitgeführt
  - Follow-up-Phrasen wie `wie letztes Mal` oder `im gleichen Ordner` können damit letzten Server/Pfad wiederverwenden
  - `cls` löscht neben der Chat-History jetzt auch diesen operativen Kurzzeit-Kontext
- Phase 4 gestartet:
  - derselbe Capability-/Executor-Pfad unterstützt jetzt auch `SMB`
  - `file_read`, `file_write` und `file_list` laufen damit transportagnostisch über `SFTP` oder `SMB`
  - Router berücksichtigt dafür explizite SMB-Refs sowie Hinweise wie `NAS`, `Share`, `Freigabe`
- Phase 5 gestartet:
  - neue Capability `feed_read` für `RSS`-/`Atom`-Feeds
  - Router erkennt erste natürliche Feed-Formulierungen wie `RSS Feed ... zeigen`
  - Ausführung läuft über denselben Capability-/Executor-Pfad wie die Datei-Capabilities
  - `Details` zeigen die verwendete `RSS`-Connection wie bei den Datei-Aktionen
  - RSS-Antworten lesbarer formatiert:
    - nur noch kompaktere Top-Einträge statt langer Rohlisten
    - Zeitstempel werden lesbar auf `YYYY-MM-DD HH:MM` normalisiert
    - typische Tracking-Parameter wie `wt_mc` und `utm_*` werden aus Feed-Links entfernt
  - RSS-Config-UI klarer getrennt:
    - eigener `Neues Profil`-Modus mit leerem Formular
    - sichtbarer Bearbeiten-vs-Neu-Hinweis, damit bereits geladene Werte nicht wie unerklärte Altlasten wirken

### Bounded Cleanup
- `config_routes.py`:
  - wiederholte Context-Berechnung für die einfachen Connection-Unterseiten über einen gemeinsamen Helper reduziert
- `skill_runtime.py`:
  - gemeinsame Helper für Connection-Profilauflösung und Directory-Listing-Formatierung eingeführt
- Ziel war bewusst kein neuer Grossumbau, sondern weniger Wiederholung auf den gerade stark bewegten Pfaden
- Connection-Seiten UX vereinheitlicht:
  - alle vorhandenen Connection-Typen trennen jetzt klar zwischen
    - `Neue Verbindung erfassen`
    - `Bestehende Verbindungen bearbeiten / löschen`
  - das reduziert die Verwirrung durch vorbelegte Werte und schafft auf allen Connection-Unterseiten denselben Arbeitsablauf
  - neue gemeinsame Inline-Delete-Teilvorlage für Connection-Seiten eingeführt
  - Verifikation:
    - `py_compile`: OK
    - `tests/test_error_handling.py` + `tests/test_stats_routes.py`: `10 passed`
    - Neustart + `/health`: OK
- Connection-Speicherlogik nachgeschärft:
  - Bearbeiten bestehender Connection-Profile arbeitet jetzt mit `original_ref` statt still neue Profile anzulegen
  - Rename verschiebt dabei auch Secure-Store-Secrets und räumt alte Health-Einträge auf
  - neue Profile mit bereits vorhandener Ref werden blockiert statt überschrieben
  - RSS prüft zusätzlich auf doppelte `feed_url` und lehnt doppelte Feed-Verbindungen ab
  - `/config/connections/sftp` Template-/Kontextfehler behoben
  - Verifikation:
    - `py_compile`: OK
    - Jinja-Template-Load: OK
    - `tests/test_error_handling.py` + `tests/test_stats_routes.py`: `10 passed`
    - Neustart + `/health`: OK

## 2026-03-29 Webhook Capability
- Neue Capability-Familie `webhook_send` hinzugefuegt. Chat kann Webhook-Nachrichten jetzt direkt ueber konfigurierte Webhook-Profile senden.
- Neuer Routing-Pfad in `capability_router`, `action_plan`, `pipeline` und `skill_runtime`.
- Details-Badge zeigt `📡 webhook_send` und das verwendete Webhook-Profil.
- Tests erweitert fuer Router und Pipeline.

## 2026-03-29 HTTP API Capability
- Neue Capability-Familie `api_request` hinzugefuegt. Chat kann konfigurierte HTTP-API-Profile jetzt direkt ansprechen.
- Routing ueber `capability_router`, Ausfuehrung ueber `pipeline` und `skill_runtime`.
- Details-Badge zeigt `🌐 api_request` und Profil/Pfad.
- Tests erweitert fuer Router, Pipeline und Badge-Pfade.

## 2026-03-29 SMTP + IMAP Connections
- Bisherige Email-Connection im UI sauber zu SMTP umbenannt.
- Neue eigene IMAP-Connection eingefuehrt, getrennt von SMTP.
- Menue unter Verbindungen jetzt konsistent mit `SMTP` und `IMAP`.
- Alte Template-Leiche fuer `config_connections_email.html` entfernt.

## 2026-03-29 Mail Capabilities
- Neue Capability `email_send` über SMTP hinzugefuegt.
- Neue Capabilities `mail_read` und `mail_search` über IMAP hinzugefuegt.
- Mail-Badges im Chat: `✉️ email_send`, `📬 mail_read`, `🔎 mail_search`.
- Router, Pipeline und Skill-Runtime fuer Mail-Workflows erweitert.

## 2026-03-29 MQTT Capability
- Neue Capability `mqtt_publish` hinzugefuegt.
- Natuerliche Chat-Prompts koennen jetzt ueber MQTT-Profile auf ein Topic publizieren.
- Default-Topic aus dem Profil oder explizites Topic aus dem Prompt.
- Chat-Badge: `📟 mqtt_publish`.

## 2026-03-29 RSS UI Gruppierung
- RSS-Verbindungen werden auf `/config/connections/rss` jetzt thematisch gruppiert dargestellt.
- Die Gruppierung nutzt bevorzugt ein LLM fuer sinnvolle Cluster, faellt aber stabil auf heuristische Kategorien zurueck.
- `/stats` zeigt RSS nicht mehr als lange Kartenliste, sondern nur noch als kompakte Uebersicht mit Anzahl, gruen und rot.

- RSS-Gruppierung laeuft nicht mehr bei jedem Seitenaufruf neu, sondern ueber Cache + manuellen Refresh-Button `Kategorien aktualisieren`.
- `/stats` zeigt RSS jetzt als normale Status-Karte mit Lampe in derselben Reihenfolge wie die restlichen Connections.

## 2026-03-29 UI Icons
- Top-Navigation und Mehr-Menue mit lokaler schlanker Icon-Schicht versehen.
- Config-Hub mit konsistenten Icons pro Bereich und pro Connection-Typ aufgewertet.
- Bewusst ohne externe Frontend-Abhaengigkeit umgesetzt; Pictogrammers/MDI bleibt als spaeterer Ausbaupfad dokumentiert.

- Mobile-Hardening fuer iPhone: Topbar, Dropdown, Config-Hub, Prompt-Tabellen und Karten auf kleine Screens nachgeschaerft.

## 2026-03-29 SSH Testsession
- SSH-Verbindungsseite, Profil-Laden, Speichern und Auto-Test manuell geprueft: OK.
- `/stats` zeigt SSH korrekt, laedt bei vielen Connection-Checks aber spuerbar langsam.
- Runtime-Status `welche skills sind aktiv` manuell geprueft: OK.
- Freier Prompt `machst du mir ein update auf dem server` triggert den vorhandenen SSH-/Update-Skill aktuell noch nicht robust genug.

## 2026-03-29 Discord Testsession
- Discord-Verbindungsseite, Profil-Laden und Alert-Checkboxen manuell geprueft: OK.
- `/stats` zeigt Discord korrekt: OK.
- Discord-Testnachrichten kommen an: OK.
- Freier Chat-Prompt fuer Discord-Nachrichten war zunaechst nicht an den Capability-Pfad angeschlossen.
- Fix umgesetzt: neue Capability `discord_send` fuer natuerliche Chat-Prompts nach Discord.
- Retest erfolgreich: `schicke eine test nachricht nach discord, inhalt ...` sendet jetzt direkt aus dem Chat.

## 2026-03-29 SFTP Testsession
- SFTP-Verbindungsseite, Profil-Laden, Speichern und Auto-Test manuell geprueft: OK.
- `/stats` zeigt SFTP korrekt: OK.
- Chat-`file_read` via SFTP manuell geprueft: OK.
- Offener Polishing-Punkt: Connection-/Pfad-Details im Chat sollen fuer alle Connection-Capabilities konsistent angezeigt werden.

## 2026-03-29 SMB Testsession
- SMB-Verbindungsseite, Profil-Laden, Speichern und Auto-Test manuell geprueft: OK.
- `/stats` zeigt SMB korrekt: OK.
- Freier Prompt ohne klaren SMB-/Share-Hinweis (`docker verzeichnis von synrs816`) wurde noch nicht als SMB-Capability erkannt.
- Backlog: Connection-Karten auf `/stats` sollen direkt zur passenden Connection-Seite im Edit-Modus verlinken.

## 2026-03-30 UI Polish Runde
- Connection-Karten auf `/stats` sind jetzt direkt zur passenden Connection-Seite im Edit-Modus verlinkt.
- Capability-Details im Chat laufen jetzt ueber eine gemeinsame zentrale Detail-Logik.
- `mail_search` zeigt den Suchbegriff in den Details, `mqtt_publish` zeigt dort das Topic statt eines generischen Pfads.
- `Discord Alerting & Verhalten` ist auf der Discord-Seite jetzt als aufklappbarer Bereich umgesetzt.
- Die Sprachauswahl ist aus dem eingeloggten Hauptmenue entfernt und bleibt bewusst unter `Einstellungen`.
- Das ARIA-Logo zeigt bei laengeren Requests nun eine kleine Aktivitaetsanimation.

## 2026-03-30 Runtime URL + Discord UX
- `/stats` zeigt jetzt aktuelle RAM-Nutzung des ARIA-Prozesses als KPI-Karte mit kleiner Gauge und Prozentanteil am System-RAM.
- `/stats` zeigt fuer `ARIA Runtime` jetzt die real erreichbare ARIA-URL statt der Bind-Adresse.
- Discord-Systemevents verwenden dieselbe Runtime-URL-Logik fuer Host-Meldungen.
- Discord-Verbindungen zeigen aktive Kategorien jetzt kompakt direkt am geladenen Profil.
- Das Hauptmenue schliesst per Klick ausserhalb oder mit `Escape`.

## 2026-03-30 Memory List + Manual Create
- `/memories` listet Eintraege jetzt kompakter ueber Titel und Kurzinfo statt sofort als Volltext.
- Memory-Eintraege sind aufklappbar; Bearbeiten und Loeschen bleiben direkt am Eintrag moeglich.
- Manuelle Memory-Erfassung fuer Fakt / Praeferenz / Wissen direkt auf `/memories` ergaenzt.


## 2026-03-30 Backlog Cleanup + Connection Context + Chat Delete
- Top-Backlog bereinigt: bereits erledigte Punkte aus der offenen Liste entfernt, damit die Priorisierung wieder dem echten Stand entspricht.
- Connection-Aliase aus Ref plus Connection-Metadaten erweitert (Host, Share, URL, Root-Path), damit Capability-Routing Hosts/NAS/Docker-Ziele robuster erkennt.
- SMB-/Host-bezogene Prompts koennen jetzt auch ueber Alias-Matches in den Datei-Pfad kippen, statt ins generische Chat-LLM zu fallen.
- Erster sicherer Chat-Admin-Flow fuer Connections vorbereitet: Verbindungen koennen jetzt per Chat-Loeschbefehl mit bestaetigtem Token entfernt werden.
- Stats-RAM-Anzeige auf digitale LED-Optik umgestellt; Prozentangabe jetzt explizit als Anteil am gesamten System-RAM beschrieben.
- Stats-Header thematisch gebuendelt: Tokens, Kosten und Ressourcen als drei Cluster im LED-Stil; Ressourcen zeigen jetzt auch die lokal erkennbare Qdrant-DB-Groesse.
- 2026-03-30: Gemeinsamen Metadaten-Block für alle Connection-Typen eingeführt (`Titel`, `Kurzbeschreibung`, `Aliase`, `Tags`), Save-/Read-Flow zentral verdrahtet und semantische Connection-Auflösung direkt auf diese Metadaten erweitert.
- 2026-03-30: Connection-Status-Karten auf den Connection-Seiten und auf `/stats` zeigen jetzt bevorzugt Titel + Ref + Tags; SMB-/NAS-Routing für natürlichere Formulierungen erweitert; mehrere Einstellungs-Unterseiten mit konsistenten Kopf-Icons versehen.
- 2026-03-30: Connection-Selectoren zeigen jetzt `Titel · Ref`; neuer Chat-`create`-Flow für `RSS`, `Webhook` und `HTTP API` inkl. Confirm-Step und abgesicherter Parser-/Config-Testabdeckung ergänzt.
- 2026-03-30: Chat-`create` versteht jetzt optionale Connection-Metadaten (`Titel`, `Beschreibung`, `Tags`, `Aliase`) direkt aus dem Prompt; Skill-Wizard-Connection-Selectoren zeigen ebenfalls `Titel · Ref`.
- 2026-03-30: Chat-`update` für `RSS`, `Webhook` und `HTTP API` ergänzt, ebenfalls mit Confirm-Step; Metadaten-only-Updates werden unterstützt und per Tests abgesichert.
- 2026-03-30: Chat-Admin-Flow um `Discord` erweitert; Create/Update-Vorschauen zeigen jetzt lesbarere Feldnamen (`Webhook-URL`, `Base-URL`, `Health-Pfad` statt Roh-Keys).
- 2026-03-30: Chat-Toolbox und Slash-Menü auf gemeinsamen Command-Katalog umgestellt; Admin-spezifische Chat-Hilfen für Connection-Create/Update/Delete werden jetzt automatisch mitgezogen statt separat gepflegt.
- 2026-03-30: Admin-Hilfen in der Chat-Toolbox werden jetzt aus den tatsächlichen Connection-Create/Update-Specs generiert und verwenden bevorzugt reale vorhandene Refs als Beispiele.
- 2026-03-30: Chat-Toolbox priorisiert jetzt zusätzlich kontextabhängig einen kleinen Block `Passend jetzt`; dafür werden die letzten Chat-Nachrichten mit den Command-Keywords abgeglichen, ohne einen zweiten statischen Hilfekatalog einzuführen.
- 2026-03-30: Chat-Admin-Flow auf `MQTT` erweitert; `create` und `update` verstehen jetzt Broker-Host plus optionales `topic`, sichern Metadaten mit ab und erscheinen automatisch in Toolbox/Slash-Hilfen.
- 2026-03-30: Chat-Admin-Flow auf `SMTP` und `IMAP` erweitert; Create/Update verstehen jetzt die wichtigsten Mail-Felder (`smtp_host`, `host`, `user`, `from`, `to`, `mailbox`) und werden inkl. Vorschau/Toolbox automatisch mitgezogen.
- 2026-03-30: Connection-Kontext fuer freie Prompts weiter geschaerft; kindspezifische Alias-Kombinationen aus `Titel`/`Tags` (`alerts mail`, `ops inbox`, `event bus`, `inventory endpoint`) fliessen jetzt direkt in die Aufloesung ein. `email_send` und `mqtt_publish` erkennen dadurch Titel-/Alias-Prompts besser auch ohne harte Typwoerter.
- 2026-03-30: MQTT-Details zeigen jetzt auch das Default-Topic aus dem Profil, wenn kein eigenes Topic im Prompt steht.
- 2026-03-30: Chat-Admin-Flow um `SMB` erweitert; `create`/`update` verstehen jetzt Host, Share, User und optionalen Pfad inkl. Secret-Handling fuer SMB-Passwoerter, Vorschau und Toolbox-Beispielen.
- 2026-03-30: Chat-Admin-Flow um `SFTP` erweitert; `create`/`update` verstehen jetzt Host, User, optionalen Pfad und optionalen Key-Pfad inkl. Secret-Handling fuer SFTP-Passwoerter, Vorschau und Toolbox-Beispielen.
- 2026-03-30: Chat-Admin-Flow um `SSH` erweitert; `create`/`update` verstehen jetzt Host, User, optionalen Key-Pfad und optionale Allow-Commands inkl. Vorschau/Toolbox-Beispielen.
- 2026-03-30: Freie Alias-/Titel-Prompts fuer `Discord`, `HTTP API` und `IMAP` sind jetzt per Pipeline-Tests abgesichert.
- 2026-03-30: Qdrant-DB-Groesse auf `/stats` zeigt jetzt belegten Plattenplatz statt theoretischer Sparse-Dateigroessen; damit faellt die lokale Anzeige von ueber `1 GB` auf einen plausiblen Wert im Bereich von rund `133 MB`.
- 2026-03-30: Neue Produkt-/GitHub-Übersicht `project.docu/aria-overview.md` ergänzt; README-Einstieg auf allgemeine ARIA-Beschreibung statt altem Session-Stand umgestellt.
- 2026-03-30: `project.docu/aria-copy-pack.md` ergänzt mit Kurz-, Mittel- und Langtexten für GitHub About, Repo-Intro, Release Notes, Landingpage und Elevator Pitch.

- 2026-03-30: Zentralen `connection_catalog` eingefuehrt; Labels, Beispiel-Refs, Toolbox-Keywords und Chat-Insert-Templates liegen jetzt in einer gemeinsamen Registry statt verteilt in mehreren Mappings. Semantische Connection-Aufloesung nutzt denselben Katalog; zusaetzlich gibt es jetzt einen generischen LLM-Fallback fuer die Auswahl des passenden Connection-Profils, waehrend die Ausfuehrung deterministisch bleibt.

- 2026-03-30: Chat-Admin-Pending-Cookies fuer Connection-Create/Update/Delete serverseitig gehaertet; signierte Pending-Daten tragen jetzt `issued_at`, verfallen auch serverseitig und werden ueber ein kindspezifisches Feld-Schema bereinigt. Dadurch gehen komplexere Felder wie `host`, `share`, `key_path`, `allow_commands`, `smtp_host`, `mailbox` oder `topic` beim Confirm-Step nicht mehr still verloren.
- 2026-03-30: `connection_catalog` um Feld-Schemata sowie Config-Seite/Ref-Query-Metadaten erweitert; `/stats` und `config_routes` nutzen diese gemeinsame Registry jetzt ebenfalls fuer Edit-Ziele. Das ist die vorbereitende Basis fuer spaetere schema-getriebene Connection-Formulare.

- 2026-03-30: Erste schema-gerenderte Config-Formularbloecke fuer `RSS`, `Webhook`, `HTTP API`, `MQTT`, `SMTP` und `IMAP` eingefuehrt. Die Basisfelder laufen dort jetzt ueber einen gemeinsamen `_connection_schema_fields.html`-Renderer auf Grundlage des `connection_catalog`, waehrend Metadaten weiterhin ueber den separaten gemeinsamen Metadaten-Block laufen.
- 2026-03-30: Chat-`create`/`update` fuer Connections auf eine kataloggetriebene Parserbasis umgestellt. `connection_catalog` beschreibt jetzt auch Chat-Aliase, Primary-Felder und sinnvolle Defaultwerte; `main.py` extrahiert gemeinsame Felder (`user`, `share`, `pfad`, `key`, `mailbox`, `topic`, `from`, `to`, `password`, `token`, `method`, `content-type`, `port`, `timeout`) ueber eine zentrale Feldtabelle statt ueber viele per-Type-Regeln. Zusaetzliche Tests sichern generische Secret-/Token-Felder jetzt explizit ab.
- 2026-03-30: Parser-Feldregeln weiter in den `connection_catalog` verschoben; explizite Chat-Formen wie `url ...`, `host ...`, `token ...` oder `password ...` werden jetzt direkt ueber katalogisierte Feldregeln verarbeitet. Connection-Vorschauen leiten ihre sichtbaren Felder ebenfalls aus dem Katalog ab statt aus einer lokalen Feldliste.
- 2026-03-30: `capability_catalog` um Executor-Bindings und Detail-Metadaten erweitert. Die Pipeline registriert Executor dadurch jetzt per Katalog-Loop statt ueber eine feste Registerliste; separate Tests sichern die erwarteten Capability-/Executor-Paare und Detailzeilen ab.
- 2026-03-30: Connection-Katalog um Template-/Seitenspezifikationen erweitert. `config_routes` rendert die meisten Connection-Seiten jetzt ueber einen gemeinsamen Seiten-Helper statt ueber viele fast identische `TemplateResponse`-Bloecke; zusaetzliche Tests sichern Spezialfaelle wie `HTTP API -> config_connections_http_api.html` und `SMTP -> config_connections_smtp.html` ab.
- 2026-03-30: Die schema-nahen Connection-Seiten `RSS`, `Webhook`, `HTTP API`, `SMTP`, `IMAP` und `MQTT` nutzen jetzt gemeinsame Partials fuer Intro-/Summary- und Live-Status-Bloecke. Seitentitel und Untertitel dieser Bereiche kommen ueber `connection_menu_meta(...)` aus dem gemeinsamen Katalog statt aus lokal wiederholten Template-Texten.
- 2026-03-30: Auch die komplexeren Connection-Seiten `SSH`, `SFTP`, `SMB` und `Discord` wurden auf dieselben gemeinsamen Intro-/Status-Partials gezogen. Live-Status-Texte kommen jetzt ueber `connection_status_meta(...)` aus dem gemeinsamen Katalog; der Verbindungen-Hub zaehlt Profile/Healthy/Issues direkt aus den gemeinsamen Statuszeilen statt ueber eine separate lokale Key-Tabelle. `RSS` nutzt den gemeinsamen Statusblock jetzt ebenfalls vollstaendig mit.
- 2026-03-30: Wiederholte Connection-Summary-Karten (`Profiles`, `Healthy`, `Issues`) laufen jetzt ueber `_build_connection_summary_cards(...)` und `connection_overview_meta(...)` statt ueber pro Seite erneut duplizierte Kartenlisten. Nur die wirklich typ-spezifischen Extra-Karten bleiben lokal. Zusaetzlich ziehen Chat-Toolbox-Emojis und die zusammengefasste RSS-Stats-Karte ihre Typ-Metadaten jetzt ebenfalls aus dem gemeinsamen Connection-Katalog.
- 2026-03-30: Custom-Skill-Routing fuer freie Prompts nachgeschaerft. Deterministische Skill-Treffer nutzen jetzt einen gewichteten Matcher auf Keywords/Name/Beschreibung statt nur exakte Teilstrings. Capability-Pfade haben dabei bewusst Vorrang; erst wenn kein deterministischer Capability-Pfad greift, darf ein enger LLM-Fallback genau einen passenden Skill vorschlagen. Neue Tests decken natuerliche Skill-Phrasen, Capability-Vorrang und den LLM-Skill-Fallback ab.
- 2026-03-30: Reverse-Proxy-/Cookie-Haertung eingezogen. Neue zentrale Helferfunktion `request_is_secure(...)` wertet `x-forwarded-proto` aus und wird jetzt fuer Auth-, Session-, CSRF-, Sprach-, Auto-Memory- und Pending-Confirm-Cookies in `main.py` sowie fuer relevante Cookie-Refreshes in `config_routes.py` und `memories_routes.py` verwendet. Damit bleibt das Cookie-Verhalten auch hinter HTTPS-Reverse-Proxy konsistent; neue Unit-Tests decken Secure-Erkennung und Runtime-URL-Aufloesung explizit ab.
- 2026-03-30: Session-/Recovery-Haertung nachgezogen. Ungueltige Auth-Cookies werden bei geschuetzten Routen jetzt aktiv bereinigt und `/session-expired` loescht Auth-/Session-/Pending-Cookies ebenfalls serverseitig aus. Abgelaufene oder ungueltige Bestätigungstokens fuer Forget/Safe-Fix/Connection-Admin raeumen ihre Pending-Cookies jetzt selbst auf. Ausserdem laedt `_reload_runtime()` neue Settings/PromptLoader/LLM/Pipeline erst komplett vor und uebernimmt sie nur noch atomar, damit ein Reload-Fehler die laufende Runtime nicht in einen halbkaputten Zustand schiebt. Neue Recovery-Tests sichern Redirect- und Cookie-Cleanup-Verhalten ab.
- 2026-03-30: `/activities` auf Memory-artige, aufklappbare Karten umgestellt. Interne Rauschinfos werden jetzt ausgeblendet: `Tokens`, `Kosten`, `Chat-Modell` und `Quelle` erscheinen nur noch, wenn sie fuer den konkreten Run wirklich relevant sind; `web`/`chat` werden nicht mehr als pseudo-Quelle angezeigt.
- 2026-03-30: `Security Guardrails` von reiner Bootstrap-Seite zu echtem SSH-Guardrail-MVP ausgebaut. Wiederverwendbare `SSH Guardrail-Profile` mit `Allow-Wording` und `Deny-Wording` koennen jetzt unter `/config/security` gepflegt und an SSH-Verbindungen angehaengt werden. Der SSH-Runtime-Pfad setzt diese Guardrails fuer Custom-Skills und Safe-Fix-Kommandos jetzt tatsaechlich durch; separate Tests decken deny- und allowlist-blockierte Kommandos ab.
- 2026-03-31: Qdrant fuer die spaetere Distribution nachgeschaerft. `MemoryConfig` kennt jetzt `qdrant_api_key`, ENV-Override und Secure-Store-Merge; Secret-Migration deckt den neuen Key ebenfalls ab. Memory-Skill, Stats und Qdrant-Admin-Overview verwenden den API Key jetzt beim Client-Aufbau konsistent.
- 2026-03-31: `/config/memory` hat jetzt einen echten Backend-Block fuer `enabled`, `backend`, `qdrant_url` und `qdrant_api_key`. Der Key wird bei aktiviertem Secure Store verschluesselt abgelegt; nur ohne Secure Store faellt der Flow auf Klartext in `config.yaml` zurueck.
- 2026-03-31: `docker-compose.yml` auf Zwei-Container-Basis fuer `aria` + `qdrant` umgestellt. ARIA spricht standardmaessig intern ueber `http://qdrant:6333`, Qdrant bekommt ein eigenes persistentes Volume und kann optional ueber `ARIA_QDRANT_API_KEY` mit API Key abgesichert werden. Der Qdrant-Dashboard-Link wird bei interner Container-URL bewusst im Browser versteckt.
- 2026-03-31: Frontend von externer CDN-Abhaengigkeit geloest. `htmx` wird jetzt lokal aus `aria/static/vendor/htmx-1.9.12.min.js` ausgeliefert statt ueber `unpkg`.
- 2026-03-31: Globalen Fehlerpfad fuer Requests gehaertet. `/chat` bekommt bei ungefangenen Fehlern jetzt strukturierte JSON-Details statt stiller 500er; normale HTML-Seiten bekommen eine einfache ARIA-Fehlerseite. Das Chat-Frontend liest diese Detailmeldungen jetzt aus und zeigt sie statt einer pauschalen Standardmeldung.
- 2026-03-31: Connection-Admin-Fehler fuer den Chat vereinheitlicht. Ein neuer Friendly-Error-Pfad in `connection_admin.py` uebersetzt rohe Exceptions in besser lesbare Nutzertexte; Pflichtfelder verwenden katalogisierte Feldlabels, Security-Store-Zwaenge werden neutraler kommuniziert. Die Chat-Flows fuer Connection-`create`/`update`/`delete` nutzen diese Fehlertexte jetzt konsistent.
- 2026-03-31: Persona-Name aus `prompts/persona.md` in den UI-Core gehoben. `PromptLoader` liest jetzt `Name: ...` direkt aus der Persona-Datei; sichtbare UI-Texte ersetzen `ARIA`/`Aria` zentral durch diesen Persona-Namen. Brand-/Seitentitel und die einfache HTML-Fehlerseite nutzen denselben Wert jetzt ebenfalls.

- 2026-03-31: Prompt Studio und Workbench-Dateieditor auf einen gemeinsamen Editor-Flow vereinheitlicht. Beide Seiten nutzen jetzt dieselbe Dateiauswahl mit Metadaten, grossem Texteditor und sichtbaren Save-/Reload-Aktionen. Beim Speichern von Dateien unter `prompts/` oder `aria/skills` laedt der Workbench-Editor die Runtime jetzt ebenfalls direkt neu, damit Prompt- und Skill-Aenderungen konsistent wirksam werden.

- 2026-03-31: Schlanke Startup-/Runtime-Diagnostik eingefuehrt. Neuer Core-Block `runtime_diagnostics.py` prueft Prompt-Dateien, Qdrant, Chat-LLM und Embeddings in einheitlicher Form; beim Start wird diese Diagnostik im Hintergrund ausgefuehrt und ueber die geschuetzte Route `/api/system/preflight` abrufbar gemacht. Damit werden typische Release-/Betriebsprobleme frueher sichtbar, ohne den normalen App-Start zu blockieren.

- 2026-03-31: Startup-Preflight in `/stats` integriert. Die Seite zeigt den letzten bekannten Runtime-/Startup-Diagnostikstand jetzt als eigenen Block mit Gesamtstatus, Zeitstempel und Einzelkarten fuer Prompt-Dateien, Qdrant, Chat-LLM und Embeddings. Zusätzliche Tests sichern die Preflight-Meta-Aufbereitung fuer die Stats-Ansicht ab.

- 2026-03-31: `/stats`-Preflight nachgeschaerft. Fehlende deutsche Warntexte fuer den Health-/Preflight-Block wurden ergänzt, nicht-ok Checks werden jetzt in einer kompakten Ursachenzeile zusammengefasst, und die Embedding-Diagnostik erkennt Vektoren robuster auch bei Dict-basierten LiteLLM-Antworten. Dadurch verschwindet der falsche Embedding-Warnzustand im aktuellen Live-Stand.

- 2026-03-31: Stats-/i18n-Haertung nachgezogen. `/stats` baut den Runtime-Preflight bei leerem Startup-Cache jetzt on-demand auf, damit kein falscher Warnzustand ohne Kontext angezeigt wird. Zusätzlich wurden die fehlenden i18n-Einträge für Kernflächen wie Topbar, Config-Hub und Stats ergänzt; ein neuer Test sichert diese `de`/`en`-Key-Abdeckung künftig ab.
