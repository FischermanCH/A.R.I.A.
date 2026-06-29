# ARIA 0.1.0-alpha427

This public alpha release catches the public line up to the latest agentic-context, runtime-routing, WebSearch, and performance work.

ARIA is still an alpha system, but this release is a meaningful step toward the intended architecture: a compact Meta-Catalog first, LLM-chosen context/action directions, source-bound loaders, strict runtime guardrails, and fewer competing side routers.

## Highlights

- Meta-Catalog and ARIA turn routing were tightened so selected context/action contracts carry clearer answer/action modes, evidence policies, target refs, and debug traces.
- Visible chat and runtime outcome context now helps route follow-up questions, especially after confirmed SSH actions, without drifting into unrelated Docs/Memory context.
- SSH runtime follow-ups are faster and safer: direct path inspections can reuse source-bound RuntimeOutcomeFrame evidence, stay single-target, and avoid an extra follow-up LLM hop.
- WebSearch is substantially better for explicit internet research. Standalone search requests can take a fast path that skips the Meta-Catalog arbiter and follow-up rewrite LLM.
- SearXNG/WebSearch result quality improved for current product/version queries with official-source supplements, official-source ranking, and per-target coverage hints for multi-product questions.
- Docs and Mill-style how-to answers are more source-bound and less likely to fall back to raw chunks or generic "not sure" responses when the selected document evidence is clear.
- RSS feed routing is stricter: inventory questions stay inventory, exact feed reads stay on the exact feed, and broad group digests still work for broad prompts.
- Large parts of the runtime and routing pipeline were split into smaller modules without changing the user-facing contract.
- Debug and performance observability are much richer: routing payload sizes, token counts, web-route timings, browser wall time, and multi-target SSH timing are now visible in debug output.

## Performance Work

- Explicit internet-search turns can now bypass expensive routing stages when the user clearly asks for web research.
- Runtime SSH path follow-ups can avoid the separate `runtime_outcome_followup_resolution` LLM call when the requested path is already present in the previous runtime output.
- Direct inventory and compact Docs answers can skip unnecessary final answer-composer work when the loaded evidence is already source-bound and compact.
- Web chat route timing now separates route preparation, history load, follow-up rewrite, flow execution, history append, template, cookie, and browser wall time.
- Multi-target SSH execution now reports per-target runtime, summary time, total timing, and the slowest target.

## WebSearch / SearXNG

- Explicit web-search requests no longer fall through to generic chat answers claiming ARIA cannot browse.
- Explicit web-search requests no longer get stolen by RSS/feed actions when the prompt asks to search the internet.
- Current product/version searches can add official manufacturer/product queries and rank official pages above news, shopping, deal, and rumor pages.
- Multi-product searches now include target coverage rows, so one well-ranked product should not cause another sourced product to be reported as missing.

## Runtime And Connections

- Confirmed single-target SSH actions now store a RuntimeOutcomeFrame that later read-only follow-ups can reuse.
- Path follow-ups such as "what is in `/tmp`?" can remain attached to the previous SSH target when the path is present in the runtime output.
- Directory inspection summaries now read actual `du`/`ls` stdout instead of being misclassified as generic disk-health checks.
- Mutating SSH requests still fail closed, but the visible response now clearly names the Guardrail/SSH policy block.
- Multi-target SSH package-update and health-check flows preserve selected target refs more reliably.

## Architecture And Maintainability

- Routing/action helper logic was moved out of the central pipeline into focused modules such as routed action resolution, forced resolution building, SSH target scope policy, RSS execution policy, connection ref scope, stage timing, context evidence, and surface loading.
- Context answer composition, TurnFrame persistence, active learning hint recall, memory recall helpers, document memory services, memory admin queries, and session compression were separated from larger runtime classes.
- The Pre-RAG capability action gate and `process()` orchestration now use clearer typed result/input structures.
- Legacy/fallback paths are better classified as technical safety, migration adapters, no-LLM fallbacks, or removal candidates.

## Safety And Privacy

- The Docker image continues to exclude local AI handoff docs, private backlog/internal docs, and real secrets files.
- Runtime action paths still validate targets, policies, guardrails, risk, and confirmation before execution.
- This release does not require deleting or recreating Qdrant, Valkey, SearXNG, or user-data volumes.

## Verification

Focused verification before the public-prep build included:

- Web/Freshness/Explicit-Research: `23 passed`
- Release/Package/i18n: `25 passed`
- PyCompile checks for touched release/WebSearch modules
- `git diff --check`
- Docker image build and container health check
- Runtime tools check for `ssh`, Docker CLI, and Docker Compose
- Docker privacy smoke for local/private docs and real secrets

## Upgrade Notes

- Public Docker tags for this release should be `fischermanch/aria:0.1.0-alpha.427` and `fischermanch/aria:alpha`.
- Managed installs should use the normal ARIA update path and should not delete volumes.
- SearXNG quality still depends on the configured engines and instance behavior; ARIA now gives the search layer better queries and ranking hints, but it cannot make a weak SearXNG backend behave like a commercial web index.
