# ARIA 0.1.0-alpha429

This public alpha hotfix tightens source-bound document search behavior for uploaded document collections.

## Fixed

- Negative document-search answers now require explicit document-corpus coverage.
- If a docs-only recall only retrieves semantic chunks that do not contain the requested evidence terms, ARIA performs a literal scan over the selected uploaded document chunks before answering.
- The scan reports how many documents and chunks were checked, per-term match counts, and the scanned document sources.
- This prevents "not found" answers from being based only on a semantic top-k miss.

## Notes

- This is not a deterministic router. It is a source-bound evidence policy inside document recall.
- Normal semantic document recall remains in place for content questions.
- No data migration is required.
- Existing Qdrant, Valkey, SearXNG, and user-data volumes can remain in place.

## Verification

- Focused MemorySkill document-corpus scan tests for both missing and present literals
- Docs/Memory/Meta-Catalog focused tests
- Release/package/i18n checks
- Python compile checks and `git diff --check`

