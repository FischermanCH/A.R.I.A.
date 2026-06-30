# ARIA 0.1.0-alpha431

This public alpha hotfix completes the deep uploaded-document corpus-scan path introduced in `0.1.0-alpha430`.

## Fixed

- Deep document corpus scans now work for explicitly selected named upload collections, not only plain per-user `aria_docs_<user>` collections.
- When the Meta-Catalog/document guides select a custom document collection, the corpus scan treats that selected collection as the source-bound scope and scans its document chunks before allowing a presence/absence answer.
- If a pre-guide corpus scan cannot find an accessible corpus, ARIA now retries the scan after document-guide selection instead of falling back to semantic top-k snippets only.

## Architecture Notes

- This remains an evidence-policy fix, not a deterministic router. The Meta-Catalog still chooses the docs/deep context contract; document guides or metadata select the document collection; the Memory skill then proves source-bound corpus coverage inside that selected scope.
- The context ledger now exposes whether a deep document turn requested `document_corpus_scan=true`.

## Upgrade Notes

- Normal managed installs should use `/updates` or `./aria-stack.sh update`.
- Fixed-tag installs can use `fischermanch/aria:0.1.0-alpha.431`.
- Normal updates should recreate only the `aria` service and keep Qdrant, SearXNG, Valkey, and persistent volumes untouched.

## Docker Images

- `fischermanch/aria:0.1.0-alpha.431`
- `fischermanch/aria:alpha`

