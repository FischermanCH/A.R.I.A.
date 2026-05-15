# ARIA - Alpha Backlog

Stand: 2026-05-15

Zweck:
- schlanker Arbeits-Backlog fuer die laufende Alpha-Linie
- oben stehen nur offene Punkte und naechste Schritte
- erledigte Aenderungen stehen im `CHANGELOG.md`
- Build-Historie steht in `project.docu/alpha-build-log.md`
- groessere Zukunftsthemen stehen in `docs/backlog/future-features.md`

Aktueller Release-Stand:
- aktuell gebaut: `0.1.0-alpha266`
- public veroeffentlicht: `0.1.0-alpha266`
- Public Docker Tags: `fischermanch/aria:0.1.0-alpha.266` und `fischermanch/aria:alpha`
- Public Docker Digest: `sha256:528ea0ef93eb346811542e85b46f671461a0d9b49e32385f48c52b7056c7a45d`
- interner Docker Build: `fischermanch/aria:0.1.0-alpha.266` / `aria:alpha-local`
- internes TAR: `/mnt/NAS/aria-images/aria-alpha266-local.tar`
- internes TAR-SHA256: `bebe761da8470f6851788d75d4dda0cb770151d181ee7237ab4aac0e48792dcd`
- interner Image-Digest: `sha256:528ea0ef93eb346811542e85b46f671461a0d9b49e32385f48c52b7056c7a45d`
- GitHub Release: `https://github.com/FischermanCH/A.R.I.A./releases/tag/v0.1.0-alpha.266`
- GitHub Wiki-Quellen und lokale Hilfe sind fuer `0.1.0-alpha266` nachgezogen
- Live-Updates auf NOX und joe sind laut Live-Test gruen
- seit `0.1.0-alpha251` fuer Public `0.1.0-alpha266` nachgezogen: durable Favicon-Assets, Speicherplatz-Routing, cached `/connections/types`, Agentic Live Regression Dossier, Learned-Recipe-Review-UX, Connection Action Contract, Recipe Result View, Operator Guardrail, Legacy/Recipe Compatibility Audit, RSS-Digest-Count, Self-Learning-Curator, Qdrant-Collection-Classifier, Update-Reconnect-Shell und Dependency-Pinning
- Connection-Modularisierung nachgezogen: Executor-Registry und Capability-Routing-Pools haengen nun am Connection Action Contract statt an stillen Runtime-Sidepaths
- Operator Guardrail nachgezogen: `/stats` prueft Release-Metadaten jetzt explizit neben Gateway, Pricing, Preflight, Health und Update-Pfad
- Kosten-/Token-Guardrail nachgezogen: `/stats` markiert deaktiviertes Token-Tracking/UsageMeter-Bypasses als Release-Fehler und Kostenluecken als Warnung
- Pricing-Overrides nachgezogen: LiteLLM-Refresh synchronisiert manuelle Aliase/Preise wieder sichtbar in den laufenden Settings-State
- Interner Build-Smoke-Test liegt in `docs/release/internal-build-smoke-test.md`
- Recipes-UX nachgezogen: Sample-Vorlagen zeigen Schritt-/Connection-/Trigger-/Schedule-/Side-Effect-Metadaten, Learned-Recipe-Review zeigt Contract/Policy/Runtime-Boundary plus Review-Reife, und Recipe Result View formatiert Schritte mit ausgefuehrt/uebersprungen-Zaehlern
- Operator Guardrail nachgezogen: Recipe Experience Memory wird auf `/stats` als Reachability-/Learning-Memory-Signal sichtbar
- Agentic-Boundaries nachgezogen: Debug-Boundaries sind zentral definiert und `agentic_runtime` markiert Runtime-Ausfuehrung explizit
- Multi-SSH-Summary nachgezogen: ausgefuehrte Read-only-Resultate werden durch einen bounded LLM-Summary-Schritt dynamisch gegen die Userfrage zusammengefasst; deterministische freie-Festplatten-Schwellen bleiben nur als Fallback/Guardrail erhalten
- Multi-SSH-Summary-Qualitaet nachgezogen: LLM-Summaries liefern strukturierte Schwellen-Fakten, harte `df -h`-Messwerte werden validiert, und Widersprueche laufen in einen bounded LLM-Repair statt in statische Spezialfaelle
- Connection-Modularisierung abgeschlossen fuer diese Alpha-Runde: Connection Action Contracts exportieren Manifest-Zeilen und `docs/product/connection-provider-manifest-checklist.md` beschreibt die deklarative Provider-Bruecke
- Admin/Observability abgeschlossen fuer diese Alpha-Runde: `/stats` Operator Guardrail hat stabile Row-Keys und `docs/product/operator-observability-guardrails.md` dokumentiert Release-/Kosten-/Update-Semantik
- Legacy-/Recipe-Cleanup abgeschlossen fuer diese Alpha-Runde: `docs/product/legacy-recipe-compatibility-audit.md` enthaelt jetzt ein explizites Migration-Gate fuer alte Skill-Bruecken
- interner Build erstellt: `0.1.0-alpha256` enthaelt Learned-Recipe-Delete-Qdrant-Purge und bounded LLM-first RSS-Digest-Count/Detail-Auswertung
- Update-Pfad nachgezogen: erfolgreiche managed/interne Updates bereinigen dangling Docker-Layer und ungenutzte ARIA-Docker-Images, ohne Container, Volumes oder Sidecars zu entfernen
- Connections-Status optimiert: `/connections/status` rendert standardmaessig aus cached/last-known Health und startet Live-Probes nur noch bewusst via `?refresh=1`
- Recipes-Overview optimiert: Status-Kacheln verwenden kurze, nicht doppelte Labels und verlinken direkt auf die passenden Rezept-Bereiche
- Learned-Recipes-Erklaerung nachgezogen: `/recipes/learned` beschreibt Lernquelle, lokalen Store, Recipe Experience Memory, Promote/Dismiss/Delete und Abrufpfad sichtbar in der UI
- Self-Learning-Curator nachgezogen: erfolgreiche einzelne Agentic-/Recipe-Lernereignisse bekommen LLM-kuratierte Review-Metadaten, bleiben aber context-only und policy-/guardrail-gebunden
- Self-Learning-Debug nachgezogen: `/recipes/learned` zeigt Curator-Quelle, Policy, Status, Zeitpunkt und Skip-/Fehlergrund sichtbar im Review-Kontext
- Learning-Noise nachgezogen: Learned Recipes unterscheiden neues Muster, Wiederholung, Formulierungsvariante, Scope-Variante, Aktionsvariante und riskante Abweichung; Review-Reife nutzt gewichtete Lern-Evidenz statt nur rohe Run-Anzahl
- Recipe Experience Memory nachgezogen: Lernsignal und gewichtete Evidenz landen als Planner-Kontext im semantischen Memory, bleiben aber weiterhin context-only
- Learned-Recipe-Delete nachgezogen: Admin-Delete entfernt jetzt lokalen Review-Store und passende Recipe-Experience-Memory-Punkte aus Qdrant, damit schlechte gelernte Kandidaten keine semantischen Daten-Leichen hinterlassen
- RSS-Digest-Umfang nachgezogen: explizite Count-/Detail-Wuensche werden bounded LLM-first extrahiert, der RSS-Reader sammelt mehrere Eintraege pro Feed bis zur sicheren Obergrenze, und die Antwort erklaert `angefragt/angezeigt/gefunden/ausgelassen`
- interner Build erstellt: `0.1.0-alpha257` enthaelt die dezente Learned-Recipes-Flow-Erklaerung, den zentralen Qdrant-Collection-Classifier, den codebase-weiten Modularitaetscheck und die Contract-backed Routing-/Guardrail-/Resolver-Zentralisierung
- interner Build erstellt: `0.1.0-alpha258` enthaelt bounded LLM-Erklaerungen fuer geblockte Policy-/Guardrail-Aktionen mit deterministischem Block, sichtbarer geplanter Aktion, Fallback-Debug und direktem Guardrail-Link auf `/config/security?guardrail_ref=...`
- interner Build erstellt: `0.1.0-alpha259` enthaelt den Block-Erklaerungs-Polish nach `alpha258`: live formulierte geplante Aktionen werden nicht mehr doppelt angehaengt und schwache Guardrail-Referenzen werden durch den kanonischen `/config/security?guardrail_ref=...`-Link ersetzt
- interner Build erstellt: `0.1.0-alpha260` enthaelt den Block-Erklaerungs-Performance-Fix: kurzes LLM-Timeout mit deterministischem Fallback, sichtbare Plain-URL fuer Guardrail-Review und kein zusaetzlicher `ssh_guardrail_intent`-LLM-Hop bei klar mutierenden SSH-Blocks
- interner Build erstellt: `0.1.0-alpha261` enthaelt den SSH-Policy-Block-Fast-Path nach `alpha260`: nach der LLM-Aktionserkennung wird die finale Safety-Antwort deterministisch und schnell gebaut, fehlende Guardrail-Review-Links werden aus der selektierten Connection nachgezogen
- interner Build erstellt: `0.1.0-alpha262` enthaelt die Update-Downtime-Reconnect-Shell per Service Worker; Navigation waehrend kurzer ARIA-Container-Recreate-Downtime zeigt nach einmaliger Service-Worker-Registrierung eine Warteseite statt Browser-Fehler und kehrt nach `/health` automatisch zur Zielseite zurueck
- interner Build erstellt: `0.1.0-alpha263` enthaelt den Performance-/Antwortqualitaets-Nachzug nach Live-Test `alpha262`: Learned-Recipe-Curator und Recipe-Experience-Memory laufen nach erfolgreicher Antwort im Hintergrund, RSS-Gruppenfeeds werden bounded parallel gelesen, RSS-Link-Parsing erkennt bracketed Markdown-Titel, Guardrail-Review wird als Markdown-Link gerendert, und File-Listen heben Ordner separat hervor
- interner Build erstellt: `0.1.0-alpha264` enthaelt den Nachzug nach Live-Test `alpha263`: RSS-Transportlimit skaliert mit angefragtem Digest-Count, bracketed Markdown-Links rendern im Chat klickbar, und Guardrail-Review-Hinweise behalten neben dem klickbaren Label auch den sichtbaren `/config/security?...`-Pfad
- interner Build erstellt: `0.1.0-alpha265` enthaelt Dependency-Pinning/Locking fuer Docker-Release-Builds: Python-/Docker-CLI-Base-Image-Digests, `constraints/runtime.txt`, gepinntes `pip/setuptools/wheel`, `--no-build-isolation`, erfolgreicher Image-Healthcheck und `pip freeze --all` matched 85 Constraints
- interner/Public-Build vorbereitet: `0.1.0-alpha266` enthaelt den `/recipes/learned` Layout-Polish mit einspaltigen Review-Karten, strukturierten Detailfeldern fuer lange LLM-Curator-Texte und korrekten `file_list`-Labels statt alter `Read File`-Anzeige

## Offen Auf Einen Blick

- Keine bekannten Public-Release-Blocker fuer `0.1.0-alpha266`.
- Learned-Recipe-Live-Dossier bleibt als laufende Alpha-Beobachtung aktiv: echte Fehl-Learnings weiter als Dossier-/Policy-/Curator-Luecken klassifizieren, nicht blind Spezialfaelle bauen.

Naechster sinnvoller Schritt nach Release:
- Public-Docker-/GitHub-Release `0.1.0-alpha266` live pruefen: `/stats`, `/updates`, RSS 10er-Digest, DNS-Guardrail-Block, SMB-Folderliste, Discord-Confirmation und `/recipes/learned`.
- Update-Reconnect-Shell nach vorherigem Seitenbesuch beim naechsten Update beobachten.

## Dauer-Guardrails

- Packaging-/Release-Hygiene aktiv halten
- kein generiertes `*.egg-info/`, `build/`, `dist/` oder `*.whl` im Workspace oder Commit
- neue Runtime-Assets muessen von `tests/test_package_data_contract.py` oder `tests/test_release_hygiene.py` abgedeckt bleiben
- `CHANGELOG.md` fuer alle sichtbaren Produkt-/Architektur-Aenderungen fortschreiben
- Agentic Live-Ausreisser zuerst in `docs/product/agentic-live-regression-dossier.md` als Kontext-, Resolver-, Policy-/Guardrail-, Runtime-/Summary- oder Observability-/Kostenluecke klassifizieren
- keine neuen Agentic-Spezialfaelle auf Verdacht bauen; Zielbild bleibt Kontext anreichern, LLM bounded Action-Draft, Policy/Guardrail entscheidet, Runtime fuehrt aus
- Flexibilitaet ist LLM-first: Sobald User-Semantik, Bewertung, Zusammenfassung oder freie Formulierungen flexibel verstanden werden muessen, soll ein bounded LLM-Schritt genutzt werden; deterministische Logik bleibt fuer Sicherheit, Normalisierung, Preflight, Policy/Guardrail und Fallbacks reserviert
- Recipes UX nur anhand echter neuer Recipe-Ausgaben/Live-Ausreisser weiter schaerfen; Templates, Review-/Promote-Flows und strukturierte Outputs nicht auf Verdacht aufblasen
- Connection-Modularisierung ueber `docs/product/connection-action-contract.md` und `docs/product/connection-provider-manifest-checklist.md` contract-backed halten; neue Provider duerfen keine Pipeline-Sidepaths bauen
- neue Provider-/Capability-Familien muessen ihre Runtime-, Policy-, Guardrail- und Direct-Gate-Eigenschaften im Connection Action Contract deklarieren; keine lokalen Provider-Listen in Pipeline, Web-Routen oder Resolvern nachziehen
- Operator Guardrail nach `docs/product/operator-observability-guardrails.md` pflegen; Kosten-/Token-Tracking-Ausfaelle bleiben Release-Fehler
- Legacy-Skill-Bruecken nur nach dem Migration-Gate in `docs/product/legacy-recipe-compatibility-audit.md` entfernen
- i18n strict vor groesseren Releases laufen lassen: `scripts/audit_i18n_code_literals.py --strict`
- deutsche UI-/Runtime-Texte gehoeren in `aria/i18n/*.json`
- deutsche Eingabe-/Routing-Lexika gehoeren in `aria/lexicons/*.json`
- Managed Update-Pfad schuetzen: normale Updates sollen nur `aria` recreaten; Qdrant/SearXNG/Valkey nur bewusst via `repair`/`update-all`

## Recipe-First Zielbild

- `Recipe Memory`: was ARIA aus Nutzung gelernt hat
- `Recipe Candidate`: was fuer eine Anfrage relevant sein koennte
- `Executable Plan`: was jetzt konkret ausgefuehrt wird
- `Policy / Guardrails`: was erlaubt, bestaetigungspflichtig oder blockiert ist
- `Runtime Adapter`: wie technisch ausgefuehrt wird
- neue Intelligenz entsteht bevorzugt aus Dossier + Planner + Policy + Summary + Learning, nicht aus starren Skills

## Danach

- Scheduler/Cron fuer kontrollierte Recipe-Automation weiter vorbereiten
- OAuth2-Connection-Foundation fuer Enduser-Integrationen ausbauen
- Google-Integrationen nach Calendar schrittweise erweitern (`Tasks`, spaeter `Drive`, `Sheets`)
- Apple bewusst spaeter und selektiv angehen (`Calendar` zuerst)
- `recipe_runtime.py` nach Executor-Domaenen weiter schneiden
- `pipeline.py` als Orchestrator weiter verschlanken

## Referenzen

- Release-Details: `CHANGELOG.md`
- Alpha-Build-Historie: `project.docu/alpha-build-log.md`
- Public-Release-Text: `docs/release/github-release-v0.1.0-alpha.266.md`
- Public-Rollup-Hintergrund: `docs/release/public-alpha-rollup-alpha167-to-next.md`
- Connection-Manifeste: `docs/product/connection-provider-manifest-checklist.md`
- Codebase-Modularitaetscheck: `docs/product/codebase-modularity-audit-alpha257.md`
- Operator Guardrail: `docs/product/operator-observability-guardrails.md`
- Legacy Recipe Compatibility: `docs/product/legacy-recipe-compatibility-audit.md`
- Zukunftsthemen: `docs/backlog/future-features.md`
