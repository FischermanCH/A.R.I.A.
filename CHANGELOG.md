# Changelog

All notable changes to ARIA should be documented in this file.

Format: `Added` / `Changed` / `Fixed` / `Security` / `Known Limitations` / `Upgrade Notes`

## [Unreleased]

No entries yet.

## [0.1.0-alpha.125] - 2026-04-24

Public hotfix release on top of `0.1.0-alpha.124`.

### Fixed
- managed GUI updates now try one automatic `./aria-stack.sh repair` when the post-update `validate` step still fails once; this closes the painful half-updated state where the image changed but config/data mounts still needed a manual repair
- the managed stack helper now treats `qdrant`, `searxng-valkey`, `searxng`, `aria`, and `aria-updater` as one runtime group for `repair`, `restart`, and `update`, so a repair no longer leaves stateful sidecars on stale bind mounts
- the update helper now self-heals stale red `/updates` states: if the stored helper status says `error`, but `./aria-stack.sh validate` is already clean again, the helper resets itself back to `ok` instead of showing an old failure forever

### Upgrade Notes
- this release is recommended immediately for managed installs using `/updates`
- if a previous update left `/updates` red even after `./aria-stack.sh repair`, `alpha125` will clear that stale helper state automatically once the stack validates cleanly
- if a previous managed update recreated `aria` but left `qdrant` or `searxng` on stale mounts, `alpha125` makes future repair/update runs recreate the whole managed runtime group together

## [0.1.0-alpha.124] - 2026-04-24

Public hotfix release on top of `0.1.0-alpha.123`.

### Fixed
- managed GUI updates now resolve the real host-side source path behind the updater's `/managed` bind mount before they call `docker run ... /app/docker/setup-compose-stack.sh`; this fixes the false `/managed/.env` lookup on existing managed installs

### Upgrade Notes
- this release supersedes `alpha123` for managed installs using `/updates`
- if a previous GUI update stopped during `Refresh managed stack files`, upgrade to this release once and rerun the managed update

## [0.1.0-alpha.123] - 2026-04-24

Public hotfix release on top of `0.1.0-alpha.122`.

### Fixed
- managed GUI updates no longer abort the whole update run just because the stack-file refresh helper cannot re-open the managed install through `docker run ... /app/docker/setup-compose-stack.sh`; existing managed installs now continue with their current `.env` and `docker-compose.yml` instead of failing early with `Bestehende Env-Datei nicht gefunden: /managed/.env`

### Upgrade Notes
- this release is recommended immediately for managed installs using `/updates`
- if a previous `alpha122` GUI update already pulled the image but stopped during stack refresh, rerun the managed update after upgrading to this hotfix

## [0.1.0-alpha.122] - 2026-04-24

Public roll-up release covering the internally tested `alpha122` to `alpha167` line since the previous public `alpha121` release.

### Added
- ARIA now has a first real personal end-user path:
  - a dedicated `Google Calendar` connection type with secure secret storage, a guided setup flow, and a read-only live test
  - natural calendar prompts such as `was steht heute in meinem kalender?` and `wann ist mein naechster termin?` now route into the shared planner/guardrail execution path
- ARIA now has a first `Notes / Notizen` product path:
  - a dedicated `/notes` surface with folders, board view, editor, delete, move, and Markdown export
  - Markdown files are the source of truth while Qdrant is used as a derived semantic index
  - notes can already be created, searched, and opened from chat and the toolbox
- ARIA now has a first `Watched Websites / Beobachtete Webseiten` connection type:
  - URL-first profile creation for websites without RSS
  - automatic title/description/alias/tag suggestions
  - grouping and connection health checks through the same connection status pipeline
- `/config/operations` now includes helper-backed restart actions for `qdrant` and `searxng`

### Changed
- the routing stack now behaves much more like one product path instead of separate chat/debug worlds:
  - live chat and the routing workbench share the same routing, planner, payload, and guardrail chain for supported connection kinds
  - Qdrant routing indexes rebuild more automatically, so users do not have to babysit the index manually
  - follow-ups, confirmations, and target hints are handled more consistently across chat and admin tooling
- the UI was cleaned up substantially across the domain hubs:
  - `Memories`, `Connections`, and `Skills` no longer repeat redundant `Next steps` teaser blocks above the real hub navigation
  - the overall menu/domain structure is calmer and more product-like
- `Notes` now behave more like a small file explorer:
  - default board-first view without an already open editor
  - direct board/editor switching instead of hidden lower-page editors
  - a standalone surface instead of hanging off the Memory sub-navigation
- the Memory Map now treats Notes as a first-class knowledge branch:
  - per-user `aria_notes_<user>` collections are shown explicitly
  - the graph now includes `Notizen` as a dedicated branch back to `/notes`
- user-facing docs were refreshed for the current product shape:
  - `README.md`
  - product docs
  - wiki drafts
  - help pages for Memory, Notes, Connections, SearXNG, and Qdrant
- the web layer was significantly simplified internally:
  - large pieces of `main.py` and `aria/web/config_routes.py` were moved into clearer route/helper modules
  - this release keeps behavior but reduces monolith pressure and maintenance drift

### Fixed
- the memory setup no longer exposes a normal UI toggle that can silently disable the whole memory backend; saving the Qdrant setup now keeps Memory enabled
- skill toggles no longer disable each other just because the current page only posted one skill group
- natural SSH disk checks such as `check mal die festplatte auf meinen dns server` now normalize to `df -h` instead of trying to execute the whole sentence as a shell command
- `Admin mode off` hints now lead directly to the real admin-mode toggle, and the old users-surface save path no longer falls into `Not Found`
- Notes editor overflow and width regressions in Safari/Firefox were fixed, and the board/editor flow no longer hides created folders or forces awkward scrolling
- watched website connection flows now jump directly into create/edit mode instead of landing at the top of a longer page
- connection test messaging for webhook, HTTP API, SMTP, and IMAP is clearer around auth, permission, TLS/SSL, timeout, and reachability failures

### Security
- controlled restart actions for `qdrant` and `searxng` now ask for explicit browser confirmation before execution
- guarded outbound and connection-backed actions now keep stronger `allow / ask_user / block` behavior across the unified planner path

### Known Limitations
- Google Calendar is intentionally read-only in this release
- Google Calendar setup is guided in-product, but still uses a manual Google OAuth / OAuth Playground flow
- refresh tokens from Google test-mode projects can still expire after seven days unless the Google-side app moves beyond testing

### Upgrade Notes
- a hard browser reload is recommended after upgrading because this release includes broader UI, CSS, and navigation changes
- if you use managed installs, `/updates` and `./aria-stack.sh update` remain the supported update paths
- if you use Google Calendar, finish the in-product setup flow once after upgrading; no automatic account migration is needed
- Notes use Markdown as the source of truth and Qdrant only as the derived search index, so semantic note search still expects a working Qdrant-backed Memory setup

## [0.1.0-alpha.121] - 2026-04-16

Public roll-up release covering the already internally tested `alpha111` to `alpha121` line since the previous public `alpha110` release.

### Added
- `/config/routing` now exposes a Qdrant-backed routing index admin/debug surface with status, rebuild, testbench output, and live-routing controls for bounded candidate routing
- SSH and SFTP profiles now support a `Service URL`; ARIA can use the linked page plus the active UI language to draft routing-friendly titles, descriptions, aliases, and tags
- SSH profile creation can optionally create a matching SFTP profile with the same connection basics in one step
- `Memory Map` now surfaces routing/system collections in both the textual overview and the graph, so routing data is visible without mixing it into semantic user memory

### Changed
- runtime reloads now build a fresh runtime bundle and swap it atomically under a lock, which reduces stale-state drift after config saves and profile changes
- managed update validation now compares `config`, `prompts`, and `data` host/container views and surfaces the real failing check in the update UI instead of only a generic `exit code 1`
- connection metadata helpers now align generated routing hints more closely with the active UI language, which improves German/English routing coverage for SSH, SFTP, and RSS profiles
- `/config/routing` now includes the live Qdrant-routing controls directly in the UI, including threshold, candidate limit, and low-confidence fallback behavior
- the routing stack now keeps deterministic exact-name and alias matches first, then optionally consults the bounded Qdrant candidate set instead of jumping straight into generic chat behavior
- connection pages make the primary create action more prominent and support richer routing-oriented metadata via titles, descriptions, aliases, tags, and service context
- safety-sensitive SSH custom-command rendering now quotes user query placeholders more defensively, and guardrail matching uses stricter token/boundary behavior for simple deny terms

### Fixed
- managed update and update-button regressions from the internal `alpha111` to `alpha121` line are rolled up into this public release, including stronger mount validation for managed installs and clearer recovery guidance via `./aria-stack.sh repair`
- natural SSH questions such as `Wie lange laeuft mein DNS Server schon?` and `Wie lange ist mein DNS Server schon online?` now route back to `ssh_command` / `uptime` instead of falling into generic chat or SFTP file reads
- natural uptime / health / runtime prompts now win over accidental SFTP `file_read` matches for server-status style questions
- first-contact SSH `known hosts` warnings are filtered from the user-visible stderr output, while real SSH errors stay visible
- routing collections on `/memories/map` are no longer easy to miss; they now appear as a dedicated system branch in the graph
- config saves keep session-cookie lifetime and related runtime settings consistent after reloads instead of quietly continuing with stale route dependencies
- provider preset confusion between chat LLM and embedding configuration pages is resolved; the LLM page again shows chat-model presets and the embeddings page embedding-specific presets
- config save redirects and the logical back-navigation flow on config and skills pages no longer strand users on blank POST result pages or same-page history loops
- explicit Discord sends resolve through the connection routing path again instead of slipping into generic chat or memory behavior

### Upgrade Notes
- managed installs can continue to use `/updates` or `./aria-stack.sh update`; if validation reports a mount mismatch, `./aria-stack.sh repair` remains the supported recovery path
- the internal TAR/NAS update flow stays a private test path; public installs should continue to use `aria-setup` or `docker-compose.public.yml`

## [0.1.0-alpha.110] - 2026-04-12

### Added
- managed stacks now expose `./aria-stack.sh repair` as an official recovery path; it regenerates the managed stack files from the configured ARIA image and recreates the runtime services before running the normal validation again

### Changed
- managed GUI updates now refresh stack files from the target ARIA image via `docker run ... /app/docker/setup-compose-stack.sh` instead of relying on the currently running updater container's bundled script, which reduces stale-helper drift during upgrades
- `./aria-stack.sh update` and `update-all` now refresh the managed stack files from the configured ARIA image before recreating services, so manual host-side updates follow the same safer recovery-aware path as the new repair flow

### Fixed
- managed runtime validation now compares the host `storage/aria-config/config.yaml` with the live container view of `/app/config/config.yaml` and fails loudly when the container does not actually see the same config state
- managed update failures now point operators directly at `./aria-stack.sh repair` when a config-mount mismatch is detected, instead of silently reporting a healthy restart while profiles appear to be missing in the UI

## [0.1.0-alpha.108] - 2026-04-11

### Fixed
- `/updates` now also performs the post-update re-login check server-side, so even an update that was started from an older browser tab or an older UI build cannot fall back into a stale pre-update session after ARIA comes back
- managed GUI updates now clear the current instance auth boundary more reliably in multi-instance setups on the same domain, reducing the chance that `white`, `neo`, or similar stacks reopen with the wrong session after pressing the update button

## [0.1.0-alpha.107] - 2026-04-11

### Fixed
- the GUI update flow now forces a clean per-instance re-login after a managed restart instead of silently reusing the old browser session, which hardens multi-instance setups on the same domain against stale-session mixups after pressing the update button
- `/updates` now redirects through a dedicated relogin path that clears the current instance cookies before returning to `/login`, so `white`, `neo`, and other managed stacks can finish updates on a clean auth boundary

## [0.1.0-alpha.106] - 2026-04-11

### Fixed
- `/config/llm` and `/config/embeddings` no longer show the wrong provider preset list; the LLM page now uses chat-model presets again and the embeddings page now uses embedding-specific presets again

## [0.1.0-alpha.105] - 2026-04-11

### Fixed
- fresh managed installs via `aria-setup` now pull the referenced Docker images before the first `docker compose up`, so a host with an older cached `fischermanch/aria:alpha` image can no longer silently come up on the wrong ARIA version after a supposedly clean reinstall

## [0.1.0-alpha.104] - 2026-04-11

### Fixed
- config save flows that were switched to the new logical `return_to` handling no longer break on pages such as `/config/appearance/save`; affected config forms redirect cleanly again instead of ending on a blank POST result page
- the shared config redirect helper now accepts an explicit `return_to` target consistently, aligning it with the skills redirect behavior and preventing silent regressions across config forms
## [0.1.0-alpha.103] - 2026-04-11

### Fixed
- the embeddings configuration page now uses embedding-specific provider presets instead of reusing the chat-LLM preset list, so fresh installs no longer suggest irrelevant chat providers such as Anthropic on the embeddings screen
- embedding preset defaults are now better aligned with proxy-based setups like LiteLLM, reducing the chance that a fresh profile setup quietly drifts toward a mismatched default embedding model

## [0.1.0-alpha.102] - 2026-04-11

### Changed
- managed installs and the managed compose template no longer inject implicit Ollama LLM or embedding defaults into the runtime environment; fresh installs now leave these runtime overrides empty unless the operator explicitly sets them
- `.env.example`, setup docs, and README environment-override notes now make it explicit that runtime env overrides are optional and should stay unset when ARIA manages saved provider profiles itself

### Fixed
- active saved LLM and embedding profiles now win over stale container environment overrides, so old managed `.env` files can no longer silently force the runtime back to `host.docker.internal` and Ollama defaults after a profile was loaded in the UI
- blank environment values no longer erase valid LLM or embedding runtime settings during config load
- managed stack reinstalls via `aria-setup` no longer materialize misleading default LLM / embedding endpoints that make profile-based setups look broken immediately after startup

## [0.1.0-alpha.101] - 2026-04-11

### Added
- custom skills support conditional steps now, so later actions can be skipped based on earlier outputs; the included Linux fleet healthcheck sample uses this to send a Discord alert only when the LLM marks a run as actionable
- `/config/llm` and `/config/embeddings` now show the active saved profile more clearly, include the effective runtime values, and expose an explicit live test action for the currently loaded profile

### Changed
- the routing foundation is now more data-driven: default routing lexica and capability/status keywords moved out of hard-coded German-heavy lists and into the shared routing lexicon layer, with the pipeline passing language context through more consistently
- chat admin/toolbox command catalog logic and pending admin action helpers were pulled out of `main.py` into dedicated web modules, reducing the size and coupling of the main application module
- `/stats` now collapses every connection family into a summary tile once more than three profiles exist and uses cached health for large groups instead of probing every profile live during first render

### Fixed
- capability detail output now follows the active UI language more consistently, including file-read and other connection-backed actions that previously still emitted German detail lines in English mode
- explicit Discord sends resolve through the connection capability path again instead of falling back into generic chat/memory behavior
- config and skills pages now use a logical app-level back target instead of raw browser history, so saving/reloading forms no longer makes the back button bounce to the same page state
- `/favicon.ico` is served through a dedicated app route again, which restores the classic favicon path for browsers that do not reliably pick up the static PNG reference alone

## [0.1.0-alpha.89] - 2026-04-10

### Changed
- managed compose installs now run a deeper post-start validation through `./aria-stack.sh validate`, so fresh installs, upgrades, and GUI-triggered managed updates confirm both ARIA health and the `aria-updater` sidecar before they report success
- managed update helpers now validate the refreshed stack after the recreate step, instead of stopping at a plain web healthcheck

### Fixed
- ARIA now compares local Qdrant storage against the live Qdrant API and surfaces a clear warning when collections exist on disk but are missing from the API; that makes partial or unloaded memory stores much easier to diagnose from `/memories/config` and `/stats`
- `aria-setup migrate` now normalizes ownership on copied Qdrant storage, which reduces the risk that migrated collections stay on disk but are not loaded by the new managed Qdrant service

## [0.1.0-alpha.88] - 2026-04-10

### Fixed
- auth sessions are now signed with the current instance scope, so a valid login cookie from one ARIA instance can no longer be accepted by another instance on the same host just because both live under the same domain with different ports
- cookie scoping prefers the actual request host and port over a potentially stale configured `ARIA_PUBLIC_URL`, which makes multi-instance setups more resilient after updates, migrations, or reused stack definitions
- managed `./aria-stack.sh update` and `restart` flows now refresh `aria-updater` together with `aria`, so the GUI update helper no longer lags one release behind the main ARIA container on managed installs

## [0.1.0-alpha.87] - 2026-04-09

### Fixed
- auth and session cookies now stay isolated more reliably across multiple ARIA instances on the same host because legacy shared cookies are no longer reused for login/session state after scoped cookies are active
- managed compose installs now write an explicit `ARIA_COOKIE_NAMESPACE`, so browser-side state remains instance-local even if multiple ARIAs share one hostname

## [0.1.0-alpha.86] - 2026-04-09

### Fixed
- `aria-setup` respects explicitly passed install values better during interactive runs instead of prompting for the same `--stack-name`, `--install-dir`, `--http-port`, or `--public-url` again
- the managed install health check now verifies ARIA locally through `127.0.0.1:<ARIA_HTTP_PORT>/health` instead of depending on the public/browser URL during first start
- first-start health checks for managed installs now retry until ARIA is really ready, instead of failing too early on a short startup race directly after `docker compose up -d`
- the public `aria-setup` download flow works again end to end when it has to fetch its helper from GitHub on demand

## [0.1.0-alpha.85] - 2026-04-09

### Added
- die Chat-Toolbox kennt jetzt auch Websuche, Stats, Aktivitäten, Config-Backups und kontrollierte Updates; Admins koennen damit neue Systemfunktionen direkt aus dem Chat starten oder als Link/Statusauskunft anstossen, statt nur ueber die jeweiligen UI-Seiten zu gehen
- `/updates` zeigt jetzt zusaetzlich eine konkrete sichere Update-Sequenz fuer interne `aria-pull`-Setups, Docker Compose und Portainer, damit der Update-Weg direkt in der GUI sichtbar ist
- Managed-Compose-Installationen bringen jetzt einen separaten `aria-updater`-Helper mit; Admins koennen dadurch auf `/updates` ein kontrolliertes GUI-Update mit Status und Log-Auszug anstossen, statt fuer jeden normalen Release wieder auf den Host zu wechseln
- der interne lokale `aria-pull`-/Portainer-Stack kann denselben `/updates`-Button jetzt ebenfalls ueber einen eigenen `aria-updater`-Sidecar nutzen; damit bleibt der gewohnte TAR-/NAS-Update-Weg erhalten, wird fuer Admins aber direkt aus ARIA heraus startbar
- neuer Host-Helper `docker/aria-host-update.sh` erkennt Compose-basierte ARIA-Stacks auf einem Host und aktualisiert gezielt nur den `aria`-Service eines gewaelten Projekts; damit gibt es fuer Multi-Setup-/Portainer-Hosts einen sichereren Update-Weg ausserhalb des Containers
- fuer Host-Updates gibt es jetzt zusaetzlich eine optionale Vorlage `docker/aria-host-update.env.example`, damit Portainer-Zugangsdaten spaeter sauber aus einem dedizierten Host-Update-Kontext oder aus einer kuenftigen UI/DB-Schiene in denselben Helper fliessen koennen
- neues Setup-Script `docker/setup-compose-stack.sh` erstellt jetzt einen kontrollierten ARIA-Compose-Stack in einem eigenen Verzeichnis inklusive `.env`, bind-mount-basiertem `storage/` und lokalem `aria-stack.sh` fuer Start/Status/Updates
- neues Top-Level-Script `aria-setup` dient jetzt als benutzerfreundlicher Ein-Befehl-Einstieg fuer Docker-Installationen, fragt nur fehlende Werte interaktiv ab und kann den niedrigeren Compose-Setup-Helper bei Bedarf auch direkt von GitHub nachladen
- `aria-setup upgrade` aktualisiert jetzt bestehende verwaltete Compose-Installationen auf neue Stack-Layouts, behaelt vorhandene `.env`-Werte und Secrets bei und ergaenzt fehlende Dienste wie `searxng` ohne Neuaufbau des kompletten Hosts
- `aria-setup` erkennt jetzt bestehende verwaltete ARIA-Installationen automatisch und schaltet bei genau einem passenden Fund selbststaendig vom Neuinstallations- in den Upgrade-Pfad um; bei mehreren Funden wird interaktiv ausgewaehlt oder im non-interactive Modus sauber abgebrochen
- `/config/backup` kann jetzt die komplette ARIA-Konfiguration als einzelne JSON-Datei exportieren und spaeter wieder importieren; enthalten sind `config.yaml`, Secure-Store-Secrets und Benutzer, Prompt-Dateien, der Error-Interpreter sowie Custom-Skill-Manifeste
- `/config/security` zeigt jetzt ein direkt importierbares Guardrail-Starter-Pack aus `samples/security`, damit neue Installationen schneller mit wiederverwendbaren SSH-, Datei-, HTTP- und MQTT-Guardrails starten koennen
- die mitgelieferten Skill-Samples wurden um neue Vorlagen fuer Service-Status via SSH, Memory-Pressure via SSH und eine kuratierte RSS-Security-Watchlist erweitert; sie tauchen wie die bestehenden Samples direkt im Skills-UI auf

### Changed
- die Docker-/Compose- und lokalen Stack-Samples schreiben die benoetigte SearXNG-Konfiguration jetzt direkt beim Containerstart nach `/etc/searxng/settings.yml`; damit bleibt der Setup-Weg ohne manuelles Host-File robust, auch wenn Compose-/Portainer-Umgebungen Docker-`configs` nicht sauber bis in den Container durchreichen
- `docker-compose.managed.yml` und `docker/setup-compose-stack.sh` erzeugen jetzt zusaetzlich den internen `aria-updater`-Dienst, hinterlegen dafuer ein eigenes Update-Token in `.env` und geben Managed-Stacks damit einen standardisierten GUI-faehigen Update-Endpunkt
- die lokalen Portainer-/`aria-pull`-Stack-Dateien bringen jetzt ebenfalls einen `aria-updater`-Dienst samt eigenem Healthcheck mit; der ARIA-Container und der Helper teilen sich damit denselben kontrollierten Update-Button, ohne dass der bestehende Qdrant-/Volume-Pfad angeruehrt wird
- die lokalen Helper-Skripte fuer `aria-pull`/Build-Export muessen keine separate SearXNG-Settings-Datei mehr neben das TAR kopieren, weil die Stack-Dateien die Konfiguration jetzt selbst mitbringen
- `docker/export-local-build.sh` und `docker/pull-from-dev.sh` liefern jetzt sowohl den neuen Host-Update-Helper als auch `aria-setup` zusammen mit den bestehenden lokalen Update-Artefakten aus, damit Zielhosts den kompletten verwalteten Setup-/Update-Weg ohne zusaetzliches Nachziehen direkt nutzen koennen
- der Host-Update-Helper kann Registry-/Public-Portainer-Stacks jetzt optional direkt ueber die Portainer-API aktualisieren, wenn `PORTAINER_URL` und `PORTAINER_API_KEY` gesetzt sind; damit muessen Portainer-Stacks nicht mehr ueber wegkopierte YAML-Dateien gepflegt werden
- `docker-compose.managed.yml` bildet jetzt zusammen mit `aria-setup` den neuen kontrollierten Standard fuer Compose-Installationen mit sichtbaren Bind-Mounts statt anonymen Volumes; Portainer bleibt moeglich, ist aber nicht mehr der bevorzugte Setup-Weg
- die GitHub-/Docker-Dokumentation erklaert den Install- und Update-Prozess jetzt klarer in Englisch und trennt sauber zwischen `aria-setup`, manuellem Compose, Portainer und internem `aria-pull`
- GitHub-README, Setup-Doku und Docker-Hub-Overview fokussieren den Oeffentlichkeitsweg jetzt auf `aria-setup` und manuelles Docker Compose; Portainer bleibt nur noch als Legacy-Hinweis im Hintergrund statt als gleichberechtigter Hauptpfad
- `/updates` startet den GUI-Update-Lauf jetzt ohne harten Seitenwechsel direkt in-place, zeigt den Running-State prominenter als eigene Live-Karte und verbindet sich nach einem kurzen ARIA-Recreate ueber Helper-/Health-Polling automatisch wieder
- die Chat-/Config-Schiene liest Custom-Skill-Manifeste und rohe `config.yaml`-Daten jetzt ueber mtime-basierte In-Memory-Caches, statt dieselben Dateien pro Seitenaufruf immer wieder komplett neu zu parsen

### Fixed
- Chat-Antworten koennen jetzt auch sichere interne Markdown-Links wie `/updates` oder `/config/backup/export` rendern; dadurch funktionieren neue Chat-Hilfen fuer Backup, Update, Stats und Aktivitäten als echte klickbare Aktionen statt nur als Text
- auf `/config` und `/config/connections/searxng` zeigt ARIA jetzt klar, wenn der SearXNG-Stackdienst fehlt oder nur mit Warnstatus antwortet, statt die Websearch-Connection kommentarlos wie einen normal verfuegbaren Dienst wirken zu lassen
- ein `HTTP 403` vom internen SearXNG-Stack wird nicht mehr faelschlich als "Stackdienst nicht erreichbar" dargestellt; ARIA markiert den Dienst jetzt als erreichbar mit Warnstatus und erklaert, dass meist `format=json` oder eine Limiter-/Zugriffsregel die JSON-Probe blockiert
- der interne GUI-Update-Pfad fuer `aria-pull`-Setups prueft nach dem Recreate jetzt auch ohne `curl` zuverlaessig per Container-Python auf `/health`, statt den Lauf nur mit einem uebersprungenen Host-Healthcheck enden zu lassen
- die lokalen Update-Helfer (`update-local-aria.sh`, `pull-from-dev.sh`, `aria-host-update.sh`, `export-local-build.sh`) verwenden jetzt portable TAR-Auswahl-Logik statt GNU-awk-spezifischer `match(..., ..., array)`-Muster; dadurch bricht der GUI-Update-Flow in schlankeren Runtime-Umgebungen nicht mehr mit `awk`-Syntaxfehlern ab
- der `/updates`-Button kann den Update-Helper jetzt auch per AJAX anstossen und faellt fuer Admins bei kurzen Container-Restarts nicht mehr so leicht auf eine leere Browser-Fehlerseite zurueck
- der neue Raw-Config-Cache liefert isolierte Kopien zurueck und aktualisiert sich beim Schreiben selbst, damit Config-Seiten weniger YAML parsen muessen, ohne veraltete In-Memory-Mutationen zu riskieren
- der neue Konfig-Import versucht bei Fehlern automatisch auf den vorherigen Snapshot zurueckzugehen, statt die Instanz in einem halb importierten Zustand stehen zu lassen
- die Backup-Seite erklaert jetzt ausdruecklich, dass Connection-Profile und Connection-Secrets mitgesichert werden, lokale SSH-Key-Dateien unter `data/ssh_keys` aber bewusst ausserhalb des Exports bleiben

## [0.1.0-alpha.69] - 2026-04-08

### Added
- pre-alpha Websuche ueber self-hosted `SearXNG` ist lokal vorbereitet: eigener Connection-Typ, eigener Chat-Intent und Quellenanzeige in den Chat-Details
- die Compose-/Portainer-Stacks koennen jetzt zusaetzlich einen separaten `SearXNG`- und `Valkey`-Dienst mitfuehren, inklusive automatisch aktivierter JSON-API fuer ARIA
- `SearXNG` taucht als eigene Connection-Familie in Config, Status und Connection-Hub auf

### Changed
- `Memory`/RAG-Quellen und Web-Quellen nutzen jetzt dieselbe `detail_lines`-Schiene, damit spaetere Recherche- und Websearch-Pfade dieselbe Quellenanzeige im Chat verwenden koennen
- die SearXNG-Stacks nutzen jetzt eine statische `searxng.settings.yml` statt eines Shell-Bootstrap-Blocks im Compose/Portainer-Stack; `secret_key` und Valkey-URL kommen ueber normale Container-Umgebungsvariablen
- SearXNG-Profile in ARIA fragen die Stack-URL nicht mehr pro Verbindung ab; ARIA nutzt dafuer standardmaessig `http://searxng:8080` aus dem Stack bzw. einen zentralen Override und laesst pro Profil nur noch Suchverhalten und Routing-Metadaten konfigurieren
- die SearXNG-Config-Seite ist jetzt schlanker: Kategorien und Engines werden per Checkboxen gepflegt, dazu Sprache, SafeSearch, Zeitbereich, Trefferzahl sowie Name, Aliase und Tags fuer Routing wie `youtube` fuer Videos oder `startpage` fuer Buecher
- der globale Restart-/Health-Poll im Frontend laeuft fuer eingeloggte Seiten jetzt deutlich ruhiger ueber einen getakteten Timeout-Loop statt alle 3 Sekunden per `setInterval`; beim Zurueckkehren in einen sichtbaren Tab wird dafuer einmal zeitnah nachgeprueft
- Connection-Seiten zeigen bestehende Health-/Test-Resultate jetzt standardmaessig aus dem Cache statt beim bloessen Oeffnen sofort neue Live-Probes gegen SSH, SFTP, Discord, HTTP, SearXNG oder MQTT zu fahren; fuer frische Live-Checks bleiben die vorhandenen Test-Buttons zustandig
- der Public-Docker-Weg ist jetzt auf einen konsistenten SearXNG-Stack gezogen: `docker-compose.public.yml`, `docker/portainer-stack.public.yml`, `.env.example` und die Quick-Start-Doku zeigen denselben Compose-/Portainer-Schnitt fuer ARIA + Qdrant + SearXNG + Valkey

### Fixed
- explizite Websuche mischt keinen Auto-Memory-Recall mehr in die Quellen; Web-Details bleiben dadurch bei Anfragen wie `recherchiere im web ...` sauber auf Web-Treffer fokussiert
- SearXNG-Connection-Tests und Websuche geben bei `HTTP 429 Too Many Requests` jetzt einen klaren Hinweis auf den internen Stack-Fix mit `SEARXNG_LIMITER=false`, statt nur den rohen Fehler weiterzureichen
- der interne `aria-pull`-/`update-local-aria`-Flow ueberfaehrt den laufenden Qdrant-Key nicht mehr still mit einem veralteten Wert aus `aria-stack.env`; bei Abweichungen nutzt ARIA fuer den reinen Service-Recreate jetzt den aktiven Live-Key des laufenden Stacks und vermeidet dadurch `HTTP 401 Unauthorized` gegen Qdrant nach Key-Rotationen im Portainer-Stack
- Websuche uebergibt erkannte Trefferdaten jetzt sichtbarer in den Chat-Kontext: Treffer mit publiziertem Datum zeigen ihr Datum in den Details, und bei klaren Recency-/Release-Anfragen werden datierte Ergebnisse fuer die Antwortvorbereitung staerker nach oben sortiert
- explizite Formulierungen wie `suche im internet ...` oder `recherchiere im internet ...` werden jetzt sauber als Websuche erkannt und nicht mehr von der Feed-/RSS-Heuristik als `feed_read` uebernommen
- interne SearXNG-Probes und die eigentliche Websuche senden fuer Stack-Ziele jetzt zusaetzlich lokale Proxy-/IP-Header mit; das macht den internen JSON-API-Pfad robuster gegen Bot-Detection/Proxy-Pruefungen, solange der Dienst ueber `http://searxng:8080` im Stack angesprochen wird
- die Websuche filtert generische Treffer ohne sinnvollen Query-Bezug jetzt haerter weg und priorisiert thematisch passende Ergebnisse vor bloessen `news`-/SEO-Treffern; dadurch rutschen irrelevante Quellen wie fachfremde Sammelseiten bei Produkt-News deutlich seltener in die Antwort

### Security

### Known Limitations
- Websuche ist bewusst noch ein pre-alpha Block: ARIA nutzt die Top-Treffer aus SearXNG, aber noch kein Full-Page-Fetching oder Deep-Research-Crawling

### Upgrade Notes
- fuer interne ARIA-Stacks wird SearXNG jetzt standardmaessig ohne API-Limiter betrieben (`SEARXNG_LIMITER=false`), weil ARIA sonst schnell in `HTTP 429 Too Many Requests` fuer die JSON-API laufen kann
- fuer bestehende Portainer-Stacks aus der Zeit vor `alpha69` gilt: vorhandene Volume- und Netzwerk-Namen weiterverwenden und nur den neuen `searxng`-/`searxng-valkey`-Teil als Delta ergaenzen; den frischen Public-Sample nicht blind ueber funktionierende `aria2_*`-Volumes legen

## [0.1.0-alpha.64] - 2026-04-07
### Added
- `aria --version` und `aria version-check` stehen jetzt als kleine CLI-Schnellchecks fuer installierte Version und oeffentlichen Release-Status bereit
- an zentralen Stellen wie LLM, Embeddings, Memory und RSS gibt es jetzt kurze Kontext-Hinweise mit Direktlink zur passenden Help-Seite
- neue Sample-Skills erweitern die mitgelieferte Sammlung um RSS-Headlines fuer Chat, SSH-Disk-Usage und eine SFTP-Config-Vorschau

### Changed
- LLM- und Embedding-Nutzung laeuft jetzt ueber eine zentrale Metering-Schicht statt nur ueber den Chat-/Pipeline-Pfad; damit koennen kuenftige Modellfunktionen konsistent ueber dieselbe Kosten- und Token-Erfassung laufen
- direkte Hilfs- und Admin-Aufrufe wie RSS-Metadaten, RSS-Gruppierung, Runtime-Diagnostics, Skill-Keyword-Generierung, RAG-Ingest und Memory-Embeddings werden jetzt ebenfalls ueber denselben Token-/Kosten-Zaehler erfasst
- Pipeline-/Chat-Logs aggregieren jetzt alle innerhalb eines Runs angefallenen LLM- und Embedding-Aufrufe zentral, statt nur den letzten Haupt-LLM-Call und separat gemeldete Teilmengen zu beruecksichtigen
- statische Assets wie CSS, Logo und htmx werden jetzt pro Release mit einer Versionskennung ausgeliefert, damit Browser nach UI- und CSS-Updates weniger oft an alten Cache-Dateien haengen bleiben
- `/stats` zeigt fuer den Release-Block jetzt auch die passenden CLI-Kommandos und fuehrt Modellnutzung zusaetzlich nach Quellen wie `chat`, `rss_metadata` oder `rag_ingest` auf
- `/stats` zeigt die Quellen-Aufschluesselung fuer Requests, Tokens und Kosten jetzt zusaetzlich als eigene ausklappbare Kachel `Kosten Details`, statt die Source-Daten nur in tieferen Detailbloecken zu verstecken
- `Preise aktualisieren` in `/stats` refresht den Pricing-Block jetzt per HTMX direkt an Ort und Stelle, statt die ganze Seite neu zu laden und Scroll-/Details-Zustand zu verlieren
- auf der RSS-Seite aktivieren `Kategorien mit LLM aktualisieren`, `Jetzt pingen` und `Check mit LLM` jetzt sichtbar den globalen Busy-Zustand, damit das drehende Logo bei laengeren Aktionen klar zeigt, dass ARIA noch arbeitet
- Klicks auf Collection-Kacheln und Collection-Nodes in der `Memory Map` fuehren jetzt direkt in den passenden Collection-Inhalt statt in eine unklare `all`-Sicht; bei aktivem Collection-Filter oeffnet `Memory` die betroffenen Gruppen ausserdem automatisch
- Dokument-Stores verhalten sich in `Memory` jetzt hierarchisch: ein Klick auf eine Dokument-Collection zeigt zuerst die enthaltenen Dokumente, und erst ein Klick auf ein Dokument oeffnet die zugehoerigen Chunks
- Dokument-Recall priorisiert bei klaren Dokument-Hinweisen jetzt die passendsten Guide-Treffer deutlich enger, damit Fragen zu einem hochgeladenen Manual nicht mehr so leicht mit Chunks aus anderen Dokumenten vermischt werden
- ein Wechsel von Embedding-Modell oder API Base in `/config/embeddings` verlangt bei vorhandenem Memory jetzt eine explizite Bestaetigung und verweist direkt auf den JSON-Export, damit bestehendes Memory/RAG nicht versehentlich in einen unzuverlaessigen Zustand kippt
- Memory- und Dokument-Payloads tragen jetzt einen Embedding-Fingerprint; Recall, Suche und Dokument-Guides mischen dadurch keine alten und neuen Embedding-Generationen mehr still miteinander
- Session-Komprimierung baut jetzt echte Wochen- und Monats-Rollups mit eigener Metadatenstruktur statt nur unsichtbarem generischem Kontext-Wissen; damit wird der Weg fuer spaetere Graph-/Map-Beziehungen klarer
- die `Memory Map` zeigt jetzt zusaetzlich einen einfachen read-only Graphen fuer Typen, Collections, Dokumente und Rollups, damit gespeichertes Memory schneller visuell erfassbar wird

### Fixed
- auf `/config/connections/rss` ist der Ruecksprung zur RSS-Uebersicht im Intro jetzt ein echter Button statt nur ein unauffaelliger Link
- `/updates` zeigt jetzt unterhalb der aktuellen Release Notes auch die fuenf vorherigen Versionen als einklappbare Release-Historie mit ihren jeweiligen Release Notes
- die `Memory Map` gruppiert importierte Dokumente jetzt pro Dokument-Collection in einklappbaren Kacheln, statt alle Dokumente in einem langen Block zu mischen
- `Dokumente im Speicher` startet in der `Memory Map` jetzt standardmaessig eingeklappt, und einzelne Dokumentkarten verlinken direkt auf ihre Chunk-Ansicht
- die alte zweite Bubble-/Kachel-Wiederholung unter `Collections im Speicher` ist aus der `Memory Map` entfernt, damit Collections nicht doppelt und verwirrend erscheinen
- auf `/memories/map` gibt es jetzt zusaetzlich klickbare Collection-Kacheln fuer die vorhandenen Qdrant-Collections; ein Klick oeffnet die normale Memory-Ansicht direkt mit aktivem Collection-Filter, sodass die Eintraege dieser Collection gezielt durchgesehen, exportiert oder gepflegt werden koennen
- Buttons auf Memory-/Config-Seiten laufen auf schmalen Mobile-Viewports nicht mehr pauschal ueber die ganze Breite und sind dadurch wieder klarer als Buttons erkennbar
- auf der RSS-Verbindungsseite verwenden die Aktionsbuttons `Jetzt pingen` und `Check mit LLM` im Matrix-Theme jetzt denselben dunklen Button-Text wie die restlichen Buttons der Seite, statt schlecht lesbarer heller Schrift
- die RSS-Verbindungsseite zeigt nach `Jetzt pingen` jetzt wieder echte Feed-Artikel bzw. Headlines aus dem Feed an, statt nur den Profilnamen bzw. eine generische Erfolgsmeldung
- auf `/config/connections/rss` ist `Kategorien mit LLM aktualisieren` jetzt ebenfalls ein echter Button statt nur ein Link
- gecachte RSS-Gruppen uebernehmen beim Laden jetzt wieder die aktuellen Anzeigenamen aus den Live-Statusdaten, statt alte `ref`-basierte Profilnamen weiter anzuzeigen, wenn sich nur der Display-Name geaendert hat
- LLM-Kosten in `/stats` und den Token-Logs untererfassen jetzt nicht mehr still bestimmte Nebenpfade; auch nicht-interaktive Modellaufrufe ausserhalb des normalen Chat-Flows laufen jetzt durch denselben Metering- und Kostenpfad
- `/stats`, Token-Log-Auswertung und Log-Pruning brechen bei einem unlesbaren oder root-owned Token-Log nicht mehr hart weg, sondern fallen fail-safe auf leere bzw. unveraenderte Log-Ausgaben zurueck
- Login- und Update-Seiten geben bei neuen Releases jetzt klarere Hinweise fuer harte Browser-Reloads, falls nach UI/CSS-Aenderungen noch alte Assets sichtbar bleiben
- bestehendes Memory bleibt bei einem spaeteren Embedding-Wechsel besser abgesichert, weil alte ungetaggte Legacy-Eintraege nur so lange kompatibel bleiben, wie der konfigurierte Memory-Fingerprint nicht auf eine neue Embedding-Generation umgestellt wurde
- `Memory Map` zeigt Session-Rollups jetzt als eigene Wochen-/Monats-Sicht mit Zeitraum und Quellenanzahl, statt verdichteten Kontext nur indirekt ueber die Knowledge-Collection versteckt zu halten

### Security

### Known Limitations

### Upgrade Notes

## [0.1.0-alpha.54] - 2026-04-06

### Added
- `/help` ist jetzt ein echter lokaler Docs-Hub mit Karten, Navigation und Markdown-Rendering auf Basis derselben Quelldateien wie `docs/wiki/` und `docs/help/`
- fuer die Help-/Wiki-Inhalte gibt es jetzt mehrsprachige Seitenvarianten (`*.de.md` / `*.en.md`), damit lokale Hilfe und GitHub-Wiki dieselben Inhalte sauber in der gewaehlten Sprache ausspielen koennen
- zwei neue Spass-Themes stehen in der Appearance-Auswahl bereit: `Nyan Cat` und `Puke Unicorn`

### Changed
- der lokale Help-Hub waehlt Markdown-Dateien jetzt sprachabhaengig aus (`.de.md` / `.en.md`), damit `/help` nicht mehr aus gemischten deutschen und englischen Seiten besteht
- die Preisaufloesung fuer LLM-Kosten ist toleranter: gaengige Claude-Sonnet-Aliase wie `claude-sonnet`, `claude-3-5-sonnet-latest` oder `anthropic/claude-3-5-sonnet-latest` werden grosszuegiger auf bekannte Preis-Eintraege aufgeloest
- die Startseite unter `/config` gruppiert grosse Bereiche wie `Tune Intelligence`, `Fine-Tune Memory`, `Personality & Style`, `Connections` und `Workbench` jetzt in einklappbaren Boxen, damit die Seite bei wachsendem Umfang ruhiger und schneller scannbar bleibt
- `Dokumente importieren` und `Eigene Memory erfassen` sind auf `/memories` jetzt ebenfalls einklappbar, damit die Seite ruhiger bleibt wenn der Fokus auf der bestehenden Memory-Liste liegt

### Fixed
- wichtige Config-Seiten wie `/config/llm`, `/config/embeddings`, `/config/routing`, `/config/skill-routing` und `/config/prompts` bleiben auf iPhone-/Mobile-Viewports jetzt innerhalb der Bildschirmbreite, statt horizontal ueberzulaufen
- `CyberPunk Classic` zeigt die grossen Boxen auf `/config` nicht mehr in einem schmutzig-braunen/senfigen Ton, sondern mit klarerem Pink/Gruen-Look passend zum Theme

### Security

### Known Limitations

### Upgrade Notes

## [0.1.0-alpha.50] - 2026-04-06

### Added
- `Memory` unterstützt jetzt erste RAG-Dokument-Uploads direkt im bestehenden Bereich, ohne neues Hauptmenü oder neue Top-Level-Seite
- `txt`, `md` und `pdf` mit eingebettetem Text können in Dokument-Collections importiert, gechunkt, embedded und in Qdrant gespeichert werden
- `/stats` zeigt im Bereich `Systemzustand` jetzt einen direkten `Updates`-Eintrag mit Status und Link auf `/updates`
- Dokument-Chunks werden in `Memory` jetzt als eigener UI-Typ `Dokument` geführt, statt optisch mit normalem Rollup-Wissen zusammenzufallen
- jeder Dokument-Upload erzeugt jetzt zusätzlich einen internen Dokument-Guide mit Summary und Stichworten, damit Chat-Recall passende Dokumente gezielter vorselektieren kann

### Changed
- `/updates` und `/stats` lesen die installierte ARIA-Version jetzt aus derselben gemeinsamen Release-Metadatenquelle, damit interne und öffentliche Versionsanzeigen konsistent bleiben
- Dokument-Uploads in `Memory` arbeiten jetzt gezielt mit Dokument-Collections wie `aria_docs_*`, statt beliebige Memory-Collections zu vermischen
- `Memory` bietet jetzt einen eigenen Filter und eigene Zählung für Dokumentwissen; `Dokumente` und `Rollup-Wissen` bleiben im UI sauber getrennt
- der Dokument-Import zeigt während Chunking und Qdrant-Ingest einen sichtbaren Arbeitszustand direkt im Upload-Block, nicht nur über das drehende Logo
- importierte Dokumente werden jetzt gesammelt in der `Memory Map` verwaltet, inklusive Dokumentname, Chunk-Anzahl, Vorschau und zentralem Entfernen ganzer Dokumente aus Qdrant
- die `Memory`-Ansicht gruppiert Einträge jetzt zusätzlich nach Typ und zeigt klickbare Typ-Kacheln, damit große Mengen an Facts, Dokumenten, Session-Kontext und Rollup-Wissen nicht in einer langen Mischliste untergehen
- der Chat-Recall nutzt bei Dokumentwissen jetzt zuerst den internen Dokument-Guide-Index und fragt danach gezielt nur passende Dokument-Chunks ab, statt blind alle Dokument-Collections mitzunehmen
- Chat-Details zeigen bei Dokument-Recall jetzt die verwendeten Quellen mit Dokumentname, Collection und Chunk-Referenz an; dieselbe Detail-Schiene kann später auch für Websuche-Quellen wiederverwendet werden
- Quellen in den Chat-Details werden jetzt nutzerfreundlich sortiert: Dokumente/Web zuerst, danach stabilere Memory-Typen vor flüchtigem Session-Kontext
- die globale Restart-Erkennung lädt Seiten nach kurzen `/health`-Aussetzern nicht mehr blind neu, sondern zeigt erst nach mehreren aufeinanderfolgenden Failures einen klaren Reload-Hinweis
- das `Cyberpunk`-Theme mischt jetzt Türkis und dunkles Blau in die bisher sehr grünlastige Neon-Palette
- das ursprüngliche `Cyberpunk`-Theme ist jetzt wieder als `CyberPunk Classic` zurück; der neue Look bleibt separat als `CyberPunk Neo` auswählbar, damit bestehende Setups optisch stabil bleiben

### Fixed
- der Dokument-Upload akzeptiert serverseitig keine Nicht-Dokument-Collections mehr; falsche Collection-Wahlen werden sauber abgewiesen
- PDFs ohne eingebetteten Text geben jetzt eine klare Fehlermeldung statt still zu scheitern; Scan-/Bild-PDFs werden in RAG v1 explizit als nicht unterstützt markiert
- Multipart-Dokument-Uploads werden nicht mehr fälschlich als `Bitte eine Datei auswählen` abgewiesen; die Upload-Route akzeptiert jetzt sowohl FastAPI- als auch Starlette-UploadFile-Objekte sauber
- die Dokument-Verwaltung liegt nicht mehr unpassend mitten im normalen `Memory`-Log, sondern an der thematisch passenderen Stelle in der `Memory Map`
- der sichtbare Upload-Hinweis in `Memory` bleibt nach erfolgreichem Import nicht mehr hängen, sondern wird beim nächsten Seitenaufbau sauber zurückgesetzt
- `/updates` bleibt bei GitHub-API-Rate-Limits nutzbar und fällt für die Versionsbestimmung sauber auf den öffentlichen `CHANGELOG.md` zurück, statt dauerhaft eine störende `403 rate limit exceeded`-Warnung anzuzeigen
- der Dokument-Upload-Hinweis wird im Idle nicht mehr fälschlich angezeigt; das `hidden`-Verhalten der Statusmeldung wird jetzt auch per CSS sauber respektiert
- Discord-Systemevents zeigen beim Start nicht mehr irreführend eine Docker-Bridge-IP als Host an; ohne gesetzte `ARIA_PUBLIC_URL` meldet ARIA jetzt klar, dass die öffentliche URL nicht konfiguriert ist

### Security

### Known Limitations
- RAG v1 unterstützt bei PDFs nur eingebetteten Text; OCR und bildbasierte PDFs sind noch nicht enthalten

### Upgrade Notes

## [0.1.0-alpha.40] - 2026-04-05

### Added

### Changed
- ARIA verwendet für Login-, CSRF- und Session-Cookies jetzt instanzspezifische Cookie-Namen, damit mehrere ARIA-Container auf demselben Host mit unterschiedlichen Ports sich nicht mehr gegenseitig die Browser-Session überschreiben

### Fixed
- der automatische Logout nach wenigen Minuten in Multi-Instanz-Setups wurde behoben; Ursache waren kollidierende Cookie-Namen zwischen z. B. `aria.black.lan:8800` und `aria.black.lan:8810`
- LLM-, Embeddings-, Chat- und Memory-Flows lesen jetzt konsistent die zur aktuellen Instanz gehörenden Cookies, statt versehentlich Session- oder CSRF-Werte einer anderen ARIA-Instanz zu verwenden

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes
- bei mehreren ARIA-Instanzen auf demselben Host kann nach dem Update ein einmaliges Neuanmelden sinnvoll sein, damit alte globale Legacy-Cookies nicht mehr im Browser bevorzugt werden

## [0.1.0-alpha.39] - 2026-04-05

### Added

### Changed
- Login-Timeout und Bootstrap-Einstellungen wurden von `Security Guardrails` nach `Benutzer` verschoben; die Security-Seite fokussiert sich jetzt auf Guardrail-Profile

### Fixed
- geschützte Fetch-/JSON-Requests löschen den Auth-Cookie bei nur temporärer Security-/Auth-Store-Unverfügbarkeit nicht mehr; dadurch verschwinden Sitzungen nicht mehr “einfach so” nach einigen Minuten durch einen Nebenrequest
- der Login-Timeout bleibt damit als konfigurierbare Einstellung relevant, statt von einem separaten Session-Fehlerpfad überlagert zu werden

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.37] - 2026-04-05

### Added
- die Security-Seite zeigt den Login-Timeout jetzt zusätzlich in einer menschenlesbaren Form an, z. B. `12 Stunden` oder `1 Tag 6 Stunden`, damit große Minutenwerte nicht im Kopf umgerechnet werden müssen

### Changed
- Login-Sessions können jetzt über `Security` mit einem konfigurierbaren Default-Timeout gesteuert werden; der Wert wird intern weiter in Sekunden gespeichert und kann zusätzlich per `ARIA_SECURITY_SESSION_MAX_AGE_SECONDS` gesetzt werden
- Update-Checks bleiben für den Zustand `up to date` deutlich frischer, damit neue Public-Releases schneller in Lampe und `/updates` sichtbar werden

### Fixed
- Login-Sessions bleiben bei LLM-/Embeddings-Konfigurationen und normalen Seitenwechseln stabil, statt durch unkritische Nebenrequests oder Runtime-Reloads ungewollt verloren zu gehen
- frisch angemeldete Nutzer werden bei der Modellkonfiguration nicht mehr fälschlich auf `Login` oder `Sitzung abgelaufen` zurückgeworfen, solange die Session gültig ist

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.35] - 2026-04-05

### Added

### Changed

### Fixed
- der Auth-Cookie wird nicht mehr auf unkritischen Responses wie öffentlichen Nebenrequests versehentlich gelöscht; dadurch bleiben Login-Sessions bei `Load models`, Profilwechseln und normalen Seitenwechseln stabil
- LLM- und Embeddings-Konfigurationen können wieder zuverlässig Modelle laden und speichern, ohne Nutzer auf `Login` oder `Bitte zuerst anmelden` zurückzuwerfen

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.34] - 2026-04-05

### Added

### Changed

### Fixed
- gültige, signierte Login-Sessions bleiben jetzt auch dann erhalten, wenn der Security-/Auth-Store während eines Runtime-Reloads kurzzeitig nicht verfügbar ist; ARIA wirft Nutzer in diesem Fall nicht mehr vorschnell auf `/login`
- Debug-Header für die Session-Diagnose wurden vorbereitet (`X-ARIA-Auth-Reason`, `X-ARIA-Auth-Degraded`), damit künftige Auth-Probleme gezielter eingegrenzt werden können

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.33] - 2026-04-05

### Added

### Changed
- `Updates` wurde aus der Hauptnavigation herausgenommen und als Kachel in `/help` neben `Produkt-Info` platziert

### Fixed
- Login-Sessions bleiben in internen HTTP-/LAN-Setups stabiler, weil Auth- und Preference-Cookies nur noch dann `Secure` werden, wenn die App wirklich unter HTTPS läuft oder `ARIA_PUBLIC_URL` explizit auf `https://...` gesetzt ist
- die Client-Restart-Erkennung lädt nach einer kurzen Runtime-Unterbrechung jetzt die aktuelle Seite neu, statt Nutzer blind auf `/login` zu schicken
- die `/updates`-Seite prüft jetzt frisch gegen GitHub und ignoriert veraltete Cache-Zustände, bei denen die installierte Version neuer als die gecachte `latest`-Version ist
- der Typing-Indikator über dem Chat-Composer bleibt im Idle garantiert verborgen und hinterlässt keinen leeren Rahmen mehr

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.30] - 2026-04-05

### Added

### Changed

### Fixed
- JSON-Fetches für LLM-/Embeddings-Modelllisten erhalten bei fehlender oder abgelaufener Session jetzt saubere JSON-Fehler statt Login-HTML; die Config-UIs senden dafür explizit API-artige Request-Header und Credentials

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.29] - 2026-04-05

### Added

### Changed

### Fixed
- auth cookies trust proxy HTTPS headers more conservatively, reducing false logouts on fresh HTTP/container setups where a stray forwarded header could make the browser drop the session cookie

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.28] - 2026-04-05

### Added

### Changed

### Fixed
- `aria-pull` / `update-local-aria.sh` retaggt geladene TAR-Images jetzt korrekt auf das lokale Compose-Image-Tag wie `aria:alpha-local`, damit echte Updates nicht still auf dem alten lokalen Image hängen bleiben

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.27] - 2026-04-05

### Added
- Update-Hinweis auf Basis von GitHub-Tags plus Release-Notes-Seite unter `/updates`

### Changed
- Login-Screen und Menü zeigen jetzt ein dezentes oranges Update-Lämpchen, wenn eine neuere öffentliche Version verfügbar ist

### Fixed

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.26] - 2026-04-05

### Added

### Changed
- `README.md` now links Docker Hub directly in the header, next to the GitHub repository link.

### Fixed
- Prompt Studio no longer disables saving for editable prompt files like `prompts/persona.md`; prompt rows now carry explicit `edit` metadata and the shared editor template defaults missing modes to editable.
- LLM and Embeddings config now also create or overwrite a named profile when a different profile name is entered and the normal `Save` button or Enter key is used, instead of silently only updating the current active profile.

### Security

### Known Limitations
- ARIA is still primarily a personal single-user system
- No full shared-skill/shared-connection RBAC model yet
- Capability results are not automatically written into Memory unless modeled explicitly
- Public internet exposure is still not recommended for this ALPHA line

### Upgrade Notes
- Update the ARIA container/image, keep persistent volumes
- Hard-refresh the browser after the update if old CSS/theme assets are still cached

## [0.1.0-alpha.25] - 2026-04-04

### Added
- Added practical, human-readable DE/EN Alpha help docs (`docs/help/alpha-help-system.de.md` / `.en.md`) and made `/help` load the matching language variant

### Changed
- Chat toolbox skill entries now show the actual skill name plus a compact `/skill` badge and a wrapped description/example line, instead of repeating only `/skill` for every skill button
- In the user menu, `Help` now appears after `Config` and before `Users`, so support docs sit closer to settings but still before user administration
- `README.md` is now split into a clear English-first section and a separately labeled German section instead of silently switching language mid-document
- `README.md` now embeds the architecture diagrams directly in both language sections

### Fixed
- `Systemzustand` cards in `/stats` now expose `visual_status` as well, so ARIA Runtime, Model Stack, Memory/Qdrant, Security Store, and Activities/Logs use the same status lamps as the rest of the page

### Security
- Repo/privacy sweep: removed personal dev-host defaults from `docker/pull-from-dev.sh`, neutralized `config/secrets.env`, removed stray root artifacts `=1.2` / `=2.1`, and excluded `project.docu/` from the public repo while keeping it locally

### Known Limitations
- ARIA is still primarily a personal single-user system
- No full shared-skill/shared-connection RBAC model yet
- Capability results are not automatically written into Memory unless modeled explicitly
- Public internet exposure is still not recommended for this ALPHA line

### Upgrade Notes
- Update the ARIA container/image, keep persistent volumes
- Hard-refresh the browser after the update if old CSS/theme assets are still cached

## [0.1.0-alpha.24] - 2026-04-04

### Added
- `/skills` now exposes bundled sample-skill manifests from `/app/samples/skills` and lets admins import them directly without downloading files out of the container first
- `/config` now exposes bundled sample-connection YAMLs from `/app/samples/connections` and lets admins import them directly into `config.yaml`
- Added `rss-morning-briefing-to-discord-template.json`, a scheduled multi-RSS + LLM + Discord sample for a daily curated morning briefing

### Changed
- Product Info now only exposes user-facing docs; the internal Copy Pack card was removed from the Product Info page
- CyberPunk Pulse buttons and menu labels are now rendered in neon green for stronger theme contrast, and Deep Space was shifted toward a darker violet/nebula palette so it is less close to Harbor Blue
- Skill Wizard now explicitly documents that `llm_transform` prompts can use `{prev_output}` as well as step-specific placeholders like `{s1_output}` and `{s2_output}`

### Fixed
- `samples/` is now packaged into the Docker image, so bundled sample skills, sample connections, and sample guardrails are available inside the container as `/app/samples`

### Security

### Known Limitations
- ARIA is still primarily a personal single-user system
- No full shared-skill/shared-connection RBAC model yet
- Capability results are not automatically written into Memory unless modeled explicitly
- Public internet exposure is still not recommended for this ALPHA line

### Upgrade Notes
- Update the ARIA container/image, keep persistent volumes
- Hard-refresh the browser after the update if old CSS/theme assets are still cached


## [0.1.0-alpha.23] - 2026-04-04

### Added

### Changed
- CyberPunk Pulse theme tuned further: stronger hot-pink panel/glow treatment, while secondary helper/meta/status text and chips now use neon `#00ff00`
- `Produkt-Info` moved out of the top menu and linked from the `/help` page instead, so product docs are presented as support material rather than a main navigation item

### Fixed
- iPhone chat view no longer allows subtle horizontal side-panning/drift while scrolling; chat container and message bubbles are now locked to vertical pan with hard X-axis clipping
- `/help` and `/product-info` docs are now packaged into the Docker image, so read-only help/product pages no longer show missing-file fallbacks in container deployments
- Qdrant DB size in `/stats` no longer stops at `0 B` when telemetry reports collections but zero disk bytes; ARIA now falls through to local storage-path inspection first and only then uses the zero-byte telemetry fallback

### Security

### Known Limitations
- ARIA is still primarily a personal single-user system
- No full shared-skill/shared-connection RBAC model yet
- Capability results are not automatically written into Memory unless modeled explicitly
- Public internet exposure is still not recommended for this ALPHA line

### Upgrade Notes
- Update the ARIA container/image, keep persistent volumes
- Hard-refresh the browser after the update if old CSS/theme assets are still cached

## [0.1.0-alpha.22] - 2026-04-03

### Added
- Read-only `/help` page backed by `docs/help/help-system.md`
- Read-only `/product-info` page with overview, feature list, architecture docs, and embedded architecture diagrams
- Memory JSON export from `/memories` for the current user and current filter/search scope
- `/stats` reset flow with explicit `RESET` confirmation
- MIT `LICENSE` and `THIRD_PARTY_NOTICES.md`

### Changed
- Documentation tree reorganized into public `docs/` and internal `project.docu/history/`
- Login, Users, and Security UI now explain first-run bootstrap and Admin/User mode boundaries more clearly
- CyberPunk Pulse theme shifted toward stronger hot-pink/magenta accents
- Auto-Memory now skips transient one-off questions and pure tool/action prompts unless they contain stable facts/preferences
- Capability results are intentionally not auto-persisted to Memory by default; future durable state should use explicit summary/state-memory flows
- Memory docs/backlogs now treat weighted multi-collection recall and JSON export as Public Alpha scope, while session rollup and reindex remain post-alpha work

### Fixed
- More robust Qdrant DB size fallback for separate Docker/Portainer Qdrant volumes mounted read-only into the ARIA container
- Long `Tages-Kontext` / `Login-Session` debug IDs no longer cause horizontal overflow on iPhone chat screens
- Help-file tests updated to the new `docs/help/...` paths

### Security
- Third-party attribution for Qdrant and key runtime dependencies documented explicitly

### Known Limitations
- ARIA is still primarily a personal single-user system
- No full shared-skill/shared-connection RBAC model yet
- Capability results are not automatically written into Memory unless modeled explicitly
- Public internet exposure is still not recommended for this ALPHA line
- Home Assistant, document ingest, web research, SSE streaming, and full multi-user sharing remain roadmap items

### Upgrade Notes
- Update the ARIA container/image, keep persistent volumes
- Hard-refresh the browser after the update if old CSS/theme assets are still cached
- If you use a separate Qdrant container, ensure the Qdrant storage volume is mounted read-only into the ARIA container as in the updated stack examples

## [0.1.0-alpha.21] - 2026-04-03

### Added
- New UI themes: CyberPunk Pulse, 8-Bit Arcade, Amber CRT, Deep Space
- RSS metadata helper button `Check mit LLM` to suggest/enrich title, description, aliases, and tags
- Global RSS poll interval for all RSS feeds
- Stable per-feed RSS poll phase offset to avoid all feeds becoming due on the same interval edge

### Changed
- RSS routing now uses title, description, aliases, and tags of RSS profiles more strongly
- Short free-form RSS prompts like `was für news gibs auf heise` are recognized more reliably
- Statistics / Startup Preflight / System health now display state mostly via status lamps instead of repeated text labels
- CyberPunk theme adjusted toward stronger hot-pink/magenta accents and a darker black base

### Fixed
- RSS page search now correctly hides non-matching groups and feeds
- RSS search also reacts when the browser clear `x` resets the search field

### Security
- No dedicated security change in this release block

### Known Limitations
- ARIA is still primarily a personal single-user system
- No full shared-skill/shared-connection RBAC model yet
- Capability results are not automatically written into Memory in the same way as normal chat responses
- Public internet exposure is still not recommended for this ALPHA line

### Upgrade Notes
- Update the ARIA container/image, keep persistent volumes
- Hard-refresh the browser after the update if old CSS/theme assets are still cached

## Internal Notes

- Detailed internal build history currently lives in `project.docu/alpha-build-log.md`
- Public release wording can be derived from:
  - `docs/product/feature-list.md`
  - `docs/backlog/future-features.md`
  - `docs/setup/setup-overview.md`
  - `docs/product/architecture-summary.md`
  - `docs/release/versioning.md`
