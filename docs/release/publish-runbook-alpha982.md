# Publish runbook: Alpha982

Run this only after reviewing the completed Alpha982 acceptance evidence and the release diff. These commands are for the repository owner; Codex does not execute any push, release creation or registry publication.

## 1. Review and commit

```bash
cd /path/to/A.R.I.A
git status --short
git diff --check
git diff --stat
git add -A
git status --short
git diff --cached --check
git commit -m 'Release alpha982'
```

The audited `.gitignore` keeps `.codex/`, local config/secrets, runtime data, browser output and build archives out of `git add -A`. Stop if the staged tree includes any local-only artifact.

## 2. Tag and push source

```bash
git tag -a v0.1.0-alpha.982 -m 'ARIA 0.1.0-alpha982'
git remote -v
git push origin HEAD
git push origin v0.1.0-alpha.982
```

The expected origin repository is `github.com/FischermanCH/A.R.I.A.`. Verify it before pushing.

## 3. Create the GitHub release

```bash
gh release create v0.1.0-alpha.982 \
  --repo FischermanCH/A.R.I.A. \
  --title 'ARIA 0.1.0-alpha982' \
  --notes-file docs/release/github-release-v0.1.0-alpha.982.md
```

Publishing the tag and the repository `CHANGELOG.md` is what lets Alpha604's update check discover Alpha982 and show its notes.

## 4. Publish Docker tags

The existing public repository currently uses the same single-architecture image flow as the local release build; no verified prior multi-architecture manifest was found. Publish the already accepted local image without rebuilding it:

```bash
docker image inspect fischermanch/aria:0.1.0-alpha.982
docker tag fischermanch/aria:0.1.0-alpha.982 fischermanch/aria:alpha
docker tag fischermanch/aria:0.1.0-alpha.982 fischermanch/aria:latest
docker push fischermanch/aria:0.1.0-alpha.982
docker push fischermanch/aria:alpha
docker push fischermanch/aria:latest
```

If a multi-architecture publication process is introduced later, reproduce the accepted image inputs with `docker buildx` and verify every platform before moving `alpha` or `latest`; do not improvise that change during this release.

## 5. Post-publish verification

```bash
docker pull fischermanch/aria:0.1.0-alpha.982
docker image inspect fischermanch/aria:0.1.0-alpha.982
```

- On a clean host, run the documented fresh install and confirm `aria`, `aria-updater` and `qdrant` are healthy.
- On an isolated Alpha604 copy, open `/updates`; it must show `0.1.0-alpha982` and the new public changelog section.
- Confirm the GitHub release title/tag/notes and all three Docker tags resolve to the intended release.
- Log in, run a normal chat, inspect Memories, and run the optional old-learning-collection cleanup only after backup.
- Keep the previous immutable Alpha604 image available for rollback evidence; never remove user volumes as part of image rollback.
