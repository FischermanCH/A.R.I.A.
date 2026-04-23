# ARIA - Alpha Backlog

Stand: 2026-04-22

Zweck:
- schlanker Arbeits-Backlog fuer die laufende Alpha-Linie
- oben stehen nur noch offene Punkte und naechste Schritte
- bereits gelieferte Aenderungen stehen im `CHANGELOG.md`
- groessere Zukunftsthemen stehen in `docs/backlog/future-features.md`

Aktueller Release-Stand:
- public: `0.1.0-alpha122`
- lokal / intern: `0.1.0-alpha167`

## Jetzt

### Release- und Runtime-Hardening
- Managed-GUI-Update Ende-zu-Ende weiter absichern
  - `P0`: Mount-/Config-/Prompt-/Data-Konsistenz nie wieder verlieren
  - `P2`: `aria-setup` frisch gegen Host mit bestehender ARIA gegenpruefen
- groesste Monolithen mit dem hoechsten Hebel zuerst schneiden
  - verbleibende Rest-Helfer und letzte gemischte Web-Logik weiter aus `aria/web/config_routes.py` ziehen
  - verbleibende Rest-Helfer und letzte gemischte Web-Logik weiter aus `aria/main.py` ziehen

### Routing / Planner / Live-Chat
- Routing-Produktpfad weiter entschlacken und vereinheitlichen
  - verbleibende Direkt-/Sonderpfade in Chat/Admin auf denselben Resolver ziehen
  - Prompt-/Follow-up-Robustheit fuer echte Alltagsfaelle weiter haerten
- bounded LLM-Routing als naechsten sauberen Ausbau vorbereiten
  - deterministische Treffer + Qdrant-Kandidaten bleiben die Vorstufe
  - kleine Router-LLM entscheidet anschliessend nur innerhalb des erlaubten Kandidatenraums
  - Ziel: weniger Keyword-Pflege, bessere Mixed-Language-Abdeckung, keine freie Tool-Wahl ohne Guardrails
- Pending-/Admin-Sonderpfade sprach- und resolverseitig weiter mit dem Produktpfad angleichen

### Produktfluss nach dem UI-Rework
- Onboarding / Empty States weiter verankern
  - Hub-Seiten fuer `Gedaechtnis`, `Faehigkeiten` und `Verbindungen` gezielter mit naechsten Schritten versehen
  - bestehende Datenlage bewusst nutzen, damit Einsteiger und Rueckkehrer nicht dieselben Hinweise sehen
- Live-Ausfuehrung / Confirm-UX weiter schaerfen
  - `allow`, `ask_user`, `block` noch menschlicher und eindeutiger zeigen
  - Rueckfragen, bestaetigungspflichtige Aktionen und sichere Standardfaelle konsistenter formulieren
- Mobile-/Tablet-Pass als eigener Politur-Block
  - Hub-Navigation, Formulare, Submenus und dichte Listen fuer kleinere Breiten gezielt nachziehen

### Persoenliche Enduser-Funktionen vorbereiten
- erster persoenlicher Produktpfad: Google Calendar read-only
  - naechster Fokus: sprachliche Robustheit und Follow-ups im Live-Betrieb
  - Auth-/Reconnect-/Fehlerpfad fuer echte Nutzerfaelle weiter glätten
  - Kalender-Schreibpfad bewusst spaeter
  - Ziel: echter Enduser-Nutzen ohne sofortiges Aenderungsrisiko
- Notizen als Markdown-first Produktpfad starten
  - Quelle bleibt eine echte `.md`-Datei pro Notiz statt nur Qdrant-Payload
  - Qdrant dient als abgeleiteter Such-/Kontextindex, nicht als Source of Truth
  - bei Aenderungen an bestehenden Notizen wird die betroffene Notiz komplett neu gechunked und neu indiziert
  - gelieferter MVP:
    - Notiz anlegen
    - loeschen
    - Ordner anlegen
    - verschieben ueber Ordnerfeld
    - Markdown exportieren
    - Chat-/Toolbox-Einstieg
    - semantische bzw. lexikale Suche
    - explizite Web-Recherche mit Notes-Kontext
    - normaler Web-Search-Pfad bekommt passende Notes jetzt ebenfalls als Zusatzkontext
    - natuerliche Chat-Phrasen wie `halte fest ...` koennen Notes direkt anlegen
    - Web-URLs koennen direkt aus dem Chat als Notiz uebernommen werden
    - leichte Tag-Vorschlaege werden jetzt ebenfalls mitgespeichert
  - naechster Ausbau:
    - ruhigere, noch smartere Chat-Magie fuer Ordner-/Titel-/Tag-Vorschlaege
    - Notes als wiederverwendbarer Zusatzkontext fuer weitere Routing-/Research-Flows jenseits der Websuche

### Learning Loop / Selbstlernender Produktpfad
- kontrollierten ARIA-Learning-Loop als Kernfunktion vorbereiten
  - Ziel: aus echter Nutzung sollen Fakten, Routing-Aliase und wiederverwendbare Prozeduren entstehen
  - ARIA lernt transparent und kontrolliert, nicht als heimlicher Auto-Mutator
- MVP-Phase 1: Learning Candidates sammeln
  - erfolgreiche komplexe Tasks, Routing-Klaerungen und wiederholte Korrekturen als `learning candidate` markieren
  - noch keine automatische Skill-Erstellung, nur strukturierte Beobachtung
- MVP-Phase 2: Reflection + Classification
  - Candidate in `fact`, `alias`, `procedure` oder `skill_draft` einordnen
  - nur niedrig-riskante Fakten/Aliase duerfen spaeter automatisch vorgeschlagen werden
- MVP-Phase 3: sichtbare Lernvorschlaege im Produkt
  - nach erfolgreicher Aufgabe optional anbieten:
    - `Als Gedächtnis merken`
    - `Als Routing-Alias merken`
    - `Skill-Entwurf daraus erstellen`
    - `Ignorieren`
- MVP-Phase 4: Skill-Draft-Bruecke
  - akzeptierte `procedure`-/`skill_draft`-Vorschlaege direkt in einen editierbaren Skill-Entwurf ueberfuehren
  - bestehende Guardrails, Confirm-Logik und Routing-Metadaten mitnutzen
- zusaetzlicher Web-/Research-Pfad: Internet -> Memory
  - Web-/Suchergebnisse sollen gezielt ins Memory uebernommen werden koennen
  - nicht alles automatisch speichern; User waehlt Treffer oder Ausschnitte bewusst aus
  - Quelle, URL, Zeitstempel und Provenienz muessen beim Speichern erhalten bleiben
  - Ziel: ARIA-Wissen gezielt aus aktueller Web-Recherche erweitern, ohne unkontrolliertes Memory-Rauschen

### Sicherheit / Betrieb
- restliche P0-/P1-Hardening-Punkte abschliessen
  - Login-Rate-Limit
  - getrennte Pending-Action-Secrets
  - Signing-Secrets nicht mehr leer initialisieren
  - Cookie-Review sauber abschliessen
  - Qdrant-Migrations-/Upgrade-Validierung weiter haerten

## Danach

### Connections und Integrationen
- Connections deklarativ und importierbar machen
  - YAML-/Manifest-Import fuer bestehende Connection-Typen vorbereiten
  - gemeinsames Connection-Manifest-Schema aufbauen
  - sichere Secret-Zuordnung getrennt vom Import halten
  - Routing-/Healthcheck-/Action-Metadaten direkt im Manifest fuehren
- Enduser-Integrationen als eigener Produktpfad vorbereiten
  - OAuth2-Connection-Foundation
  - Connect-/Callback-/Reconnect-/Revoke-Flow
  - Refresh-Token-Handling und per-User-Token-Zuordnung
  - zuerst Google (`Calendar`, `Tasks`, spaeter `Drive`, `Sheets`)
  - Apple bewusst spaeter und selektiv (`Calendar` zuerst)
  - Calendar-Architektur providerfaehig schneiden
    - kanonische Faehigkeiten zuerst als `calendar_read`, spaeter `calendar_create` / `calendar_update`
    - Google ist der erste Traeger, nicht das langfristige API-Modell
    - spaeter Apple Calendar auf denselben Produktpfad setzen statt zweite Sonderwelt bauen

### Core-Architektur
- `skill_runtime.py` nach Executor-Domaenen schneiden
- `pipeline.py` als Orchestrator weiter verschlanken
- gemeinsame Helper statt Copy-Paste schrittweise konsolidieren

### Skill-Automation
- Skills als kontrollierte Ausfuehrungsschicht unter natuerlicher Sprache weiter staerken
  - Connections = wohin
  - Routing = welches Ziel und wofuer
  - Skills / Templates = wie sicher ausgefuehrt wird
  - Scheduler / Cron = wann es automatisch laeuft
- strukturierte Skill-Outputs weiter ausbauen
- Skill-Fehler-/Skip-Zustaende im UI und in Activities sauberer machen
- Chat-zu-Skill-Draft-Flow vorbereiten

## Erledigt in der laufenden Alpha-Linie

Hinweis:
- die Details stehen im `CHANGELOG.md`
- hier nur noch die groben gelieferten Bloecke zur Orientierung

### UI / IA / Domain-Struktur
- Hauptnavigation und Bereichsseiten wurden konsequent auf die Produkt-Domaenen ausgerichtet
  - `Gedaechtnis`
  - `Faehigkeiten`
  - `Verbindungen`
  - `Einstellungen`
  - `Statistiken`
  - `Hilfe`
- Hauptbereiche wurden als ruhigere Hub-/Unterseiten-Struktur aufgebaut
- gemeinsamer Clean-Look mit konsistenter Domain-Shell ueber die Hauptbereiche gezogen
- Doku-/Info-Bereich (`Hilfe`, `Produkt-Info`, `Updates`, `Lizenz`) konsistent neu aufgebaut
- `Benutzer` lebt jetzt logisch unter `Einstellungen` statt als eigener Hauptmenuepunkt
- die Hubs fuer `Gedaechtnis`, `Verbindungen` und `Faehigkeiten` zeigen keine redundanten `Naechste Schritte`-Duplikate mehr direkt vor der eigentlichen Hub-Navigation

### Public-Readiness / Sicherheit / Produktfluss
- `Google Calendar`-Setup fuehrt jetzt direkt ueber die benoetigten Google-Links und die sinnvolle Schrittfolge, statt nur einen knappen Empfehlungsblock zu zeigen
- Service-Neustarts fuer `Qdrant` und `SearXNG` fragen vor dem Absenden jetzt explizit nach, damit Admin-Aktionen im UI weniger leicht versehentlich ausgeloest werden

### Skills / Connections / Memory UX
- `Gedaechtnis` wurde als echter Bereich mit `Uebersicht`, `Explorer`, `Map`, `Setup` beruhigt
- `Faehigkeiten` wurden in Hub + Unterseiten geschnitten (`start`, `mine`, `system`, `templates`)
- `Verbindungen` wurden als Hub + Unterseiten (`status`, `types`, `templates`) aufgebaut
- Skill-Wizard wurde deutlich vereinfacht
  - `Simple` vs. `Advanced`
  - starke Skill-Typ-Defaults
  - gefuehrtere Connection-Auswahl
- viele alte doppelte Menues, internen Erklaerbaeren und UI-Wiederholungen wurden entfernt

### Routing / Planner / Live-Chat
- Routing-Workbench und Live-Chat teilen sich jetzt denselben Routing-/Planner-/Payload-/Guardrail-Pfad fuer die unterstuetzten Connection-Kinds
- alte Chat-Sonderpfade fuer direkte Capability-Ausfuehrung wurden aus dem Hauptfluss herausgezogen
- bestaetigungspflichtige Outbound-Aktionen laufen konsistenter ueber `ask_user`
- Routing-Index verhaelt sich jetzt fuer User selbstheilender
  - Rebuild beim Start
  - Rebuild nach Connection-Aenderungen
  - Rebuild bei Bedarf im Live-Chat
- Routed-Actions mit noch fehlender Pflichtangabe behalten jetzt ebenfalls einen echten Pending-Zustand
  - kurze Folgeantworten wie eine nackte Discord-Nachricht koennen den offenen Plan direkt fortsetzen
  - der Chat kippt in diesen Faellen nicht mehr in generische Antworten zurueck
- Capability-Namen und Capability-/Connection-Kind-Kompatibilitaet wurden zentralisiert
- `CapabilityRouter` wurde bereits deutlich entschlackt und staerker an den gemeinsamen Resolver angebunden
- `requested_connection_ref`-Marker und Ignore-Terme kommen jetzt ebenfalls aus dem gemeinsamen Routing-Lexikon statt aus einer weiteren harten Mini-Regelwelt im Router
- weitere Router-Heuristiken wurden ebenfalls ins gemeinsame Lexikon gezogen
  - MQTT-Topic-Marker
  - natuerliche SSH-Uptime-/Online-Phrasen
  - Mail-Such-Folgebegriffe
  - bevorzugte Connection-Kind-Fallback-Reihenfolge
- Discord-/Alert-/Log-Aliase wurden fuer natuerliche Zielanfragen verbessert
- Routing-Testbench zeigt den kompletten Dry-run-Pfad bis zur finalen Would-run-Entscheidung
- bestaetigte Routed-Actions bleiben in ihren Detailzeilen naeher am eigentlichen Produktpfad
- Workbench-/Confirm-UI trennt lesbare Produkttexte jetzt klarer von internen Codes

### Produktfluss / Confirm / Mobile
- erste Onboarding-/Next-Step-Bloecke auf den Hub-Seiten sind drin
- Confirm-/Guardrail-Sprache wurde lesbarer und menschlicher gemacht
- Chat-Arbeitsflaeche reagiert auf Mobile dynamischer auf kurze vs. lange Chats

### Themes / Appearance / Hintergrundbilder
- Backgrounds laufen jetzt konsequent dateibasiert ueber `background-*` in `aria/static/`
- Theme und Background lassen sich sauber kombinieren
- Label fuer neue Background-Dateien werden automatisch aus dem Dateinamen abgeleitet
- Theme-/Background-Logik wurde gegen doppelte Eintraege bereinigt

### Doku / Release / Backoffice
- `/updates` ist konsistent in `Einstellungen > Betrieb & Transfer` eingeordnet
- `/config/operations` bietet jetzt einen kontrollierten Neustart-Einstieg fuer `qdrant` und `searxng`, damit gekoppelte Systemdienste auch ohne direkten Docker-Zugriff wieder anwerfbar bleiben
- der normale `Gedaechtnis`-Setup-Pfad kann das Memory-Backend nicht mehr versehentlich stilllegen; das fruehere `Memory backend enabled`-Toggle wurde aus der UI entfernt und das Qdrant-Setup bleibt beim Speichern aktiv
- der kleine Robustheits-Gate fuer spaetere persoenliche Integrationen ist gestartet
  - Secret-/Login-basierte Connection-Karten zeigen klarer `verbunden`, `Anmeldung fehlt` oder `optional`
  - Webhook-, HTTP-API-, SMTP- und IMAP-Tests erklaeren Auth-, TLS-/SSL-, Timeout- und Reachability-Fehler produktfaehiger
  - Kalender-/Termin-Prompts bleiben im Capability-Router vorerst bewusst frei fuer den spaeteren `calendar_*`-Pfad
- die erste Google-Calendar-Connection-Foundation ist vorhanden
  - eigener Connection-Typ inklusive UI, Secure-Store-Secrets, Statuskarten und Live-Test
  - bewusst read-only geschnitten, damit ARIA den ersten persoenlichen Produktpfad ohne sofortigen Schreibzugriff vorbereiten kann
- der erste echte persoenliche `calendar_read`-Pfad ist jetzt vorhanden
  - natuerliche Kalenderprompts fuer `heute`, `morgen` und `naechster Termin` laufen in denselben Routing-/Planner-/Payload-/Guardrail-Pfad wie die anderen Connection-Typen
  - Google Calendar wird read-only ueber die neue Connection ausgefuehrt statt als Sonderwelt ausserhalb des Produktpfads
- Routing geht robuster mit natuerlichen Ziel- und Folgephrasen um
  - beschreibende Discord-Ziele wie `ops alerts channel` wirken jetzt als weiche Hinweise statt gute Treffer wieder zu blockieren
  - Follow-up-Nachrichten wie `schreib einfach TESTNACHRICHT` fuellen fehlende Inhalte sauberer in den offenen Routed-Action-Plan ein
- `Lizenz` als eigener sichtbarer Bereich inklusive Drittanbieterbezug ist vorhanden
- Hilfetexte und Mikrocopy wurden auf den Hauptseiten deutlich reduziert und enttechnisiert
- Build-/NAS-/Release-Metadaten wurden ueber die Alpha-Linie laufend nachgezogen
- Chat-Admin-/Pending-Flows fuer Connection create/update/delete, kontrollierte Updates sowie Backup-/Info-Aktionen wurden aus `aria/main.py` in `aria/web/chat_admin_flows.py` gezogen
- Routed-Action-/Safe-Fix-/Memory-Forget-Pending-Flows sowie die Chat-Follow-ups fuer neue Pending-Aktionen wurden aus `aria/main.py` in `aria/web/chat_pending_flows.py` gezogen
- Cookie-Scoping, Cookie-Naming, Request-/Response-Cookie-Helfer und Auth-Cookie-Clearing wurden aus `aria/main.py` in `aria/web/cookie_helpers.py` gezogen
- Auth-Session-Encoding/-Decoding, scoped Auth-Cookie-Reads, Session-Max-Age-Sanitizing und CSRF-Token-Erzeugung wurden aus `aria/main.py` in `aria/web/auth_session_helpers.py` gezogen
- Runtime-Bundle-Bau, Runtime-Reload-Swap und Startup-Diagnostics-State wurden aus `aria/main.py` in `aria/web/runtime_manager.py` gezogen
- Runtime-Stabilitaet wurde als eigener Alpha-Block abgeschlossen
  - Runtime-Reload baut neue Bundles ausserhalb des Locks und fuehrt Diagnostics zentral ueber den Runtime-Manager
  - Runtime-Preflight/Health/Updates folgen jetzt einem gemeinsamen Laufzeitpfad statt verteilten Schattenzustaenden
  - die verbleibende `/chat`-Ausfuehrungsorchestrierung lebt jetzt in `aria/web/chat_execution_flow.py` statt weiter halb in `main.py`
- der Monolith-Abbau hat die beiden groessten Web-Dateien deutlich gedrueckt
  - `aria/main.py` liegt jetzt unter `1200` Zeilen
  - `aria/web/config_routes.py` liegt jetzt unter `1000` Zeilen
- der verbleibende innere Profil-/Embedding-/Sample-Helper-Block aus `aria/web/config_routes.py` lebt jetzt in `aria/web/config_profile_helpers.py`, waehrend die alte Moduloberflaeche fuer Tests und Monkeypatches stabil blieb
- der `/connections`-Hub (`overview`, `status`, `types`, `templates`) sowie der Sample-Import wurden aus `aria/web/config_routes.py` in `aria/web/connections_surface_routes.py` gezogen
- die per-Typ-GET-Seiten fuer `ssh`, `sftp`, `smb`, `discord`, `webhook`, `smtp`, `imap`, `http-api`, `searxng`, `rss` und `mqtt` wurden aus `aria/web/config_routes.py` in `aria/web/connection_detail_routes.py` gezogen
- die Connection-Mutationsrouten fuer Save/Test/Delete, SSH-Key-Setup sowie RSS-Import/-Export wurden aus `aria/web/config_routes.py` in `aria/web/connection_mutation_routes.py` gezogen
- die verbleibenden Connection-Metadata-Suggest-Routen sowie der Save/Delete-Helper-Lifecycle wurden aus `aria/web/config_routes.py` in `aria/web/connection_metadata_routes.py` und `aria/web/connection_admin_helpers.py` gezogen
- die verbleibenden Connection-Reader sowie die per-Typ-Connection-Context-Builder wurden aus `aria/web/config_routes.py` in `aria/web/connection_reader_helpers.py` und `aria/web/connection_context_helpers.py` gezogen
- die Config-Hub-/Operations-Oberflaechen inklusive gemeinsamem Seitenkontext und kontrolliertem Service-Neustart wurden aus `aria/web/config_routes.py` in `aria/web/config_surface_routes.py` gezogen
- die Persona-Oberflaechen fuer `Appearance`, `Language` und `Prompt Studio` wurden aus `aria/web/config_routes.py` in `aria/web/config_persona_routes.py` gezogen
- die Operations-Detailrouten fuer `Backup` und `Logs` wurden aus `aria/web/config_routes.py` in `aria/web/config_operations_detail_routes.py` gezogen
- die Access-Detailrouten fuer `Debug`, `Users` und `Security Guardrails` wurden aus `aria/web/config_routes.py` in `aria/web/config_access_detail_routes.py` gezogen
- die Routing- und Skill-Routing-Detailrouten (`/config/routing`, Workbench, Index-Status/Test/Rebuild sowie `/config/skill-routing*`) wurden aus `aria/web/config_routes.py` in `aria/web/config_routing_detail_routes.py` gezogen
- die Intelligence-/Workbench-Detailrouten fuer `LLM`, `Embeddings`, `Datei-Editor` und `Error Interpreter` wurden aus `aria/web/config_routes.py` in `aria/web/config_intelligence_workbench_routes.py` gezogen
- die verbleibenden Connection-Save/Test/Delete-Handler sowie SSH-/RSS-Mutationslogik wurden aus `aria/web/config_routes.py` in `aria/web/connection_mutation_handlers.py` gezogen; die FastAPI-Mutationsoberflaeche in `aria/web/connection_mutation_routes.py` verdrahtet jetzt nur noch in diese Handler
- die verbleibenden Connection-Page-Helper fuer Generic-Statuskontext, Mode-Umschaltung und Seiten-Rendering wurden aus `aria/web/config_routes.py` in `aria/web/connection_page_helpers.py` gezogen; doppelte SSH-Key-/Exchange-Implementierungen im Restfile wurden dabei entfernt
- der Connections-Hub-/Surface-Kontext fuer `/connections`, `status`, `types` und `templates` wurde aus `aria/web/config_routes.py` in `aria/web/connections_surface_helpers.py` gezogen
- die Config-Surface-Helfer fuer Return-to-/Surface-Pfade, formatierte Info-Meldungen und die Overview-Checks wurden aus `aria/web/config_routes.py` in `aria/web/config_surface_helpers.py` gezogen
- die Config-Navigation-Helfer fuer Cookie-Namen/-Scope, Return-to-Aufloesung, Redirects und logische Rueckwege wurden aus `aria/web/config_routes.py` in `aria/web/config_navigation_helpers.py` gezogen
- die verbleibenden Config-Support-Helfer fuer Guardrail-Samples, Guardrail-Optionen, SSH-Key-/Exchange-Helfer und prompt-/skill-bezogene Datei-Reload-Logik wurden aus `aria/web/config_routes.py` in `aria/web/config_support_helpers.py` gezogen
- der Update-/System-Status-Block (`/health`, Preflight, Auto-Memory-Status, `/updates*`) wurde aus `aria/main.py` in `aria/web/system_update_routes.py` gezogen
- der Doku-/Info-Block (`/help`, `/product-info`, `/licenses`, Produkt-Info-Assets) wurde aus `aria/main.py` in `aria/web/docs_surface_routes.py` gezogen
- der Auth-/Session-/Preference-Block (`/login`, `/logout`, `/session-expired`, `/set-username`, `/set-auto-memory`) wurde aus `aria/main.py` in `aria/web/auth_surface_routes.py` gezogen
- die Chat-Startseite (`/`) mit Toolbox-/Hint-/Session-Oberflaeche wurde aus `aria/main.py` in `aria/web/chat_surface_routes.py` gezogen
- die Vorbereitungs-/Cookie-Schicht der `/chat`-Route wurde in `aria/web/chat_route_helpers.py` ausgelagert, damit der eigentliche Chat-Handler weniger Pending-/Admin-/Cookie-Verkabelung traegt
- Runtime-Reload baut neue Bundles jetzt ausserhalb des Locks und fuehrt Startup-Diagnostics zentral ueber `aria/web/runtime_manager.py`, damit Reloads weniger blockieren und weniger Schattenzustand halten
- die Memory-/Qdrant-Runtime-Helfer fuer Session-Collection, Auto-Memory-Status, Qdrant-Basis-URL/Dashboard und Qdrant-Overview wurden aus `aria/main.py` in `aria/web/memory_runtime_helpers.py` gezogen
- die eigentlichen FastAPI-Chat-Endpoints fuer `/chat` und `/chat/history/clear` wurden aus `aria/main.py` in `aria/web/chat_execution_routes.py` gezogen, damit `main.py` fast nur noch App-Bootstrapping und Route-Registrierung traegt
- die Auth-/Session-Middleware fuer Request-State, Login-Gating, CSRF-Pruefung sowie Security-/Cookie-Header wurde aus `aria/main.py` in `aria/web/auth_middleware.py` gezogen
- die verbleibenden UI-/Dokument-Helfer fuer Agent-Name-Ersetzung, Chat-Badges/Fehlertexte, Markdown-/Doku-Rendering, Sprach-Labels sowie Skill-/Kalender-Helfer wurden aus `aria/main.py` in `aria/web/main_ui_helpers.py` gezogen; `main.py` behaelt dafuer Import-Aliase und bleibt als Oberflaeche stabil
- der verbleibende Config-/Datei-/Update-Helferblock fuer Raw-Config-Cache, Datei-/Prompt-Aufloesung, Bootstrap-Admin-Write, Release-/Update-Metadaten, Pricing-Lookup und Model-Loading wurde aus `aria/main.py` in `aria/web/main_config_helpers.py` gezogen; `main.py` behaelt die alten Namen bewusst als Alias-Oberflaeche
- der verbleibende Request-/Sanitizer-Helferblock fuer Skill-Routing-Infotexte, lokalisierte Custom-Skill-Beschreibungen, Username-/Role-/Session-/CSRF-Sanitizing und Username-Aufloesung wurde aus `aria/main.py` in `aria/web/main_request_helpers.py` gezogen; `main.py` behaelt auch hier die alten Namen als Alias-Oberflaeche
- der verbleibende Runtime-/Profile-/Support-Helferblock fuer Prompt-Dateiliste, Profilzustand, Secure-Store-Zugriff, Auth-Manager, aktive Admin-Zaehler, Runtime-Preflight und Update-Finished-Checks wurde aus `aria/main.py` in `aria/web/main_runtime_support_helpers.py` gezogen
- kleinere Config-Utility-Helfer fuer CSRF-/Ref-Sanitizing, Embedding-Fingerprint-/Modell-Labels, Session-Timeout-Labels, Memory-Point-Totals und Datei-Editor-Zeilen wurden aus `aria/web/config_routes.py` in `aria/web/config_misc_helpers.py` gezogen; das Restfile behaelt dabei bewusst Alias-Namen fuer die bisherigen Test-/Import-Kanten
- die groesseren Connection-UI-/Schema-Helfer fuer Form-Felder, Toggle-Bloecke, Intro-/Statuskarten und Edit-URL-Aufbereitung wurden aus `aria/web/config_routes.py` in `aria/web/connection_ui_helpers.py` gezogen; `aria/web/config_routes.py` behaelt wieder Alias-Namen fuer die bestehenden Aufrufer
- die verbleibenden Connection-/Factory-/SSH-Support-Helfer fuer Factory-Reset, Qdrant-Wipe, SSH-Key-Management, Connection-Metadaten, RSS-Dedupe, Sample-Zeilen und SSH-Key-Exchange wurden aus `aria/web/config_routes.py` in `aria/web/connection_support_helpers.py` gezogen; auch hier behaelt `aria/web/config_routes.py` die alten Namen als Kompatibilitaets-Aliase
