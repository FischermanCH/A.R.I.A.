# ARIA 0.1.0-alpha983

Alpha983 is a focused public hotfix for the document-inventory regression in Alpha982.

## Fixed

- Native document inventory now returns one structured row per imported document from the authoritative MemorySkill inventory metadata, including document name and collection.
- Inventory explicitly requests up to 200 documents instead of silently stopping at the MemorySkill default of 12.
- Document search and answer results retain their source document names and collections when source metadata is available.
- Tool guidance now distinguishes complete inventory questions from content search: inventory says which documents exist, while search finds excerpts inside documents and does not prove completeness.

**No document data was lost in Alpha982.** Imported files and their chunks remained stored; only the native Tool's inventory presentation discarded the correct listing and could then fall back to an incomplete content search.

## Upgrade

Back up the ARIA config/data mounts or volumes and the Qdrant volume, then replace the ARIA image with `fischermanch/aria:0.1.0-alpha.983`. No schema migration or data rewrite is required for this hotfix. Existing Alpha604 and Alpha982 installations are covered by the isolated upgrade gate.

The immutable image tag is `fischermanch/aria:0.1.0-alpha.983`; moving `alpha` and `latest` tags are updated only after explicit release approval.
