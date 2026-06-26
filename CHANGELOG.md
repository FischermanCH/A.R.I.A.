# Changelog

All notable changes to ARIA should be documented in this file.

Format: `Added` / `Changed` / `Fixed` / `Security` / `Known Limitations` / `Upgrade Notes`

## [Unreleased]

## [0.1.0-alpha398] - 2026-06-26

### Fixed

- Hardened the public update checker after the `alpha397` corrective release. When the GitHub Tags API is rate-limited and the raw `main` changelog is still cached, ARIA now falls back to GitHub's releases Atom feed before using the changelog-only fallback, so future update checks can still discover the newest public prerelease.

## [0.1.0-alpha397] - 2026-06-26

### Added

- Added a versioned Docs Meta-Catalog backed by `aria_doc_meta_<user>` collections. Document uploads now rebuild a per-user catalog from existing document guides, keep the active and previous build in the same collection, leave the old active build intact on rebuild failure, and feed active document-meta hits into the Meta-Catalog router so prompts such as wireless heating can select `docs:search` without the user explicitly saying "documents".
- Hardened the Docs Meta-Catalog migration path for existing document stores. Rebuilds now synthesize catalog entries from legacy document chunks when no document guide exists, discover users from document collections/payloads, and run during startup maintenance so upgraded installs can route old manuals into `docs:search` without a re-upload.

## [0.1.0-alpha394] - 2026-06-26

### Changed

- Added a presentation-stability contract slice after `alpha391`. Broad SSH fleet prompts with a confirmed multi-target objective can expand Meta-Catalog sample targets to the full configured SSH fleet, connection inventory questions such as "what security feeds do I have?" are normalized away from feed-read actions into `connections:inventory`, and simple Notes overview questions can return a source-bound note list without the extra answer-composer LLM hop.
- Adjusted the Chat viewport UI after `alpha393`. The scroll-to-latest arrow is now anchored inside the message pane instead of the full chat shell, and small iPhone layouts keep a usable minimum message history area instead of collapsing the prompt/answer list when Safari reports a tight visual viewport.
- Tightened the Notes inventory fast path after the `alpha392` live smoke. Notes evidence now uses the shared topic-term extraction, and the fast source-bound note list filters loaded hits by the real topic so similar ARIA/A.R.I.A. notes are not listed for an AREA41 query.
- Fixed Meta-Catalog action preflight for seeded action contracts whose merged intents include `context_inventory`. A valid Meta/Turn action seed now bypasses the free pre-RAG chat-intent filter, so mixed connection contracts such as disk-capacity checks can produce an executable SSH preflight instead of failing closed with `capability=-`.
- Hardened Meta-Catalog target propagation for SSH server-update action contracts. Meta-selected SSH targets are now carried as structured `CapabilityDraft.connection_refs` and bound before free alias/context single-target resolution, preventing a selected multi-target server update check from being narrowed to an unrelated SSH profile.
- Hardened mixed Meta-Catalog action contracts for server update checks. If a Meta-Catalog action contract includes RSS advisory sources and SSH server targets, but the action IDs are missing or mixed, ARIA now seeds the SSH multi-target action from the selected SSH targets instead of executing the first RSS feed as the terminal action.
- Added a runtime task/outcome contract for server update checks. Meta-Catalog answer routes over connection context can now be overridden by a bounded runtime task decision when the user is asking for an operational SSH package-update check, and multi-target SSH executions store a structured runtime outcome frame so follow-ups such as "which packages from those are most important?" answer from the previous `apt list --upgradable` results instead of falling into connection inventory.
- Fixed the `alpha388` docs-only contract propagation gap in the normal SkillRuntime path. `RecipeRuntime.run_skills()` now forwards `docs_only=true` to MemorySkill recall, so `docs:search` cannot silently fall back to fact/preference/knowledge/learning recall after the Meta-Catalog selected the Docs surface; a focused regression test covers this path.
- Fixed the post-`alpha386` docs-source isolation gap: `docs:search` now runs MemorySkill in docs-only mode, excludes normal fact/preference/knowledge/learning recall targets, and accepts direct docs answers only when the evidence source is an actual document collection/source.
- Hardened the Meta-Catalog inventory/source contract for `alpha386`. Broad inventory questions now stay on surface-level `connections:inventory` with catalog IDs carried only as hints unless an exact ref is explicitly bound, source-bound evidence is forced whenever local/catalog context is loaded, inventory SkillResults are merged before the LLM-first answer composer, explicit document/note/memory source requests force the matching surface, and Inventory Reindex moved into the Memory menu as Memory Reindex.
- Switched the Strict Meta-Catalog Contract gate to soft mode by default for `alpha385`. The contract instrumentation (`contract_mode`, `evidence_policy`, richer follow-up state, and evidence packets) remains active, but invalid strict contracts no longer block the route unless `routing.meta_catalog_strict_contract_enabled=true` is explicitly enabled for internal comparison testing.
- Added the Strict Meta-Catalog Contract slice for `alpha384`. `aria_meta_catalog_routing` now asks the LLM for an explicit `contract` (`mode=answer|action|clarify|empty`, `evidence_policy=source_bound|allow_general`), validates that contract before accepting the route, carries `contract_mode` and `evidence_policy` through `AriaTurnPlan`, debug output, follow-up `TurnFrame`, and the LLM-first answer-composer evidence packet, and keeps a temporary rollback switch via `routing.meta_catalog_strict_contract_enabled=false` for internal testing only.
- Added the first Qdrant Meta-Catalog migration slice after the `alpha379` architecture review. ARIA can now build a separate `aria_meta_catalog_*` collection with surface and connection capability documents containing safe semantic fields such as what an object knows, what context it can load, candidate actions, loader/executor contracts, risk hints, and confirmation policy. The existing Inventory index remains intact during migration, and the operations reindex flow now rebuilds both indexes side by side.
- Activated the Qdrant Meta-Catalog as the first bounded chat routing step. ARIA now queries `aria_meta_catalog_*`, sends the compact candidate catalog plus the user prompt to `aria_meta_catalog_routing`, validates selected ContextRequests/actions against registered surfaces and catalog candidates, and falls back to the old turn arbiter only when the meta-catalog path is empty or uncertain.
- Moved the legacy keyword router behind the Meta-Catalog contract for normal pipeline turns. Successful `aria_meta_catalog_routing` now skips the old turn-intent, pre-RAG semantic action classification, recipe arbitration, and freshness gates; selected inventory requests can bind to exact `catalog_id/kind/ref`, and selected actions seed the existing executor/guardrail path from the Meta-Catalog instead of re-detecting capability intent from free text.
- Expanded the Meta-Catalog contract beyond coarse surfaces. It now indexes local context families such as facts, preferences, knowledge, context memory, sessions, learning artifacts, notes, and docs, binds selected local families to exact user collections for recall, and maps generic connection actions such as SSH, RSS, websites, SFTP/SMB, HTTP API, mail, webhook, Discord, calendar, and MQTT into existing capability/preflight paths.
- Hardened the Meta-Catalog/backup action contract for `alpha381`. Any validated turn plan with selected actions, `needs_confirmation`, or `plan_action` now enters action preflight or fails closed; it can no longer fall through into direct context answers or final chat. Backup arbiter actions seed the same capability draft path as Meta-Catalog actions, selected multi-SSH targets stay multi-target, and debug now exposes when legacy semantics are used only as a backup fallback.
- Hardened the Meta-Catalog context contract for `alpha382`. A successful Meta-Catalog route with `needs_context=true` and a selected surface but no explicit `context_requests` now synthesizes a validated loader request, e.g. `connections:inventory`, instead of accepting an empty load plan. This keeps source-bound inventory questions on the Inventory loader/direct-answer path and prevents unrelated memory/session context plus final chat from claiming ARIA has no access to configured data.
- Added the LLM-first Answer-Composer contract for `alpha383`. Selected local context and inventory outcomes are now normalized into evidence packets, sent to a bounded `aria_answer_composer` operation for free wording, and then checked by deterministic claim guardrails so source-bound answers cannot claim missing access, invent matches, or use unrelated local context.
- Hardened the remaining Meta-Catalog contracts for `alpha383`: selected non-chat surfaces now force a validated loader request even when the LLM incorrectly sets `needs_context=false`; local memory/search results with `matched=false` stay source-bound empty instead of falling into final chat; and seeded Meta SSH actions can be refined through the existing LLM capability-draft objective contract so package-update checks use the read-only update probe instead of defaulting to uptime.
- Shifted the ARIA turn arbiter toward the Agentic Context Routing directive. The arbitration payload now exposes `routing_meta_context`, and the plan can carry `needs_context`, `context_directions`, and `context_depth` so the LLM decides whether ARIA should deepen context and in which direction instead of only selecting a surface/action menu.
- Let high-confidence local context arbitration run before the legacy turn-intent arbiter and skip the old active-hint/turn-intent/freshness gates for direct local recall. This keeps direct Memory/Learning/Notes questions on the new context-routing path and avoids avoidable LLM/recall hops.
- Added real arbiter-driven local recall limits. Selected Memory/Learning/Docs collections are passed down to `MemorySkill` as `target_collections`, Notes-only routes skip broad memory recall, and document guide lookup can be disabled unless the selected direction needs documents.
- Added first Context Ledger debug lines for ARIA context routing. Details now show selected context directions, depth, collections/actions, query overrides, memory targets, loaded skill contexts, source counts, detail-line counts, embedding tokens, and arbiter tokens.
- Tightened the local-context fast path after the first `alpha363` live test. High-confidence local context turns now skip the pre-RAG action and recipe arbitration stages completely, and Notes-only routes no longer emit a fake `memory_recall` skill result when Memory was intentionally disabled by the arbiter.
- Added a no-context guardrail for agentic local retrieval. When the LLM correctly selects a local context direction such as Notes, Docs, Memory, or combined local sources but ARIA loads zero usable sources, the pipeline now returns a source-bound empty-result answer instead of sending the turn to the final LLM where it could claim ARIA has no access or invent unrelated context.
- Added the same fail-closed contract for selected web side actions. If the ARIA action gate selects a Notes or watched-website side action but the concrete side-flow cannot execute it, the web chat now returns a clear non-execution answer instead of falling through into generic chat.
- Added the Agentic Context Runtime v2 foundation. ARIA now has generic `ContextSurface`, `SurfaceRegistry`, `ContextRequest`, `ContextPacket`, and builtin Surface adapters for Memory, Notes, Docs, Connections, and Web so future data/function surfaces can register metadata instead of requiring central router phrase logic.
- Extended the ARIA turn arbiter with registry-backed `context_requests`. The LLM can now choose registered surfaces such as `connections` with a mode like `inventory`, and ARIA validates that choice against the SurfaceRegistry before any loader or executor is used.
- Added a safe Connection Inventory context path. Questions about configured/observed websites or connections can now load non-secret inventory context instead of being mistaken for watched-website actions; Stage-1 metadata intentionally excludes hosts, URLs, tokens, keys, passwords, and similar sensitive fields.
- Changed final answer context filtering so a later `chat_local_context_relevance` decision can no longer discard context that the explicit ARIA TurnPlan already selected. It now skips with a debug line when the TurnPlan is the semantic authority.
- Tightened the Agentic Context Runtime after live tests. Stage-1 SurfaceRegistry payloads now expose compact `routing_metadata` only, remove the duplicate full menu payload, and keep deep inventory metadata for the selected loader step instead of sending it to the arbiter.
- Generalized inventory loading behind registered ContextSurfaces. `context_inventory` no longer depends on a Connections-only helper; selected surfaces can expose safe inventory metadata through the registry and the answer context stays source-bound.
- Added a Context Isolation contract for selected turns. Answer-context skill results are filtered against the selected `ContextRequest`, and selected Notes/Inventory turns do not run pre-answer Auto-Memory/session/user recall context that could contaminate the answer.
- Added a lightweight `TurnFrame` for follow-up routing. ARIA now passes the previous selected surface/mode/topic to the next arbiter call as weak context, so short follow-ups such as "und was ist mit IT-Security?" can continue an inventory frame without hard-coded phrases.
- Changed the web pre-pipeline side-flow gate to become terminal only for genuine action intents. A stray watched-website action name inside an inventory/context turn no longer blocks the normal pipeline with a non-execution action message.
- Added a content-existence context mode. Topic-specific questions such as "do I have information about X in memory?" are steered toward `exists`/search-style local retrieval instead of being satisfied by shallow inventory metadata alone.
- Hardened generic inventory matching. Configured-item inventory now matches against individual safe item metadata, keeps many selected safe summaries for the deep loader, reports matched-vs-configured counts, avoids generic surface-word matches such as "websites" pulling unrelated items, and does not expose secret URLs/hosts/tokens.
- Removed the extra web pre-pipeline LLM arbitration for normal free-text turns. Slash/UI shortcuts still enter the legacy side flows, but ordinary prompts now go straight to the single pipeline arbiter, which reduces latency and avoids pre-pipeline action misclassification for knowledge/inventory questions.
- Changed chat badge timing to report end-to-end web request time and added `Routing Debug: web_request_timing` with total and pipeline milliseconds, making UI latency visible instead of only showing a partial pipeline/model duration.
- Added tightly scoped direct context answers for already-selected inventory and memory-existence turns. When the TurnPlan selects registered inventory context or a source-bound memory `exists` check, ARIA can answer from the loaded context without a second final-answer LLM call.
- Made memory-existence retrieval more selective by keeping session collections out of `memory_target_collections` unless the TurnPlan explicitly requests sessions.
- Documented ARIA's Qdrant collection contracts in `docs/product/qdrant-collections.md` and made `aria_inventory_*` authoritative for inventory questions. Legacy `website_list` capability drafts now route into `connections:inventory` when the Qdrant inventory index is active, empty inventory results no longer fall back to broad action lists, inventory debug lines expose `authoritative=true`, and evidence-term selection keeps the actual topic in natural-language inventory questions.
- Improved mobile chat viewport handling for iPhone Safari. The chat shell now uses a visual-viewport height variable, keeps the composer above the safe-area inset, and scrolls the message pane to the latest message after layout changes instead of relying on a single immediate `scrollTop` write.
- Hardened source-bound follow-up context. Direct capability inventory answers now store a `TurnFrame`, follow-up plans preserve the previous registered surface/mode unless the user switches surface or requests an action, and empty registered local context returns a source-bound empty result instead of falling through to generic chat.
- Reduced Direct-Context pipeline work for selected local context. High-confidence source-bound Notes/Memory/Docs turns now skip the legacy `turn_intent_arbiter` even when the ARIA turn plan's intent is still `chat`, and Notes-only hits can return a source-bound direct answer instead of paying for a final chat LLM pass.
- Added a fast positive-only ContextSurface selector before the full ARIA turn arbiter. It uses only compact registered-surface metadata, can select one local/source-bound context request, and falls back to the full arbiter for actions, web/freshness, recipes, admin, pending confirmations, learning capture, uncertainty, or invalid surface/mode choices.
- Slimmed the full ARIA turn arbiter payload in registry-backed mode by dropping duplicate legacy surface rows while keeping validated collections/actions. Selected TurnPlan context now skips late recent-context enrichment, direct Memory/Docs search requests can answer source-bound without a final chat LLM when evidence matches, and stage timing now includes `pipeline_wall_time`.
- Tightened the generic evidence contract after the `alpha376` live test. Inventory and memory-existence answers now derive evidence from topic terms instead of raw user-query words, ignore Surface/Mode/request/scope wording such as RSS, websites, feeds, sources, list, inventory, and question filler, allow soft scope words such as monitoring to become the topic only when no stronger topic remains, and preserve the previous TurnFrame surface/mode for short underspecified follow-ups unless the user explicitly switches surface or requests an action.
- Added a Chat scroll-to-latest overlay button. When the user scrolls upward in the chat history, ARIA now shows a compact floating down-arrow that jumps back to the newest message without shifting the composer.
- Hardened the post-`alpha377` semantic evidence contract. Multilingual filler terms such as `and`, `the`, `für`, and `fuer` no longer count as topic evidence, unrelated inventory neighbors are rejected for unmatched topics such as beef grilling, and the fast memory-existence path is rejected when a resource/inventory question does not explicitly target Memory.
- Re-centered the ARIA turn architecture on the full agentic TurnPlan after `alpha378` live regressions. The compact fast context selector and follow-up frame arbiter no longer run before the full turn arbiter, and local frame-preservation helpers no longer override the LLM's selected surface/mode after arbitration. Direct context loading remains an execution optimization after a validated TurnPlan, not an independent semantic router.

## [0.1.0-alpha362] - 2026-06-16

### Added

- Added the ARIA Turn / Surface / Action Arbiter path. The new bounded arbitration module accepts a deterministic menu of allowed surfaces, Qdrant collections, and runtime actions, validates LLM choices against that menu, rejects invented entries, forces confirmation for risky actions, emits a unified routing debug line, and is now integrated into the pipeline before retrieval/action execution.
- Documented the `Agentic Learning Loop v2` product direction: ARIA should turn real usage into controlled learning artifacts such as reflections, routing hints, procedure/recipe/skill candidates, eval candidates, and recipe improvements, with deterministic schemas, policy, guardrails, review, promotion gates, and tests controlling what becomes active.
- Added the first Learning Event Ledger implementation. ARIA can now persist redacted JSONL audit events, load/filter recent events, record successful Auto-Memory `LERNEN` reflections as `memory_reflection` artifacts, and mirror those events into Qdrant as visible `learning_event` memory chunks for the future reflection/review loop.
- Added the first bounded Learning Classifier. Successful Auto-Memory learning events can now be classified into review-only learning candidates such as `source_rule_candidate`, `procedure_candidate`, `recipe_candidate`, or `eval_candidate`, then stored visibly in Qdrant under `aria_learning_candidates_<user>` without activating runtime behavior.
- Added a first Learning Candidate review surface in the Memory Explorer. `learning_candidate` chunks can now be filtered, inspected, marked as reviewed, or rejected in Qdrant payload metadata while promotion remains blocked until validator/eval gates exist.
- Added the first Learning Candidate Validator/Eval dry-run. Review-only candidates now produce visible `learning_eval` chunks in Qdrant under `aria_learning_evals_<user>` with blockers, expected path, expected behavior, negative examples, and `promotion_allowed=false`.
- Added a bounded User Feedback Learning detector in the chat flow. When Auto-Memory is enabled, durable feedback about ARIA's answer quality, source handling, routing, memory, UI, or workflow can create visible Qdrant `learning_event`, `learning_candidate`, and `learning_eval` chunks without activating runtime behavior.
- Added the first runtime Outcome Learning recorder. Explicit URL/source WebSearch outcomes now carry source-quality metadata and, when Auto-Memory is enabled, can create review-only Qdrant `learning_event`, `learning_candidate`, and `learning_eval` chunks for page-excerpt/source-handling behavior.
- Added a Deterministic Meaning Audit document that identifies where free user semantics are still decided by keyword/regex/list logic and sets the next refactor priority toward bounded `turn_intent_arbitration`.
- Added bounded Turn Intent Arbitration around the normal pipeline router. The legacy `KeywordRouter` now acts as a signal source for top-level chat/memory/web intents, and a bounded LLM arbiter can override misleading keyword signals with sufficient confidence while falling back to the deterministic router when unavailable or uncertain.
- Added a Capability Draft Fallback Boundary. The pre-RAG action gate now tries bounded LLM capability drafting before local heuristic drafts, treats LLM `no_action` as authoritative, allows local fallback only for unavailable/uncertain draft states, and records local fallback usage as a review-only learning outcome when Auto-Memory is enabled.
- Added bounded Notes Action Arbitration for chat Notes flows. Natural-language Notes requests can now be classified into canonical Notes commands or `no_action` before the legacy regex handlers run, while slash/UI-style commands and low-confidence cases still fall back to the existing deterministic handlers.
- Added bounded Follow-up Resolution for vague chat rewrites. ARIA now asks a constrained LLM resolver whether follow-up turns should be rewritten for web search or local context, treats high-confidence `no_rewrite` as authoritative, and keeps the old deterministic rewrite helpers only as low-confidence/no-LLM fallback.
- Broadened runtime Outcome Learning beyond WebSearch and local capability fallback. Stored-recipe catalog misses and confirmed routed connection actions can now create review-only Qdrant learning events/candidates/evals when Auto-Memory is enabled.
- Added the first low-risk Learning Candidate Promotion Gate. Reviewing a Qdrant learning candidate now writes a deterministic gate result back into the candidate payload: low-risk `source_rule_candidate` and `routing_hint` candidates become `eligible`, while higher-risk procedures/recipes remain `reviewed_blocked` and runtime activation stays disabled.
- Added a guarded Apply preparation step for eligible low-risk Learning Candidates. The Memory Explorer can now mark eligible `source_rule_candidate`/`routing_hint` candidates as `apply_state=prepared` with `apply_requires_regression=true`, while still keeping `runtime_activation_allowed=false`.
- Added a read-only Apply Preview for prepared low-risk Learning Candidates. Admins can inspect the proposed source-rule/routing-hint structure, provenance, regression requirement, and disabled runtime status before any future activation path exists.
- Added Regression Gate status to Learning Candidate apply preparation and preview. Prepared candidates now default to `regression_status=missing`, the preview shows missing/linked regression state and references, and runtime activation remains disabled.
- Added a Regression Link route in the Learning Candidate Apply Preview. Admins can link concrete pytest refs such as `tests/test_pipeline.py::test_name`, which updates the Qdrant candidate payload to `regression_status=linked`; invalid refs keep the candidate at `missing`.
- Added Regression Ref verification for Learning Candidate Apply Preview. Linked pytest refs can now be checked against the workspace for file and test-function existence, writing `regression_verified`, `regression_test_exists`, and `regression_verify_result` back to Qdrant without running or activating runtime behavior.
- Added focused Regression Test execution for verified Learning Candidate refs. The Apply Preview can now run the linked pytest ref and store `regression_verify_result=passed|failed`, return code, timestamp, and sanitized output in Qdrant while keeping runtime activation disabled.
- Added the first Active Learning Hint activation path. Reviewed/prepared low-risk candidates now require an activation preflight with a passed regression run before they can be stored as visible Qdrant `learning_active_hint` chunks under `aria_learning_active_hints_<user>`.
- Added weak runtime use of active learning hints. Turn intent arbitration can now receive reviewed Qdrant active hints as bounded weak signals, while policy, guardrails, and runtime activation remain deterministic gates.
- Added Active Learning Hint outcome tracking. When Auto-Memory is enabled and a Qdrant active hint is available during turn intent arbitration, ARIA now records a review-only learning outcome so active hints can later be evaluated, refined, or withdrawn.
- Added Universal Host/App Artifact Learning. Confirmed connection-action results can now surface observed paths, Compose files, Dockerfiles, systemd units, ports, packages, and health terms as review-only `app_artifact_candidate`, `install_plan_candidate`, and `health_check_candidate` learning artifacts in Qdrant.
- Added App Identity Hypotheses for host artifact learning. Observed artifacts can now be condensed into review-only `app_identity_candidate` data with runtime kind, app root, entry artifacts, health surfaces, install/update surfaces, and rollback surfaces.
- Added review-only Install/Update Plan Drafts from app identity hypotheses. Drafts include preflight checks, backup targets, proposed steps, health checks, rollback steps, blockers, required confirmation, and disabled runtime activation.
- Added Install/Update Plan Validation gates. Drafts are now assessed for missing gates, mutating steps, required confirmations, regression suggestions, and risk while keeping promotion and runtime activation disabled.
- Added structured Health Check and Regression Drafts from validated install/update plans. Drafts remain non-mutating and review-only, making future checks and tests derive from observed app artifacts instead of ad hoc rules.
- Added Memory Explorer visibility for app-learning candidates. App identity, plan drafts, validation gates, health drafts, and regression drafts now render as structured chips and preview sections for Qdrant learning candidates.
- Added review-only Pytest Skeleton Proposals from regression drafts. Proposals include target file, test function sketches, fixtures, safety notes, and disabled write/runtime activation flags.
- Added read-only Pytest Apply Preview gates for app-learning proposals. The preview renders proposed test code, checks that targets stay under `tests/`, flags existing files and duplicate test functions, and still never writes files automatically.
- Added a manual Pytest Write preparation gate for app-learning proposals. A ready preview can now store a `prepared` Qdrant payload with target file, test names, code preview, and SHA-256 hash while keeping `pytest_write_allowed=false` and writing no files.
- Added prepared artifact review feedback for app-learning proposals. Operators can mark prepared Pytest write artifacts as accepted, needing changes, or rejected; ARIA stores that outcome back into the Qdrant candidate payload as learning feedback while keeping file writes and runtime activation disabled.
- Added Review Outcome Learning for prepared artifacts. Accepted reviews create review-only `artifact_pattern_candidate` chunks, needs-change reviews create `artifact_improvement_candidate` chunks, and rejected reviews create `negative_pattern_candidate` chunks, each with a matching learning event and eval dry-run in Qdrant.
- Added Learning Pattern Recall for app-learning proposals. New Pytest skeleton proposals can now recall prior accepted, needs-change, and rejected artifact review candidates from Qdrant as weak guidance and carry them visibly in the proposal payload without granting write or runtime permission.
- Added the first Recipe Candidate Generator. Successful connection workflow outcomes can now create an additional review-only `recipe_candidate` plus eval dry-run in Qdrant, with similar existing recipe candidates recalled as weak duplicate/improvement guidance and no runtime promotion.
- Added the first Recipe Improvement Loop behavior. When similar `recipe_candidate` or `recipe_improvement` chunks already exist in Qdrant, new successful workflow outcomes now create review-only `recipe_improvement` candidates instead of another duplicate recipe candidate.
- Added Procedure/Skill Memory with gating. Successful connection workflow outcomes now create review-only `procedure_candidate` chunks and eval dry-runs in Qdrant; when similar procedure/skill memories already exist, ARIA can also propose a high-risk review-only `skill_candidate` without implementation, promotion, or runtime activation.
- Added an Async Learning Worker status path. Runtime learning captures now go through a shared background job registry, and the Memory Explorer shows running, completed, failed, and latest learning jobs while Qdrant remains the durable learning store.
- Added Learning Worker job detail, retry, and flush controls. Admins can inspect a job snapshot, force-retry failed/rejected runtime learning jobs with backoff metadata, and clear finished worker history without touching Qdrant learning artifacts.
- Added first Learning Worker budget gates. Runtime learning jobs now carry estimated tokens, consumed token/cost metadata when available, max-attempt limits, in-process budget totals, and budget rejection status in the Memory Explorer.
- Added Learning Worker observability to Stats and Operator Guardrail. `/stats` now surfaces worker running/completed/failed/rejected counts, budget state, latest job links, and a guardrail row that warns on failures, rejections, or exhausted learning budgets.
- Added Learning Worker runtime audit and failure categories. Finished/rejected/maintenance worker events are recorded as a compact JSONL operations audit, summarized in the worker snapshot, and grouped into operational categories such as budget, Qdrant, provider, validator, worker, route, and unknown.
- Added a Learning Review Queue summary to the Memory Explorer. Qdrant learning artifacts now show candidate, eval, active-hint, regression, and activation counts before the normal Memory type filters.

### Fixed

- Removed the rejected direct recall phrase fix and its tests. Questions like "what did I tell you..." are no longer solved through special phrase rules; they must flow through the common ARIA turn/surface/action arbitration path.
- Moved web chat Notes/Websites side flows behind the common ARIA action gate. Free user turns can no longer be terminally answered by those side flows before the shared arbiter has a chance to choose the surface/action plan.
- Let the pipeline use ARIA arbiter-selected collection queries for local recall, web research, and Notes retrieval, including Notes snippets as normal context instead of a pre-pipeline terminal route.
- Avoid spending Active Learning Hint recall on explicit web-search or clear connection-action contexts while keeping active hints available as weak signals for normal free turns.
- Added missing Learning Worker Stats i18n keys so the full release hygiene suite covers the new stats surface cleanly.
- Keep explicit external `http(s)` URLs out of the agentic pre-RAG connection action gate, even when the bounded capability draft would classify them as watched-website reads. Direct URL/anchor questions now stay on the chat freshness/WebSearch path and preserve the literal URL as the search/fetch query.
- Treat recalled `[LERNEN]` memory reflections as durable behavior guidance in the final chat prompt, so questions such as "was hast du aus meinem AREA41 feedback gelernt?" answer from the learning memory instead of claiming nothing was learned while a `LERNEN` source is present.
- Give fetched web page excerpts higher final-answer priority than search snippets and raise the final context budget so official page excerpts are not truncated behind aggregator snippets before the final LLM answer.

## [0.1.0-alpha360] - 2026-06-15

### Fixed

- Keep arbitrary `http(s)` URLs out of watched-website routing so direct page/anchor questions can use web research instead of asking for a configured Website profile.
- Fetch one additional strong domain/path match beyond the first two web-search results, so official pages such as `area41.io/#speakers` can provide page excerpts even when a search engine ranks aggregator pages higher.
- Let agentic Auto-Memory extract durable feedback reflections into per-user `aria_learning_*` collections. These `LERNEN` memories are visible in Memory/Qdrant and are searched during recall as context-only self-improvement guidance.

## [0.1.0-alpha359] - 2026-06-14

### Fixed

- Move document import into its own chat Toolbox group so it is visible as a first-level document entry instead of being hidden inside Commands.
- Fetch and inject page excerpts for concrete web-search result URLs, including explicit `#anchor` URLs, so official pages can provide answer context beyond search snippets.

## [0.1.0-alpha358] - 2026-06-14

### Fixed

- Keep the ARIA working-logo emblem stable while ARIA is busy. The busy indicator now uses a slow rotating light aura and soft glow instead of rotating or flipping the logo itself, avoiding upside-down frames.

## [0.1.0-alpha357] - 2026-06-14

### Fixed

- Restore the ARIA working-logo animation to a vertical emblem turn so the logo no longer rotates upside down while keeping the smoother light pulse from the previous pass.

## [0.1.0-alpha356] - 2026-06-14

### Changed

- Surface document import from the main chat toolbox. The toolbox item opens the Memory document import panel directly and focuses the file picker so RAG document ingestion is no longer hidden in configuration.

## [0.1.0-alpha355] - 2026-06-14

### Fixed

- Smooth the ARIA working-logo animation by replacing the hard 3D flip/scanline loop with a continuous rotation, synchronized energy sweep, and softer light pulse.

## [0.1.0-alpha354] - 2026-06-14

### Fixed

- Link the main-screen Auto-Memory status indicator directly to the Auto-Memory settings section, following the app rule that option indicators should lead to their option settings.

## [0.1.0-alpha353] - 2026-06-14

### Fixed

- Move the Stats cost-card disclaimer below the cost metrics so the card leads with the actual numbers and keeps the explanatory text near the pricing actions.
- Keep the main Auto-Memory indicator aligned with agentic Auto-Memory extraction. Existing configs with Auto-Memory enabled now get `agentic_extraction_enabled=true` filled in at load time when missing, and the UI/Core toggles update both flags together.

## [0.1.0-alpha352] - 2026-06-14

### Fixed

- Keep explicit recipe-catalog questions catalog-bound even when no recipe candidate matches. Questions such as "gibt es ein rezept fuer dns health" now answer from the stored catalog instead of drifting into a generic checklist.
- Carry recent web-search topic context into vague local Notes/Documents follow-ups in the web chat flow. A follow-up like "und was steht dazu in meinen notizen?" now searches local notes for the prior topic instead of using only the pronoun-like phrase.
- Give bounded capability drafting an earlier chance for local system check prompts before freshness/web-search arbitration. Local checks such as Pi-hole inspection no longer fall through to unrelated web results when configured connections can handle the request.
- Let Auto-Memory use a bounded agentic extraction pass when enabled. ARIA can now persist durable user-specific behavior conventions, aliases, preferences, and infrastructure facts from chat messages, while deterministic extraction remains the fallback and persistence stays limited to facts, preferences, and session context.
- Capture action-sensitive memory boundaries through the same agentic Auto-Memory pass. Durable approval requirements, expiry/trust constraints, and "do not act until..." notes are stored as visible memory facts prefixed with `Action boundary:` so future turns can recall them as context without bypassing runtime policy.

## [0.1.0-alpha351] - 2026-06-14

### Fixed

- Keep general advice and chat questions out of the stored-recipe no-match path. Recipe catalog misses now produce a direct no-recipe answer only when the user explicitly asks about a recipe; normal diagnostic and explanation questions continue through chat.
- Block mutating SSH requests before multi-target read-only fallbacks. Install, upgrade, restart, delete, and similar side-effect requests no longer get silently replaced by status probes such as `uptime`.
- Give recent SSH runtime context the first chance for immediate follow-up questions before drafting a fresh SSH action. Follow-ups such as asking for per-server package details can reuse the previous multi-target result instead of losing the target group.
- Stop passing local Notes/RAG context into normal web-search turns unless the user explicitly asks for local context, reducing unrelated note bleed in follow-up searches.

## [0.1.0-alpha350] - 2026-06-14

### Fixed

- Keep the chat window height stable while long conversations grow. On the main chat page, the outer app frame stays fixed to the viewport and only the message history scrolls upward.
- Keep stored-recipe explanation questions catalog-bound. When `recipe_execution_intent` rejects execution, ARIA now uses a bounded LLM explanation step over the matching recipe manifest, or says that no matching recipe exists instead of inventing a generic server-update runbook.
- Keep automatic freshness/web-search routing LLM-first. When an LLM is available, ARIA now asks `chat_freshness_arbitration` for normal chat questions instead of letting currentness/product keyword filters decide whether the LLM may arbitrate; deterministic freshness terms remain only for no-LLM fallback and explicit/local-context gates.
- Consolidate repeated bounded LLM call handling. Recent-runtime context relevance, local chat-context relevance, and stored-recipe catalog explanations now share `BoundedDecisionClient` for LLM calls, JSON parsing, usage extraction, confidence coercion, and error handling.
- Split the chat turn pipeline into clearer internal stages. Recipe arbitration, freshness/web-search arbitration, and recent-runtime-context enrichment now live in dedicated stage helpers instead of being embedded directly in `Pipeline.process()`.
- Continue untangling the chat turn pipeline. Web-search failure prechecks, direct stored-recipe chat responses, and final chat response/usage accounting now run through dedicated stage helpers.
- Move the chat turn stage helpers into `pipeline_turn_stages.py`, including recipe-status and pre-RAG action exits. `Pipeline.process()` now mostly orchestrates stage calls, capability-draft and pre-RAG chat/action arbitration use `BoundedDecisionClient`, and routing-debug line formatting is shared for the touched debug paths.
- Keep free capability drafts agentic-first before local SSH fallbacks. Bounded `capability_draft_decision` now gets the first semantic pass for non-explicit SSH-like prompts, and an explicit LLM `chat/no_action` decision blocks local SSH fallback.

## [0.1.0-alpha349] - 2026-06-13

### Fixed

- Keep follow-up suggestions after read-only runtime context inspect-oriented. When ARIA answers from a recent read-only runtime result, it should offer read-only next steps such as listing affected items per target instead of suggesting state-changing operations.
- Keep free-language SSH intent LLM-first. The deterministic capability router no longer turns natural health, uptime, status, disk, or free-space phrasing into SSH commands such as `uptime` or `df -h`; those prompts are left to the bounded LLM capability draft while deterministic code keeps only explicit commands, executor availability checks, and policy validation.
- Adapt broad multi-target SSH bundles only from bounded LLM `target_intent` values such as `health_check`, `capacity_check`, or `package_update_check`, instead of falling back to health/capacity wordlists in the pipeline.
- Classify SSH requested runtime effect with a bounded LLM step instead of mutating-request wordlists. ARIA now uses `ssh_requested_runtime_effect` to distinguish read-only, mutating, and unknown user intent, while SSH policy still blocks mutating commands and prevents guardrail healthcheck fallbacks from masking state-changing requests.
- Select SSH guardrail healthcheck fallback commands with a bounded LLM step from the explicit allowlist instead of deterministically concatenating every allowed command. ARIA rejects invented or edited selections and still validates the final command through SSH policy before use.
- Decide stored recipe execution intent with a bounded LLM step. Deterministic recipe scoring now only builds a candidate shortlist; `recipe_execution_intent` must explicitly return `execute=true` for ARIA to run a stored recipe, so explanatory or comparison questions about a recipe topic do not execute it.
- Keep action planner scores as ranking hints instead of final semantics. When multiple bounded action candidates match and no LLM decision is available, ARIA now asks for confirmation instead of selecting an action from keyword or score gaps alone.
- Decide local chat context relevance with a bounded LLM step. Local notes, documents, and memory snippets are now filtered through `chat_local_context_relevance` before the final chat prompt; the old regex-based how-to/diagnostic filter remains only as a fallback.
- Link the Memory Map "Compression due" health card directly to the rollup/compression section in Memory setup so the warning has an immediate repair path.
- Keep loose connection target matches LLM-first. Exact alias/ref matches may still resolve deterministically, but a single soft score candidate no longer bypasses semantic LLM resolution when multiple profiles are available.
- Re-check Learned Recipe promotion blockers when loading runtime candidates. Promoted records with multi-target or side-effect blockers are now ignored even if stale or manually edited store data contains a stored recipe id.
- Expose bounded local chat-context relevance decisions in routing debug details. When `chat_local_context_relevance` keeps or filters local notes, documents, or memory context, debug mode now shows the LLM decision, confidence, candidate count, and reason.
- Expose bounded stored-recipe execution intent decisions in routing debug details. When `recipe_execution_intent` accepts or rejects a stored recipe candidate, debug mode now shows execute true/false, confidence, candidate count, selected id when applicable, and reason.
- Expose action-planner and connection-target decisions in routing debug details. Debug mode now shows `action_plan_debug` for bounded planner choices and `connection_target_selection` for semantic/forced/explicit target resolution while keeping the existing human-readable routing lines.

## [0.1.0-alpha348] - 2026-06-13

### Fixed

- Keep recent multi-target SSH runtime context available for immediate follow-up questions. After a multi-target check, ARIA can now answer which SSH targets the previous result referred to instead of falling back to unrelated local RAG context.

## [0.1.0-alpha347] - 2026-06-13

### Fixed

- Route multi-target SSH package/update-status questions such as "sind meine server up to date" to a read-only package update listing instead of reusing the broad health check command. `apt list --upgradable` is now allowed as a safe SSH read-only probe while mutating apt operations remain blocked.

## [0.1.0-alpha346] - 2026-06-11

### Fixed

- Separate Qdrant Brain graph scrolling from the Payload Preview and the classic Memory Graph. The Brain viewport and the regular Memory Graph now own their horizontal scroll areas independently instead of sharing the outer Memory Map frame scroll.

## [0.1.0-alpha345] - 2026-06-10

### Fixed

- Make Qdrant Brain usable on mobile/touch devices by adding a deliberate touch movement mode. Touch users can now scroll and tap the page by default, then enable graph movement when they want to pan or drag nodes, avoiding the previous conflict between browser scroll, graph pan, and node drag.

## [0.1.0-alpha344] - 2026-06-10

### Changed

- Make Qdrant Brain point dragging behave like a real layout edit: connected neighbors are directly nudged while dragging, and the whole moved graph segment stores its current position as the new layout base on release instead of returning to the original coordinates.

## [0.1.0-alpha343] - 2026-06-10

### Changed

- Make Qdrant Brain point dragging feel stickier and closer to Qdrant: moved points keep their dropped position as their new local home, spring pullback is softer, and motion damping is heavier so the graph does not snap back toward its original layout as strongly.

## [0.1.0-alpha342] - 2026-06-09

### Fixed

- Make the Qdrant Brain collection start map readable by replacing the radial collection layout with a lane-based overview and wrapped collection labels. Long collection names now keep reserved text space instead of overlapping neighboring labels.

## [0.1.0-alpha341] - 2026-06-09

### Fixed

- Center Qdrant Brain collection and point views against the actual visible browser viewport instead of only the internal SVG viewBox. Collection labels are included in centering bounds and right-side collection labels flip left, preventing the start view and Center action from landing visibly right-heavy or clipping labels.

## [0.1.0-alpha340] - 2026-06-09

### Changed

- Make Qdrant Brain point drilldowns feel more like a live graph explorer: point nodes can be dragged directly, connected edges act like damped springs, and the graph settles with a short elastic bounce after interaction. Point edges now also render subtle arrowheads for a closer Qdrant-style visual language.

## [0.1.0-alpha339] - 2026-06-09

### Changed

- Make Qdrant Brain point drilldowns more graph-like by building a connected nearest-neighbor backbone per collection and then adding additional semantic neighbor edges. This makes point collections look closer to Qdrant's own visualization instead of appearing as loose dots that merely share a collection.
- Thin Qdrant Brain point edges to keep denser semantic neighborhoods readable.

## [0.1.0-alpha338] - 2026-06-09

### Changed

- Improve Qdrant Brain viewport interaction so graph drag/zoom behaves more like a dedicated graph canvas: pointer dragging no longer selects labels, wheel zoom keeps the cursor anchor stable, toolbar zoom keeps the graph centered, and pan deltas are calculated in SVG coordinates instead of raw CSS pixels.

## [0.1.0-alpha337] - 2026-06-09

### Changed
- Add sparse landmark labels to Qdrant Brain point drilldowns: highly connected points and the active/focused point show short labels directly in the map without returning to a fully labelled dense graph.
- Add a Qdrant Brain center control that recenters the currently visible collection or point graph while preserving the current zoom level.

## [0.1.0-alpha336] - 2026-06-09

### Fixed
- Fix Qdrant Brain drilldown node activation by preventing viewport pan handling from swallowing node pointer events. The payload detail panel now sits below the graph, giving the graph more horizontal room.

## [0.1.0-alpha335] - 2026-06-09

### Changed
- Change the Qdrant Brain on `/memories/map` from a fully labelled all-node graph to a drilldown view. The graph now starts at Collection level, opens a Collection into unlabeled Qdrant-style point nodes, and keeps payload details in the side panel so dense memories stay readable.

## [0.1.0-alpha334] - 2026-06-09

### Fixed
- Fix the Qdrant Brain sampler runtime error caused by a stale `_normalize_user_id` helper reference. `/memories/map` can now sample Qdrant points through the existing user-filter path instead of falling back to the empty-state error.

## [0.1.0-alpha333] - 2026-06-09

### Fixed
- Make the Qdrant Brain visible on `/memories/map` even when the first sampled collections do not produce graphable points. ARIA now samples additional ARIA Qdrant collections beyond the narrow recall/document target set and renders a clear empty-state diagnostic instead of silently showing no Brain section.

## [0.1.0-alpha332] - 2026-06-09

### Added
- Add a Qdrant Brain visualization into `/memories/map`. The existing Memory Map now includes a zoomable, pannable similarity graph built from a bounded Qdrant point sample. ARIA computes semantic edges server-side and exposes only safe labels, previews, collection names, and point IDs to the browser; raw vectors are never rendered.

## [0.1.0-alpha331] - 2026-06-08

### Fixed
- Treat explicit user requests to research/search/browse the internet as Web Search freshness candidates, even when the topic is not a current-version question. The LLM freshness arbiter still crafts the actual query, preventing prompts such as DIY cyberdeck research from falling back to stale model-only chat answers.

## [0.1.0-alpha330] - 2026-06-08

### Fixed
- Hide the static ARIA header logo while the busy animation is active and render the holographic light effect on a transparent logo-emblem mask only. This prevents the old logo from showing underneath and avoids the visual impression of a full square plaque rotating.

## [0.1.0-alpha329] - 2026-06-08

### Fixed
- Keep the ARIA header logo frame static during the global busy animation and animate only the inner logo layer, so the holographic effect feels cleaner and less jumpy.

## [0.1.0-alpha328] - 2026-06-08

### Changed
- Replace the main ARIA header logo with the new ARIA artwork while keeping the existing `logo-aria-v01.png` runtime path for compatibility.
- Regenerate all browser icon assets (`favicon.ico`, `favicon-16x16.png`, `favicon-32x32.png`, `favicon-48x48.png`, `apple-touch-icon.png`) from the new ARIA logo.
- Replace the temporary busy-logo sprite animation with a CSS-driven holographic logo flip, glow halo and scanline effect to avoid visible sprite-frame labels and improve smoothness.

## [0.1.0-alpha327] - 2026-06-08

### Changed
- Replace the subtle busy-logo ring overlay with the new `aria_rotate.png` sprite animation. Whenever ARIA enters the global busy state, the brand logo now switches to the horizontal ARIA rotation sprite.

## [0.1.0-alpha326] - 2026-06-08

### Fixed
- Improve automatic freshness web-search quality for current version and latest release questions. ARIA now steers freshness queries toward official changelogs, GitHub releases, package registries and vendor docs, and ranks those sources ahead of generic news hits for version lookups.

## [0.1.0-alpha325] - 2026-06-08

### Changed
- Speed up the Notes workspace folder and board navigation by loading lightweight note previews for board/sidebar rendering and reading the full Markdown body only when a note is opened, exported, saved, or deleted.

## [0.1.0-alpha324] - 2026-06-08

### Fixed
- Stop passing Notes context into the Web Search skill when web search was added automatically by chat freshness arbitration. This removes visible `Notiz-Kontext` source lines from automatic current-product/version answers while keeping explicit web-search prompts able to use Notes context as search assistance.

## [0.1.0-alpha323] - 2026-06-08

### Changed
- Add a trusted freshness instruction with the current date to final chat prompts when ARIA automatically adds web context for current product/version/setup questions. This keeps answers from mixing fresh web results with outdated fallback dates or training-cutoff language.

### Fixed
- Suppress local Notes/Memory context in automatic freshness web-search answers unless the user explicitly asks for local notes, documents, or memory. Explicit web searches can still use note context as search assistance.

## [0.1.0-alpha322] - 2026-06-08

### Added
- Add chat freshness arbitration for current product, version, release, API, SDK, CLI and setup questions. When Web Search is configured, ARIA can now add web context before the final chat answer instead of relying on stale model knowledge for current tooling questions such as OpenAI Codex setup.

### Fixed
- Keep explicit local notes/document questions out of the automatic freshness web-search path.

## [0.1.0-alpha321] - 2026-06-08

### Fixed
- Treat an explicitly named SFTP target in prompts such as `liste die dateien auf meiner sftp verbindung dev-node-01` as a hard requested profile. If that SFTP profile does not exist, ARIA now reports the missing SFTP profile instead of falling back to stale memory from another SFTP target.

## [0.1.0-alpha320] - 2026-06-08

### Changed
- Keep multi-target SSH operator summaries LLM-authored while sending compact per-target result facts to the summary prompt. This reduces prompt bulk for large health checks without replacing the LLM interpretation.
- Raise bounded multi-target SSH execution parallelism slightly so large read-only checks spend less time waiting for slow targets in serial batches.

### Fixed
- Let requested role phrases such as `developer server` expand through SSH connection metadata before single-target resolution. Prompts like `haben meine developer server noch genug festplattenspeicher` should now stay on the developer-server group instead of collapsing to the first matching host.
- Treat multi-target payloads with `connection_refs` as already resolved in the requested-ref guard, avoiding false “missing connection ref” handling for grouped SSH actions.

## [0.1.0-alpha319] - 2026-06-07

### Changed
- Parallelized allowed multi-target SSH execution with bounded concurrency. Large checks such as `wie fit sind meine server?` no longer wait for each SSH target strictly one after another; result ordering and preflight details stay stable.
- Clear pasted-log/advice prompts can now run a bounded chat-vs-action arbitration before the expensive LLM capability-draft step. This keeps prompts such as `was mach ich damit: Message from syslogd ... soft lockup ...` in chat faster when the LLM chooses advice instead of runtime.

### Fixed
- Ignore stale Memory hints that point outside an already detected plural SSH target group. Prompts such as `haben meine developer server noch genug festplattenspeicher` should stay on the matching developer-server group instead of jumping to an unrelated recent host such as a management server.

## [0.1.0-alpha318] - 2026-06-07

### Fixed
- Let LLM-generated SSH capability drafts still pass through chat-vs-action arbitration before runtime. This keeps pasted log/advice prompts such as `was mach ich damit: Message from syslogd ... soft lockup ...` in chat even if the LLM proposes a diagnostic SSH command first.

## [0.1.0-alpha317] - 2026-06-07

### Fixed
- Prefer a concrete bounded SSH capability draft over Stored Recipe candidates when the draft already contains an explicit command. This prevents simple checks such as `prüf dev-node-01 kurz` from being replaced by broader, complex healthcheck recipes that may trip stricter SSH guardrails.
- Filter weak local RAG/document context from general diagnostic-advice chat answers such as pasted `syslogd`/kernel lockup messages plus `was mach ich damit`, so unrelated manuals are not shown as sources unless local notes/documents are explicitly requested.

## [0.1.0-alpha316] - 2026-06-07

### Added
- Added Runtime Health visibility for third-party sidecars when the ARIA runtime can inspect Docker containers. The card reports Qdrant, SearXNG, and Valkey image/status data without turning missing Docker-socket access into a warning.

### Changed
- Documented the deliberate full-stack sidecar update path and the required smoke checks after Qdrant/SearXNG/Valkey are updated.

### Fixed
- Added LLM arbitration before ambiguous connection routing, so known hosts/services can remain context for general advice or log/error interpretation instead of forcing an action merely because a configured connection name appears.
- Removed the deterministic DNS/Pi-hole command override from SSH agentic resolution. DNS health semantics now stay with the bounded LLM command decision or an explicit LLM-classified Guardrail health bundle; deterministic code only validates policy and runtime safety.

## [0.1.0-alpha315] - 2026-06-07

### Added
- Added an explicit chat Recipe Learn Mode in the chat toolbox. Users can start a bounded learning run, let ARIA observe following chat turns, and finish it into a review-only Learned Recipe candidate; no learned candidate becomes active automatically.
- Added a chat toolbox action and `/chat note` command to save the current chat history as a Markdown Note. The saved note is reindexed into the Notes Qdrant collection when indexing is enabled, while normal Notes deletion removes the derived index entries again.

### Changed
- Polished the Notes workspace with consistent ARIA form styling, calmer editor typography, a wider desktop work area, mobile-friendly stacking, and collapsible folder management.
- Extracted chat-context relevance filtering from the main pipeline into a dedicated core module, keeping the pipeline focused on orchestration while preserving the existing RAG safety behavior.
- Moved the generic routed capability runtime fallback into an `AgenticExecutionHandler`, so normal single-target capability execution now uses the same handler registry shape as RSS and multi-target SSH.

### Fixed
- Filter weak local RAG/document context from general how-to or product-information chat answers, so unrelated manuals are not shown as sources unless the user explicitly asks for local notes/documents.
- Apply that weak local RAG filter even when the normal chat route also carries an automatic `memory_recall` intent, preventing unrelated Arlo/Mill sources on prompts such as Claude Code version checks.
- Filter mixed local Memory/RAG source packets for general chat as well, so a single recall result containing document, fact, and session hits cannot leak unrelated Arlo/Mill sources into normal how-to answers.
- Make the `/help` home page start section clickable by linking Quick Start, Memory, Connections, Recipes, Releases and Upgrades, Pricing, Security, and the local help-system docs to their real `/help?doc=...` pages.
- Keep explicit local Notes/Documents/Memory questions out of connection runtime routing even when the query term matches a connection alias, and recognize natural Notes questions such as `was steht in meinen notizen zu ARIA`.
- Keep general setup/how-to questions that mention SSH/server terms in normal chat instead of turning them into SSH runtime actions.
- Let explicit but vague web-search follow-ups reuse the recent chat topic, so `suche im internet nach der neusten version` after a Claude Code question searches for the relevant product instead of a generic “newest version”.
- Aligned the Notes editor height more closely with the Notes sidebar on desktop so new/edit note screens feel visually calmer.
- Contained long Notes card titles, URLs, tags, and folder labels so the Notes board no longer overflows horizontally on desktop or mobile.
- Format `uptime -s` SSH results as a normal chat answer (`running since ...`) instead of exposing the raw Stored Recipe SSH executor output.
- Suppressed the normal automatic Learned Recipe update path while chat Recipe Learn Mode is active. `/lernen abbrechen` now discards the observed turn without also updating an existing learned recipe through the background auto-learning path.
- Let singular DNS/Pi-hole health role prompts such as `ist mein dns server ok` expand from a primary alias hit to matching primary/secondary DNS SSH profiles, while keeping mutating DNS requests single-target and guardrail-bound.
- Keep DNS resolver-probe hardening scoped to real DNS health/status prompts, so DNS-target disk or uptime questions keep their intended `df`/`uptime` commands instead of being rewritten to `dig`.

## [0.1.0-alpha306] - 2026-06-05

### Fixed
- Let singular role phrases such as `developer server` match Dev/Development connection metadata like `dev server`, `development`, or `entwicklung` instead of blocking the semantic LLM-selected SSH profile as an unknown requested ref.

## [0.1.0-alpha305] - 2026-06-05

### Fixed
- Prefer a real local DNS resolver probe for single-target DNS/Pi-hole health checks when the LLM only proposes a service-active check, while keeping explicit Guardrail health bundles in control when configured.

## [0.1.0-alpha304] - 2026-06-04

### Fixed
- Allowed standard read-only DNS probe commands (`dig`, `host`, `nslookup`) in the SSH read-only policy so DNS health checks can run without an unnecessary confirmation prompt.
- Added a Security Guardrails review link for built-in SSH policy blocks when no specific Guardrail profile is attached to the connection.

## [0.1.0-alpha303] - 2026-06-04

### Fixed
- Prevented the bounded planner / recipe-experience step from overriding an already resolved plural SSH multi-target payload. This keeps prompts such as “haben meine dev-server noch genug festplattenspeicher” on the resolved dev-server group instead of collapsing back to the first learned single target.

## [0.1.0-alpha302] - 2026-06-04

### Fixed
- Tightened plural SSH metadata grouping so the short seed `dev` no longer matches unrelated words such as `device`, and rebuilt already-complete single-target SSH plans into multi-target plans when a plural metadata group is detected.

## [0.1.0-alpha301] - 2026-06-04

### Fixed
- Improved plural SSH group scoping when one matching profile is found through memory/routing but sibling profiles only match through related metadata such as `development`, `entwicklung`, `code-server`, or `vscode`. Prompts such as “dev servers” now stay on the matching server group instead of collapsing to the first matched profile.

## [0.1.0-alpha300] - 2026-06-04

### Fixed
- Moved the optional SSH Service URL next to the metadata “Check with LLM” action so the URL source field is visible where it is used.
- Scoped plural SSH checks to strongly matched connection metadata groups, so prompts such as “dev servers” do not expand to every SSH profile when matching aliases/tags identify a narrower server set.

## [0.1.0-alpha299] - 2026-06-01

### Changed
- Clarified Learned Recipes wording so the overview refers to the local review/learning list instead of the ambiguous term “Store”.

### Fixed
- Let SSH connection metadata suggestions use Host/User/Port when no Service URL is configured, and clarify SSH host-key verification failures during connection tests.

## [0.1.0-alpha298] - 2026-05-21

### Added
- Added an LLM-assisted Guardrail draft flow on the Security page: ARIA can turn a natural-language safety intent into a reviewable Guardrail proposal, while saving remains an explicit user action and deterministic Guardrail evaluation stays unchanged.
- Added a lightweight working-status indicator to the Guardrail AI draft form, so users can see when ARIA is checking context, contacting the LLM, and preparing the review draft.
- Added a Guardrail test mode on the Security page, allowing saved Guardrails to be checked against example requests before they are attached to live connections.
- Added a visible stats billing-period reset on the Costs card. Reset now archives the current token/run log before starting a fresh local usage period.

### Changed
- Clarified Discord startup host reporting: ARIA now reports the configured base URL or an automatically detected local address instead of warning about a missing public URL.
- Clarified the Stats token card request label so it refers to the current local period instead of a misleading fixed 7-day label after a usage reset.
- Clarified the Stats cost card so ARIA labels LLM costs as usage estimates for orientation, not invoice-grade provider billing.
- Changed the default runtime log retention to 90 days and extended startup/maintenance cleanup to prune the redacted LLM prompt debug log alongside token/cost/activity logs.
- Started aligning connection detail pages around the SSH page as the master pattern: the shared connection status block is now collapsible, profile cards show a visible edit action, and the other connection detail pages use collapsible edit/create work areas instead of hidden mode-only cards.
- Moved guardrail attachment UI and save-time validation for SSH, SFTP, SMB, Webhook, and HTTP API connection pages into shared templates/context/helper logic, keeping current single-Guardrail behavior while preparing a cleaner Multi-Guardrail follow-up.
- Scoped saved Guardrails can now carry exact compatible connection kinds, so a File Access Guardrail drafted for SFTP is not offered on SMB connection pages and vice versa.
- Opened the security/advanced option panels by default on Guardrail-capable connection forms, making Guardrail assignment visible without an extra expand step.
- Reworked the Security Guardrails page into focused collapsible sections, so AI drafting, loading/editing, deletion, manual creation, and sample imports are no longer all expanded at once.
- Reworked the SSH connection page into focused collapsible sections and made profile cards open the edit mode, with a visible edit action and clearer access to the Guardrail selector.
- Replaced the unsupported Google Calendar device-code/OAuth setup with a simpler read-only secret iCal URL setup, so LAN/IP-only end-user installs can connect a personal calendar without Google Cloud clients, redirect URIs, client secrets, or refresh-token handling.
- Updated product, help, and wiki docs so current Google Calendar guidance points to the read-only iCal setup instead of the obsolete OAuth path.

### Fixed
- Made Operator Guardrail warnings actionable on the Stats page by listing the exact non-OK checks, their details, and deep links to the relevant section.
- Fixed Stats in-page detail links so targets such as Costs & Pricing open their collapsed details section before scrolling.
- Fixed Guardrail dry-run and runtime evaluation for file, webhook, and HTTP API actions so generated read-only/status Guardrails receive structured operation context such as `file_list`, `read`, `webhook_send`, `status`, and `health` instead of only a bare path or payload.
- Fixed pending routed action execution so user-confirmed SSH/HTTP actions that were classified as `ask_user` can pass their explicit confirmation into runtime policy instead of failing again with the same confirmation-required error.
- Tightened chat admin delete parsing so webhook/API payload text such as `delete user record` is no longer misclassified as a request to delete a connection profile.
- Tightened memory-forget routing so webhook/API/message payloads containing words like `delete` are not intercepted before capability routing.
- Improved deterministic blocked-action fallback text for file write attempts, so read-only Guardrail blocks explain the blocked write more naturally when the LLM explanation path times out.
- Classified HTTP API 4xx/5xx endpoint responses as external endpoint status errors instead of internal recipe failures, with clearer chat wording and no Discord recipe-error alert for expected HTTP status responses.
- Classified runtime Guardrail blocks as intentional security decisions in chat, avoiding the generic profile/access-rights warning and Discord recipe-error alert for expected policy blocks.
- Added direct Guardrail review links to runtime Guardrail block messages and aligned the blocked-action timeout fallback with the same security-decision wording.
- Routed colloquial multi-server health prompts such as `wie fit sind meine server?` into the SSH multi-target health path instead of falling back to generic chat/RAG.
- Fixed connection mode navigation so switching to “new connection” no longer carries an already selected profile ref, and hash links such as `#manage-existing` reliably open the intended edit card.
- Fixed SFTP connection status rows so profile cards receive the same edit URLs as other connection types.
- Removed the obsolete Google Calendar OAuth/device-code routes and setup UI to avoid the repeated `OAuth Client-ID fehlt` loop.
- Limited Google Calendar `next appointment` reads to the single nearest event, while broader upcoming/week ranges still return event lists.

## [0.1.0-alpha280] - 2026-05-16

### Fixed
- Added hidden Google OAuth JSON fallback fields for the Calendar device-code flow, so Safari/form-submit edge cases can still send the parsed client ID even when the visible input value is not received by the backend.

## [0.1.0-alpha279] - 2026-05-16

### Fixed
- Added a backend fallback for Google Calendar device-code start that rereads the submitted form when FastAPI injects an empty client ID, using the last non-empty client ID value from the form before failing.

## [0.1.0-alpha278] - 2026-05-16

### Fixed
- Autofilled the Google Calendar client ID and optional client secret in the browser as soon as an OAuth JSON file is selected, making upload parsing visible before starting the code flow.

## [0.1.0-alpha277] - 2026-05-16

### Fixed
- Let the Google Calendar default device-code flow accept OAuth client JSON files that provide a client ID without a client secret, and omit the secret from token refresh/device requests when the Google client has none.
- Clarified the Google Calendar setup UI so Client Secret is shown as optional for the default code flow and only required for the advanced browser-redirect path.

## [0.1.0-alpha276] - 2026-05-16

### Changed
- Clarified the Google Calendar setup guide by pointing users to download the OAuth client JSON from the Google OAuth Clients list before uploading it in ARIA.
- Pre-filled new Google Calendar profiles with `primary-calendar` as the default connection ref so the device-code setup does not fail on an empty internal profile id.
- Added a server-side Google Calendar default ref fallback so the OAuth/device-code handlers still use `primary-calendar` if the browser submits an empty ref.

## [0.1.0-alpha275] - 2026-05-16

### Added
- Added a Google Calendar device-code sign-in flow as the default self-hosted setup path, so ARIA can connect calendars from LAN/IP-only installs without requiring a public redirect URI.

## [0.1.0-alpha274] - 2026-05-16

### Fixed
- Treated `sind meine server in ordnung`, `are my servers healthy`, and related multi-server health phrasings as broad SSH health checks, so strict per-host guardrails can use the richer allowed status bundle instead of falling back to bare `uptime`.

## [0.1.0-alpha273] - 2026-05-16

### Fixed
- Routed short multi-server health prompts such as `sind meine server ok` into the SSH multi-target health path instead of falling back to generic chat/RAG.

## [0.1.0-alpha272] - 2026-05-16

### Changed
- Kept long-running chat working-status messages category-specific after the 8-second fallback, so server checks continue to show that ARIA is waiting for server responses instead of falling back to a generic working message.

## [0.1.0-alpha271] - 2026-05-16

### Added
- Added lightweight chat working-status messages that show the user what ARIA is likely doing while a request is running, such as checking servers, reading feeds, searching files, preparing messages, or summarizing results.

### Changed
- Let the main chat view expand toward the available viewport height so the message area grows with the screen while the composer remains anchored below it.

## [0.1.0-alpha270] - 2026-05-16

### Added
- Extended the Connection Action Contract and Provider Manifest with planner-level roles, confirmation metadata, sensitive-content metadata, and optional draft capabilities so future providers such as e-mail can share read/search/draft/send boundaries instead of adding provider-specific pipeline branches.
- Added the first generic Agentic Content Access request/result contract and handler registry for read/search/list providers, keeping future mail, files, tickets, notes, and similar content adapters separate from send/write side-effect execution.
- Added an optional Pipeline content-access hook: registered read/search/list handlers can take over from a generic `ActionPlan`, while existing IMAP/file/feed executors remain the fallback when no handler is registered.

### Changed
- Consolidated documentation under `docs/`: public/release docs stay tracked, the internal build log moved to `docs/internal/alpha-build-log.md`, and local-only handoff/history/screenshots now live under ignored `docs/local/`.

### Fixed
- Broadened vague multi-server health prompts such as `wie geht es meinen servern` to the same strongest allowed read-only SSH status bundle used for capacity checks, avoiding narrow `uptime` probes that can be blocked by stricter per-host guardrails.
- Fixed an unterminated mobile CSS block that could break later styles on iPhone-sized screens, added iOS safe-area viewport support, and kept mobile form fields at 16px to avoid Safari input zoom.

## [0.1.0-alpha269] - 2026-05-16

### Fixed
- Broadened vague multi-server capacity checks such as `haben meine server überall genug kapazität?` from a narrow `uptime` probe to the strongest read-only health/capacity bundle allowed across all SSH targets, with deterministic fallback to disk or memory probes when stricter guardrails require it.
- Kept partial capability executions labeled as their actual capability in chat details instead of showing misleading `memory_error` badges for blocked SSH subtargets.

## [0.1.0-alpha268] - 2026-05-15

### Fixed
- Fixed mixed-language plural SSH disk prompts such as `hab ich auf all meinen server mehr als 10gb harddisk speicher frei ?` so they enter the multi-target SSH disk-check path instead of falling back to memory/RAG.
- Added a bounded LLM capability-draft fallback for operational remote prompts that carry a connection-kind signal but miss deterministic capability lexicons, keeping flexible server/disk wording out of memory/RAG while still routing through deterministic policy, guardrails, and runtime.
- Loosened the Pre-RAG action gate so bounded LLM capability classification can override ambiguous keyword-router hits such as false `memory_store` matches, while explicit web-search/recipe-status and runtime guardrails remain deterministic.

## [0.1.0-alpha267] - 2026-05-15

### Added
- Added `docs/product/agentic-flow-map-alpha267.md` to map the controlled Agentic Action Flow from Pre-RAG context enrichment through bounded draft, policy/guardrails, runtime execution, summary, and context-only learning.
- Added `aria/core/agentic_execution.py` and `docs/product/agentic-execution-handler-contract-alpha267.md` as the first generic Agentic execution handler contract for future connection adapters.
- Added `aria/core/agentic_execution_registry.py` and `aria/core/agentic_execution_learning.py` so provider adapters register through a shared execution registry and record successful capability learning through one service.
- Added `aria/core/connection_provider_manifest.py` as the first internal provider-manifest contract, grouping existing Connection Action Contracts by connection kind with auth modes, runtime adapter ids, capability rows, and validation.

### Changed
- Agentic context debug lines now use a shared context-boundary helper, so capability-draft and candidate-pool debug output explicitly carry `boundary=context_enrichment`.
- Bounded planner selection debug now marks the draft phase with `boundary=draft`, making the Agentic debug contract easier to audit before further pipeline modularization.
- Learned Recipe promotion now goes through a shared deterministic promotion gate: multi-target observations stay context-only, side-effect learned actions can become review-ready but not directly executable, and stored-recipe promotion validates the same blockers used by the UI.
- Multi-target SSH learning now marks learned scope as `target_scope=multi_target` / `learning_origin=plural_target_scope`, preventing fleet checks from looking like single-target recipe evidence.
- Learned Recipe candidates now validate `connection_kind` plus `capability` against the Connection Action Contract before re-entering the bounded planner, so stale mismatched records such as RSS/feed actions with SSH scope cannot hijack SSH questions.
- Learned HTTP API action recording now accepts the normalized `api_request` capability as well as the legacy `http_api_request` alias when extracting the learned path.
- Multi-target SSH runtime execution now runs through `MultiTargetSSHExecutionHandler`, the first adapter on the generic Agentic execution hook path, while preserving existing preflight, guardrail, context-memory, learning, and operator-summary behavior.
- RSS feed execution now runs through `RSSFeedExecutionHandler`, moving RSS group-bundle and digest-option enrichment onto the same Agentic execution registry while keeping runtime execution, summaries, context memory, and learning behavior intact.
- Agentic execution learning is now centralized through `AgenticExecutionLearningService`, removing duplicated Learned Recipe recording code from the SSH and RSS handlers.
- The Connection Provider Manifest checklist now documents the concrete internal schema, built-in export, validator, and tests that future community/provider manifests must satisfy before UI or import support is added.

## [0.1.0-alpha266] - 2026-05-15

### Added
- Added `constraints/runtime.txt` as the Docker release-build dependency lock baseline, pinned from the tested `alpha264` container.
- Added an update-reconnect service worker that serves a small multilingual waiting shell when navigation happens during ARIA's brief container-recreate downtime, then polls `/health` and returns to the original page once ARIA is reachable again.
- Added `docs/product/codebase-modularity-audit-alpha257.md` to document the full codebase modularity audit, accepted provider-specific seams, residual watchpoints, and the LLM-first versus deterministic safety boundary.
- RSS digest planning now has a bounded LLM preference extraction step for explicit count/detail requests, passing the requested result count into the read-only RSS runtime while keeping deterministic caps and fallbacks.
- Learned Recipe review cards now show Curator debug metadata (`curation_source`, policy, status, timestamp, and skip/error reason), making it visible when bounded LLM curation ran or why it stayed skipped/context-only.
- Learned Recipe store entries now record qualitative learning signals (`new_pattern`, repeat, wording/scope/action variants, risky deviations) plus weighted learning evidence, so self-learning can distinguish repeated noise from useful variation.
- Added a Learned Recipe promotion preview page that shows the planned stored recipe manifest, policy/side-effect boundary, confidence/risk, trigger set, limits, and step parameters before an admin writes the promoted recipe.
- Added a bounded LLM Learned Recipe Curator that enriches successful single Agentic/Recipe learning events with review-only metadata: confidence, risk level, generalization hint, suggested trigger phrasings, promotion reason, and explicit reuse limits.
- Managed and internal update helpers now prune dangling Docker image layers and unused ARIA Docker images after a successful health check, keeping old image layers from filling `/var/lib/docker` while leaving containers, sidecars, volumes and tagged non-ARIA images untouched.
- Added machine-readable Agentic debug boundary constants that map debug lines back to the canonical context-enrichment, LLM-draft, policy/guardrail, and runtime-execution phases.
- Added `docs/product/agentic-live-regression-dossier.md` as the active live-test dossier for Agentic Action Flow regressions, linking real prompts to expected routing, policy, runtime, debug, and cost behavior.
- Added `aria/core/connection_action_contract.py` and `docs/product/connection-action-contract.md` as the shared contract layer for capability operation, executor-kind, policy-family, required-field, side-effect, and runtime-debug metadata.
- Added `docs/product/legacy-recipe-compatibility-audit.md` to make the remaining Skill-era bridges explicit: public surfaces stay recipe-first, while old imports, `/skills*` redirects, `skills:` config roots, and `skill_*` log/config fields remain compatibility seams until a deliberate migration release removes them.
- Added `aria/core/recipe_result_view.py` as the shared presentation layer for stored recipe execution summaries, skipped/error-continue step labels, and friendly recipe runtime error text.
- Added an Operator Guardrail card on `/stats` that combines Model Gateway Audit, Pricing Coverage, Startup Preflight, runtime health, and update-path status into one release/operations readiness view.
- Added explicit release metadata validation to the `/stats` Operator Guardrail, so missing or inconsistent release labels/versions are surfaced before a public build or update test is trusted.
- Added `docs/release/internal-build-smoke-test.md` as the repeatable internal build/update smoke checklist for `/stats`, Agentic routing, SSH guardrails, Discord confirmation, SMB, RSS, RAG, and managed update-path checks.
- Learned Recipe review cards now expose the underlying Connection Action Contract boundary (`family`, `policy`, `runtime`, side-effect state), making promoted/context-only candidates easier to audit before adoption.
- Learned Recipe review cards now show a localized review-maturity hint, separating strong promotion evidence from candidates that still need a target, action, or more successful runs.
- Bundled recipe template cards now show step count, connection families, trigger count, schedule/manual state, step types, and whether a template has side effects that require confirmation/policy review.
- Added `connection_action_manifest_rows()` plus `docs/product/connection-provider-manifest-checklist.md` as the bridge from today's Python-backed connection contracts to future declarative provider manifests.
- Added `docs/product/operator-observability-guardrails.md` to document the `/stats` release/operations guardrail rows, status semantics, cost-tracking strictness, and maintenance rules.

### Changed
- Docker builds now pin the Python and Docker CLI base image digests, install ARIA through the runtime constraints file, and disable build isolation after pinned `pip/setuptools/wheel` bootstrap, reducing base-image and Python transitive dependency drift before public releases.
- RSS read-only runtimes now size their internal transport budget from the requested digest count, so a `10 news` request is not truncated before the chat summarizer can format all requested entries.
- Learned Recipe curation and Recipe Experience Memory writes now run as non-blocking post-response follow-up work, keeping self-learning context-only while preventing successful chat actions from waiting on curation LLM calls or memory embeddings.
- RSS category reads now fetch the bounded feed set concurrently instead of serially, so slow or timing-out feeds no longer stack into minute-long digest responses.
- File-list summaries now separate directories from file examples, making SMB/SFTP folder listings easier to scan without changing the bounded file-list runtime.
- Routing Workbench kind options, pending chat action route kinds, default Qdrant routing-index kinds, and generic pipeline capability-gate pools now derive from the Connection Catalog / Connection Action Contract instead of page- or pipeline-local provider lists.
- Agentic read/message resolver capability families now derive from the Connection Action Contract, keeping LLM-backed operation resolution attached to the same provider contract used by runtime and policy.
- RSS category digests now collect multiple entries per feed up to a safe cap, instead of always taking one item per feed and formatting at most six items.
- RSS digest summaries now explain request/result gaps such as `10 requested, 4 found/readable, 1 skipped`, making feed count limits, timeouts, and sparse sources visible to the user.
- Learned Recipe review maturity now prefers weighted learning evidence over raw run count, reducing overconfidence from repeated identical executions while still keeping raw success count visible for audit.
- Recipe Experience Memory text now carries the learning signal and weighted evidence as planner context, so future LLM-backed planning can see whether an experience was fresh evidence, wording variation, or repeated noise.
- Learned Recipe cards now route promotable candidates through the promotion preview instead of writing a stored recipe directly from the list action.
- Learned Recipe Experience Memory now includes curated confidence/risk/generalization/limits in its semantic text, so future planning can use richer context while runtime execution remains gated by normal bounded planning and guardrails.
- `/recipes/learned` now explains the full learning lifecycle in the UI: where learned patterns come from, where review candidates and semantic experience memory are stored, what Promote/Dismiss/Delete do, and how learned context is retrieved without bypassing policy or guardrails.
- `/recipes` overview status cards now use compact, non-duplicated status labels and link directly to the matching recipe sections, so the lamp cards behave like the navigation elements they visually resemble.
- `/connections/status` now renders from cached/last-known connection health by default and exposes an explicit live-refresh link, so opening the status page no longer waits on slow SSH, RSS, API, SearXNG, or network probes.
- `agentic_runtime` debug lines now include `boundary=runtime_execution`, making runtime execution visually separate from context enrichment, LLM drafts, and policy decisions.
- Multi-target SSH checks now run an LLM-backed operator-summary pass over the already executed read-only results, with deterministic summaries kept as fallback only; this lets ARIA answer phrased constraints such as free-space reserves more flexibly without letting the LLM choose or bypass execution policy.
- The active alpha backlog now removes the completed Agentic Intelligence block from the open work list and keeps only the ongoing live-regression dossier process as a standing guardrail.
- `pre_rag_action_gate` debug output now includes the context-enrichment boundary plus target/path/content hints, and final chat/RAG responses in debug mode show an explicit `action_path=no_action` line when the Agentic gate intentionally declines to take over.
- The live agentic routing regression now covers the natural German prompt `habe ich genügend freien speicherplatz auf meinen servern?`, ensuring it stays out of `memory_store`/RAG and fans out through the bounded SSH multi-target disk check.
- Learned Recipe review cards now show a localized next-action hint, localize row status/safety labels with the active UI language, and preserve state/kind/sort filters after Promote/Dismiss/Delete actions.
- Learned Recipe admin success messages now use recipe-first `learned_recipes.*` i18n keys instead of legacy `skills.learned_*` compatibility keys.
- Stored recipe summaries now render skipped step markers through the same readable Recipe Result View formatter as executed steps.
- Connection Action Contract tests now pin the side-effect boundary so write/send/publish capabilities stay auditable and cannot silently look read-only.

### Fixed
- Learned Recipes review cards now render as full-width contained cards with wrapped badges and structured details for long LLM curator fields, preventing promotion reasons, trigger lists, and limits from tearing the `/recipes/learned` layout apart.
- Learned Recipe `file_list` candidates now display list/browse labels in the review UI even when older stored learning records still carry legacy `Read File` titles or intents.
- Assistant-message Markdown rendering now supports link labels that contain square brackets, so RSS titles such as Exploit-DB `[webapps]` entries remain clickable in the chat UI.
- Guardrail review hints now keep the visible `/config/security?guardrail_ref=...` path next to the clickable Markdown link, so copied chat text still contains the concrete review target.
- RSS digest formatting now preserves explicit `Link:` lines for source titles that already contain bracketed Markdown labels such as Exploit-DB `[webapps]` entries.
- Guardrail review references in blocked-action answers now render as Markdown links to `/config/security?guardrail_ref=...` instead of plain URL text.
- SSH policy-block responses now use a deterministic safety fast-path after the LLM has identified the intended action, avoiding an extra blocked-action LLM call and recovering the guardrail review URL from the selected connection when the safety decision did not carry it forward.
- Blocked policy/guardrail actions now keep the deterministic block decision but use a bounded LLM explanation step for the user-facing answer, with deterministic fallback, visible planned action, and direct `/config/security?guardrail_ref=...` review links when a guardrail profile is attached.
- Blocked-action LLM explanations now post-process live wording more strictly: if the LLM already mentions the concrete command, ARIA does not append a duplicate planned-action line, and weak guardrail references are replaced with the canonical guardrail review link.
- Blocked-action explanation calls now have a short timeout with deterministic fallback, and clearly mutating SSH requests skip the extra guardrail-intent LLM classification once policy has already blocked the command.
- Guardrail-kind mapping now lives in the Connection Action Contract and is reused by dry-run plus recipe runtimes, removing duplicated HTTP/file/MQTT/SSH mapping tables from execution paths.
- Memory Overview/Map and Stats now share a central Qdrant collection classifier, auto-detect ARIA system collections such as `aria_recipe_experience_*`, show Recipe Experience Memory even when empty, and keep future unknown `aria_*` system collections visible instead of silently dropping them from the graph.
- Learned Recipes flow explainer cards now render explanatory body text with the same subdued visual weight as the meta hints, keeping `/recipes/learned` calmer when the learned store is empty.
- Deleting a Learned Recipe now also purges matching Recipe Experience Memory points from Qdrant for the current user, preventing stale context-only learning data from surviving after an admin deliberately removes a bad candidate.
- `/stats` Operator Guardrail now has a dedicated Cost Tracking row: disabled token tracking and UsageMeter bypasses fail the release guardrail, while estimated-vs-logged cost gaps surface as warnings.
- `/stats` Operator Guardrail now includes Recipe Experience Memory reachability when that metadata is available, so Qdrant learning-memory outages are visible without making disabled/fresh installs look broken.
- Pricing refresh now reuses the shared pricing-settings sync path after preserving manual prices and aliases, so manual alias overrides remain visible in the running settings object immediately after a LiteLLM refresh.
- Agentic runtime debug operation/payload rendering now uses the shared Connection Action Contract instead of a local capability `if` chain, so future connection types have one explicit place to declare their runtime shape.
- Executor registration and capability routing now derive valid `(connection_kind, capability)` bindings from the Connection Action Contract; unsupported runtime bindings fail fast instead of quietly creating a side path outside the modular connection contract.
- Bundled sample-manifest regression coverage is now recipe-first: `samples/recipes/` is pinned as the public import surface, `/recipes` links are required there, and `samples/skills/` is verified only as a parity fallback for old installs.
- Stored recipe step output now keeps its legacy marker for compatibility but also renders a clearer recipe run status, readable per-step states, skipped steps, technical run details, and result text.
- Recipe Result View summaries now include executed/skipped step counts ahead of the detailed step list, making multi-step recipe output easier to scan.
- Operator Guardrail rows now carry stable machine-readable keys, so tests and future UI/admin tooling do not have to infer row meaning from visual order.
- The Legacy Recipe Compatibility Audit now includes an explicit migration gate for removing old Skill-era bridges instead of leaving those compatibility seams as vague cleanup debt.
- Multi-target SSH LLM summaries now carry structured threshold facts and are validated against the measured read-only `df -h` results; if the first LLM summary contradicts hard measurements, ARIA asks the LLM for a bounded repair and only falls back to a measured threshold summary if repair fails.
- Browser favicons are now real bundled favicon assets instead of a PNG served through `/favicon.ico`: ARIA ships `.ico`, 16/32/48 PNG variants and an Apple touch icon, the base template declares all of them, and regression tests pin the route, template links and package-data coverage.
- Multi-target SSH LLM summaries no longer pass unsupported per-call `temperature` overrides to the shared `LLMClient`; skipped or failed summary calls now leave a routing-debug line instead of silently falling back to the old deterministic summary.
- German disk-space questions such as `hab ich noch genug speicherplatz auf meinen servern?` no longer get misclassified as `memory_store` just because `speicherplatz` contains the memory-store verb stem `speicher`.
- Multi-target SSH disk summaries now honor explicit free-space thresholds from the user prompt, so requests like `mehr als 10gb freien festplattenspeicher` report hosts below that threshold instead of reusing the generic all-ok disk summary.
- The memory-store keyword boundary regex now uses Unicode word boundaries instead of an inline German character class, keeping the `speicherplatz` fix while passing the strict i18n literal audit.
- Learned Recipe Dismiss/Delete redirects now render human-readable info messages instead of leaking raw `learned_dismissed:*` / `learned_deleted:*` status codes.
- `/connections/types` now uses cached/last-known connection status rows instead of live-probing every configured service while rendering the type hub, so slow RSS or network endpoints no longer block that page load.

## [0.1.0-alpha251] - 2026-05-12

### Fixed
- The host-side update helper now preflights published Compose ports before recreating the ARIA service. If a new Compose plan would publish a host port that is already occupied by something other than the current ARIA container, the update aborts before touching the running stack instead of failing mid-recreate.
- RSS digests now print the URL explicitly below linked titles, so copied chat output still contains usable links even when the browser drops Markdown link targets during copy/paste.
- Natural plural SSH prompts such as `von meinen server` no longer leak article fragments like `requested_ref=n server` into routing debug output.
- Host-side public updates can now pass `--target-image` to move fixed-tag installs to a newer ARIA image while still recreating only the `aria` service; managed stack helper files are refreshed from the target image and file ownership is restored afterwards.
- `docker/aria-host-update.sh` no longer leaves a stale lock cleanup error on exit after an update, and its managed-file refresh avoids root-owned `.env` files on user-owned installs.
- Managed public stack updates now refresh/recreate only the `aria` service during normal `aria-stack.sh update`; stateful sidecars such as Qdrant/SearXNG remain untouched unless `repair` or `update-all` is run deliberately.
- Multi-target SSH fleet checks now keep all-ok responses compact and action-oriented: when every target looks healthy, ARIA reports the fleet status and "no action required" instead of listing every host result in the main chat answer; mixed results still surface only hosts that need attention, were blocked, or failed while the full execution trace remains in details.
- Plural SSH target requests are now finalized again after bounded planning/template normalization, so a late stale `connection_ref` missing-input state cannot undo the multi-target command draft and ask for one SSH profile.
- Mutating SSH requests such as `starte meinen dns server neu` can no longer be converted into a safe healthcheck guardrail fallback; ARIA keeps the intended mutating command visible and lets SSH policy block it.
- Plural SSH target requests with an empty command draft can now ask the SSH agentic resolver for the missing read-only command before deciding whether bounded multi-target execution is possible, and the resulting multi-target action clears stale `connection_ref` missing-input state.
- The alpha246 live-test sequence is now covered by one regression spanning multi-target SSH, management disk checks, DNS health, blocked restarts, API availability, Discord confirmation, and SMB root listing.
- Chat one-click confirmation buttons still send the signed confirmation command internally, but the visible user bubble now shows the clicked button label instead of the raw `bestätige aktion ...` token command.
- Recent file-context hints such as `im gleichen Ordner` now distinguish a previously listed directory from a previously opened file, so a follow-up after listing `/tmp` stays in `/tmp` instead of jumping to `/`.
- Chat one-click confirmation buttons now post the signed pending-action payload with the confirmation request, so the action can be confirmed even if the browser has not persisted the pending cookie yet; the typed confirmation fallback remains available.
- SSH block previews are now rebuilt when the agentic resolver replaces a stale generic command with the actual intended command, so restart/state-change requests show the mutating command that policy blocked instead of an old `uptime` probe.
- Recent file-context hints such as `im gleichen Ordner` now override default root/path placeholders like `.`, including explicit or single-profile SFTP/SMB routes.
- Plural SSH target requests such as `meine Server` now suppress stale stored-recipe and single-host memory candidates, but safe read-only SSH commands such as `df -h` can fan out across all matching SSH profiles as a bounded multi-target action with a localized multi-target summary.
- Multi-target SSH execution now preflights every target against its own profile allowlist, guardrail allow terms, and SSH read-only policy; mixed target sets execute allowed profiles and report blocked profiles as localized partial failures.
- Multi-target SSH chat responses now include a compact operator summary before per-host details, highlighting how many targets look ok, need attention, were blocked, or failed.

### Changed
- RSS category digests now keep useful operator context in the main chat answer: entries are rendered as a readable list with source, timestamp, short snippet, and clickable Markdown links instead of collapsing everything into a one-line headline/source summary.
- Public-facing release copy was refreshed for the post-`alpha167` rollup: README and Docker Hub overview now describe ARIA as recipe-first with LLM-assisted action planning, and `docs/release/public-alpha-rollup-alpha167-to-next.md` provides a human-readable GitHub/Docker release narrative.
- The active alpha backlog has been compacted so old build history lives in `docs/internal/alpha-build-log.md` / `CHANGELOG.md`, while `docs/backlog/alpha-backlog.md` now focuses on current blockers, live-test focus, and next cleanup steps.
- LiteLLM is no longer a hard base dependency of the ARIA package; model gateway calls load it lazily and Docker installs it explicitly via the `model-gateway` extra, so pricing can remain independent from the runtime provider package.
- SSH, HTTP API, SFTP/SMB file, outbound messaging, and read-only agentic resolvers now share one explicit LLM action-draft contract: enrich context via a target dossier, let the LLM propose only a bounded draft, and leave allow/ask/block decisions to policy and guardrails.
- Agentic Pre-RAG action paths now run inside a request usage scope, so LLM calls used for SSH/HTTP/File/Messaging/Read decisions are reflected in the visible `PipelineResult`, chat token badge, and token log instead of showing misleading `0 tokens`.
- Pending routed actions in chat now expose a one-click confirmation button instead of asking users to manually type a confirmation code; the signed pending-cookie flow and typed-token fallback remain in place for safety and compatibility.
- Agentic routing now fixes the first `alpha238` live-test outliers: generic HTTP availability prompts can use the only configured API profile instead of treating `erreichbar` / `reachable` as a profile name, SMB folder-list prompts default to the share root, and fresh Discord-send prompts are no longer consumed as a pending SMB path reply.
- Natural SSH status/disk wording now keeps the router at Intent/Ziel level and leaves the concrete command proposal to the agentic SSH resolver before guardrails run, instead of baking `uptime` / `df -h` into the capability router itself.
- Introduced an explicit generic Pre-RAG Action Gate in the pipeline: chat/memory requests are first checked for bounded capability/connection actions before document RAG, with `pre_rag_action_gate` debug output showing whether unified routing or direct capability action took precedence
- Natural SSH disk wording now treats `HD`, `HDD`, `hard drive`, and German plate/free-space variants as disk-check terms, so prompts such as `wie sieht die hd auf meinem management server aus` route to the bounded SSH `df -h` action path before generic RAG chat can pull irrelevant documents
- The Workbench surface at `/config/workbench` now links directly to `/config/llm/debug`; the LLM Prompt Debug entry is no longer only visible on the older settings overview
- LLM Prompt Debug now persists redacted audit entries to `data/runtime/llm_audit.jsonl` in addition to the in-memory ring, so prompts remain visible across multiple web workers and can still be cleared from `/config/llm/debug`
- Final chat/RAG responses now tag their LLM gateway call with `source`, `operation=final_chat_response`, `user_id`, and `request_id`, making the exact prompt context and model answer inspectable instead of only token totals
- Recipe `llm_transform` steps now tag their gateway calls as `recipe_runtime` / `llm_transform` for clearer prompt debugging
- Added an admin-only LLM Prompt Debug page at `/config/llm/debug` backed by the central `LLMClient` gateway; recent prompts, responses, source, operation, model, duration, and token usage are captured in memory with secret redaction and no disk persistence
- The LLM gateway now records failed, empty, and successful calls in a bounded in-memory audit ring so agentic routing can be inspected without guessing what was sent to the model
- Soft/ordinal connection targets such as `zweiten dns server` now trigger semantic LLM disambiguation across the available profiles before an alias-derived explicit ref is accepted, so `second DNS server` can resolve to `pihole2` instead of the first `dns server` alias match
- SSH restart/state-change requests now get a second mutating-intent LLM pass when the first command proposal incorrectly substitutes a harmless status probe such as `uptime`; the real intended command is then blocked by policy instead of misleading the user
- Explicit SSH command requests such as `führe uptime auf meinem dns server aus` now keep the requested command as the action draft; ARIA no longer expands those into a full healthcheck bundle unless the user asked for a broader health/status check
- Mutating SSH requests now ask the SSH LLM resolver to identify the intended command so the policy layer can block the real requested operation instead of showing a misleading safe `uptime` fallback
- Plural SSH target requests such as `meine Server` no longer accept a single-host semantic LLM guess when no explicit target was selected; until multi-target execution is implemented, ARIA keeps the request bounded instead of silently choosing one server
- Bounded planning now carries an explicit `context_enrichment -> llm_action_proposal -> policy_guardrail_decision -> runtime_execution` contract into the LLM prompt, planner result, and routing debug output, making deterministic context advisory while keeping guardrails as the execution gate
- Natural SSH status requests that arrive with only a generic deterministic `uptime` draft now ask the bounded SSH LLM resolver for a concrete command proposal first, unless the user explicitly requested `uptime`; the resulting command still goes through the same SSH guardrail allow/ask/block policy
- Google Calendar now translates the most common real-world OAuth and API failures more precisely across both connection tests and live `calendar_read` execution, including expired refresh tokens, disabled Calendar APIs, and permission/scope mismatches
- natural calendar search requests no longer depend only on quoted text; ARIA now also extracts simple unquoted filters such as `Termine mit Zahnarzt nächste Woche`
- short calendar follow-ups now reuse recent calendar context more naturally, so requests like `und morgen?` can keep the last calendar filter instead of falling back to a generic chat answer
- the Google Calendar setup page now includes an explicit reconnect hint for the common case where only the refresh token needs to be renewed later
- Google Calendar no longer depends on a manual OAuth Playground copy/paste step; ARIA can now start the Google sign-in flow directly from the connection form and store the refresh token server-side on callback
- Notes can now be browsed more naturally from chat and the toolbox, including folder listing, folder-scoped note lists, and opening a note by query
- Notes folders can now be renamed directly from the Notes UI, while note title edits now explain more clearly that changing the title also renames the note
- note cards on the Notes board now wrap long titles instead of stretching the whole board layout sideways
- `öffne notizen in ordner ...` now resolves into the Notes flow and opens the folder view instead of falling through into unrelated generic routing
- watched websites now have their own lightweight chat entry points for opening and listing profiles, and admin users can start a website profile via the short `beobachte https://...` command that drops into the existing confirm flow
- `/stats` now renders token usage as a compact vertical token card with one prominent total and smaller detail rows, so the added chat/embedding/model metrics no longer break the top-row visual balance
- `/stats` now includes a `Model Gateway Audit` card that shows the active chat model, embedding model, shared `UsageMeter` status, memory embedding wiring, token-log status, and unpriced-token warnings
- LLM and embedding runtime calls are now guarded by a contract test so provider calls stay behind the metered `LLMClient` / `EmbeddingClient` gateway instead of reappearing as untracked side paths
- natural SSH status questions such as `wie geht es meinem dns server` now count as health/status requests for the guardrail fallback, so an unsafe or unlisted narrow `uptime` draft can be replaced by the allowed healthcheck command bundle
- successful SSH healthcheck guardrail fallbacks now enrich Learned Recipe candidates with the natural user wording, the final allowed command bundle, target scope, and fallback provenance; unpromoted learned recipes remain non-executable until review/promotion
- successful recipe/guardrail runs are now also indexed as semantic `Recipe Experience Memory` in Qdrant and retrieved as bounded planner context only, so prior successes can inform planning without becoming a direct executor
- `/stats` now shows Recipe Experience Memory status, collection count, and point count, making the new self-learning context layer visible during testing
- the Learned Recipes review UI now exposes the original user wording and learning origin for each candidate, making promotion decisions easier to audit
- full SSH healthcheck summaries now end with a human conclusion such as `Fazit: unauffällig` or `Fazit: Handlungsbedarf`, so users get an operator-level read instead of only raw metrics
- SSH healthcheck summary wording now uses `result_ssh.*` i18n keys from the language files instead of German text embedded in the summarizer code, with an English regression test covering the full healthcheck path
- a new `scripts/audit_i18n_code_literals.py` helper and `docs/backlog/i18n-code-literal-audit.md` report document the remaining German literals in Python code so the cleanup can be handled deliberately
- Connection Admin now uses structured error codes and `connection_admin.*` i18n keys for success/error messages instead of German runtime strings in Python
- Chat Admin connection/update/backup/status replies now use `chat_admin.*` i18n keys instead of hard-coded German assistant text
- Connection mutation handlers now use `connection_mutation.*` i18n keys and structured errors for form/redirect failures instead of raw German runtime strings
- Connection catalog UI labels, Discord toggle metadata, and chat insert examples now use `connection_catalog.*` / `config_conn.*` i18n keys instead of raw German metadata strings in Python
- Recipe Runtime status output, step error markers, recipe-step summaries, SMB connection errors, and the stored-recipe selection prompt now use `recipe_runtime.*` i18n keys instead of raw German runtime strings
- Chat command catalog no longer carries the old German-to-English insert replacement bridge; delete-connection inserts now use `chat.tool_delete_connection_insert`, and remaining German toolbox text is confined to i18n-backed fallbacks
- Recipe route wizard presets, follow-up-step suggestions, connection-choice hints, and import/wizard validation errors now use `recipes_routes.*` i18n keys instead of raw German UI/runtime strings
- Memory routes now use `memories_routes.*` i18n keys for graph labels, manual memory types, document delete/import errors, backend validation errors, and compression status text instead of raw German route strings
- Chat pending flows now use `chat_pending.*` i18n keys for action confirmations, safe-fix prompts, memory-forget confirmations, and alias follow-ups, removing German UI text from `chat_pending_flows.py`
- Config intelligence/workbench routes now use `config_workbench.*` i18n keys for LLM and embedding profile validation, model API validation, file editor errors, and error-interpreter rule validation
- Main app documentation defaults, runtime reload errors, startup Discord alerts, and unexpected-error responses now use English fallbacks or `app.*` i18n keys instead of German literals in `main.py`
- `/stats` pricing coverage now falls back directly to the ARIA bundled pricing seed and treats rows with logged numeric model costs as priced, avoiding false “unpriced model usage” warnings for known Claude/OpenAI models when the saved pricing catalog is empty or stale
- Action Planner dry-run, heuristic, and bounded-recovery messages now use `action_planner.*` i18n keys, and Notes Store validation/file-action errors now use `notes_store.*` i18n keys instead of German core literals
- Document ingest validation/errors and Safe-Fix held-package summaries/execution messages now use `document_ingest.*` and `safe_fix.*` i18n keys instead of German core literals; localized document stopwords also moved out of Python code
- Config surface routes and Notes route status messages now use `config_surface.*` and `notes_routes.*` i18n keys instead of German route literals
- Routing config/workbench route messages and shared main UI error helpers now use `config_routing_routes.*` and `main_ui.*` i18n keys instead of German route/helper literals
- Config profile helper messages and Stats route summaries now use `config_profile_helpers.*` and `stats_routes.*` i18n keys instead of German helper/route literals
- Action planner candidate detail labels and agentic SSH clarification/confirmation messages now use `action_planner_candidate_details.*` and `ssh_agentic_resolution.*` i18n keys instead of German core literals
- Operations config, connection context hints, action candidate taxonomy labels, and IMAP result summaries now use `config_operations_detail_routes.*`, `connection_context_helpers.*`, `action_candidate_taxonomy.*`, and `result_imap.*` i18n keys instead of German literals
- Auth surface, main config helpers, Notes Magic, HTTP API result summaries, and Website Runtime now use `auth_surface_routes.*`, `main_config_helpers.*`, `notes_magic.*`, `result_http_api.*`, and `website_runtime.*` i18n keys instead of German runtime strings or local German note-folder lexicon in Python
- Google Calendar support errors, Web Search result text/lexicon, config overview helper messages, and chat execution warnings now use `google_calendar_support.*`, `web_search.*`, `config_surface_helpers.*`, and `chat_execution_flow.*` i18n keys instead of inline German strings in Python
- Capability detail lines, action-planner result labels, RSS result summaries, and file-operation summaries now use `capability_catalog.*`, `action_planner_result_state.*`, `result_rss.*`, and `result_file_operation.*` i18n keys instead of hard-coded German labels in Python
- Connections surface headings/cards and Notes context/index fallback text now use `connections_surface_routes.*`, `connections_surface_helpers.*`, `notes_context.*`, and `notes_index.*` i18n keys instead of German UI/runtime strings in Python
- LLM client errors, executor registry errors, learned-recipe promotion validation, and stored-recipe manifest validation now use `llm_client.*`, `executor_registry.*`, `learned_recipe_promotion.*`, and `recipe_manifests.*` i18n keys instead of German runtime strings in Python
- Config guardrail/persona errors, config file-save reload warnings, OPML RSS import exhaustion, and SSH authorized_keys write failures now use `config_access_detail_routes.*`, `config_persona_routes.*`, `config_support_helpers.*`, `connection_reader_helpers.*`, and `connection_support_helpers.*` i18n keys instead of German runtime strings in Python
- User-admin CLI text, secure-store/migration errors, source-lookup previews, SSH template term matching, and HTTP API status term matching now use `user_admin.*`, `secure_store.*`, `secure_migrate.*`, `behavior_families.*`, `execution_dry_run_template_payloads.*`, and `http_api_agentic_resolution.*` i18n keys instead of German literals in Python
- The i18n audit now reports zero `raw_runtime_literal` and zero `llm_prompt` findings after moving the remaining config, connection-health, maintenance, router, routing-hint, RSS grouping, learned-recipe UI, runtime-diagnostics, pipeline, and memory-skill strings into language keys
- The first large `inline_localized` cleanup moved connection runtime, recipe runtime, and chat command catalog fallback text behind `connection_runtime.*`, `recipe_runtime.*`, and `chat.*` language keys, reducing inline localized audit findings from 252 to 93
- A second `inline_localized` cleanup moved capability pipeline messages, recipe overview/wizard fallbacks, and memory hub/upload text behind `pipeline_capability_messages.*`, `skills.*`, and `memories_routes.*` language keys, reducing inline localized audit findings from 93 to 50
- The final `inline_localized` cleanup moved dry-run labels/reasons, learned and stored recipe candidate previews, planner follow-up prompts, connection mutation status messages, pipeline capability details/execution text, auth JSON fallbacks, and docs license summaries behind i18n keys, reducing inline localized audit findings from 50 to 0; remaining German code-literal findings are input lexicon only
- The declarative input-lexicon cleanup moved routing profiles, capability-routing terms, chat notes/admin/website command patterns, action-planner scoring/extractor hints and template overrides, auto-memory rules, routing-resolver scoring, capability-router patterns, recipe-runtime matching terms, connection-catalog extras, semantic resolver prompts, pipeline missing-input patterns, Notes tag normalization, and update-helper failure detection into `aria/lexicons/*.json`; visible Chat Notes replies now use `chat_notes.*` i18n keys, and the German code-literal audit now reports zero findings
- `scripts/audit_i18n_code_literals.py` now has a `--strict` guardrail mode plus regression tests, so new German runtime, inline-localized, LLM-prompt, or input-lexicon literals in Python can fail validation instead of silently re-entering the codebase
- Python package builds now declare ARIA runtime assets as setuptools package data, including `aria/i18n/*.json`, `aria/lexicons/*.json`, templates, and static files, so normal wheel installs keep the i18n and lexicon cleanup usable outside the Docker source tree
- `docs/backlog/alpha-backlog.md` now reflects the current post-`alpha215` working state, separating shipped build facts from unbuilt guardrail/package-data follow-ups and reprioritizing the remaining backlog around Recipe legacy, model-cost tracking, Experience Memory, monolith cleanup, i18n guardrails, and release hygiene
- `/stats` now separates logged USD from estimated USD and can reprice historical token rows from model names plus prompt/completion or embedding token counts once Claude/OpenAI pricing is known, making stale zero-cost rows visible instead of silently understating usage
- Recipe Experience Memory now adds explicit planner-debug lines for retrieved experience hits, including score, target, success count, and previously working action, while marking the layer as `context_only` so learned memory remains planner context and never becomes a direct executor
- Learned Recipe review cards now surface the original user wording, target scope, previously working action, and safety state directly in the admin UI, making it clearer that unpromoted experience is review/context only
- The SSH healthcheck learning path now has an end-to-end regression covering successful guardrail fallback execution, Learned Recipe store payload creation, Experience Memory storage, and later planner-context retrieval/debug formatting
- Learned Recipe admin UI text now uses the `learned_recipes.*` i18n namespace instead of the legacy `skills.learned_*` keys, keeping the visible Recipe-first surface separated from Skill compatibility keys
- Recipes hub, nav, page headings, overview cards, start/custom/system/template sections, save/load hints, wizard controls, wizard form labels, and wizard JavaScript status text now use `recipes.*` / `learned_recipes.*` i18n keys instead of legacy `skills.*` keys or hard-coded German template strings, while old Skill keys remain only for compatibility and internal migration seams
- `recipes_routes.py` is now slimmer and more readable after moving Recipes overview/next-step UI construction into `recipes_surface_context.py`, Wizard preset/follow-up/connection catalog data into `recipes_wizard_catalog.py`, Learned Recipe promote/dismiss/delete action handling into `recipes_learned_actions.py`, sample-template listing/import handling into `recipes_template_import.py`, Wizard form-to-manifest save logic into `recipes_wizard_save.py`, and shared return-to/CSRF/admin helpers into `recipes_route_support.py`
- Recipe runtime matching now uses recipe-first helper names internally (`_recipe_tokens`, `_recipe_match_score`, `_looks_like_recipe_execution_request`) while retaining legacy `skill_*` aliases for compatibility
- Recipe runtime file/guardrail diagnostics now use `recipe_runtime.*` i18n keys instead of embedded German strings, unused duplicated SFTP/SMB list-step helpers were removed, and SFTP/SMB file execution now lives in `recipe_runtime_file_adapters.py` behind a small `RecipeFileRuntime` adapter
- RSS feed parsing, URL cleanup, timestamp normalization, summary formatting, and single-feed execution now live in `recipe_runtime_rss.py`, while `RecipeRuntime` keeps thin compatibility wrappers for existing tests and callers
- Google Calendar OAuth token exchange, event fetching, range calculation, event-time formatting, and result rendering now live in `recipe_runtime_calendar.py`, with `RecipeRuntime.execute_google_calendar_read(...)` preserved as the stable public entry point
- Webhook sends, Discord sends, and HTTP API requests now live in `recipe_runtime_http.py`, reusing the existing guardrail enforcer through dependency injection while keeping the stable `RecipeRuntime` execution methods as thin delegates
- SMTP email send, IMAP read/search, and MQTT publish execution now live in `recipe_runtime_messaging.py`; `RecipeRuntime` keeps compatibility delegates for the existing public methods and shared mail-header helper
- Direct Discord recipe steps now reuse the HTTP runtime adapter for webhook delivery instead of building `URLRequest` calls inside the recipe step executor
- Recipe step execution, condition checks, template rendering, SSH step summaries, and LLM transform steps now live in `recipe_runtime_steps.py`, reducing `RecipeRuntime` to runtime composition and compatibility delegates
- RSS group-read aggregation now also lives in `recipe_runtime_rss.py`, leaving `RecipeRuntime.execute_rss_group_read(...)` as a compatibility delegate
- `/stats` pricing refresh now preserves local/custom pricing entries and lets marked manual overrides (`source_name: Manual` or `notes: source=manual`) keep precedence over refreshed provider prices, so ARIA can update provider catalogs without destroying deployment-specific cost settings
- `/stats` pricing refresh now also imports the public LiteLLM GitHub pricing JSON as a short-timeout remote source without depending on the LiteLLM Python package for pricing, expanding automatic model-price coverage while keeping ARIA's bundled seed and manual overrides as safeguards
- LiteLLM's public GitHub pricing JSON is now the primary pricing source: ARIA caches the last good copy in `data/pricing/litellm_model_prices.json`, refreshes it on startup when older than seven days, uses `/stats` refresh as a forced update, and falls back to the cached copy or bundled emergency seed when GitHub is unavailable
- `/stats` now labels the active LiteLLM GitHub pricing source and local cache explicitly, and the top Costs card uses a compact hero/list layout so estimated/logged/average/request metrics no longer stretch the header row
- `/stats` cost metrics now use a stable two-column LED matrix instead of mixed label/value rows, preventing labels such as `Logged USD` from wrapping away from their values in the narrow top-row card
- `/stats` now stacks the long Model Gateway Audit and Recipe Experience Memory diagnostics as full-width rows, avoiding a broken two-card row with an empty third column
- Recipe legacy internals are reduced further: action-planner recipe candidates now live in `action_planner_recipe_candidates.py`, stored recipe manifests use recipe-first helper/cache names, wizard presets use recipe-type names internally, and old `skill_runtime.py` / `custom_skills.py` / `skills_routes.py` modules are explicit compatibility wrappers instead of `sys.modules` aliases
- Recipe Experience Memory now normalizes learned entries with target/action/experience fingerprints, keeps distinct successful actions for the same learned recipe, applies explicit target/capability/intent ranking bonuses during recall, and surfaces recent experience rows on `/stats` for easier self-learning audits
- Monolith cleanup continued along product seams: Pipeline Recipe Experience context/debug formatting, Recipe Runtime status text, and Recipes manifest delete/export actions now live in dedicated helper modules with thin compatibility delegates in the old entry points
- i18n and packaging hygiene now have stronger regression coverage: the strict German code-literal audit is exercised through its CLI, and package-data tests verify that every current i18n, lexicon, template, and static runtime asset is covered by setuptools package data
- Release hygiene now blocks common generated packaging artifacts (`*.egg-info/`, `build/`, `dist/`, `*.whl`) and has a regression test for current release-label/backlog consistency plus required container source assets such as recipe prompts and sample recipe manifests
- `/stats` now includes an admin-only Pricing Overrides panel for adding local model aliases and manual chat/embedding prices directly from the UI; manual prices are marked as overrides, survive LiteLLM refreshes, and can be removed without exposing provider-synced rows to accidental deletion
- Recipe Experience Memory can now be deliberately promoted from `/stats` into the Learned Recipe review store as a context-only candidate; web/search-derived review entries are supported by the same core contract, while non-promotable capabilities no longer show a stored-recipe Promote action in the Learned Recipes UI
- Natural SSH health questions such as `ist mein dns server ok` now use a bounded LLM guardrail-intent classifier before falling back to the configured healthcheck bundle, instead of requiring a new hard-coded phrase or executing a blocked bare `uptime` probe
- Agentic action resolution now has a shared core contract that separates LLM-proposed action drafts from policy/runtime decisions, with SSH and HTTP API debug paths starting to report the same draft-versus-policy boundary
- SSH and HTTP API agentic resolution now share the same action-draft, policy-result, and debug-line helpers, making the first two capability families follow one visible `LLM draft -> policy decision -> runtime` shape
- File operations now have the same generic agentic action-draft shape for SFTP/SMB list/read/write, plus secret-free file target dossiers and dry-run debug output that separates the proposed file action from the `file_access` policy result
- SFTP/SMB file operations now have a bounded LLM resolver that can fill missing operation details from the file target dossier, while already complete file actions stay deterministic and every draft still flows through the normal payload, confirmation, and `file_access` guardrail checks
- Discord, webhook, email, and MQTT outbound messaging now share a bounded agentic message draft and secret-free message target dossier; the LLM resolver only fills missing content/topic fields, while complete drafts stay deterministic and all sends still require the normal side-effect confirmation/guardrail path
- RSS, Google Calendar, IMAP mail read/search, and watched website read/list flows now share a bounded read-only agentic draft plus secret-free read target dossier; the LLM resolver only fills missing selector/query fields and complete read actions remain deterministic
- Agentic policy actions are now canonicalized to `allow`, `ask_user`, or `block` in the shared core, and dry-run debug for SSH, HTTP API, File, Messaging, and Read capabilities now exposes the same draft-versus-policy boundary
- Deterministic helper logic now has an explicit boundary registry for routing hints, normalizers, policies, runtimes, summaries, and compatibility wrappers, with regression coverage that prevents treating deterministic helpers as new product-level intent logic
- Agentic debug lines now mark whether a line represents a draft, policy, or draft-policy boundary, and routed runtime execution can emit a separate `agentic_runtime` debug line before the human-facing execution details
- Old `bounded_planner_poc` / `ssh_status_agentic_poc` naming has been removed from the active bounded-planner path; the legacy candidate-key fallback is kept only for config compatibility
- Agentic free-form regression coverage now verifies that natural file, message, read/mail, and HTTP status prompts can fill bounded drafts while mutating SSH and HTTP requests are still blocked or confirmed by policy rather than executed directly
- The Model Gateway contract test now blocks direct OpenAI/Anthropic SDK usage and synchronous/asynchronous LiteLLM bypasses outside the central `LLMClient` / `EmbeddingClient`
- `UsageMeter` now has a regression test proving known Claude chat models and OpenAI embedding models resolve to non-zero USD costs through the central ARIA pricing fallback
- `/stats` pricing now uses the ARIA bundled pricing seed plus OpenRouter enrichment instead of only OpenAI/Anthropic rows, covering common OpenAI and Anthropic names offline while OpenRouter remains available as live enrichment
- The `/stats` unpriced-model warning is now a compact status strip with a details link, so a missing price can no longer break the top Costs card layout
- `/stats` pricing refresh now shows a visible result message with refreshed chat/embedding model counts, timestamp, and refresh errors directly in the pricing details panel
- `/stats` pricing details now list the exact unpriced model names and token counts, making custom deployment aliases easy to identify and map
- `/stats` pricing refresh now treats ARIA bundled pricing seed as the primary offline source and keeps OpenRouter as a short-timeout optional enrichment, so a slow OpenRouter response no longer makes the refresh feel stuck
- `/stats` pricing refresh now shows an inline "refreshing prices" indicator next to the button while the HTMX request is running
- Pricing no longer imports `litellm` or reads `litellm.model_cost`; the cost layer now uses an explicit ARIA-owned seed plus optional OpenRouter enrichment, while LiteLLM remains only the current runtime adapter for model calls
- Pricing now supports `pricing.model_aliases` for deployment/provider aliases; common embedding aliases such as `embed-small` and `openai/embed-small` map to `openai/text-embedding-3-small`, fixing false unpriced-token warnings for LiteLLM/OpenAI-compatible embedding deployments

### Fixed
- plural/fleet-style target requests such as `check mal ob meine server noch genug festplatten platz haben` no longer let stale Experience/Memory hints force a single previous SSH profile; ARIA now keeps the bounded SSH draft and asks for an explicit target until safe multi-target execution exists
- unified routing now passes the capability draft's connection kind into the live routing chain, so an SSH disk-space draft such as `df -h` can no longer be hijacked by an unrelated RSS/Qdrant routing candidate
- concrete SSH disk-space drafts now suppress conflicting stored-recipe candidates during routed execution, preventing old fleet-health recipes from producing `recipe_manifest_missing` or Discord recipe-error events for a simple `df -h` check
- generic SSH template commands such as `uptime` are no longer treated as the user's real action when the natural request is mutating; the bounded SSH resolver can infer the dangerous command and the policy blocks it instead
- natural SSH disk-space questions such as `check mal ob meine server noch genug festplatten platz haben` now resolve to a bounded `df -h` disk draft and ask for the target when multiple SSH profiles exist, instead of selecting a generic `server` alias or falling into an old fleet-health stored recipe
- very short connection refs or aliases such as `a` / `b` no longer match arbitrary letters inside normal words when extracting explicit connection targets
- SSH health/status requests such as `ist mein dns server ok` no longer keep the stale blocked `uptime` decision after the guardrail healthcheck bundle has replaced it with an allowed command sequence
- SFTP/SMB list requests now treat the share/root path as a valid `.` default instead of asking for a path when the user wants to list folders on a share root
- clear Discord/message requests no longer fall through to stale SMB/file context when no matching messaging connection profile is configured; ARIA now returns the missing-profile message instead of trying to list a bogus SMB path
- `/connections/types` no longer performs live connection probes while rendering the type overview, avoiding slow page loads caused by status checks that belong on `/connections/status`
- connection detail pages opened from `/connections/types` no longer render as an empty page when no profile exists yet; ARIA now opens the create form automatically for empty connection types such as Discord
- the Discord connection page now receives its toggle-section builder through the normal route-helper dependency wiring, fixing the broken `/config/connections/discord?...` render path
- German HTTP API field labels now use `Base-URL` again in connection-admin validation messages

### Upgrade Notes
- Public release `0.1.0-alpha266` publishes Docker tags `fischermanch/aria:0.1.0-alpha.266` and `fischermanch/aria:alpha`.
- Python dependencies and base-image digests are pinned for Docker release builds; Debian `apt` packages still come from normal Debian repositories unless a future snapshot-repo hardening step is added.
- A hard browser refresh is recommended after updating because this release includes UI, CSS, service-worker, and chat-rendering changes.

## [0.1.0-alpha.167] - 2026-04-25

Public release aligned with the internally tested `alpha167` code line.

### Changed
- the main menu now only shows `Updates` when a newer release is actually available; the old permanent entry added noise on installs that were already current
- ARIA now treats the visible release label as one shared product version line again instead of reinforcing a separate public-vs-internal numbering story in the UI and docs

### Upgrade Notes
- this release intentionally brings the public Docker/GitHub line onto the same visible release number as the internal ARIA line
- managed and internal-local update paths can still differ technically, but the product should now report the same release label for the same code line

## [0.1.0-alpha.127] - 2026-04-24

Public hotfix release on top of `0.1.0-alpha.126`.

### Changed
- the main user menu now exposes `Updates` as its own destination instead of only hinting availability with the small header lamp; when a newer release exists, the menu entry itself is marked with `Update verfügbar`, so users can see immediately where to go

### Upgrade Notes
- this release is recommended if users already noticed the update lamp but had to guess that the update flow lives under `/updates`
- the managed update-path fixes from `alpha126` remain the base for this release and should now be easier to discover in normal everyday use

## [0.1.0-alpha.126] - 2026-04-24

Public hotfix release on top of `0.1.0-alpha.125`.

### Fixed
- managed GUI updates no longer try to run the critical stack `update` / `repair` / `validate` path via in-container `/managed/...` compose calls; the updater now executes those operations through a short-lived helper container that uses the real host stack path, which fixes the recurring config-sync and stale-mount regressions seen on real managed installs like `whity` and `neo`
- the app header now uses the configured persona/agent name again instead of falling back to `settings.ui.title`, so renamed assistants such as `J.O.E.` show up correctly next to the logo

### Upgrade Notes
- this release is recommended immediately for managed installs using `/updates`
- if a previous `alpha125` update left the stack drifted, run `./aria-stack.sh repair` once after upgrading; future managed updates should then stay on the corrected host-path-aware update flow

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
- der automatische Logout nach wenigen Minuten in Multi-Instanz-Setups wurde behoben; Ursache waren kollidierende Cookie-Namen zwischen z. B. `aria.example.lan:8800` und `aria.example.lan:8810`
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
- Repo/privacy sweep: removed personal dev-host defaults from `docker/pull-from-dev.sh`, neutralized `config/secrets.env`, removed stray root artifacts `=1.2` / `=2.1`, and excluded the then-current local project documentation folder from the public repo while keeping it locally

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
- Documentation tree reorganized into public `docs/` and the then-current internal history folder
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

- Detailed internal build history currently lives in `docs/internal/alpha-build-log.md`
- Public release wording can be derived from:
  - `docs/product/feature-list.md`
  - `docs/backlog/future-features.md`
  - `docs/setup/setup-overview.md`
  - `docs/product/architecture-summary.md`
  - `docs/release/versioning.md`
