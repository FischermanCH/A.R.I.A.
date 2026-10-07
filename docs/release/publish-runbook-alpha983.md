# Publish runbook: Alpha983

Run this only after reviewing the completed Alpha983 acceptance evidence and release diff. These commands are for the repository owner; Codex does not execute a push, release creation or registry publication without separate explicit authorization.

## 1. Review and commit

```bash
cd /path/to/A.R.I.A
git status --short
git diff --check
git diff --stat
git add -A
git status --short
git diff --cached --check
git commit -m 'Release alpha983'
```

The audited `.gitignore` keeps `.codex/`, local config/secrets, runtime data, browser output and build archives out of `git add -A`. Stop if the staged tree includes any local-only artifact.

## 2. Tag and push source

```bash
git tag -a v0.1.0-alpha.983 -m 'ARIA 0.1.0-alpha983'
git remote -v
git push origin HEAD
git push origin v0.1.0-alpha.983
```

The expected origin repository is `github.com/FischermanCH/A.R.I.A.`. Verify it before pushing.

## 3. Create the GitHub prerelease

```bash
gh release create v0.1.0-alpha.983 \
  --repo FischermanCH/A.R.I.A. \
  --title 'ARIA 0.1.0-alpha983' \
  --notes-file docs/release/github-release-v0.1.0-alpha.983.md \
  --prerelease
```

## 4. Publish Docker tags

Publish the already accepted local image without rebuilding it:

```bash
docker image inspect fischermanch/aria:0.1.0-alpha.983
docker tag fischermanch/aria:0.1.0-alpha.983 fischermanch/aria:alpha
docker tag fischermanch/aria:0.1.0-alpha.983 fischermanch/aria:latest
docker push fischermanch/aria:0.1.0-alpha.983
docker push fischermanch/aria:alpha
docker push fischermanch/aria:latest
```

Do not introduce an ad-hoc multi-architecture process during this hotfix. Verify every platform first if the publication process changes later.

## 4b. Update the Docker Hub overview page

`docker push` does not update the text on hub.docker.com. Replace the Docker Hub Overview content with `docs/release/docker-hub-overview.md`, then confirm the page shows Alpha983 and the document-inventory hotfix note.

## 5. Post-publish verification

```bash
docker pull fischermanch/aria:0.1.0-alpha.983
docker buildx imagetools inspect fischermanch/aria:0.1.0-alpha.983
docker buildx imagetools inspect fischermanch/aria:alpha
docker buildx imagetools inspect fischermanch/aria:latest
```

- Confirm GitHub `main`, tag and prerelease resolve to the reviewed Alpha983 commit.
- On a clean host, run the documented fresh install and confirm ARIA and Qdrant are healthy.
- On an isolated Alpha604 copy, confirm the upgrade preserves users, config, chat, memories, recipes and documents.
- Import at least five documents into one collection and verify an inventory question lists all five names.
- Keep immutable Alpha604 and Alpha982 images available for rollback evidence; never remove user volumes as part of image rollback.
