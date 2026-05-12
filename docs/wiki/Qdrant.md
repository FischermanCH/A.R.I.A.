# Qdrant in ARIA

Updated: 2026-05-12

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

## Day-to-day checks

If memory, RAG, or routing feels weak:

- check `/stats` preflight
- open `/memories/map`
- check embedding model and fingerprint
- test connection routing under `/config/routing`
- watch Qdrant collection and storage warnings

## Update note

Normal managed updates recreate only `aria`. Qdrant and its volume intentionally stay running. Use `repair` or full-stack work only when release notes or recovery guidance say so.
