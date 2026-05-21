# Agentic Flow Map - alpha267 prep

Status: 2026-05-15

Purpose:
- document the current controlled Agentic Action Flow before further modularization
- make debug-boundary expectations explicit for future providers and capabilities
- keep ARIA extensible without adding provider-specific side paths back into `pipeline.py`

## Target Flow

1. User prompt
2. Deterministic context enrichment
3. Bounded target/action draft
4. Policy and guardrail decision
5. Runtime execution
6. Result summary and optional context-only learning

LLMs may interpret meaning, propose bounded action details, summarize runtime results, and curate review metadata. They do not grant execution permission. Policy, guardrails, preflight validation, runtime adapters, hard-fact validation, and fallbacks remain deterministic.

## Current Code Map

### 1. Pre-RAG Action Gate

Entry point:
- `aria/core/pipeline.py::_try_pre_rag_action_gate`

Responsibilities:
- rewrite safe follow-up phrasing for calendar/SSH context
- classify a `CapabilityDraft`
- decide whether to use direct capability execution, unified routing, or no action
- emit `pre_rag_action_gate` debug with `boundary=context_enrichment`

Expected outcomes:
- `action_path=capability_action`
- `action_path=unified_routing`
- `action_path=missing_capability_target`
- `action_path=no_action`

### 2. Context Enrichment and Routing

Entry points:
- `aria/core/pipeline.py::_resolve_unified_routed_action`
- `aria/core/pipeline.py::_build_kind_only_routed_resolution`
- `aria/core/pipeline.py::_build_forced_routed_resolution`

Responsibilities:
- collect connection candidates
- preserve explicit/requested target hints
- resolve semantic routing when appropriate
- build action/payload/safety/execution dry-run records
- emit capability draft and candidate-pool debug with `boundary=context_enrichment`

Modularity note:
- provider availability and valid capability bindings must continue to come from the Connection Catalog, Capability Catalog, and Connection Action Contract, not local provider lists.

### 3. Bounded Draft

Entry points:
- `aria/core/action_planner.py::debug_bounded_action_plan_decision`
- `aria/core/bounded_planner.py::debug_bounded_planner_decision`
- provider-specific bounded resolvers such as `ssh_agentic_resolution.py`, `file_agentic_resolution.py`, `messaging_agentic_resolution.py`, and `read_agentic_resolution.py`

Responsibilities:
- let the LLM propose target/action details inside bounded candidates
- backfill missing read-only command/path/message/query details
- keep draft debug visible with `boundary=draft`

Modularity note:
- bounded resolvers may be provider-specific, but they must return normalized draft/payload data that still flows through the shared policy and runtime boundaries.

### 4. Policy and Guardrails

Entry points:
- `aria/core/execution_dry_run.py::evaluate_guardrail_confirm_dry_run`
- `aria/core/ssh_policy.py`
- `aria/core/http_api_policy.py`
- `aria/core/guardrails.py`

Responsibilities:
- decide `allow`, `ask_user`, or `block`
- keep mutating SSH requests visible as the intended mutating command
- require confirmation for side-effect actions
- emit policy debug with `boundary=policy` or `boundary=draft_policy`

Modularity note:
- guardrail kind, policy family, side-effect state, runtime operation, and payload fields belong in `aria/core/connection_action_contract.py`.

### 5. Runtime Execution

Entry points:
- `aria/core/pipeline.py::_execute_routed_action`
- `aria/core/pipeline.py::_execute_multi_target_ssh_action`
- `aria/core/executor_registry.py`
- connection/runtime adapters such as SSH, RSS, file, messaging, and HTTP runtimes

Responsibilities:
- execute only complete and allowed/confirmed action plans
- emit `agentic_runtime` debug with `boundary=runtime_execution`
- keep provider-specific transport details inside runtime adapters

Current modularity watchpoint:
- multi-target SSH and RSS group/digest handling still sit in `pipeline.py` and are good candidates for future extraction.

### 6. Summary, Validation, and Learning

Entry points:
- multi-target SSH operator summary helpers in `pipeline.py`
- result summarizers in `aria/core/result_summarizers/`
- learned recipe integration and Recipe Experience Memory modules

Responsibilities:
- summarize executed runtime output for the user
- validate hard runtime facts after LLM summaries where applicable
- record context-only learning after successful runs
- never turn learned context into direct execution without admin promotion

Current modularity watchpoint:
- learning followups are intentionally background work, but the scheduling hooks should move out of the pipeline when the execution boundary is extracted.

## Debug Boundary Contract

Required boundary labels:
- `boundary=context_enrichment`: deterministic context, candidates, hints, and no execution decision
- `boundary=draft`: LLM or resolver proposed bounded action details
- `boundary=policy`: policy/guardrail decision without a new draft
- `boundary=draft_policy`: draft plus policy decision are visible together
- `boundary=runtime_execution`: runtime is executing a normalized action after policy/confirmation

New Agentic paths should add or reuse helpers instead of composing free-form boundary strings locally.

## Next Extraction Candidates

1. SSH Agentic execution
- Move multi-target SSH execution, preflight records, operator summary orchestration, and hard-fact validation into a domain module.
- Keep `Pipeline` responsible for orchestration and result assembly only.

2. RSS digest/group execution
- Move group bundle construction, digest count/detail note handling, and feed-group execution coordination behind an RSS domain helper.

3. Learning followups
- Move successful routed action/recipe learning scheduling behind a small context-only learning service.

4. Blocked/confirmation flow
- Keep policy decisions deterministic, but move user-facing blocked/confirmation response assembly behind shared helpers.

## Verification Anchors

- `tests/test_agentic_action_resolution.py`
- `tests/test_agentic_runtime_debug.py`
- `tests/test_agentic_free_form_regressions.py`
- focused `tests/test_pipeline.py` regressions listed in `docs/product/agentic-live-regression-dossier.md`
- `tests/test_connection_action_contract.py`
