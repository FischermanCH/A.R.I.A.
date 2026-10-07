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
