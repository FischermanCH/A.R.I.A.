# ARIA Codex Operating Contract

This file is the highest-priority local working contract.

## 1. Active Mode

At the start of every ARIA task, state the active mode and forbidden actions.

There are only two user grants, interpreted case-insensitively:

- `FREIGABE: CODE`: analyze, document, design acceptance, edit code/docs, and run local tests or isolated Dev-ARIA diagnostics. No Docker build/export.
- `FREIGABE: BUILD`: build/export only after green acceptance with `build_allowed: true`. No product behavior edits.

Without an applicable grant, remain read-only. A direct request to update these operating instructions authorizes only that documentation change.

CODE and BUILD never imply access to Live-ARIA, productive data, connections, secrets, Qdrant, provider calls, runtime actions, NAS mutation, or public release. Those require explicit authorization for the concrete target and operation. Paid model calls also require an agreed call and cost budget.

## 2. Architecture Direction

ARIA is being rebuilt as a real modular system, not a static ownership map.

- The kernel owns bootstrap, plugin lifecycle, generic contracts, auth, permissions, policy, confirmation, observability, and the existing Qdrant MetaCatalog routing infrastructure.
- The existing Qdrant MetaCatalog is the single runtime routing source. Do not create a second catalog truth.
- Every functional module must provide its own MetaCatalog projections, contracts, config, source authority, runtime, UI contributions, migrations, and tests.
- The kernel must not contain fixed domain or connection IDs such as SSH, SFTP, Recipes, or Notes.
- Modules may depend only on the module SDK, kernel ports, and explicitly declared neutral services. No direct sibling-module imports.
- A module failure, removal, or change must not alter unrelated modules. In particular, SSH changes must leave SFTP code, contracts, MetaCatalog points, and tests untouched.
- Custom modules and connection providers must be installable without editing kernel, routing, config, UI, or other modules.
- Qdrant selects relevant module/operation candidates. The selected module's authoritative store supplies complete rows and runtime targets; Qdrant top-k never defines inventory completeness.
- No fallback may silently replace unavailable Qdrant routing with config scans, keywords, or plain chat.

The canonical target and migration order are in `docs/internal/modularization-master-plan.md`.

## 3. Evidence Before Change

After a live failure:

1. Preserve and read the complete export or log.
2. Reproduce the exact production-shaped failure locally.
3. Identify the shared architectural boundary before editing a leaf module.
4. Create or update the end-to-end acceptance matrix.
5. Implement the smallest architectural block that removes the old truth instead of adding a competing truth.
6. Run focused isolation tests first, the full suite once at the end, and stop before build.

A failed live review overrides green local or provider tests. Do not call a fix correct, robust, complete, or in the right layer without naming exact prompt, route, source authority, target scope, confirmation, runtime order, call count, and latency evidence.

Test fixtures must not invent or auto-fill model fields whose absence is possible in production. Optional explanation, confidence, or telemetry fields must never become execution authority.

## 4. Agentic Semantics

Never infer natural-language intent, route, source, scope, entity, answer mode, or content through keyword lists, regex cascades, substrings, tokens, stems, or phrase triggers.

Use model-based or genuinely semantic interpretation. Deterministic code is limited to schema validation, exact identifiers, permissions, source authority, confirmation, budgets, call counts, security redaction, protocol parsing, and fail-closed execution.

If semantic interpretation is unavailable, invalid, or ambiguous, fail closed or use an already accepted agentic fallback. Do not create a word-list fallback.

## 5. CODE Autonomy And Stops

With `FREIGABE: CODE`, start the next unfinished macroblock in the canonical
master plan and work autonomously through all locally solvable phases. Continue
into the next macroblock when no build or external review is useful between
them. Progress updates are not pauses. Stop only when:

- build/export would be the next useful action;
- productive or otherwise unauthorized access would be required;
- the exact live failure cannot be reproduced within isolated scope;
- a high-risk change lacks its acceptance matrix;
- continuing would create a second truth or require an unplanned broad refactor.

Local test failures, missing acceptance detail, documentation updates, ordinary
implementation choices, and reversible migrations are work to resolve, not
reasons to stop. If one independent module is blocked, preserve its evidence and
continue other safe work in the same macroblock.

Do not ask the user to perform locally testable passive checks. Do not repeat an already granted budget request.

## 6. Required Reading

Before behavior changes, read in this order:

1. `AGENTS.md`
2. `docs/AI_CONTEXT.md`
3. `docs/internal/modularization-master-plan.md`
4. `docs/ai-context/07-agentic-routing-acceptance-contract.md`
5. the newest live evidence
6. the active slice acceptance file

Historical plans and Alpha evidence are references, not directives.

## 7. Reporting

At the end of each block, report:

- what changed;
- which focused, isolation, and final gates passed;
- what remains unproven;
- whether a build is sensible;
- exactly who acts next and which grant is needed.

Never leave the user with only diagnosis or an unexplained pause.

## 8. Lean Execution (owner decision 2026-10-17, cost/time)

Measured on alpha1025: ~55 % of tokens went into tests/builds, ~33 % alone into
polling long-running commands every 30 s with a ~188k-token context. Therefore:

- **One fresh Codex conversation per work-order.** Everything needed is in this
  file and the acceptance JSON; do not rely on earlier conversation history.
- **Minimal reading.** For a scoped work-order (e.g. Vibe:Lab) read only this
  file, the active acceptance JSON and the code you touch. Read the documents in
  section 6 only when the work-order changes architecture/routing/agent semantics.
- **No polling.** Run long commands (full suite, e2e, docker build/export) as ONE
  blocking command with a long timeout, or redirect to a log file and read the
  log ONCE when it finished. Never poll with short yield intervals. Print only
  summaries/failures (e.g. `pytest -q`, `| tail -n 40`), never full logs.
- **Gate tiers** (the acceptance JSON may override):
  - *Every change:* focused tests for the touched area + `import aria.main`.
  - *Internal build (owner installs a TAR):* the full pytest suite once after the
    version bump + only the e2e scenarios of the touched area + a secret scan of
    the diff. No fresh-install/upgrade matrix, no theme matrix, no full e2e, no
    visual baseline unless the work-order touches shared/global UI or migrations.
    Before every build, run `tests/e2e/test_basics_smoke.py`; all nine Vibe:Lab
    combinations (desktop, touch tablet, WebKit phone × llm, agent, terminal)
    must pass and must be reported individually.
  - *Migration/persistence changes:* add ONE upgrade test from the installed
    baseline version.
  - *Public release only:* full e2e, fresh-install, upgrades from the public
    versions, theme pass, visual baseline.
- **Real behaviour over fakes.** Flows that talk to external tools (Codex
  app-server, SSH, browser UI) need at least one test against the REAL shape:
  recorded real protocol fixtures or a real local run. Hand-made fakes alone do
  not prove a user flow.
- **Fixed TAR location (owner's updater depends on it):** every build exports to
  `/mnt/NAS/aria-images/aria-alpha<N>-local.tar` AND updates the alias
  `/mnt/NAS/aria-images/aria-alpha-local.tar` (byte-identical, verify sha256).
  Never only to `dist/` or any other path; keep at most the last 5 internal
  builds (KEEP_TARS=5; public TARs 604/982/983/1007 and the demo image are always kept).
- **Short report** (max ~15 lines): what changed, which gates ran, what is
  unproven, the TAR path. No long tables unless the acceptance JSON asks.
- **Never add scope** beyond the acceptance JSON; no extra features, no
  refactors outside the named files.

## 9. CHANGELOG.de.md Format (owner decision 2026-10-20)

`CHANGELOG.de.md` is parsed by the WordPress plugin on aria-agent.dev (single
source of truth for the public changelog, internal builds included as roadmap).
Every new or edited entry from `0.1.0-alpha983` upward must follow this format;
entries older than alpha983 stay untouched (the parser stops there).
`CHANGELOG.md` (English) is not covered by this rule.

- Version heading, exactly:
  `## 0.1.0-alpha<N> - <YYYY-MM-DD> [public|intern]`
  Check regex: `^## 0\.1\.0-alpha\d+ - \d{4}-\d{2}-\d{2} \[(public|intern)\]$`
  No brackets around the version, no dot before the number (`alpha983`, not
  `alpha.983`). The date is the build date of that version.
- `[intern]` for every internal build. `[public]` only for versions the owner
  released publicly; only the owner switches a version to `[public]`.
- Sub-headings (`### `) are optional and free-form (thematic titles are fine).
  `### Sicherheit` is reserved: security content uses exactly `### Sicherheit`,
  never a variant such as `### Security`, `### Sicherheit und …`.
  Preferred standard titles: `### Highlights`, `### Neu`, `### Geändert`,
  `### Behoben`, `### Upgrade-Hinweise`, `### Bekannte Einschränkungen`.
- No status notes like `> Nur interner Build …`; the `[intern]`/`[public]` tag
  in the version heading carries that information.
- Content as Markdown bullets (`- `); hard-wrapped bullets are allowed.
- Language in prose: real umlauts (ä/ö/ü/Ä/Ö/Ü), Swiss `ss` instead of `ß`.
  Never change text inside backticks, code blocks, URLs, paths or identifiers.
- Newest version on top; one heading per version.

## 10. Website Feature Page (owner decision 2026-10-21)

The «Funktionen» page on aria-agent.dev is generated from `main`: n8n runs
`python3 scripts/export_features.py --ref main` daily. Texts and order live in
`docs/website/features.json`; images in
`docs/assets/screenshots/features/<lang>/<id>.webp` and
`docs/assets/screenshots/themes/<lang>/<theme>.webp`.

- When a UI function described in `docs/website/features.json` changes (route,
  selector, behaviour, new or removed function), update `features.json` in the
  same commit: text `de` and `en`, and `shot`.
- The website must stay current WITHOUT owner editing (owner decision
  2026-10-24). Therefore, after EVERY successful BUILD/export (internal and
  public), before `scripts/release/push_docs.sh`:
  1. `scripts/demo/reset.sh` (it starts the demo on the image of the current
     `pyproject.toml` version automatically),
  2. `.venv/bin/python scripts/release/capture_feature_screenshots.py`
     (its public-safety check must pass; do not open or review the images -
     Claude reviews them on request),
  3. `python3 scripts/export_features.py --ref HEAD` must report every
     non-hidden feature with an image, except features that cannot be
     captured yet - list those in the report,
  4. commit only `docs/assets/screenshots/features/`, `.../themes/` and
     `docs/website/features.json` on `main`.
  Do not run pytest while capturing (`tests/test_alpha999_demo_instance.py`
  rewrites `demo/generated`). On public releases also run
  `capture_public_screenshots.py`.
- New or removed user-visible functions get their `features.json` entry
  (de + en text, `shot`) in the same work; the AI writes the text itself
  following the rules below - the owner does not edit the website.
- Texts: Swiss Standard German (ä/ö/ü and ss, never ß); the English version is
  written on its own in British English, not a literal translation; no internal hostnames, IPs or
  paths.

## 11. Website-Synchronisation (aria-agent.dev) (owner decision 2026-10-23)

Die Website liest per n8n ausschliesslich den committeten Stand von `main`
(`git show main:<datei>`), nie das Arbeitsverzeichnis und nie andere Branches.

- Changelog: Nach jedem Build wird der neue Eintrag in `CHANGELOG.de.md` im selben Zug
  auf `main` committet (Push nur über `scripts/release/push_docs.sh`). Ein Build ohne committeten Changelog-Eintrag
  erscheint nicht auf der Website.
- Hilfe: Änderungen an Hilfe-Dokumenten (gemäss `aria/modules/static_help_docs/manifest.py`)
  und deren Übersetzungen ebenfalls auf `main` committen.
- Funktionen-Seite: Ändert sich eine in `docs/website/features.json` beschriebene Funktion,
  wird `features.json` (Text de und en, `shot`) im selben Commit nachgeführt.
  Nach jedem Build die Feature-Screenshots neu erzeugen und mitcommitten (Abschnitt 10).
- Vor dem Abschluss einer Aufgabe prüfen: `git status` darf für `CHANGELOG.de.md`,
  die Hilfe-Dokumente und `docs/website/` keine uncommitteten Änderungen zeigen.

### English changelog (`CHANGELOG.md`)

- Every new build gets its entry in BOTH files in the same commit:
  `CHANGELOG.de.md` and `CHANGELOG.md`, with an identical heading
  (`## 0.1.0-alpha<N> - <YYYY-MM-DD> [public|intern]`). `CHANGELOG.de.md` is
  authoritative for build, date and status; the website takes only the text
  from `CHANGELOG.md` (a missing build shows the German text with «Only
  available in German»).
- Sub-sections mirror the German entry: `### Neu` = `### Added`,
  `### Geändert` = `### Changed`, `### Behoben` = `### Fixed`,
  `### Sicherheit` = `### Security` (exactly; the website hides it for
  unpublished internal builds).
- English text: a faithful, not literal, translation in clear neutral
  technical **British English** (organise, colour, behaviour, licence,
  localise, centre). Code, paths, commands and versions unchanged in backticks.
  No internal hostnames, IPs, user names or paths beyond the German text.
- Before finishing a task run the check; the `diff` must be empty and the
  security counts must match:

```bash
diff <(grep -oE '^## 0\.1\.0-alpha[0-9]+ - [0-9-]+ \[(public|intern)\]' CHANGELOG.de.md) \
     <(grep -oE '^## 0\.1\.0-alpha[0-9]+ - [0-9-]+ \[(public|intern)\]' CHANGELOG.md | head -n $(grep -cE '^## 0\.1\.0-alpha' CHANGELOG.de.md))
grep -c '^### Sicherheit' CHANGELOG.de.md; grep -c '^### Security' CHANGELOG.md
```

### Documentation push after builds (owner authorisation 2026-10-24)

The owner grants a standing, narrow authorisation to push documentation to
GitHub so internal builds appear on aria-agent.dev:

- After every successful BUILD/export and the section 11 changelog/help commit,
  run `scripts/release/push_docs.sh` and report its output.
- The script pushes `main` only if every commit in `origin/main..main` touches
  nothing but `CHANGELOG.de.md`, `CHANGELOG.md`, `docs/help/`, `docs/wiki/`,
  `docs/website/` and `docs/assets/screenshots/{features,themes}/`, the added
  lines pass its secret/internal-host scan, the changelog headings match and
  the push is a plain fast-forward. It never forces and never pushes tags or
  other branches.
- If it refuses: do NOT push by any other means, do not rewrite history, do not
  "fix" the check - report the reason and the listed files to the owner.
- This authorisation covers nothing else: no README, product code, AGENTS.md,
  Docker Hub, tags, releases or public images.
- Commit only explicitly staged documentation files on `main`; never sweep the
  uncommitted working tree into a commit.
