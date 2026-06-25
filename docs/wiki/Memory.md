# ARIA Help: Memory and Stores

Updated: 2026-06-09

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

- `/memories` for entries, search, editing, deletion, and JSON export
- `/memories/map` for collections, document groups, rollups, structure, and the Qdrant Brain graph
- `/config/embeddings` for embedding model and safety confirmation when memory already exists

### Memory Map and Qdrant Brain

The Memory Map first shows the logical structure: user, memory types, collections, document groups, rollups, notes, routing, and system collections.

When Qdrant is reachable and enough embedded points exist, the same page also shows the **Qdrant Brain**. This graph starts with Collections and lets you drill into a Collection to inspect its Qdrant points:

- nodes are memory, document, notes, and rollup points
- edges show computed semantic similarity between embeddings
- zoom, pan, and node details help inspect clusters and relevance
- raw vectors are never sent to the browser; only safe metadata, text previews, collection names, and point IDs are shown

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
- check `/memories/map` for collection/rollup structure
