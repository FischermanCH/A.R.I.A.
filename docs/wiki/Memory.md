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

The Learning Governor bounds new events, candidates, and evals per source and day/session using FIFO, deduplicates equivalent artifacts despite changing IDs, and stores evals only above the configured review/importance threshold. The Memory browser applies no hidden filter to existing points and labels `active effective`, `review only`, and `audit only`. Automatic importance retention cleans event, candidate, and eval collections at startup and after new writes. It keeps important and source-diverse evidence and protects activated, promoted, regression-passed, or explicitly protected points; age is not a selection criterion.

`/memories/auto-memory` shows the user's complete learning inventory and supports point-level manual deletion. A bounded LLM-first synthesis consolidates compatible raw candidates into canonical review artifacts with provenance; it grants no runtime effect and removes sources only after a successful store.

The page separates all visible raw candidates from the actual review queue. Only canonical synthesis candidates backed by at least two source points can be accepted or rejected; raw evidence remains visible and deletable but requires no manual decision. Accepting means human-reviewed only: the promotion gate then decides between `eligible` and `reviewed_blocked` without runtime activation. Eligible low-risk candidates can be prepared for apply and taken through regression, preflight, and a separate explicit Learning Hint activation under `Gate & regression`.

Activated Learning Hints reach the preferred MetaCatalog/AriaTurn path as weak signals and cannot override safety, configuration, explicit targets, or source authority. Matches and actual LLM use are counted separately. Recent feedback is linked only to used hints; repeated negative feedback automatically suspends a hint.

Explicitly confirmed alternative spellings can be learned through the `entity_alias_v1` contract. A typo alone does not create a durable alias. Activation requires distinct observed/canonical forms, explicit user confirmation, and an exact canonical-form reference in existing non-learning Memory. The active hint remains a weak LLM-first signal and cannot alter facts or dosages.

Structured personal claims carry type, scope, authority, and lifecycle status. Only active claims enter the bounded personal context used by turn planning and answers; raw learning artifacts and historical or suspended claims stay visible but ineffective. `/memories/auto-memory` shows use and feedback and supports point-level suspend, reactivate, and delete controls.

Validity windows are enforced automatically: scheduled and expired claims remain visible but do not enter ARIA's personal turn context.

Corrections supersede claims visibly instead of silently overwriting them. Goals and projects have dedicated pause, resume, complete, and reopen actions; session scope remains in session memory.

`/memories/auto-memory` shows lifecycle, version, match/use counters, feedback, and last use for each active hint. Hints can be suspended, reactivated, or deleted point by point. Deferred evidence is reconsidered in bounded batches when new evidence arrives.

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
