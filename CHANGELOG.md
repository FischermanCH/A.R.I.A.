# Changelog

## 0.1.0-alpha983

### Fixed

- Fixed the document inventory fallback introduced in `0.1.0-alpha982`: questions such as “Which documents, PDFs or leaflets do you have?” now return one named, collection-bound row for every imported document instead of reporting no documents or deriving an incomplete list from search excerpts.
- Inventory now explicitly requests up to 200 document records instead of silently inheriting the MemorySkill default of 12. Content search and answer results also retain their source document names and collections when that metadata is available.
- **No data was lost.** Imported documents remained stored throughout; only the native Tool's completeness-preserving inventory presentation was broken.

## 0.1.0-alpha982

> **About the version numbers:** ARIA's version numbers deliberately count development iterations. Alpha604 to Alpha982 are 378 iterations of building ARIA together with AI — the number is kept transparent on purpose and will keep counting, past 1000 if need be.

### Highlights

1. **A modular ARIA under the familiar surface.** From the outside, only the GUI still looks much like the Alpha604 release; underneath, the application has been rebuilt into independently owned modules with explicit contracts. This removes the former monolithic core as a second source of truth and makes connection, memory, recipe, chat and administration changes safer to isolate.
2. **Self-learning that asks before it becomes memory.** ARIA can recognize recurring personal preferences and offer them as a user-scoped memory only after repeated evidence. The model does not silently store casual statements, and the user decides through the dedicated action before a personal claim is saved.
3. **Self-learning recipes.** Repeated actionable sequences can be grouped into an inactive recipe suggestion, including semantic variants and supported cross-connection copies. Suggestions remain reviewable and inactive until the user explicitly saves them; the retired legacy learning stack is no longer part of this path.
4. **A native tool-calling agent with MCP and durable jobs.** The agent can use ARIA's native tools and enabled MCP servers, while longer work continues as background jobs with pause, resume, correction, cancellation, budget extension and in-job confirmation. Tool images can be passed to supported Claude-family vision models, and output guards refuse fabricated resource contents or action claims when no Tool supplied the evidence.
5. **A cleaner memory database boundary.** Core memories, facts, preferences, documents and recipe experience remain supported, while obsolete legacy-learning collections from the old architecture are no longer written. After upgrading, administrators can remove those old per-user collections explicitly from **Memories → Maintenance → Clean up old learning collections** without deleting personal memories, facts or preferences.

### Added

- MCP client support for enabled HTTP/SSE servers, namespaced Tool discovery, per-server trust and call timeouts, administration status, reconnect controls, bounded Tool results and confirmation previews for mutating Tools.
- Persistent, user-scoped Agent Jobs with progress, token/cost observability, completion notices and controls for pause, resume, correction, confirmation, budget extension, finalization, cancellation and retention.
- Native recurrence learning for personal-memory suggestions and inactive recipe suggestions, plus an explicit maintenance action for old learning collections.
- A strict, isolated browser E2E harness for the Agent, MCP, jobs, confirmations and vision contracts; it is development tooling and is not included as a production service.

### Changed

- Runtime ownership is modular: the kernel keeps generic lifecycle, auth, policy, confirmation and observability while modules own domain contracts, routes, runtime and UI contributions.
- Web answers use configured provider-native capabilities; the former search sidecar is not used by fresh installs.
- Memory creation, personal claims, recipe execution and cross-connection bindings use explicit structured contracts and stable identifiers.
- Provider compatibility now supports an omitted per-model temperature, longer bounded agent turns, prompt caching, rolling Tool-image windows and honest retries for selected provider limitations.

### Removed

- SearXNG and Valkey sidecars from the supported fresh-install stack.
- The dead legacy-learning modules, worker/admin surfaces and automatic learning-data writers replaced by native memory and recipe recurrence.
- Obsolete monolithic compatibility modules and inactive public samples whose live owners had already moved to modules.

### Fixed

- Confirmation turns retain the pending Tool even when the relevance selector is active, and MCP sessions recover or fail honestly without blocking normal turns.
- Agent jobs no longer duplicate budget-pause or completion notices, lose confirmation state, become blind after four Tool images, or silently stop at provider output limits.
- Memory recurrence now clusters stable topic values across phrasing and language-preserving extraction, while explicit memory capture retries bounded transient store failures and exposes safe diagnostics.
- Release, setup, routing, chat-history and update boundaries were hardened through the Alpha605–Alpha982 iteration series.

### Security

- Mutating native and untrusted MCP Tools run through the existing confirmation kernel with frozen arguments and a one-shot ledger claim; trusted MCP servers are an explicit administrator decision.
- Agent-job controls and maintenance actions are authenticated, CSRF-protected and user-scoped.
- Output-side honesty guards reject unsupported claims about resource contents or completed actions, and secrets in MCP headers, logs, job snapshots and release artifacts stay redacted or excluded.
- Public-repository hygiene excludes local configuration, secrets, runtime data, internal work logs and developer browser state, with generic privacy and credential-shape scanning before export.

### Upgrade Notes

- Back up the ARIA config/data bind mounts or volumes and the Qdrant volume before upgrading from `0.1.0-alpha604`.
- The isolated Alpha604→Alpha982 test verifies that authentication, both users, configuration and connections, chat history, personal facts/preferences, recipes and Qdrant-backed memories survive when the same storage is mounted into Alpha982. Existing legacy-learning collections are deliberately not removed automatically.
- After the update, open **Memories → Maintenance → Clean up old learning collections** once per user. It removes only that user's obsolete learning-candidate/evaluation/event/hint/reflection collections; personal memories, facts, preferences, documents and recipe experience are untouched.
- Old SearXNG and Valkey containers are no longer in the supported stack and may be removed manually after the ARIA/Qdrant backup and successful upgrade verification; ARIA never removes them automatically. See `docs/release/alpha981-upgrade-note.md`.
- Per-model `temperature` may be left empty for models that reject it. For long Agent/Blender jobs, start with about `16000` maximum output tokens and a `300` second model timeout, then tune for the chosen model and budget; MCP call timeout is configured per server.
- LiteLLM proxy users no longer receive `tool_choice=none`. MCP and Blender setup is documented in `docs/setup/mcp-and-blender.md`.

### Known Limitations

- Tool-result image vision is currently supported only with Claude-family models.
- AI 3D generation invoked through a Blender MCP add-on needs the user's own paid generator keys; ARIA does not provide those services or credits.
- The Blender MCP bridge runs on the user's machine and must be reachable from the ARIA container; it is not bundled as a sidecar.
- Token usage, cost and achievable job budgets depend on the selected provider and model. The E2E harness is developer-only test tooling, not a production component.

## 0.1.0-alpha981

- Removed four verified-dead legacy modules and their stale registry, manifest, audit and test ownership while preserving the live SSH runtime, memory browser and legacy-learning collection cleanup action.
- Removed the retired search sidecar from fresh-install, Compose, Portainer, environment and public setup artifacts; provider-native web tooling remains the supported web-search path and upgrades do not mutate old sidecars.
- Hardened the public-repository ignore boundary for local agent state, runtime data, test/browser output, build archives and editor metadata, and removed the last inert Discord sample toggle.

## 0.1.0-alpha979

- LLM-Temperatur ist optional; leere Konfigurationen senden keinen Sampling-Parameter, während bestehende numerische Werte unverändert bleiben.
- Modellbezogene Temperature-Ablehnungen lösen genau einen parameterlosen Wiederholungsversuch aus und werden pro Prozess für weitere Calls gemerkt und diagnostiziert.
- Der isolierte Strict-Fake-Browserprüfstand reproduziert die exakte Live-Ablehnung und erweitert das Gate um S19.

## 0.1.0-alpha978

- Native-Agent-Budget-Finalizer ist proxy-kompatibel; detached Jobs können ihr Budget kontrolliert erweitern oder sofort abschließen.
- Agent-Job-Aufbewahrung, veraltete Pausenbereinigung und nutzerspezifische Löschaktionen ergänzt.

## 0.1.0-alpha977

- Sniffed bounded PNG, JPEG, GIF and WebP magic bytes before forwarding MCP images, correcting mislabeled media types and keeping unknown bytes as text-only placeholders.
- Added a single budgeted text-only retry when a provider rejects an image block, hardened detached confirmation-resume failures into terminal jobs, and report total job wall time in completion notices.
- Extended the strict isolated browser harness with MIME/byte validation and S14–S16 for mislabeled images, provider image degradation and post-confirm resume failure.

## 0.1.0-alpha976

- Added bounded, owner-scoped mid-flight corrections and resumable detached-job confirmations that reuse the existing pending-action store and confirmation ledger with frozen arguments and exact Tool-result pairing.
- Added global job status/toasts, honest partial-budget completion summaries and finalizer diagnostics, stable in-place Jobs scrolling, per-server MCP call timeouts, and corrected unreachable-server footer handling after failed MCP calls.
- Extended the isolated strict-fake browser harness with S10–S13 for correction, in-job confirmation, global status/toasts and incomplete-job reporting.

## 0.1.0-alpha975

- Moved detached Agent Job Pause/Resume/Cancel controls into each panel-card header and the originating chat bubble, with authenticated CSRF-protected JSON actions and status-preserving polling.
- Replaced full-page Jobs polling reloads with escaped in-place updates, added collapsible step histories and timeout recovery links, persisted post-pipeline web timing into terminal notice Details, and added safe `**bold**` rendering.

## 0.1.0-alpha974

- Added clean-boundary pause and restart-safe resume for detached Native Agent jobs: paired Tool history, budgets, guard state and bounded metrics persist in the worker-shared store while inline image bytes never do.
- Added user-scoped, CSRF-protected Pause/Resume controls and per-event chat notices; cancellation, terminal finalization, prompt caching, MCP discovery/selection and the default-off 37-Tool Core Registry remain unchanged.

## 0.1.0-alpha973

- Moved the final Anthropic prompt-cache breakpoint for Tool messages onto the Tool-result envelope, preserving string and multimodal content while preventing invalid `cache_control` metadata inside `tool_result.content` after LiteLLM conversion.
- Unmatched Native/provider failures now use a generic agent-error badge; explicit memory availability, embedding and memory errors retain their existing badges.

## 0.1.0-alpha972

- Supported bounded MCP image results are now carried as real current-turn vision blocks for Claude models while chat history, Agent Jobs, traces, details and logs retain base64-free references; unsupported, oversized and excess media stay honest placeholders.
- Deduplicated unreachable-server footers and stripped them only from provider history, broadened truthful earlier-turn recap authority, and scoped action-claim negation to the matched completion claim.

## 0.1.0-alpha971

- Added a conservative output-side guard for unsupported action-completion claims: a no-Tool mutation claim gets one bounded corrective retry, then a localized honest refusal if it persists, while explicit earlier-turn recaps and tool-backed results remain valid.
- MCP transport and availability failures now immediately invalidate the affected server's cached Tool snapshot and publish a bounded error status for the next turn; remote Tool `isError` results keep the connection healthy.

## 0.1.0-alpha970

- Failed MCP discovery becomes cold again after its bounded cooldown, while idle persistent sessions recycle before reuse and only idempotent discovery may retry once on a fresh session after a timeout; timed-out Tool calls remain honest and are never replayed.
- Native turns now disclose matching unreachable MCP capabilities without secrets, omit unseen image/audio/binary payloads instead of passing base64 to the model, and preserve bounded multiline Agent Job completion summaries.

## 0.1.0-alpha969

- Detached Agent Jobs now link directly to their panel row and append exactly one localized assistant-only terminal notice, including the recorded result, usage/cache/tool Details, and live user-scoped chat polling without duplicating persisted history.
- Normalized assistant-only history into valid alternating provider messages and made externally closed MCP sessions return an honest `mcp_call_failed` result instead of cancelling the caller task.

## 0.1.0-alpha968

- Added a scoped MCP reconnect action that cleanly drops one server session, clears its discovery failure cooldown and cache, and immediately performs a bounded fresh discovery.
- Added an admin-only, CSRF-protected per-server Reconnect button with localized success and failure feedback; MCP configuration, trust, secrets, and enabled state remain unchanged.

## 0.1.0-alpha967

- Reused one persistent MCP transport session per enabled server for discovery and Tool calls, with per-server serialization, one bounded reconnect after transport failure, and clean application-shutdown closure.
- Preserved MCP discovery snapshots, failure cooldowns, timeouts, Tool binding/confirmation/trust, selector, Agent Jobs, prompt caching and the default-off 37-Tool Native Registry.

## 0.1.0-alpha966

- Added a lossless one-hour Anthropic prompt-cache breakpoint to the final block of the current Native Agent message history, allowing later loop/finalizer calls and subsequent turns to reuse the longest stable conversation prefix.
- Kept the existing system and final-Tool breakpoints, non-Anthropic requests, Tool schemas, selection, budgets, retries and usage/cache metering unchanged while staying below Anthropic's four-breakpoint limit.

## 0.1.0-alpha965

- Cold enabled MCP servers now perform one shared, timeout-bounded first discovery on the first native turn so their Tools are available immediately; warm snapshots and failure-cooldown servers remain non-blocking.
- Added a fail-soft background MCP discovery warm-up during application startup without changing Tool calls, bindings, confirmation, trust, selection or the default-off 37-Tool Core Registry.

## 0.1.0-alpha964

- Raised the configurable Native Agent loop and provider-call budgets to 16 and added bounded retries for transient upstream 5xx, overload, connection and timeout failures without retrying non-transient 4xx errors.
- When final summarization remains unavailable after successful mutating Tool steps, return and persist an observation-only result with a visible warning instead of misclassifying completed partial work as a failed job.

## 0.1.0-alpha963

- Raised the configurable Native Tool selector MCP allowance to 16 while keeping all 37 Core Tools available on every normal large-catalog turn; confirmation turns and catalogs at or below 40 remain unchanged.
- Added an authenticated, user-scoped Agent Jobs panel with live JSON polling, progress/result history and CSRF-protected cooperative cancellation at completed tool-step boundaries.

## 0.1.0-alpha962

- Made per-turn MCP discovery snapshot-only: missing or stale server catalogs refresh in one bounded background task per server while chat continues without waiting for network discovery.
- Failed discovery now caches an honest empty result and error status for a 60-second cooldown, retries once eligible, and uses an 8-second background probe timeout without changing the 30-second MCP Tool-call timeout.

## 0.1.0-alpha961

- Added a worker-shared SQLite Agent Job foundation: long native-agent turns detach after a configurable 25-second synchronous budget, continue without cancellation, checkpoint completed tool steps, and expose user-scoped read-only status at `/jobs`.
- Short turns and confirmation-token turns remain synchronous and do not create visible jobs; startup marks only stale in-flight jobs as interrupted after a worker restart.

## 0.1.0-alpha960

- Bypass semantic Native Tool relevance selection only for turns carrying an existing confirmation token, preserving the full assembled and connection-filtered Tool catalog so the frozen pending Tool can be resolved and claimed.
- Keep normal large-catalog selection and diagnostics unchanged while removing misleading selector activity and embedding latency from confirmation turns.

## 0.1.0-alpha959

- Project every discovered Tool from an enabled MCP server into the Native Tool assembly: explicit read-only Tools remain direct, while unannotated or mutating Tools from an untrusted server reuse ARIA's existing frozen-argument confirmation flow.
- Added a default-off per-server trust setting to the sanctioned MCP admin surface; trusted servers run all Tools directly only after an explicit advanced-admin choice and prominent warning.

## 0.1.0-alpha958

- Added an advanced-admin MCP server page under Connections for sanctioned add/edit/disable/delete and global enable/disable through the existing raw-config write and RuntimeManager reload path.
- Added secret-safe masked server summaries and fail-soft live discovery status with explicit read-only Tool counts; Alpha957 bindings/calls and the default-off 37-Tool Core Registry remain unchanged.

## 0.1.0-alpha957

- Added an opt-in generic MCP client for configured SSE and Streamable HTTP servers, with cached discovery and additive projection of only explicitly read-only MCP Tools into the Native Tool assembly.
- MCP discovery and calls fail softly with secret-safe diagnostics and bounded honest Tool results; the default-off path remains the unchanged 37-Tool core Registry and catalogs above 40 reuse the existing semantic selector.

## 0.1.0-alpha956

- Added the embedding-based Native Tool relevance selector for future catalogs above the unchanged 40-Tool threshold, with deterministic top-8 ranking over Tool name and description.
- Reused owner-scoped descriptor embeddings across turns and degraded missing or failed embeddings to a logged stable first-eight fallback; the current 37-Tool path performs no selector or embedding work and emits no selector detail.

## 0.1.0-alpha955

- Generalized the existing semantic stored-Recipe copy suggestion from SSH hosts to any exact matching primary Recipe step type on a different connection, while retaining the existing embedding batch, 0.88 threshold, one-shot pair claim and confirmation-gated inactive copy.
- Reused the existing generic connection-ref repointing with connection-neutral copy wording; SSH selection, actionable recurrence clustering/telemetry, Anti-Fabrication, Kernel, Guardrails and the 37-tool Registry remain unchanged.

## 0.1.0-alpha954

- Hardened the Native Agent resource-evidence prompt so file/resource content, command output, listings and status always require a fresh tool result from the current turn, including familiar/default resources and repeated reads.
- Added a conservative no-tool final-output veto with one bounded corrective retry and a localized honest refusal if the model persists, while leaving tool-backed reads and ordinary conversation/code unchanged.

## 0.1.0-alpha953

- Preserved the best same-bucket actionable recurrence cosine as passive telemetry even below the unchanged `0.88` clustering threshold, without changing signature, count or offer behavior.
- Added bounded `near_sim` and actual embedding-vector usage to the existing recurrence Details line while leaving SSH cross-host and Memory recurrence diagnostics unchanged.

## 0.1.0-alpha952

- Generalized Native actionable-sequence recurrence embeddings from SSH commands to the existing signature-bearing primary parameters of all actionable step kinds while retaining exact signatures, type/connection buckets, similarity and offer thresholds.
- Kept stored-Recipe semantic comparison and cross-host copy suggestions strictly SSH-only, with unchanged SSH command embedding and confirmation behavior.

## 0.1.0-alpha951

- Removed the high-priority preload for the decorative appearance background while preserving the existing CSS-loaded WebP background rendering.

## 0.1.0-alpha950

- Unified manual Memory creation with the structured Personal Claim contract for explicit facts and preferences, including bounded validation and authoritative store errors.
- Re-encoded all eight shipped appearance backgrounds as bounded WebP assets and preload the active background without changing its slug or resolver contract.

## 0.1.0-alpha949

- Folded the retained Memory Reindex action and compact canonical status into Memory Maintenance with card-local focused feedback.
- Moved all seven existing Reindex scheduler controls into Memory setup while preserving the existing save and rebuild implementations.
- Retired the standalone Reindex page/template and redirected legacy entry points to the retained Maintenance and setup surfaces.

## 0.1.0-alpha947

- Generalized adaptive stored-Recipe connection binding from SSH to the connection kinds owned by SFTP, SMB, Discord, Webhook, Email, MQTT and HTTP API steps while preserving explicit references and unrelated steps.
- Retained the exact SSH fleet fan-out contract, reused its 20-target cap for SFTP/SMB, exposed bounded localized `recipe_connection_*` failures and kept confirmation previews bound to resolved configured targets.

## 0.1.0-alpha946

- Removed the two unreferenced Legacy Learning POST routes for active-hint mutation and the retired candidate-action stub from Memory Admin routing and manifest metadata.
- Preserved Personal Model claim actions, Memory deletion routes, Legacy Learning collection classification and cleanup, the protected Memory browser, and the 37-tool Native Registry.

## 0.1.0-alpha945

- Removed stale Auto-Memory wording from both localized Memory setup descriptions and their Maintenance fallback while retaining the remaining setup guidance.
- Kept rollup, suggestion-reset and Legacy Learning cleanup feedback inside the triggering Maintenance card with deterministic focus query parameters and anchors; unknown or absent focus retains the page-top fallback.

## 0.1.0-alpha944

- Added an explicit authenticated and CSRF-protected Memory maintenance action that removes only retired Legacy Learning Qdrant collection kinds with the exact current-user suffix.
- Added a confirmed maintenance card and bounded localized result while protecting Core Memory, documents, notes, sessions, Recipe Experience, routing, backups, external collections and other users.

## 0.1.0-alpha943

- Added a bounded three-attempt retry with 0.2/0.4-second backoff around failed Personal Memory store results, without retrying successful or deduplicated writes or changing claim lifecycle logic.
- Preserved the bounded authoritative store error in failed `memory_capture` diagnostics while keeping the existing friendly user-facing response and Registry contract unchanged.

## 0.1.0-alpha942

- Removed the final Legacy Auto-Memory configuration authority and its dead cookie, status, recipe and runtime plumbing while continuing to accept old configuration files that contain an ignored `auto_memory` section.
- Removed only the retired Auto-Memory status and Learning-effect presentation from the retained Memory browser; recall, capture, Personal Model, navigation, graph, stats and search remain intact.

## 0.1.0-alpha941

- Physically removed the nine closed Legacy Learning modules and their exclusive tests and UI partial, reducing the registered module graph from 118 to 109 without deleting `memory_learning_bridge` or stored Learning data.
- Removed their static registry entries and remaining Recipe/Auto-Memory manifest edges; Core Memory, `/memories`, Personal Model, Native learning and Recipe tools remain on their retained owners.

## 0.1.0-alpha940

- Removed all ten Legacy Learning candidate review, apply, regression, generated-pytest and activation admin routes plus their apply-preview template from Memory Admin while preserving the Memory browser and Personal Model.
- Severed the retained Memory Admin module from `learning_candidates`, `learning_artifacts` and `prepared_artifacts`; the Learning ring remains registered as an intentionally closed dead subgraph for the separately authorized Stage 3c-2.

## 0.1.0-alpha939

- Removed the obsolete Legacy Auto-Memory status badge and its unused styling from the Chat debug header while retaining the remaining Chat diagnostics.
- Extended the server-owned Memory-learning cost pre-filter to skip German and English first-token question-word messages without changing extraction, recurrence or Registry behavior.

## 0.1.0-alpha938

- Stripped Legacy Learning retention, synthesis status, active-hint recall and inventory behavior plus all Learning imports from the retained Core MemorySkill while preserving personal claims, recall, capture, documents, cleanup and the Memory browser.
- Removed the `learning_context_read` Native tool and its integration point, reducing the Registry to 37 tools, and deleted the Learning-only procedure guidance helper while relocating the generic Memory admin query facade into the retained `memory` module.

## 0.1.0-alpha937

- Reduced the former Auto-Memory page to the retained Personal Model, removing the Auto-Memory toggle, extraction/retention controls, Legacy Learning inventory and synthesis presentation while preserving personal claims and their lifecycle actions.
- Removed the obsolete Auto-Memory save and Learning synthesis POST routes and renamed the Memory navigation tab to Personal Model; MemorySkill, AutoMemoryConfig and `/memories` remain unchanged.

## 0.1.0-alpha936

- Decoupled retained runtime execution contracts, Stats, Memory Admin and personal feedback linking from Legacy Learning Runtime while preserving normal action execution, `/memories`, memory recall and explicit capture.
- Removed the Startup Learning-retention call and its logging while retaining document MetaCatalog rebuild and empty-collection cleanup; Learning modules remain registered for later B2 stages.

## 0.1.0-alpha935

- Relocated passive stored-Recipe manifest projections from `recipe_learning` to `recipe_runtime` and repointed Recipe UI, Chat Surface, dry-run and planner consumers without changing their visible projection contract.
- Removed the dead learned-Recipe planner candidate branch, historical startup purge and Stats learned-review promotion path while retaining the registered `recipe_learning` module for B2 Stage 3c.

## 0.1.0-alpha934

- Retired the explicit Chat Learn Start/Stop/Cancel mode from live POST dispatch and passive chat presentation; former commands now follow the normal Chat flow while `recipe_remember` and Native recurrence remain the supported learning paths.
- Removed chat-learn session reads, observation writes, state badges, toolbox controls and two now-dead Chat Execution manifest dependencies without deleting or relocating the `recipe_learning` module.

## 0.1.0-alpha933

- Removed the dead Legacy Learning Worker and Self-Learning sections and their admin routes from Memory maintenance while retaining the user-scoped native learning-suggestion reset.
- Detached Pipeline from the unused Legacy Learning helper mixin/handler registration and removed RecipeRuntime Learning Governance event writes; all Learning modules remain registered for later B2 stages.

## 0.1.0-alpha932

- Clarified the Native memory prompt so direct remember, save or note requests must call the existing confirmation-gated `memory_capture`, while incidental preferences still never receive textual storage offers.
- Required server Memory-learning topic values to remain in the user's message language and never be translated, while preserving the existing lowercase singular bare-topic contract.

## 0.1.0-alpha931

- Severed the two B2 Stage 1 legacy Learning inputs: startup maintenance no longer enqueues global synthesis, and RecipeRuntime no longer records Learning candidates or evaluations while claim storage, Recipe execution and auto-memory event handling remain intact.

## 0.1.0-alpha930

- Tightened native memory extraction so paraphrases of one durable preference emit the same lowercase singular bare topic value while predicate retains nuance, and exposed the bounded extracted value in Routing Debug diagnostics.

## 0.1.0-alpha929

- Resolved native learning-suggestion reset stores from the canonical project runtime files instead of lazy per-Pipeline attributes, so the authenticated maintenance action works before that worker has handled a Native turn while retaining the existing user scope.

## 0.1.0-alpha928

- Added memory-specific German and English presentation for native learning suggestions so the existing `memory_capture` action no longer appears as a Recipe offer; recipe recurrence and cross-host copy wording remain unchanged.

## 0.1.0-alpha927

- Changed native memory recurrence embeddings to use only the normalized claim value, so model-variable predicates no longer split paraphrases of the same topic while exact-key matching, subject buckets and stored claim fidelity remain unchanged.

## 0.1.0-alpha926

- Strengthened the Native Agent memory rule with an explicit rationale, German and English negative examples, and positive response guidance so ordinary durable statements do not receive model-written remember/save offers; explicit `memory_capture` requests remain unchanged.
- Added user-scoped, atomic reset operations for native memory and recipe suggestion recurrence, plus an authenticated, CSRF-protected and confirmation-gated maintenance action that does not delete stored memories or recipes.

## 0.1.0-alpha925

- Changed the server-memory prefilter to use only the existing structural gates plus expanded German and English first-person forms; durable-claim classification remains exclusively owned by the structured extraction model.
- Removed the hard-coded durable-word requirement so first-person preferences such as `ohne Chili schmeckt mir Essen nicht` reach extraction and can advance the unchanged recurrence and confirmation-gated offer path.

## 0.1.0-alpha924

- Replaced model-selected `memory_note_candidate` observation with a server-owned, concurrent structured extraction step that records durable first-person facts and preferences independently of native tool choice.
- Anchored memory recurrence to subject, claim kind and normalized value, offers the existing confirmation-gated capture affordance on the second observation, and checks already-stored claims through a bounded semantic query that reuses the candidate embedding.
- Retired `memory_note_candidate`; the Native Tool Registry returns to 38 tools while explicit `memory_capture` requests keep their existing preview and confirmation contract.

## 0.1.0-alpha923

- Made the silent native `memory_note_candidate` observation best-effort: invalid candidates and unavailable or failing observation dependencies now degrade to a non-suggesting ignored result instead of failing the user turn closed.

## 0.1.0-alpha922

- Enforce the native personal-memory recurrence gate in the agent prompt: ordinary durable facts and preferences are observed silently through `memory_note_candidate`, while only explicit requests to remember use confirmation-gated `memory_capture`.

## 0.1.0-alpha921

- Added conservative native personal-memory observation with semantic recurrence clustering and a one-shot confirmation button that reuses the existing `memory_capture` authority.

## 0.1.0-alpha920

- Bundled the ARIA MIT `LICENSE` in the runtime image so `/licenses` can render the complete, theme-readable license text after deployment.

## 0.1.0-alpha919

- Fixed runtime background discovery after modularization so saved Appearance selections survive reload and resolve to their selected shipped image instead of falling back to Grid Signal.

## 0.1.0-alpha918

- Restored every background offered by Appearance to its matching shipped image while preserving theme-aware overlays and structural colors.

## 0.1.0-alpha917

- Replaced structural hardcoded green surfaces across admin, statistics, connection, and shared configuration UI with theme tokens while preserving semantic success and health colors.
- Removed the duplicate Updates entry from the About hub group and suppressed the empty ARIA license container when the license file is not bundled.

## 0.1.0-alpha916

- Replaced the Cyberpunk theme's full-magenta configuration accordion surfaces with dark ARIA house-style cards and green borders across Guardrails and connection settings.

## 0.1.0-alpha915

- Renamed Activities to Execution History and included provider-native web searches in its existing single-record usage projection.
- Decoupled the license page from the full Help wiki navigation and aligned Guardrail cards with the dark green ARIA house style.

## 0.1.0-alpha914

- Removed the redundant Workbench overview and experimental rollout controls while keeping File Editor, Error Interpreter, and LLM Debug directly available from the configuration hub.

## 0.1.0-alpha913

- Added native Recipe, memory and system-tool runs to the existing user-scoped Activities projection, including duration, error status, Recipe name and resolved target metadata.

## 0.1.0-alpha912

- Filled thin configuration-hub groups with their real model, access, backup, log, update, and activity subpages, while retaining a landing card whenever removing it would leave a group empty.

## 0.1.0-alpha911

- Simplified the grouped configuration hub by turning natural section headings into overview links, removing repeated landing cards, and dropping redundant group subtitles.

## 0.1.0-alpha910

- Replaced the parallel settings/admin navigation trees with one role-gated, topic-grouped `/config` hub while preserving all detail pages.
- Moved the existing Agentic Loop rollout controls to the System & Development workbench and retired the redundant admin group pages.
- Renamed the visible `/licenses` entry to License agreements without changing its route.

## 0.1.0-alpha909

- Removed the retired connection-routing configuration, workbench, and legacy skill-routing redirect pages while retaining the routing index backend and diagnostics.

## 0.1.0-alpha908

- Replaced UI audit autosave with one CSRF-protected bulk-save form and corrected the localized page heading.

## 0.1.0-alpha907

- Replaced per-row UI audit form submissions with debounced in-place autosave and per-row save feedback.

## 0.1.0-alpha906

- Added an admin-only, self-discovering UI route audit with persistent keep/verify/cut/regroup decisions and JSON export.

## 0.1.0-alpha905

- Strengthened the native agent's live-state rule so every repeated current-state request requires a fresh tool call in that turn rather than reusing conversational output.

## 0.1.0-alpha904

- Replaced model-authored Recipe learning suggestions with deterministic, nonblocking chat buttons backed by server-frozen one-shot confirmation payloads.

## 0.1.0-alpha903

- Added optional embedding-based same-host recurrence clustering and one-shot cross-host inactive Recipe-copy suggestions while preserving exact matching as the graceful fallback.

## 0.1.0-alpha902

- SSH targets now resolve deterministically by configured reference, unique display name, or unique host while ambiguous values remain unresolved.
- Exact recurrence tracking now uses canonical SSH references and ignores unresolved or transport-failed actions while retaining actual policy blocks.

## 0.1.0-alpha901

- Added bounded, persistent, per-user exact recurrence tracking for native actionable sequences.
- The third exact repetition can produce one non-authoritative Recipe suggestion while existing Recipes and prior offers suppress duplicates.
- Added secret-free recurrence signature/count diagnostics; native tool count remains unchanged.

## 0.1.0-alpha900

- Added Anthropic ephemeral prompt-cache breakpoints for the native agent's unchanged static system prompt and offered tool schemas.
- Added per-call native LLM latency and cache-token diagnostics to the existing routing details without exposing credentials or dynamic content.

## 0.1.0-alpha899

- Removes internal confirmation-control echoes from user history before native-agent model calls, preventing action tokens from being reused as Recipe identifiers.

## 0.1.0-alpha898

- Adds an explicit, confirmation-gated `recipe_remember` flow that stores the caller's last actionable native-tool sequence as an inactive Recipe draft.
- Retires legacy learned-recipe state once at startup through an idempotent, narrowly scoped purge.

## 0.1.0-alpha897

- Removed the obsolete learned-Recipe UI, routes, navigation, and templates while preserving the shared recipe-learning backend and normal stored-Recipe surfaces.

All notable public-facing changes to ARIA should be documented in this file.

Format: `Added` / `Changed` / `Fixed` / `Security` / `Known Limitations` / `Upgrade Notes`

For the full German working changelog and detailed internal alpha history, see [CHANGELOG.de.md](CHANGELOG.de.md).

## [Unreleased]

- Internal Alpha896 makes mutating host-maintenance intents inspect the offered
  Recipe inventory before synthesizing an ad-hoc SSH command. A matching active
  Recipe is executed by exact ID; ad-hoc SSH remains a guardrail-bound last
  resort when none matches. Literal one-off commands and reads, 37 native tools
  and public alpha604 are unchanged.
- Internal Alpha895 clarifies the model-facing native tool contract: stored
  Recipes named or intended by the user take precedence over reconstructing
  their actions as ad-hoc SSH commands. Literal one-off SSH reads and commands,
  confirmation, policy, guardrails, 37 native tools and public alpha604 are
  unchanged.
- Internal Alpha894 adds an optional SSH timeout field to the Recipe wizard.
  Positive values round-trip through saved `ssh_run` parameters; empty, zero or
  invalid values remain omitted so the connection default still applies.
  Execution, SSH policy, guardrails, 37 native tools and public alpha604 are
  unchanged.
- Internal Alpha893 adds a Duplicate action to every editable saved-Recipe
  card. Copies receive collision-safe IDs, preserve their steps, and are always
  saved inactive for review before activation. Recipe execution, adaptive
  binding, guardrails, 37 native tools and public alpha604 are unchanged.
- Internal Alpha892 adds user-scoped, TTL-bounded live Recipe progress to the
  existing chat wait indicator. The browser polls while a request is active and
  shows the current logical step, expanded SSH host and cumulative host outcome;
  idle or unavailable progress keeps the existing elapsed-time display. Recipe
  execution, confirmation, guardrails, 37 native tools and public alpha604 are
  unchanged.
- Internal Alpha891 adds exact enabled-Recipe allowlists to SSH guardrail
  profiles. A whitelisted, kernel-confirmed Recipe may bypass that profile's
  ordinary allow/deny terms, but a code-owned absolute floor still blocks root
  or home wipes, raw block-device writes/formats, fork bombs and power-state
  commands. Direct SSH and non-whitelisted Recipes remain fully guarded; the
  native registry stays at 37 tools and public alpha604 is unchanged.
- Internal Alpha890 makes confirmed Recipe output readable and complete. The
  Recipe tool relays its user-facing `direct_chat_text` or content as plain
  text, while adaptive multi-host SSH output is grouped by exact connection
  reference before a following transform step. Single-host Recipes, target
  resolution, per-host policy, confirmation, 37 native tools and public
  alpha604 remain unchanged.
- Internal Alpha889 lets explicitly marked native tools relay their already
  user-facing bounded result after kernel confirmation. Only `recipes_execute`
  opts in, preserving its Recipe-generated overview without a lossy second
  model phrasing call; every other mutating tool keeps existing phrasing.
  Confirmation, Recipe execution, 37 native tools and public alpha604 remain
  unchanged.
- Internal Alpha888 initializes the intentionally empty held-package summary
  left after the safe-fix teardown, so successful `ssh_run` Recipes can reach
  their execution summary without a `NameError`. Adaptive binding, SSH policy,
  native tools and the public alpha604 marker are unchanged.
- Internal Alpha887 replaces the shipped fixed-ref demo Recipe catalog with
  exactly three adaptive SSH examples for uptime, disk usage and update checks.
  Each uses `connection_kind=ssh` plus `binding=all`; duplicate legacy files
  under `samples/skills` are removed. User runtime Recipes, Alpha886 expansion,
  policy enforcement, 37 native tools and the public alpha604 marker are
  unchanged.
- Internal Alpha886 adds additive `ssh_run` Recipe binding by configured SSH
  kind. `binding=all` expands to concrete per-profile steps with a 20-target
  cap; `binding=one` requires exactly one configured profile. Fixed
  `connection_ref` Recipes are unchanged, previews list resolved targets, and
  expanded steps retain the existing per-step SSH policy and output bounds.
  Native tool count and the public alpha604 marker are unchanged.
- Internal Alpha885 forces `search_context_size=high` at the native web-tool
  request boundary, regardless of a persisted Config/Env value. The existing
  field remains for compatibility but is non-authoritative for native search.
  Alpha884 query framing, reasoning effort, output limits, diagnostics, native
  tools and the public alpha604 marker are unchanged.
- Internal Alpha884 prevents stale-year anchoring in provider-native web
  searches: the gateway makes the current date authoritative, no longer injects
  cached evidence URLs into provider input, and the native tool uses `high` as
  its missing/empty context-size fallback. The agent must form latest/current,
  year-neutral web-tool queries. Reasoning effort, output limits, native tools
  and the public alpha604 marker are unchanged.
- Internal Alpha883 removes the temporary Alpha882 file dump and adds a
  default-off admin toggle that exposes the exact native-web provider input,
  bounded request parameters and up to eight evidence URLs in the serving
  chat turn's routing details. Secrets, raw provider responses, web behavior,
  native tools and the public alpha604 marker are unchanged.
- Internal Alpha882 candidate adds a temporary always-on, single-file native
  web diagnostic dump with exact sent input, recursively redacted raw response
  and normalized evidence. Dump failures cannot affect turns; no config or
  environment switch is added, and the public alpha604 marker is unchanged.
- Internal Alpha881 candidate removes the inert Auto/Main/Web chat-mode control,
  its client submission and discarded request plumbing. Main/Web model setup,
  native execution and the public alpha604 marker are unchanged.
- Internal Alpha880 candidate: provider-native web search now defaults to
  `search_context_size=high`. `ARIA_WEB_LLM_SEARCH_CONTEXT_SIZE` accepts
  `low`, `medium` or `high`; unsupported values use the canonical default.
  Native tools, gateway payloads and the public alpha604 marker are unchanged.
- Internal Alpha879 candidate: the native-agent system instruction now requires
  `web_search_fetch` for latest/current fast-changing external facts instead of
  permitting answers from stale model knowledge. Answers must identify the
  evidence date or as-of state and describe older evidence as the latest state
  found rather than current. Native tools, confirmation, execution authority
  and the public alpha604 marker are unchanged.
- Internal Alpha878 candidate: the retired SearXNG transition service, its
  runtime module, pipeline wiring, health/restart surfaces, stack services and
  obsolete tests/docs are removed. Provider-native `native_web_llm` and its
  `web_search_fetch` tool remain the sole web-search path.
- Internal Alpha844 candidate: native RSS, calendar and remote-file read
  fallbacks now resolve exact configured profiles by membership in the
  authoritative ref-keyed connection dictionaries. Unknown refs remain honest
  empty results without runtime execution; injected loader scope and source
  authority checks are unchanged.
- Internal Alpha843 candidate: native `list_connections` treats an unknown
  optional kind filter as an honest empty result and reports the exact kinds
  available in the same user-scoped profile authority. Known and absent filters
  retain their existing behavior; invalid scope, source authority, identity and
  secret boundaries still fail closed.
- Internal Alpha842 candidate: six user-bound read-only native tools add exact
  RSS feed, calendar, SFTP/SMB file, and IMAP mailbox reads through existing
  runtime adapters. Tool inputs are allowlisted, profiles are exact, credentials
  never enter results, empty reads are explicit, and the global honest result
  cap applies to file and mail content. All 21 native tools remain below the
  full-offer threshold; the relevance selector is not activated.
- Internal Alpha834 candidate: exact Connections lookup now returns all safe
  user-scoped profiles when the same reference exists for multiple connection
  kinds, instead of treating that benign case as a safety failure. An optional
  exact `connection_kind` narrows the lookup; single-hit and not-found formats,
  source authority validation, and secret exclusion remain unchanged.
- Internal Alpha833 candidate: the Connections owner contributes the native
  read-only `lookup_connection` tool through the P1 registry. It resolves one
  exact user-scoped profile reference and returns only whitelisted safe profile
  metadata; credentials, keys, tokens, and other secrets are excluded. Missing
  references are reported honestly and ambiguous or foreign-scope rows fail
  closed. The existing Connections rollout flag controls both Connections tools.
- Internal Alpha832 candidate: native tools are declared by their owning
  modules and assembled from active module manifests plus rollout flags. The
  existing Personal Memory and Connections tools retain their schemas,
  authorities, user scope, and behavior; the native handler no longer embeds
  either implementation. A MetaCatalog relevance-selector boundary is ready
  for larger toolsets, while the current two-tool set is offered in full.
- Internal Alpha831 candidate: enabled native-agent Web turns now invoke the
  native handler before the expensive pre-pipeline MetaCatalog arbitration.
  Pending contexts and disabled flags retain the legacy path, while an
  unexpected native `None` result lazily restores the same arbitration and
  pipeline processing without crashing. During this rollout, model-routed
  per-chat admin actions and memory forget are deferred until native tools own
  them.
- Internal Alpha830 candidate: the standalone default-off native agent now also
  offers `list_connections`, a read-only Anthropic-native tool backed by the
  complete passive Connections profile source rather than an arbitration plan.
  The current turn user is bound by the handler, an optional exact kind filter
  is supported, and Memory and Connections tools are offered independently by
  their rollout flags. Empty inventories are reported honestly.
- Internal Alpha829 candidate: a default-off standalone native agent can own an
  enabled turn before runtime follow-up and MetaCatalog arbitration. It uses the
  proven Anthropic-native `tools` path, offers one read-only Personal Memory
  tool backed by the Memory source authority, and records a bounded step trace.
  The existing admin rollout save path controls the new flag; legacy behavior
  remains unchanged while either required flag is off.
- Internal Alpha828 candidate: the native Tool-Calling selftest now passes an
  Anthropic-native tool definition through LiteLLM with an explicit
  `input_schema.type="object"`, properties, and required fields. Provider bad
  requests expose their raw error text and the exact sent tool payload in the
  admin diagnostic. Tool-call parsing and the second roundtrip step are unchanged.
- Internal Alpha827 candidate: an isolated admin-only native Tool-Calling
  selftest invokes LiteLLM with `tools` and `tool_choice="auto"`, executes only
  the local deterministic `add_numbers` diagnostic, returns its tool result to
  the model, and reports the two-hop transport evidence. It does not use
  `response_format`/JSON Schema, Qdrant, the turn pipeline, agentic loops, or
  product operations; loading the page is inert and only an explicit POST can
  make the two provider calls.
- Internal Alpha826 candidate: the default-off agentic loop now has its first
  model-driven Personal Memory Recall vertical. Recall remains MetaCatalog- and
  claim-authority-bound, produces per-step learning traces, and never turns a
  failed executor result into a successful answer. Admins can persist the
  default-off read-only rollout flags through the existing configuration UI.
  The Alpha825 correction moves the recall gate before legacy arbitration;
  a tiny model decision either enters Personal Recall or defers unchanged.
  The Alpha825 live failure exposed Anthropic Tool-Use responses with empty
  message content: Alpha826 reads the first tool call's structured arguments,
  while preserving normal content, usage, audit, cost, and empty-response behavior.
- Internal Alpha823 candidate: Stage-2 Connections and Commands discard unknown
  non-authoritative fields while exact kinds, refs, capabilities, effects,
  permissions, confirmations, and action matches remain fail-closed. Personal
  memory can repair one answer/context contract contradiction.
- Internal Alpha822 candidate: structured turn decisions now negotiate strict
  JSON-schema support gracefully. Providers that reject strict mode fall back
  once to the validated non-strict path, and later turns avoid another failed
  strict probe; providers that ignore strict remain bounded by validation and
  one model-based repair.
- Internal Alpha821 candidate: Makroblock G adds a default-off agentic execution
  loop with a read-only Connections Inventory vertical, kernel enforcement before
  execution, bounded iteration, trace evidence, and fail-closed budget handling.
- Internal Alpha820 candidate: Recipes, Chat, Connections, and Commands now use
  owner-specific bounded operation payloads after MetaCatalog dispatch.
- Command actions must be offered by current Qdrant MetaCatalog candidates;
  stale configuration no longer substitutes for runtime routing authority.
- Fixed Recipe inventory compilation, module-semantics diagnostics, and the SSH
  confirmation debug reason observed during the Alpha819 live review.
- No public release; the public version remains `0.1.0-alpha604`.

## [0.1.0-alpha808] - Public Release Candidate Draft

### Public Release Notes Draft Since 0.1.0-alpha604 - Major Changes

- **ARIA has been rebuilt from a monolith into a modular architecture.** The application is no longer organized around one large chat/runtime block. It now uses registered modules with clearer owners, manifests, read models, boundaries, import identities, and stricter release hygiene. For users this should make ARIA easier to maintain and less prone to hidden side effects; for operators this update must be treated as a major architecture upgrade, not a routine alpha bump.
- **Routing and tool use now have stricter agentic ownership boundaries.** MetaCatalog, documents, memory, notes, recipes, web/public facts, and runtime actions each have their own authority contracts. Natural-language meaning must not be inferred through keyword lists, regex cascades, substrings, tokens, stems, or phrase triggers. Models produce structured plans; ARIA then mechanically validates exact IDs, source authority, schemas, confirmations, permissions, and execution scope.
- **SearXNG is no longer the supported public WebSearch operating model.** Stored SearXNG profiles are no longer the expected WebSearch path for current public facts. Current web answers now require a suitable LLM/provider setup with web tooling or a managed web-search capability. Without that capability, ARIA must answer current-fact and web questions in a limited or fail-closed way instead of silently falling back to old local SearXNG profiles.
- **Public facts and WebSearch have been made source-bound.** Current information such as prices, device releases, software versions, or web content must not be guessed from model knowledge when a source is required. Web/public-fact answers must respect their search/tool authority and source scope.
- **Recipes now have a dedicated semantic owner.** Stored recipe manifests come from the same catalog path as the UI. Operations such as `inventory`, `explain`, `preview`, `execute`, and `none` are owned by the recipe semantic router. `execute` creates a confirmation instead of silently running anything. Unknown recipe IDs are explained source-bound and are not replaced with similar-looking recipes.
- **Notes, documents, and memory were repaired after the modularization.** Notes folder lists, document inventories, document-vs-memory source labels, and personal recall were restored to source-bound behavior across several internal alphas so ARIA does not jump between similarly worded note, memory, and document sources.
- **Runtime actions are more conservative.** Action selection, action input, target scope, and confirmation are now more tightly enforced. ARIA should not execute a runtime action until the exact structured action, target, permission, and user confirmation all match.
- **Release and artifact hygiene has been tightened substantially.** Internal review builds now check CLI/release metadata, package data, module registry state, JSON/compile/diff hygiene, source bytecode, image-layer privacy, and passive HTTP routes. Private data, secrets, productive connections, Qdrant data, and live runtime actions must not be baked into public artifacts.

### Smooth Upgrade / No CLI Recovery Goal

- **The public upgrade path must work through the browser or managed updater first.** Normal users should not need to hunt for Docker containers, patch Compose files, or run unclear recovery commands after updating. `/updates`, `aria-setup upgrade`, and `./aria-stack.sh update` are the intended paths. Raw Docker commands belong in admin or recovery documentation only.
- **No silent data or volume deletion.** Config, prompts, notes, recipes, auth data, memory, document data, and Qdrant collections must not be deleted, moved, or reinitialized during the public architecture jump unless a dedicated migration step clearly explains the change and asks for confirmation first.
- **SearXNG is an explicit stack-migration decision.** The application no longer relies on the old SearXNG profile path, but existing public stacks may still contain `searxng` and `searxng-valkey` sidecars. Recommended policy for the first public architecture jump: do not remove these sidecars automatically. Leave them as legacy/inert services and move ARIA to provider web tooling. Removing them later should be an opt-in helper with dry-run output, health checks, and rollback guidance.
- **Any script that stops, removes, or recreates services must say so first.** A future SearXNG cleanup or Compose-layout migration must show affected services, affected volumes, what will be kept, what will be removed, which backups or hashes exist, and where the operation can still abort before mutation.
- **Provider and web-tooling readiness must be visible.** Before a public release candidate, ARIA needs a clear UI/documentation path that tells operators whether an LLM with web tooling or managed web search is configured. If the capability is missing, current-fact and web questions must be limited or fail closed instead of sending users into SearXNG troubleshooting.
- **Open public release-candidate gates.** Before the next public release, an upgrade pack must cover managed setup upgrade, host-update dry-run, Compose config, passive HTTP routes, config backup/restore readpoints, provider/web-tooling messaging, SearXNG legacy behavior, and no-data-deletion checks. Matrix: `.codex/aria_acceptance/public-alpha604-to-alpha807-upgrade-transition.json`.

### Upgrade Notes

- Treat this as an architecture migration from `0.1.0-alpha604`, not as a normal point update.
- Back up configuration from `/config/backup` before upgrading.
- Prefer `/updates` or the managed install updater. Use host-side CLI helpers only for managed-admin workflows or manual Compose installs.
- Verify the upgraded instance after the update: `/health`, `/stats`, `/updates`, config pages, notes, recipes, memory, documents, one ordinary chat prompt, one recipe inventory prompt, one notes-folder prompt, one action-confirmation prompt, and one current-fact/web prompt if web tooling is configured.
- Operators who previously used SearXNG must migrate to the provider/web-tooling model. Existing SearXNG sidecars should remain untouched for the first architecture jump unless a later release ships a dedicated opt-in cleanup helper.
- The current public release remains `0.1.0-alpha604` until a separate public release-candidate workflow is explicitly approved.

### Internal Alpha Summary Since Public 0.1.0-alpha604

- **alpha830:** Adds complete read-only Connections inventory to the standalone
  native agent, with optional kind filtering, turn-user binding, dual-tool model
  selection, and an independent default-off admin rollout flag.
- **alpha829:** Adds the first standalone native agent turn: direct chat or one
  source-bound Personal Memory read through Anthropic-native Tool-Calling,
  short-circuited before legacy arbitration and default-off behind admin flags.
- **alpha828:** Corrects the live-rejected Alpha827 diagnostic tool schema to
  Anthropic-native `input_schema` and makes provider schema rejection evidence
  visible without changing the tool result roundtrip.
- **alpha827:** A standalone admin diagnostic exercises native LiteLLM
  Tool-Calling end to end with a harmless deterministic addition tool. Local
  fake tests prove parsing and isolation; only the later explicit live trigger
  can prove provider behavior.
- **alpha826:** The model gateway preserves structured Anthropic Tool-Use
  arguments when LiteLLM returns them outside empty message content, allowing
  the loop-first gate to consume its strict-schema decision.
- **alpha825:** The default-off agentic loop uses a bounded model decision for
  Personal Memory Recall, supports bounded correction observations, binds final
  answers to loaded claim evidence, and fails closed on non-success executor
  statuses.
- **alpha823:** Stage-2 field drift is tolerated consistently for Connections
  and Commands, while authority fields remain exact; the bounded repair now
  covers contradictory answer decisions that also request context.
- **alpha822:** Structured decision transport now uses strict JSON schema only
  for compatible schemas, falls back safely when providers reject it, and
  remembers that capability while preserving authority validation.
- **alpha821:** A default-off agentic execution loop is available for the
  read-only Connections Inventory vertical. Operation contracts, policy and
  confirmation enforcement remain between model decisions and execution;
  budgets, observations, and machine-readable traces fail closed.
- **alpha819:** Microkernel foundation, dynamic module loading, Qdrant-only MetaCatalog routing, module-owned projection providers, and the SSH/SFTP isolation proof are prepared as an internal review candidate. Alpha818 remains live-rejected; alpha819 does not authorize a public release.
- **alpha808:** Public release-candidate docs and update helpers were aligned for the architecture jump from `0.1.0-alpha604`: Docker Hub now leads with the major modular-architecture warning, normal managed updates recreate only `aria`, and public docs describe SearXNG as a legacy sidecar while WebSearch moves to provider/web tooling.
- **alpha807:** MetaCatalog action transport now comes only from structured authority fields. Recipe handoffs can carry zero unrelated runtime actions. Unknown recipe IDs produce source-bound recipe catalog clarification. Ordinary same-hop chat is covered with empty action transport and routing-debug diagnostics.
- **alpha806:** MetaCatalog was reduced to broad recipe-domain selection. Exact recipe operation and offered recipe ID selection moved to the recipe semantic owner with strict schema validation and fail-closed behavior.
- **alpha805:** A local public-release regression pack was added for public current facts/WebSearch, public artifact hygiene, actions/confirmation, ordinary chat/error handling, recipes, memory, notes, and documents.
- **alpha803-alpha804:** Public current-fact/WebSearch contracts and public artifact hygiene were strengthened so private/internal artifacts do not leak into public packaging.
- **alpha799-alpha801:** Notes folder authority, direct source-bound notes inventory, and document-vs-memory source labels were repaired after the modularization.
- **alpha797:** MetaCatalog safe-fallback source authority was tightened after a live recipe inventory fallback failure.
- **alpha796:** Ordinary chat was restored to the short same-hop path without unnecessary recipe, context, final-composer, or pending-action handling.
- **alpha794-alpha795:** Runtime recipe catalog authority was aligned with `/recipes/mine`, legacy-compatible recipe manifests were included, disabled recipes were excluded, and recipe transport to MetaCatalog was made smaller.
- **alpha792-alpha793:** Recipe matching debt was removed and replaced with model-owned recipe operation selection plus total fail-closed validation. The first alpha792 live test was rejected and then covered by alpha793.
- **alpha787-alpha788:** Runtime action confirmation and execution snapshots were tightened. Confirmations now expose the concrete capability, target, and payload before execution.
- **alpha783-alpha786:** Personal memory capture/recall ownership, same-hop personal recall, and latency/transport behavior were repaired and accepted in live review.
- **alpha774-alpha782:** Earlier modularization follow-ups tightened connection target authority, fleet scope, document answers, personal recall, and source-bound behavior.

### Current Internal Review Candidate

- Internal workspace/build candidate: `0.1.0-alpha871`
- **alpha871 (internal):** Removes the dead legacy decision fallthrough from `Pipeline.process`, makes the native agent the sole web/pipeline decision path, and deletes the now-reference-free process-stage and old agentic-loop bridge helpers. Explicitly disabled native operation returns an honest degraded result; the legacy funnel modules remain present for later teardown stages.
- **alpha870 (internal):** Makes the native agent the reversible delivery default by setting all 13 Agentic Loop rollout fields on by default. Every field remains configurable, and legacy-funnel tests pin the master switch off explicitly until teardown stage 3.
- **alpha869 (internal):** Tightens the native-agent system instruction so explicit or fragmented memory-persistence requests use the offered memory tool or ask for clarification, and mutation-completion language is allowed only after the matching tool returned success in the same turn. Tools, confirmation, phrasing, selector, and runtime behavior remain unchanged.
- **alpha868 (internal):** Removes the dropped legacy `safe_fix` capability, including its module, registry ownership, pipeline result/threading, executor, and chat-cookie confirmation flow. Native tools, recipes, bounded decisions, and the intentionally inert Discord `alert_safe_fix` connection setting remain unchanged.
- **alpha867 (internal):** Adds a separate default-off, administrator-only native `admin_update_run` tool. The existing confirmation kernel gates the existing GUI Update Helper trigger, while disabled, already-running, and failed helper outcomes remain explicit and administrative read tools stay independently gated.
- **alpha866 (internal):** Adds default-off native `memory_capture` under the existing write-memory rollout flag. One explicit fact or preference is frozen by the confirmation kernel and stored through the canonical personal-claim authority with server-bound user, collections, authority, risk, confidence, and source; rejected activation remains an honest not-stored result.
- **alpha865 (internal):** Resolves enabled Recipes through either their exact canonical id or one unique exact display name (case-insensitive for names), while confirmed execution always passes the canonical id to the unchanged guarded Recipe engine; ambiguous, disabled, partial, and fuzzy matches remain non-executable.
- **alpha864 (internal):** Adds default-off native `recipes_execute` with recipe-level kernel confirmation while preserving the existing per-step SSH, file, connection, and policy guardrails through the canonical Recipe engine.
- **alpha863 (internal):** Adds default-off native `file_write` and `http_api_request` tools with exact configured-profile binding and the existing confirmation kernel; HTTP execution receives `confirmed=True` only after kernel confirmation.
- **alpha862 (internal):** Adds four default-off, profile-bound native messaging tools for Discord, webhooks, email, and MQTT; every send is intercepted by the existing confirmation kernel before execution, while the all-tools threshold rises to 40 without activating the selector.
- **alpha861 (internal):** Populates every native-agent PipelineResult with the active scope's token snapshot for the per-turn chat badge, while retaining the scope flush as the sole persistent usage log and safely displaying zero when no snapshot is available.
- **alpha860 (internal):** Flushes the native-agent chat usage scope before every outcome branch, persisting aggregated tokens and request counts exactly once while treating missing or failed metering as non-destructive observability loss.
- **alpha859 (internal):** Resolves the native-agent UsageMeter from the pipeline owner's live `usage_meter` first, retaining the settings-attached meter only as a compatibility fallback, so native completion usage reaches the operator cost ledger.
- **alpha858 (internal):** Records every native-agent loop, budget-finalizer, confirmation-preview and confirmed-result model completion through the shared UsageMeter with exact provider usage and isolated duration; missing usage or meter failures never alter a turn.
- **alpha857 (internal):** Makes confirmation-required native tools direct: the model calls them with exact arguments while the kernel owns confirmation, and persisted non-authoritative request context keeps preview/result phrasing in the original request language across confirm turns.
- **alpha856 (internal):** Keeps write preview/result phrasing in the current user's language, makes the action payload the sole phrasing authority, and includes the executed SSH command in the allowlisted result so confirmations can report concrete outcomes.
- **alpha855 (internal):** Strengthens the native-agent system instruction so current server, file, remote-system, connection, command-output and stored-data questions must use an offered tool and may only answer from that turn's tool result; concrete live-state output must never be invented or reused.
- **alpha854 (internal):** Adds default-off, admin-only native `ssh_read` and confirmation-gated `ssh_command` tools. Both bind exact configured SSH targets to the existing low-level SSH policy/runtime; confirmation cannot override policy hard blocks or allow-lists.
- **alpha853 (internal):** `notes_write` now upserts one user-owned note by normalized exact title and folder when no note ID is supplied, refuses ambiguous title matches without writing, and reports explicit `created` or `updated` result actions.
- **alpha852 (internal):** Updated the native-agent system instruction to allow every offered tool and forbid claims of completed mutations unless a tool call actually performed them in the current turn.
- **alpha851 (internal):** Added default-off, kernel-confirmed personal-memory deletion by frozen claim IDs and user-scoped note updates. Unknown note IDs cannot create notes; the 24 read tools remain unchanged.
- Native write phrasing calls now omit `tool_choice` when no tools are offered, matching the Anthropic/LiteLLM request contract while preserving deterministic fallbacks.
- Native mutating-tool previews and successful results are now phrased naturally by bounded presenter calls, with deterministic raw-text fallbacks that cannot alter execution authority.
- Native mutating tools now have a kernel-enforced, server-side Preview -> Confirm -> Execute boundary; the first default-off proof is `notes_write`.
- Native-agent follow-up turns now receive a bounded prior user/assistant history, and connection-backed tools are offered only when at least one declared profile kind is configured.
- The native agent now receives the authenticated session role through a handler-bound, default-deny context and can offer three default-off administrator-only read tools for safe update status, aggregate stats, and bounded activity diagnostics. Tool arguments cannot supply or override the role; backup tools remain deferred. Public remains `0.1.0-alpha604`.
- Latest internal image: `0.1.0-alpha845`
- Latest internal TAR: `aria-alpha845-local.tar`
- Current public release: `0.1.0-alpha604`
- Public release: not yet approved
