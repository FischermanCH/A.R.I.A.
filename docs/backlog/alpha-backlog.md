# ARIA - Alpha Backlog

Stand: 2026-05-12

Zweck:
- schlanker Arbeits-Backlog fuer die laufende Alpha-Linie
- oben stehen nur noch offene Punkte und naechste Schritte
- bereits gelieferte Aenderungen stehen im `CHANGELOG.md`
- groessere Zukunftsthemen stehen in `docs/backlog/future-features.md`

Aktueller Release-Stand:
- eine sichtbare Release-Kennung pro Code-Linie
- aktuell gebaut: `0.1.0-alpha251`
- aktuell in Arbeit: Public-Release-Closure / Public-Push-Vorbereitung
- public zuletzt veroeffentlicht: `0.1.0-alpha167`

## Offen auf einen Blick

Nach `alpha247` ausgewertet:
- Multi-Target SSH ist live gruen: `check mal ob meine server noch genug festplatten platz haben` prueft 13 SSH-Ziele ohne Rueckfrage
- Restart-Safety ist live gruen: `starte meinen dns server neu` erzeugt einen mutierenden Draft und wird blockiert
- Live-Sequenz ist gruen: Management-HD, DNS-Health, API-Reachability, Discord-One-Click-Confirm, SMB-Root-Listing
- keinen weiteren Build starten, bis der Build explizit angefordert wird

Nach `alpha248` ausgewertet:
- Multi-Target SSH mit Operator-Wording ist live gruen: `check mal die festplatten von meinen server und melde mir falls handlungsbedarf besteht`
- all-ok Antwort bleibt kurz: `Gesamt: 13/13 SSH-Ziele unauffaellig. Kein Handlungsbedarf.`
- Detailspur enthaelt weiterhin alle ausgefuehrten SSH-Ziele
- RSS-Security-News brauchen nutzbaren Haupttext statt Ein-Zeilen-Digest; Fix vorbereitet: Links, Quelle, Zeit und Kurztext bleiben im Chat sichtbar
- kleine Nachzuege: `requested_ref=n server` sauberer extrahieren; Guardrail-ID-Tippfehler `ssh-healtcheck` bereinigen

`alpha249` gebaut:
- enthaelt RSS-Digest-Verbesserung mit Links/Quelle/Zeit/Kurztext
- enthaelt Public-Update-Safety-Nachzug im internen Build-Image
- Artefakt: `/mnt/NAS/aria-images/aria-alpha249-local.tar`
- Image: `fischermanch/aria:0.1.0-alpha.249` / `aria:alpha-local`
- Image-ID: `sha256:7c9a875daba4991020b09961641ddeb11b8d553ec3f20be0719073bf5cc19173`
- Verifikation: RSS-/Pipeline-/Release-Hygiene `203 passed`; Update-Helper-/Host-Update-/Managed-Setup-/Update-UI-/Release-Hygiene `36 passed`; Compile/Syntax/Diff/Container-Smoke gruen

Nach `alpha249`-Live-Test vorbereitet, noch nicht gebaut:
- RSS-Digests geben URLs jetzt explizit als `Link:`-Zeile aus, damit Copy/Paste die Links nicht verliert
- `requested_ref=n server` Parser-Artefakt entfernt; generische Plural-SSH-Prompts bleiben ohne falschen Zielnamen
- Verifikation: gezielte RSS/Router-Tests `72 passed`; Pipeline/Release-Hygiene `184 passed`; Compile und `git diff --check` gruen

`alpha250` gebaut:
- enthaelt die Nachzuege aus dem `alpha249`-Live-Test
- Artefakt: `/mnt/NAS/aria-images/aria-alpha250-local.tar`
- Image: `fischermanch/aria:0.1.0-alpha.250` / `aria:alpha-local`
- Image-ID: `sha256:6169fdcfff5a2d0f39de4d073c7455a34db77b87ea654cf7116553974792a6ad`
- Verifikation: RSS-/Router-/Pipeline-/Release-Hygiene `256 passed`; Compile/Diff/Container-Smoke gruen

`alpha251` gebaut:
- enthaelt Host-Update-Port-Preflight fuer Public-Release-Safety
- Artefakt: `/mnt/NAS/aria-images/aria-alpha251-local.tar`
- Image: `fischermanch/aria:0.1.0-alpha.251` / `aria:alpha-local`
- Image-ID: `sha256:3aacbe8145da283dddaeb9c8cdef0b56961b05119770df1871570f0e26388321`
- Verifikation: kompletter Testlauf `1023 passed`; i18n strict, Compile, Diff, Container-Smoke gruen
- Update-Pfad-Test: isolierter Managed-Stack auf Port `18831`, nur `aria` recreated, Qdrant/SearXNG/Valkey stabil

Naechste Produkt-/Cleanup-Bloecke:
- Public-Release-Closure `alpha251`: finaler Build erst nach gruenem Testlauf und sauberem Update-Pfad
- Public Push/Tag erst nach letzter Freigabe, weil `alpha251` noch den Host-Update-Port-Preflight nachzieht
- Nach Public: Agentic Intelligence nach Live-Testdaten weiter vereinheitlichen, nicht auf Verdacht neue Spezialfaelle bauen
- Nach Public: Legacy-/Recipe-Cleanup weiterfuehren, aber Safety- und Backcompat-Bruecken bewusst erhalten

Pre-Public-Cleanup:
- Git-Hygiene: Arbeitsbaum ist gross und muss vor Public Release in reviewbare Bloecke/Commits zerlegt werden
- Docker-Hygiene: viele alte Alpha-Images und Build-Cache sind lokal vorhanden; Cleanup erst nach Update-Pfad-Freigabe und ohne laufenden Stack zu gefaehrden
- Update-Safety: generierter Managed-Stack-Helper wurde so geaendert, dass `update` nur `aria` pullt/recreatet; Verifikation: Update-/UI-/Release-Hygiene-Tests `34 passed` vor Host-Helper-Nachzug, danach Host-Update-/Update-UI-/Release-Hygiene-Tests `36 passed`; Docker-/Update-Skript-Syntax gruen
- Update-Safety-Nachzug: Host-Update-Helper kann per `--target-image` alte Fixed-Tag-Installs sicher auf ein neues Image heben, refreshed Managed-Stack-Dateien aus dem Ziel-Image und recreatet weiter nur `aria`
- Echte Alt-zu-Neu-Probe mit temporaerem `alpha167`-Managed-Stack: Host-Helper recreated nur `aria`; Qdrant/SearXNG/Valkey-Container blieben stabil. Finaler Helper-Refresh-Test braucht den naechsten Build, weil `aria:alpha-local` aktuell noch `alpha248` ohne diesen Host-Helper-Nachzug enthaelt
- Verifikation nach Host-Update-Nachzug: Host-Update-/Update-UI-/Release-Hygiene-Tests `36 passed`; Docker-/Update-Skript-Syntax gruen
- Docker-Cleanup erledigt: lokale alte ARIA-Testtags `alpha167` und `alpha239`-`alpha245` entfernt; Build-Cache bewusst fuer den naechsten Build behalten
- Public-Release-Kommunikation nachgezogen: kuratierter GitHub/Docker-Hub Rollup-Text seit `alpha167` liegt in `docs/release/public-alpha-rollup-alpha167-to-next.md`; README und Docker-Hub-Overview beschreiben jetzt Recipes, LLM-assisted Action Planning und sichere Update-Pfade statt Skills-first Architektur
- Update-Pfad-Blocker gefunden und behoben: Host-Update-Helper prueft jetzt Compose-Host-Ports vor `up --force-recreate` und bricht sauber ab, wenn z.B. ein Host-Uvicorn bereits `8800` belegt
- Isolierter Managed-Stack-Test auf Port `18831`: Host-Helper hat nur `aria` recreated; Qdrant/SearXNG/Valkey-Container-IDs blieben stabil; `/health` danach gruen
- Lokale Besonderheit: der interne `aria` Docker-Container ist nach dem absichtlich provozierten Port-Konflikt `Created`; die laufende Host-Uvicorn-Instanz auf Port `8800` ist gesund. Vor einem echten lokalen Docker-Switch muss der Host-Port bewusst freigemacht werden.

## Jetzt

### `alpha247` gebaut und live validiert
- Live-Test-Befund:
  - `check mal ob meine server noch genug festplatten platz haben` bleibt in `alpha246` weiterhin in der SSH-Profil-Rueckfrage haengen
  - Debug zeigt: pluraler SSH-Scope wird erkannt, aber nach Planner/Template-Normalisierung bleibt wieder ein stale `connection_ref`-Missing-Input uebrig
- Fix vorbereitet:
  - plurale SSH-Multi-Target-Actions werden jetzt nach Bounded Planner und Template-Normalisierung nochmals finalisiert
  - wenn der Command-Draft dann noch leer ist, wird der Agentic SSH Resolver spaet erneut gefragt
  - das Ergebnis wird danach als Multi-Target-Payload mit `connection_refs` und ready Action-Decision gesetzt
- Verifikation:
  - gezielte Mehrzahl-/Live-Sequenz-Regressions: `7 passed`
  - breiter Pipeline/Planner/Dry-Run/Agentic/i18n-Core-Block: `267 passed`
  - `python -m compileall aria`: gruen
- Build-Nachzug:
  - Release-Label fuer `alpha247` gebaut
  - LiteLLM ist keine harte ARIA-Basisdependency mehr: das Python-Paket definiert ein optionales `model-gateway`-Extra, Docker installiert dieses Extra explizit, und LLM/Embedding-Clients laden LiteLLM erst beim konkreten Gateway-Call
  - Pricing bleibt damit von einem installierten LiteLLM-Python-Paket entkoppelt; LiteLLM GitHub Pricing JSON bleibt nur die Preislistenquelle
  - Gateway-/Kosten-/Stats-Regressionen: `46 passed`
  - finaler Vor-Build-Regressionsblock: `313 passed`
  - i18n-Code-Literal-Audit strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha247`
  - Artefakt: `/mnt/NAS/aria-images/aria-alpha247-local.tar`
  - Image: `fischermanch/aria:0.1.0-alpha.247` / `aria:alpha-local`
  - Image-ID: `sha256:78108f7d9c48f70e28ea929de3b2708b99319e03a6687d326fa24bb842c0f741`
- Live-Test nach Deployment:
  - Multi-Target SSH: `13/13` Ziele unauffaellig, kein RSS/Recipe-Drift, keine Ziel-Rueckfrage
  - Restart-Safety: mutierender `sudo systemctl restart pihole-FTL`-Draft wird blockiert, keine Healthcheck-Ersatz-Ausfuehrung
  - Management-HD: `ssh/ubnsrv-mgmt-master`, `df -h`, Tokens/Kosten sichtbar
  - DNS-Health: `ssh/pihole1`, Guardrail-Healthcheck-Bundle, fachliche Health-Zusammenfassung
  - API-Reachability: `http_api/n8n-test-http-api`, Pfad `/`, Read-only allow
  - Discord-One-Click-Confirm: Pending-Button und Versand via `discord/fischerman-aria-messages`
  - SMB-Root-Listing: `smb/fischer_ronny`, Pfad `.`

### `alpha248` gebaut und live validiert
- Nachzug:
  - Multi-Target-SSH-Flottenchecks geben bei komplett unauffaelligen Ergebnissen nur noch ein kompaktes Operator-Fazit mit `Kein Handlungsbedarf` aus
  - gemischte Multi-Target-Ergebnisse zeigen im Chat nur noch Auffaelligkeiten, blockierte Ziele und Fehler; OK-Hostdetails bleiben in der technischen Detailspur
  - Regression nutzt das Live-Wording: `check mal die festplatten von meinen server und melde mir falls handlungsbedarf besteht`
- Verifikation:
  - finaler Vor-Build-Regressionsblock: `317 passed`
  - `python -m compileall aria`: gruen
  - i18n-Code-Literal-Audit strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha248`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha248-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.248`
  - `aria:alpha-local`
  - `sha256:5c8643293a062dbbb009fa4a293df689ca9c9a6688504d94e1825fe33142f9a3`
- Live-Test nach Deployment:
  - Multi-Target SSH mit Operator-Wording: `13/13` Ziele unauffaellig, kompakte Antwort mit `Kein Handlungsbedarf`
  - Details enthalten weiterhin alle 13 `agentic_runtime` SSH-Ausfuehrungen
  - Plural-Scope gewinnt korrekt gegen einen einzelnen semantischen LLM-Zielvorschlag
  - aufgefallen, aber nicht blockierend: `requested_ref=n server` und Guardrail-ID `ssh-healtcheck`

### Agentic Intelligence: aktueller Stand
- Zielbild bleibt: Kontext anreichern, LLM bounded Action-Draft bauen lassen, Policy/Guardrail entscheidet, Runtime fuehrt aus
- Status: SSH, HTTP API, File, Messaging und Read laufen ueber denselben Agentic-Action-Vertrag
- deterministische Logik bleibt erlaubt fuer Routing-Hints, Normalisierung, Policy, Runtime, Summary und Compatibility, aber nicht als neue Produktlogik-Hardcodes
- Naechster sinnvoller Ausbau nach dem `alpha247`-Live-Test: weitere echte User-Ausreisser sammeln und nur daraus neue Dossier-/Policy-/Resolver-Luecken ableiten

### Naechste echte Backlog-Punkte
1. Kleine Live-Nachzuege aus `alpha248`
  - `requested_ref=n server` Parser-Artefakt bereinigen
  - Guardrail-ID-Tippfehler `ssh-healtcheck` bereinigen oder als Legacy-Alias sauber behandeln
2. Agentic Intelligence nach Live-Testdaten weiter vereinheitlichen
  - keine neuen Spezialfaelle auf Verdacht bauen
  - neue echte Ausreisser direkt als Dossier-/Policy-/Resolver-Luecke klassifizieren
  - Debug- und Cost-Signale weiter nutzen, um LLM-Drafts von deterministischen Normalisierungen sauber zu unterscheiden
3. Legacy-/Recipe-Cleanup weiterfuehren
  - Compatibility-Bruecken behalten, solange sie fuer alte Configs/Imports gebraucht werden
  - sichtbare UI-/Doku-Begriffe weiter recipe-first halten
  - alte `skill_*` Namen nur dort dulden, wo sie Browser-/Config-/Import-Backcompat sind
4. Backlog kurz halten
  - erledigte Build-Historie konsequent nur in `project.docu/alpha-build-log.md` und `CHANGELOG.md` pflegen
  - dieser Arbeitsbacklog bleibt nur fuer offene Entscheidungen, Live-Test-Fokus und naechste Schritte

### Dauer-Guardrails
- Packaging-/Release-Hygiene aktiv halten
  - kein generiertes `*.egg-info/`, `build/`, `dist/` oder `*.whl` im Workspace oder Commit
  - neue Runtime-Assets muessen von `tests/test_package_data_contract.py` oder `tests/test_release_hygiene.py` abgedeckt bleiben
  - `CHANGELOG.md` fuer alle sichtbaren Produkt-/Architektur-Aenderungen fortschreiben
- Pricing-/Kosten-Admin aktiv halten
  - LiteLLM-GitHub-Preise bleiben Source of Truth fuer Providerpreise
  - lokale Alias-/Manual-Overrides duerfen Refreshes ueberleben, muessen aber sichtbar auditierbar bleiben
- I18N-Code-Literal-Guardrail aktiv halten
  - Audit-Script: `scripts/audit_i18n_code_literals.py --strict`
  - Regression: `tests/test_i18n_code_literal_audit.py`
  - Detailreport: `docs/backlog/i18n-code-literal-audit.md`
  - aktueller Audit-Stand: 0 Treffer
  - deutsche UI-/Runtime-Texte gehoeren in `aria/i18n/*.json`
  - deutsche Eingabe-/Routing-Lexika gehoeren in `aria/lexicons/*.json`

### Bewusste Legacy-Bruecken fuer Alpha
- `skills:` bleibt vorerst lesender/kompatibler Config-Root fuer alte Installationen
- `/skills*` bleibt nur Redirect-/Backcompat-Pfad auf `/recipes*`
- `skills.*` i18n-Keys duerfen technisch noch existieren, sichtbare Texte muessen aber `Rezepte` sagen
- `aria/skills/memory.py` bleibt als Built-in-Modul bewusst unangetastet
- `skill-card` / `skills-*` CSS-Klassen duerfen als Style-Altlast bleiben, solange sie nicht als Produktbegriff sichtbar sind

### Recipe-First Zielbild Kurzfassung
- `Recipe Memory`: was ARIA aus Nutzung gelernt hat
- `Recipe Candidate`: was fuer eine Anfrage relevant sein koennte
- `Executable Plan`: was jetzt konkret ausgefuehrt wird
- `Policy / Guardrails`: was erlaubt, bestaetigungspflichtig oder blockiert ist
- `Runtime Adapter`: wie technisch ausgefuehrt wird
- neue Intelligenz entsteht bevorzugt aus Dossier + Planner + Policy + Summary + Learning, nicht aus starren Skills

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

### Core-Architektur
- `recipe_runtime.py` nach Executor-Domaenen schneiden
- `pipeline.py` als Orchestrator weiter verschlanken
- gemeinsame Helper statt Copy-Paste schrittweise konsolidieren

### Recipe-Automation
- Recipes als kontrollierte Arbeitsmuster unter natuerlicher Sprache weiter staerken
  - Connections = wohin
  - Routing = welches Ziel und wofuer
  - Recipes / Guardrails / Runtime-Adapter = wie sicher ausgefuehrt wird
  - Scheduler / Cron = wann es automatisch laeuft
- strukturierte Recipe-Outputs weiter ausbauen
- Recipe-Fehler-/Skip-Zustaende im UI und in Activities sauberer machen
- Chat-zu-Recipe-Candidate-Flow weiter vorbereiten

## Erledigt in der laufenden Alpha-Linie

Hinweis:
- Details stehen im `CHANGELOG.md`
- Build-Historie steht in `project.docu/alpha-build-log.md`
- hier bleiben nur noch die offenen naechsten Schnitte sichtbar
