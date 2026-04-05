# Memory

ARIA uses typed memory with Qdrant.

Current memory layers include:

- facts
- preferences
- session context
- rolled-up knowledge

Important current behavior:

- auto-memory no longer stores every transient question
- stable user facts and preferences are kept
- capability results are not written into memory by default

Useful references:

- `docs/help/memory.md`
- `docs/product/feature-list.md`
- `docs/product/architecture-summary.md`

