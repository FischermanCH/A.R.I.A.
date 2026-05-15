# Codebase Modularity Audit - alpha257 prep

Status: 2026-05-13

Purpose:
- keep ARIA modular as connection types, memories, recipes and agentic flows grow
- avoid hidden deterministic side paths that bypass the Connection Catalog, Connection Action Contract, policy or guardrails
- preserve the target architecture: LLM-first for meaning, intent, flexible summaries and evaluation; deterministic code for normalization, preflight, policy, guardrails, runtime execution and fallbacks

## Audited Layers

1. Connection Catalog and routing surfaces
- Routing Workbench kind options now come from `ordered_connection_kinds()` / `routing_workbench_kind_options()`.
- Pending chat action route kinds now come from the Connection Catalog.
- Default Qdrant routing-index connection kinds now come from the Connection Catalog.

2. Connection Action Contract
- Runtime operation, executor kind, policy family, guardrail kind, side-effect state and direct-gate eligibility live in `aria/core/connection_action_contract.py`.
- Pipeline executor registration derives handlers from the contract instead of a local capability map.
- Generic direct capability-gate pools derive from contract `direct_capability_gate` flags.
- Agentic read/message resolver capability families derive from the contract instead of local hard-coded capability sets.

3. Guardrail and dry-run boundaries
- Guardrail-kind mapping now belongs to the Connection Action Contract.
- Dry-run and recipe runtimes query `guardrail_kind_for_capability()` instead of duplicating mapping tables.

4. Qdrant / memory collection visibility
- Memory overview, memory map and stats share `aria/core/qdrant_collection_classifier.py`.
- `aria_recipe_experience_*` and future unknown `aria_*` system collections are visible without page-specific updates.

5. LLM-first flexibility boundary
- Multi-target SSH result interpretation remains bounded LLM-first after deterministic read-only execution.
- RSS digest count/detail interpretation remains bounded LLM-first with deterministic caps and fallback.
- Learned Recipe curation remains bounded LLM-first for review metadata only; runtime execution stays policy/guardrail-bound.

## Accepted Provider-Specific Code

These are intentionally not abstracted further in this pass:

- Admin/profile forms in `connection_admin.py`: provider-specific fields are UI/schema concerns.
- Runtime adapter modules such as file, messaging, RSS, HTTP and SSH runtimes: provider protocols differ by design.
- Connection dossiers: target dossiers intentionally expose provider-specific safe metadata for bounded LLM decisions.
- Result summarizers: user-facing output remains capability-specific.
- Recipe step runtimes: stored recipe steps are typed execution adapters, not generic routing logic.
- Lexicon-backed routing hints: language hints remain deterministic seed/context, while ambiguous meaning should move through bounded LLM planning.

## Residual Watchpoints

- `pipeline.py` is still a large orchestrator; future cleanup should move additional provider-specific helper blocks into contract-backed domain modules without changing behavior.
- New connection providers must update the Connection Catalog, Capability Catalog and Connection Action Contract together.
- If a new provider needs direct capability-gate behavior, declare it via `direct_capability_gate` rather than adding another local list.
- Any new Qdrant collection family must be visible through the central classifier first, not page-local filtering.

## Verification

- Targeted modularity regression after centralization: `250 passed`.
- Broad product/runtime regression after earlier centralization: `356 passed`.
- `py_compile` on touched core/web modules: green.
- `scripts/audit_i18n_code_literals.py --strict`: green.
- `git diff --check`: green.

No build was created as part of this audit.
