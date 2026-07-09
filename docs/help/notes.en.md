# Notes

Updated: 2026-07-09

## Purpose

Notes are ARIA's Markdown workspace. They are intentionally separate from Memory: a note is an editable document, while Memory stores semantic facts, preferences, document chunks, and learned experience.

## Working with Notes

Under `/notes`, you can:

- create new Markdown notes
- edit existing notes
- organize notes in folders
- move notes from cards or the editor into another folder
- use the dense list view for quick scanning
- select multiple notes and move them together

When a note is moved, ARIA updates the Markdown path and frontmatter. If notes are indexed, the Notes index is updated accordingly.

## Inbox and folders

Inbox is the neutral starting point for unorganized notes. Existing folders are offered in the editor and move controls so you can organize notes without editing paths by hand.

## Search and index

Notes can be indexed for search and context. The index is derived data. When you delete a note, the related index entry should also be removed.

## Difference from Memory

Use Notes for:

- working notes
- drafts
- meeting or project text
- longer Markdown content

Use Memory for:

- stable facts
- preferences
- document RAG
- Experience Memory and learned patterns

## Useful update tests

- create a note in an existing folder
- move a note from a card into another folder
- move a note from the editor
- select and move multiple notes in list view
- check search/index behaviour afterwards
