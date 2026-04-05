# GitHub Operations

This file describes the intended GitHub-side workflow for ARIA.

## Current State

Already in place:

- Git tags for public alpha releases
- `CHANGELOG.md` as the source of release notes
- Docker Hub image tags
- issue templates under `.github/ISSUE_TEMPLATE/`
- seed wiki pages under `docs/wiki/`

## Issues

Recommended issue types:

- `Bug`
- `Feature`
- `Chore / release / docs`

Recommended labels:

- `bug`
- `enhancement`
- `chore`
- `docs`
- `release`
- `ui`
- `memory`
- `skills`
- `connections`
- `rss`
- `security`
- `routing`

## Releases

Public release flow:

1. finish internal testing
2. freeze release version
3. move release notes from `Unreleased` into a concrete tag section in `CHANGELOG.md`
4. create git tag
5. push git tag
6. push Docker tags
7. create GitHub Release object from the matching `CHANGELOG.md` section

## Wiki

The files in `docs/wiki/` are the source draft for a future GitHub Wiki.

Important:

- GitHub Wiki is a separate repository on the GitHub side
- repo docs and GitHub Wiki should not drift apart without intent
- for now, `docs/wiki/` is the canonical editable source

## Token Guidance

For GitHub Release creation and label management, the preferred approach is:

- Fine-grained personal access token
- repository scope limited to `A.R.I.A.`
- permissions:
  - `Contents: Read and write`
  - `Issues: Read and write`

If we later decide to automate pushing the real GitHub Wiki repository too, we can either:

- use a separate SSH key for the wiki repo, or
- use a classic PAT with `repo` scope

The second option is broader, so it should only be used if we actually automate wiki push.

