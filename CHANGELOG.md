# Changelog

All notable changes to ARIA should be documented in this file.

Format: `Added` / `Changed` / `Fixed` / `Security` / `Known Limitations` / `Upgrade Notes`

## [Unreleased]

### Added

### Changed

### Fixed

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
