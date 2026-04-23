# Qdrant in ARIA

Status: 2026-04-21

Qdrant is ARIA's central store for semantic knowledge.

ARIA mainly uses Qdrant for:

- personal memory
- document RAG and chunks
- rollups and condensed knowledge
- routing indexes for connections and later system decisions

## What gets stored there

Typical content inside Qdrant:

- facts and preferences from memory
- document chunks from imported files
- condensed rollups
- routing metadata for semantic selection

Important:

- Qdrant is not "the chat itself"
- Qdrant is the vector and retrieval store behind it
- the main ARIA configuration still lives in `config/` and other app data

## Why Qdrant stays separate

ARIA intentionally keeps Qdrant as its own service:

- clearer separation between app and semantic storage
- easier diagnostics
- easier backup and migration
- more flexible than a tightly embedded in-process solution

That separation is useful in practice:

- ARIA stays the orchestration layer
- Qdrant stays the specialized retrieval and vector service

## What to check in day-to-day operation

When memory behaves poorly, start with:

- is Qdrant reachable?
- is the embedding setup correct?
- is the right collection active?
- were the documents really imported?

Helpful places inside ARIA:

- `/memories`
- `/memories/explorer`
- `/memories/config`
- `/stats`

So Qdrant is not a side detail. It is a core part of ARIA's knowledge layer.
