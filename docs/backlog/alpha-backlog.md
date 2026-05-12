# ARIA - Alpha Backlog

Stand: 2026-05-12

Zweck:
- schlanker Arbeits-Backlog fuer die laufende Alpha-Linie
- oben stehen nur offene Punkte und naechste Schritte
- erledigte Aenderungen stehen im `CHANGELOG.md`
- Build-Historie steht in `project.docu/alpha-build-log.md`
- groessere Zukunftsthemen stehen in `docs/backlog/future-features.md`

Aktueller Release-Stand:
- aktuell gebaut: `0.1.0-alpha251`
- public veroeffentlicht: `0.1.0-alpha251`
- Docker Tags: `fischermanch/aria:0.1.0-alpha.251` und `fischermanch/aria:alpha`
- Docker Digest: `sha256:3aacbe8145da283dddaeb9c8cdef0b56961b05119770df1871570f0e26388321`
- GitHub Release: `https://github.com/FischermanCH/A.R.I.A./releases/tag/v0.1.0-alpha.251`
- GitHub Wiki und lokale Hilfe sind fuer `0.1.0-alpha251` nachgezogen
- Live-Updates auf NOX und joe sind laut Live-Test gruen
- nach `0.1.0-alpha251` auf `main` nachgezogen: durable Favicon-Assets, Speicherplatz-Routing, cached `/connections/types`, Agentic Live Regression Dossier, Learned-Recipe-Review-UX, Connection Action Contract

## Offen Auf Einen Blick

1. Agentic Intelligence weiter vereinheitlichen
- echte Live-Ausreisser weiter in `docs/product/agentic-live-regression-dossier.md` als Dossier-/Policy-/Resolver-Luecke klassifizieren
- keine neuen Spezialfaelle auf Verdacht bauen
- LLM-Drafts, deterministische Normalisierung, Guardrails und Runtime in Debug/Kosten weiter klar trennen
- Zielbild: Kontext anreichern, LLM bounded Action-Draft bauen lassen, Policy/Guardrail entscheidet, Runtime fuehrt aus

2. Recipes UX weiter ausbauen
- Review-/Promote-Flows fuer Learned Recipes weiter anhand echter Nutzung schaerfen
- Templates besser kuratieren
- Rezept-Ausfuehrungen fuer User lesbarer zusammenfassen
- strukturierte Recipe-Outputs und Recipe-Fehler-/Skip-Zustaende weiter verbessern

3. Connection-Modularisierung vorbereiten
- gemeinsame Action-Draft-/Policy-/Runtime-Vertraege auf Basis von `docs/product/connection-action-contract.md` weiter vereinheitlichen
- Provider-spezifische Logik hinter kleinen Adaptern halten
- neue Connection-Typen nicht mehr hart in den Pipeline-Kern ziehen
- langfristig deklarative Connection-Manifeste mit getrennter Secret-Zuordnung vorbereiten

4. Admin/Observability abrunden
- LLM Prompt Debug, Model Gateway Audit, Pricing Coverage und Update-Status als Operator-Werkzeuge weiter zusammenziehen
- Kosten-/Token-Tracking als Release-Guardrail aktiv halten
- Pricing-Alias-/Manual-Overrides auditierbar halten

5. Legacy-/Recipe-Cleanup fortsetzen
- Compatibility-Bruecken behalten, solange alte Configs/Imports sie brauchen
- sichtbare UI-/Doku-Begriffe recipe-first halten
- alte `skill_*` Namen nur fuer Backcompat dulden
- `skills:` Config-Root, `/skills*` Redirects und alte i18n-/CSS-Kompatibilitaet nicht ohne Migrationspfad entfernen

## Dauer-Guardrails

- Packaging-/Release-Hygiene aktiv halten
- kein generiertes `*.egg-info/`, `build/`, `dist/` oder `*.whl` im Workspace oder Commit
- neue Runtime-Assets muessen von `tests/test_package_data_contract.py` oder `tests/test_release_hygiene.py` abgedeckt bleiben
- `CHANGELOG.md` fuer alle sichtbaren Produkt-/Architektur-Aenderungen fortschreiben
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
- Zukunftsthemen: `docs/backlog/future-features.md`
