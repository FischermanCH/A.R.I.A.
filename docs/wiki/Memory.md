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
- supported RAG v1 formats:
  - `txt`
  - `md`
  - `pdf` with embedded text only
- scan PDFs / OCR are not part of v1

Useful references:

- `docs/help/memory.md`
- `docs/product/feature-list.md`
- `docs/product/architecture-summary.md`
- `docs/product/rag-v1-plan.md`
