# ARIA Help: Memory and Stores

Updated: 2026-04-06

## Purpose

This document explains how ARIA stores knowledge, which Qdrant collections are used, and how answers are later reconstructed from that knowledge.

## What deliberately does not go into semantic memory

Not every chat message is knowledge. Operational skill triggers are therefore not stored as day-context by default.

Examples:

- `systemupdate mgmt-master`
- raw skill or tool triggers
- technical control commands
- execution prompts without lasting knowledge

Goals:

- Qdrant should contain stable knowledge where possible
- less memory noise
- better recall quality with fewer irrelevant hits

Existing older entries can be cleaned up via maintenance:

`./aria.sh maintenance`

The output includes a counter such as:

`noise=<count>`

## Store types

ARIA currently works with four main memory layers per user:

### 1. User facts store

Schema:

`aria_facts_<username>`

Purpose:

- long-term user knowledge
- stable facts that remain relevant
- explicit `remember ...` requests are written here

### 2. Day context (Qdrant)

Schema:

`aria_sessions_<username>_YYMMDD`

Purpose:

- short- to medium-term working context
- automatic memory extraction per day
- easier to manage than random session IDs

### 3. Context memory (rollup)

Schema:

`aria_context-mem_<username>`

Purpose:

- compressed knowledge from older day-context collections
- less collection sprawl in Qdrant
- still available for recall

### 4. Document collections (RAG v1)

Schema:

`aria_docs_<name>`

Purpose:

- uploaded RAG documents
- chunk-based import for `txt`, `md`, and `pdf` with embedded text
- intentionally separated from facts, preferences, and rollup knowledge

Important:

- document collections are their own knowledge source
- they should not be mixed with normal fact, preference, or session collections
- if all chunks of a document collection are gone, ARIA removes the empty collection automatically

## Write behaviour

### Explicit store

Example:

`Remember that my intranet runs on 10.0.0.10.`

Behaviour:

- ARIA detects `memory_store`
- the content is written to the user facts store
- duplicate facts are deduplicated where possible

### Auto-memory

With auto-memory enabled, ARIA separates extracted content into:

- Facts -> `aria_facts_<user>`
- Preferences -> `aria_preferences_<user>`
- Session context -> `aria_sessions_<user>_<YYMMDD>`

Transient one-off questions and raw tool/action prompts are no longer turned into session context automatically unless they contain a clear fact or preference signal.

## How recall works

For a recall question, ARIA combines multiple knowledge sources:

1. user facts
2. day context
3. rollup knowledge
4. an internal per-user document guide index
5. matching document collections (`aria_docs_*`) when document knowledge is relevant

Document recall is deliberately two-stage:

1. on upload, ARIA creates a compact internal guide entry per document
2. a recall question first searches this guide index
3. only the best matching documents are then searched deeply by chunk

If a document was used, ARIA now shows the source in chat details:

- document name
- target collection
- chunk reference, for example `Chunk 12/108`

## Forget with confirmation

ARIA requires an explicit confirmation code before deleting matched memory entries. Without a valid code, nothing is removed.

The pending delete state is signed in the browser cookie, so tampering with it blocks the delete flow.
