# Qdrant in ARIA

Updated: 2026-06-09

Qdrant is ARIA's separate vector store. It intentionally stays its own stack service so memory, document RAG, and routing indexes do not disappear into the app container.

## What ARIA stores there

- facts and preferences
- session context and rollups
- document collections for RAG
- notes indexes for search
- connection routing indexes
- Experience Memory context for safe learned action patterns

## Why Qdrant stays separate

- the ARIA app container can be replaced
- volumes stay intact
- large document/memory data is not written into the image
- update helpers can recreate ARIA without touching Qdrant

## Routing and Agentic Intelligence

Qdrant is not only memory. ARIA also uses semantic candidates for connection routing. When deterministic matches are uncertain, ARIA can combine Qdrant candidates with LLM context.

Important: Qdrant does not decide alone. Policy, guardrails, and runtime remain separate layers.

## Qdrant Brain in the Memory Map

`/memories/map` includes a visual Qdrant Brain view. ARIA reads a bounded sample from user memory and document collections in read-only mode, computes semantic edges server-side, and renders a zoomable drilldown graph from that data.

The view is meant for observation and debugging:

- it helps show which points are semantically close
- it shows clusters, collection origin, and short payload previews
- it does not export embedding vectors to the browser
- it is intentionally capped so large Qdrant instances do not block the UI
- on touch devices it starts in browse mode: normal scrolling and tapping stay available; `Move graph` deliberately enables graph pan and node drag

## Day-to-day checks

If memory, RAG, or routing feels weak:

- check `/stats` preflight
- open `/memories/map`
- check embedding model and fingerprint
- test connection routing under `/config/routing`
- watch Qdrant collection and storage warnings

## Update note

Normal managed updates recreate only `aria`. Qdrant and its volume intentionally stay running. Use `repair` or full-stack work only when release notes or recovery guidance say so.
