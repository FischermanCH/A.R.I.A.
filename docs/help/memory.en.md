# ARIA Help: Memory and Stores

Updated: 2026-07-09

## Purpose

Memory is ARIA's semantic knowledge store. It is separate from notes, logs, and raw runtime results.

ARIA uses Memory for:

- stable facts about the user and environment
- preferences
- session context
- longer-term rollups
- document RAG
- Experience Memory for safe learned action patterns

## What deliberately does not go into memory automatically

- every transient question
- complete SSH/SMB/RSS snapshots
- technical logs without lasting value
- mutating action proposals without review

This reduces memory noise and prevents ARIA from turning random one-off events into durable assumptions.

## Store types

### Facts and preferences

Long-term knowledge ARIA may reuse later.

### Session context

Working memory for active tasks and previous turns.

### Rollups

Compressed weekly/monthly or work-context summaries. Rollups help without pulling every old chat detail into every prompt.

### Document collections

RAG v1 for uploads under `/memories`. Supported formats are text, Markdown, and PDFs with embedded text. OCR/scan PDFs are not part of v1.

### Experience Memory

Successful safe recipe/guardrail/action patterns can be stored as planner context. They help ARIA propose actions, but do not replace policy or guardrails.

## Recall

Recall can combine:

1. direct facts/preferences
2. session context
3. rollups
4. document guides and matching chunks
5. Experience Memory for action planning

Chat details show sources, collection, and chunk references when document recall was used.

## UI

- `/memories` for the graphical Memory browser
- `/memories/import` for new documents and memory imports
- `/memories/auto-memory` for Auto-memory and agentic learning settings
- `/memories/maintenance` for technical maintenance, rebuilds, and internal learning artifacts
- `/config/embeddings` for embedding model and safety confirmation when memory already exists

### Auto-memory and learning

Auto-memory can store durable facts and preferences when ARIA has enough confidence. Agentic learning can also extract reviewable conventions from user feedback and successful safe runs. Learning artifacts are context and review material; they do not bypass policy, guardrails, or confirmation.

The Learning Governor bounds new events, candidates, and evals per source and day/session using FIFO admission. Content fingerprints deduplicate equivalent candidate/eval content even when event or candidate IDs change. Evals are stored only when the LLM marks them review-worthy and their importance reaches the configured threshold.

The browser continues to show every retained point without hidden filters. `active effective` identifies explicitly activated Learning Hints, `review only` identifies candidates, and `audit only` identifies events/evals. ARIA automatically cleans internal event, candidate, and eval collections at startup and after new learning writes. Retention keeps the most important and source-diverse points per learning collection; manually reviewed/prepared, activated, promoted, regression-passed, or explicitly protected points remain. Age does not decide what is kept.

The Auto-memory page lists all learning events, candidates, evals, and active hints for the current user without sampling. Entries can be expanded, reviewed by effect, source, importance, and synthesis state, and deleted individually. Deletion affects only the selected learning point.

The summary separates the `Review queue` from `Raw evidence`. Every point remains visible, but only canonical candidates consolidated by `learning_synthesis` from at least two real source points become human review tasks and receive action controls. Raw candidates remain visible and individually deletable as automatic synthesis evidence; they do not require manual acceptance.

Review candidates are handled directly in their expanded entry. `Accept` marks a candidate as human-reviewed and evaluates the promotion gate; it does not activate anything. `Reject` excludes it from promotion. Only eligible low-risk candidates can move into the still-inactive preparation stage with `Prepare apply`. `Gate & regression` opens the detailed regression, preflight, and final explicit activation flow for a weak Learning Hint. Unsupported candidate types remain visible as `reviewed_blocked`.

Automatic Learning Synthesis consolidates related review-worthy candidates into a few canonical review candidates. It preserves source IDs and excerpts, replaces raw candidates only after a successful store, and never activates runtime behavior automatically. An admin can trigger the same bounded run with `Synthesize now`; otherwise it runs at startup.

Explicitly activated Learning Hints enter the preferred LLM-first turn plan as weak signals. They cannot override safety, configuration, explicit targets, or source evidence. ARIA tracks a semantic match separately from actual use. Recent user feedback is linked only to hints that were actually used; repeated negative feedback automatically suspends the hint.

Explicitly confirmed spellings can be learned as a structured entity alias, for example `"Simpoini" means "Simponi 50 mg"`. A typo alone is not enough. Before activation, the canonical form must be linked exactly to an existing Memory point outside `aria_learning_*`. Review and activation show the observed form, canonical form, and source Memory; the active hint only helps the LLM resolve context and cannot alter facts, dosage, or the current user request.

Explicit durable user statements are stored as structured personal claims with type, scope, authority, and status. Only active claims enter the small personal turn context; superseded, suspended, or disputed claims remain visible but do not affect normal behavior. Raw learning events, candidates, and evals are not normal answer context.

The `Personal model` area on `/memories/auto-memory` shows current and historical claims with separate counters for presentation, actual LLM-reviewed use, changed outcomes, and feedback. Claims can be suspended, conflict-checked before reactivation, or deleted point by point. The current user request, safety, configuration, explicit targets, and source evidence always remain stronger than personal context.

Time-bounded claims manage their own runtime state: future claims are `scheduled`, currently valid claims are `effective`, and claims past `Valid until` are `expired`. Scheduled and expired claims remain visible for control but do not influence ARIA.

A correction creates a new current version while preserving the previous claim as history. Goals and projects can be paused, resumed, completed, and reopened. Session-scoped statements remain in the existing session-memory layer instead of becoming durable personal truth.

When more than twelve effective claims exist, the LLM selects the turn-relevant claims for the bounded capsule. A reached `Review after` timestamp is shown as due but does not silently deactivate the claim.

For active hints, `/memories/auto-memory` shows lifecycle state, version, matches, uses, positive/negative feedback, and last use. The user can suspend, reactivate, or permanently delete each hint. Deferred raw evidence is reconsidered in bounded batches when new evidence arrives.

### Memory browser

The Memory browser is the graphical maintenance and debug view for ARIA's Qdrant/Memory data. It presents the same data in two connected ways:

- The graph shows root, memory types, collections, documents, entries, and chunks as a navigable structure.
- The inspector shows details for the current level and can be used as its own navigation path.
- On the entry screen, nothing is selected; the inspector lists all collections.
- Collection levels first show their documents or entries. The related chunks appear one level deeper.
- Document collections show documents and then their chunks. Other collections show entries and their memory points.
- Individual chunks, points, and documents can be deleted in the browser. Contents are deliberately not edited inline because edits require re-embedding; deleting and re-importing is safer.

### Structure and semantic proximity

Structure mode is the default view. It supports zoom, free pan, panbars, fullscreen, inspector drilldown, and saved structure options for spacing, clustering, and attraction.

Semantic proximity appears only on concrete chunk/entry/point levels. It shows computed neighborhoods from Qdrant embeddings without sending raw vectors to the browser.

Only safe metadata, text previews, collection names, point IDs, and computed edges are visible. Fullscreen and iOS/touch handling use the same logic as the normal browser.

## Embedding fingerprint

Memory and document entries carry an embedding fingerprint. This prevents ARIA from silently mixing old and new embedding generations during recall or document routing.

## Forgetting

Entries can be deleted directly in `/memories`. In chat, ARIA can recognize explicit forget requests, but destructive operations should ask for confirmation.

## Why answers can feel thin

- Memory is disabled or Qdrant is unreachable
- embedding model changed and old entries no longer match
- too few or wrong memories exist
- the request is more of an action prompt and is routed to the Agentic Action Flow before RAG
- Top-K or recall limits are too conservative

## Test hints

- use `remember ...` for explicit storage
- ask about the same fact later
- check `/stats` and chat details for recall sources
- check `/memories` for collection/document/chunk structure and semantic proximity
