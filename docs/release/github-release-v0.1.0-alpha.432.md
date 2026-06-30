# ARIA 0.1.0-alpha432

This public alpha hotfix tightens corpus-wide uploaded-document questions.

## Fixed

- If the Meta-Catalog selects the structured document-corpus scope (`local|docs|documents`), ARIA now requires a document corpus scan even when the plan labels the context depth as shallow.
- This prevents "is this term in any uploaded document?" questions from being answered from one semantically retrieved document excerpt while claiming coverage over the whole uploaded-document set.

## Architecture Notes

- This is still evidence policy, not a deterministic meaning router. The Meta-Catalog/LLM chooses the docs surface and the document-corpus scope; Memory then proves coverage for that selected scope.
- The previous named-collection fix from `0.1.0-alpha431` remains in place, so custom uploaded-document collections selected by document guides/metadata are included in the corpus scan.

## Upgrade Notes

- Normal managed installs should use `/updates` or `./aria-stack.sh update`.
- Fixed-tag installs can use `fischermanch/aria:0.1.0-alpha.432`.
- Normal updates should recreate only the `aria` service and keep Qdrant, SearXNG, Valkey, and persistent volumes untouched.

## Docker Images

- `fischermanch/aria:0.1.0-alpha.432`
- `fischermanch/aria:alpha`
