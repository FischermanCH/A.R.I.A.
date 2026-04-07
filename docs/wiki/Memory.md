# Memory

ARIA uses typed memory with Qdrant.

Current memory layers include:

- facts
- preferences
- session context
- rolled-up knowledge
- document collections for RAG uploads

Important current behavior:

- auto-memory no longer stores every transient question
- stable user facts and preferences are kept
- capability results are not written into memory by default
- document uploads live in `/memories`
- document management lives in `/memories/map`
- the main `Memory` view also groups entries by type and offers quick type cards
- document recall uses an internal guide index with summary + keywords before ARIA drills into matching document chunks
- chat details show document recall sources with file name, collection, and chunk reference
- session compression now produces explicit weekly and monthly rollups with metadata such as bucket, period and source count
- `/memories/map` shows these rollups in a dedicated section instead of leaving them hidden as generic knowledge only
- `/memories/map` now also includes a simple read-only memory graph that makes types, collections, document groups and rollups visible at a glance
- embedding changes in `/config/embeddings` now require explicit confirmation when memory already exists, and the page links directly to the JSON export first
- memory and document payloads now carry an embedding fingerprint so ARIA does not silently mix different embedding generations during recall or document routing
- supported RAG v1 formats:
  - `txt`
  - `md`
  - `pdf` with embedded text only
- scan PDFs / OCR are not part of v1

Useful references:

- [`docs/help/memory.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/help/memory.md)
- [`docs/product/feature-list.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/product/feature-list.md)
- [`docs/product/architecture-summary.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/product/architecture-summary.md)
- [`docs/product/rag-v1-plan.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/product/rag-v1-plan.md)
