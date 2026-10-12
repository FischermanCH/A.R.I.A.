# Publish runbook: Alpha1006

Run this only after the Alpha1006 acceptance is fully green, the owner has reviewed the diff, and the owner grants a separate publication authorization. Do not rebuild the accepted image during publication.

## 1. Audit and commit the reviewed tree

```bash
cd /path/to/A.R.I.A
git status --short
python3 scripts/release/check_public_candidate.py --ocr
git diff --check
git add -A
git diff --cached --check
git commit -m 'Release alpha1006'
```

Confirm that `.codex/`, runtime data, local config/secrets, browser output and build archives are absent from the staged tree.

## 2. Tag and push source

```bash
git tag -a v0.1.0-alpha.1006 -m 'ARIA 0.1.0-alpha1006'
git push origin main
git push origin v0.1.0-alpha.1006
```

Do not move `v0.1.0-alpha.983` and never force-push.

## 3. Publish the accepted image

```bash
docker image inspect fischermanch/aria:0.1.0-alpha.1006
docker tag fischermanch/aria:0.1.0-alpha.1006 fischermanch/aria:alpha
docker tag fischermanch/aria:0.1.0-alpha.1006 fischermanch/aria:latest
docker push fischermanch/aria:0.1.0-alpha.1006
docker push fischermanch/aria:alpha
docker push fischermanch/aria:latest
```

Verify that all three remote tags resolve to the same digest.

## 4. Create the GitHub prerelease

```bash
gh release create v0.1.0-alpha.1006 \
  --repo FischermanCH/A.R.I.A. \
  --title 'ARIA 0.1.0-alpha1006' \
  --notes-file docs/release/github-release-v0.1.0-alpha.1006.md \
  --prerelease
```

## 5. Update public text

- Replace the Docker Hub Overview with `docs/release/docker-hub-overview.md`.
- Publish or refresh the website release entry from the tagged changelog workflow.
- Verify README screenshot links on GitHub and the release links on the project website.

## 6. Post-publication checks

- Confirm `origin/main`, the immutable tag and GitHub prerelease point to the reviewed commit.
- Pull and inspect `0.1.0-alpha.1006`, `alpha` and `latest`; their digests must match.
- Repeat a clean install and the documented Alpha604 and Alpha983 upgrade smokes on disposable copies.
- Keep the immutable Alpha604, Alpha982 and Alpha983 rollback artifacts.
