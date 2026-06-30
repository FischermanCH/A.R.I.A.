# ARIA 0.1.0-alpha437

This public alpha release promotes the internally tested document-corpus and runtime-performance work to the public Docker/GitHub line.

## Highlights

- Uploaded-document questions are safer for corpus-wide checks. When a user asks whether a term or substance appears in any uploaded document, ARIA keeps the corpus scope and scans the selected document store before answering.
- Document inventory questions now load the document store inventory instead of relying on a few semantic chunk hits.
- Runtime paths are leaner for common operational tasks, with less avoidable Meta-Catalog and follow-up overhead while keeping confirmations and guardrails intact.
- Web Search handling is more robust around SearXNG timeouts and official supplemental queries.

## Fixed

- Preserved the original user prompt as a scope signal when the Meta-Catalog narrows a document question to a single promising document.
- Passed explicit document target collections through the document surface loader, recipe runtime, and Memory skill for exhaustive scans.
- Prevented unrelated document or recipe-experience records from entering source-bound document corpus answers.
- Skipped stale package-update follow-up context when the next prompt is clearly a document question.
- Kept primary Web Search results when best-effort official supplemental searches time out.

## Changed

- Runtime outcome follow-up handling was moved into a focused resolver module as part of the ongoing pipeline cleanup.
- Chat feedback learning is now queued through the Learning Worker instead of being awaited in the web request.
- Clear multi-target runtime tasks can use a bounded capability-draft fast path before the full Meta-Catalog step, while execution still goes through the existing safety and confirmation path.

## Architecture Notes

- This release does not add a deterministic router for user meaning.
- The document fixes are evidence-policy and context-contract work: the LLM-selected document surface still chooses the context, and ARIA then proves coverage before a source-bound answer can claim presence or absence.

## Upgrade Notes

- Normal managed installs should use `/updates` or `./aria-stack.sh update`.
- Fixed-tag installs can use `fischermanch/aria:0.1.0-alpha.437`.
- Normal updates should recreate only the `aria` service and keep Qdrant, SearXNG, Valkey, and persistent volumes untouched.

## Docker Images

- `fischermanch/aria:0.1.0-alpha.437`
- `fischermanch/aria:alpha`
