# ARIA - Alpha Backlog

Stand: 2026-05-13

Zweck:
- schlanker Arbeits-Backlog fuer die laufende Alpha-Linie
- oben stehen nur offene Punkte und naechste Schritte
- erledigte Aenderungen stehen im `CHANGELOG.md`
- Build-Historie steht in `project.docu/alpha-build-log.md`
- groessere Zukunftsthemen stehen in `docs/backlog/future-features.md`

Aktueller Release-Stand:
- aktuell gebaut: `0.1.0-alpha254`
- public veroeffentlicht: `0.1.0-alpha251`
- Public Docker Tags: `fischermanch/aria:0.1.0-alpha.251` und `fischermanch/aria:alpha`
- Public Docker Digest: `sha256:3aacbe8145da283dddaeb9c8cdef0b56961b05119770df1871570f0e26388321`
- interner Docker Build: `fischermanch/aria:0.1.0-alpha.254` / `aria:alpha-local`
- internes TAR: `/mnt/NAS/aria-images/aria-alpha254-local.tar`
- interner Image-Digest: `sha256:677cd3f044cbb913e1abf470819832b8c17e3f897d41be0b1c16c1fcac62a06e`
- GitHub Release: `https://github.com/FischermanCH/A.R.I.A./releases/tag/v0.1.0-alpha.251`
- GitHub Wiki und lokale Hilfe sind fuer `0.1.0-alpha251` nachgezogen
- Live-Updates auf NOX und joe sind laut Live-Test gruen
- nach `0.1.0-alpha251` auf `main` nachgezogen: durable Favicon-Assets, Speicherplatz-Routing, cached `/connections/types`, Agentic Live Regression Dossier, Learned-Recipe-Review-UX, Connection Action Contract, Recipe Result View, Operator Guardrail, Legacy/Recipe Compatibility Audit
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
- interner Build erstellt: `0.1.0-alpha254` repariert den LLM-backed Multi-SSH-Operator-Summary-Call aus `alpha253` und ist fuer den internen Live-Test bereit
- Update-Pfad nachgezogen: erfolgreiche managed/interne Updates bereinigen dangling Docker-Layer und ungenutzte ARIA-Docker-Images, ohne Container, Volumes oder Sidecars zu entfernen
- Connections-Status optimiert: `/connections/status` rendert standardmaessig aus cached/last-known Health und startet Live-Probes nur noch bewusst via `?refresh=1`
- Recipes-Overview optimiert: Status-Kacheln verwenden kurze, nicht doppelte Labels und verlinken direkt auf die passenden Rezept-Bereiche
- Learned-Recipes-Erklaerung nachgezogen: `/recipes/learned` beschreibt Lernquelle, lokalen Store, Recipe Experience Memory, Promote/Dismiss/Delete und Abrufpfad sichtbar in der UI

## Offen Auf Einen Blick

Keine unmittelbaren Produkt-/Cleanup-Blocker fuer diese Alpha-Runde.

Naechster sinnvoller Schritt:
- Public-Push erst nach gruenem `alpha254`-Live-Test; vorher keine weiteren Produkt-/Cleanup-Blocker offen

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
- Public-Release-Text: `docs/release/github-release-v0.1.0-alpha.251.md`
- Public-Rollup-Hintergrund: `docs/release/public-alpha-rollup-alpha167-to-next.md`
- Connection-Manifeste: `docs/product/connection-provider-manifest-checklist.md`
- Operator Guardrail: `docs/product/operator-observability-guardrails.md`
- Legacy Recipe Compatibility: `docs/product/legacy-recipe-compatibility-audit.md`
- Zukunftsthemen: `docs/backlog/future-features.md`
