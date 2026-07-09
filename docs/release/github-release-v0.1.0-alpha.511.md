# ARIA 0.1.0-alpha511

This is the public release note source for the first public release after `0.1.0-alpha437`. It documents the user-facing rollup that has been tested internally up to `0.1.0-alpha511`.

Public tag: `v0.1.0-alpha.511`.

## Summary

`0.1.0-alpha511` is a larger public alpha release focused on making ARIA feel more like a controlled personal operator: better chat flow, clearer confirmations, richer Memory/Notes workspaces, stronger source discipline, and more observable agentic runtime decisions.

The release keeps ARIA's core safety boundary: LLMs help with meaning, planning, summarization, and review, while policy, guardrails, runtime execution, validation, and confirmations remain controlled system layers.

## Highlights

- Chat Prompt Queue: keep writing while ARIA is busy, then edit, remove, or reorder waiting prompts before sequential execution.
- Pending Confirmations stay visible in the queue with run, plan-again, and discard actions.
- Graphical Memory browser: inspect Qdrant/Memory structure, documents, entries, chunks, semantic proximity, fullscreen, and touch/iOS interaction.
- Notes workspace: move notes between folders from cards or editor, use a dense list view, and bulk-move selected notes.
- Auto-memory and agentic learning UI: clearer user-facing controls and separation between durable memory, review artifacts, and technical maintenance.
- Generated navigation: the header, account menu, Settings, Admin, Memory, Recipes, and Connections use a shared navigation registry with calmer hubs and mobile wrapping.
- Agentic Operator Trace: Details can show understanding, context, draft/policy, runtime, result, summary, and review-only learning phases.
- Document inventory and corpus checks are more source-bound and less likely to answer from unrelated snippets.
- Web freshness answers prefer official/vendor/compare/release sources for current product and version questions.
- Multi-target SSH/runtime paths keep full-fleet scope for prompts such as all Linux servers when no true subgroup is named.

## Added

- Chat Prompt Queue with per-tab waiting prompts and sequential execution.
- Visible queue item for confirmation-required actions.
- Graphical Memory browser for structure drilldown and semantic proximity.
- Dedicated Auto-memory & learning page.
- Dedicated manual Memory creation page.
- Notes list view with multi-select bulk move.
- Agentic Operator Trace detail lines for runtime observability.
- Agentic Runtime Result Contract for multi-target runtime summaries.
- Help pages for Chat & Queue, Notes, and Agentic Operator.
- Help page for Navigation & Menus, covering Extended view, the account dropdown, header navigation, Settings/Admin groups, Memory, Recipes, and Connections.

## Changed

- Recipes navigation now separates the Recipes hub, saved recipes, new/templates, learned recipes, and admin maintenance more clearly.
- Settings/Admin/Memory/Recipes/Connections navigation is generated from a shared registry instead of scattered template links.
- Admin mode is presented as Extended view and moved closer to the account/settings context.
- Connections and Settings hubs are quieter and avoid operational status-card clutter.
- Web Search source selection is stricter for current/latest product questions when official sources are available.
- Document inventory questions load document metadata evidence instead of relying only on top semantic chunks.
- LLM-first routing and bounded planning remain the preferred path for meaning, while deterministic layers handle safety and runtime contracts.

## Fixed

- Current public product questions can override accidental local Docs-only matches and route to Web Search when the user did not ask for local documents.
- Current/latest product-line questions can add official manufacturer/store/compare sources even when only one product family is named.
- Rumor, deal, news, leak, and future-model sources are demoted for current availability claims.
- Clear built-in actions no longer become ambiguous against stored recipes when no LLM client is configured.
- Reconstructed SSH follow-ups keep the current target context instead of being preempted by generic stored recipe arbitration.
- All-scope SSH target prompts keep the full fleet when only OS/runtime words such as Linux are present.
- HTTP API status/health drafts can stay on their local health-path contract without unnecessary recipe arbitration.
- Server disk-capacity prompts can use the SSH runtime fast path instead of falling into unrelated document search.
- Expired or invalid action confirmations now give a recovery hint instead of a generic failure.
- Memory upload CSRF tests and related route assertions were aligned with the current session contract.

## Security / Safety

- No guardrail bypass was added for queued prompts or pending confirmations.
- Queue execution remains sequential; ARIA does not run multiple tool/runtime requests in parallel from the prompt queue.
- Confirmation-required actions still require explicit user action.
- Learned recipes and Experience Memory remain review/context material until deliberately promoted.
- Normal managed updates should recreate only the `aria` service and keep Qdrant, SearXNG, Valkey, and persistent volumes untouched.

## Known Limitations

- ARIA remains alpha software intended for controlled LAN/VPN/homelab environments.
- Prompt Queue is per browser tab and not persisted across reloads.
- The current queue edit flow uses the browser prompt dialog.
- Full multi-user ownership/RBAC/sharing for Recipes, Connections, and Memories is not complete.
- Pricing remains a local estimate based on usage logs and known model prices.

## Upgrade Notes

- Managed installs should use `/updates` or the managed update script.
- Fixed-tag installs can use the versioned Docker image once the release is actually published.
- A hard browser refresh is recommended because the release includes UI, CSS, and navigation changes.
- Do not remove Qdrant, SearXNG, Valkey, or persistent volumes during upgrade.

## What To Test After Upgrade

- `/health` returns `ok`.
- `/help` opens and includes Chat & Queue, Memory, Notes, Recipes, Agentic Operator, Pricing, and Security.
- Submit a second chat prompt while ARIA is still answering; reorder, edit, and remove queued prompts.
- Plan a confirmation-required action and verify the visible queue item can run, plan again, or discard.
- Open `/memories`, drill into a document collection, and test fullscreen/touch navigation if available.
- Create, move, and bulk-move Notes under `/notes`.
- Ask a local document inventory question and verify source-bound document names.
- Ask a current product question and verify official sources are preferred.
- Run one read-only SSH/API/RSS workflow and inspect Details for operator/runtime trace lines.
- Check mobile Safari/iPhone width for chat, queue, help, and Memory browser usability.

## Docker Images

- `fischermanch/aria:0.1.0-alpha.511`
- `fischermanch/aria:alpha`
