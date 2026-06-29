# ARIA 0.1.0-alpha428

This public alpha hotfix improves source-bound answers for uploaded document inventories.

## Fixed

- Document inventory prompts over uploaded document collections now keep the Meta-Catalog-selected document metadata all the way into context loading.
- When several document metadata entries are selected, ARIA loads document IDs, filenames, and target collections directly instead of turning the request back into a semantic chunk search.
- This prevents list-style prompts such as "which uploaded documents do I have?" from answering with only one semantically best-matching document when the document explorer/catalog already contains several relevant documents.
- Pre-RAG SSH target recovery now refreshes stale missing-parameter state after semantic target resolution, so read-only status prompts can proceed on the resolved configured profile instead of asking for the same profile again.

## Performance

- Document inventory recall skips the embedding and chunk-search path for these metadata-list requests.
- Single-document content questions still use the normal source-bound document retrieval path.

## Privacy And Upgrade Notes

- No data migration is required.
- Existing Qdrant, Valkey, SearXNG, and user-data volumes can remain in place.
- The release notes intentionally avoid local/private instance names, internal docs, and private document contents.

## Verification

- Focused document inventory routing tests
- Focused MemorySkill document-inventory recall tests
- Focused Pre-RAG SSH semantic target recovery regression test
- Full pytest suite: `1609 passed`
- Python compile checks for touched modules
