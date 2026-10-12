# Publish runbook: Alpha1007

This runbook is not authorization to publish. Execute it only after a separate explicit release grant.

## Preconditions

- Acceptance verification is passed and the reviewed image digest matches the exported TAR.
- Full suite, module validator, import smoke, page/theme linter, E2E, demo safety, OCR hygiene, fresh install and both upgrade tests are green.
- Public metadata is changed only in the separate publication step.

## Git and GitHub

```bash
git status --short
git add --all
git commit -m 'Release alpha1007'
git tag -a v0.1.0-alpha.1007 -m 'ARIA 0.1.0-alpha1007'
git push origin main
git push origin v0.1.0-alpha.1007
gh release create v0.1.0-alpha.1007 --title 'ARIA 0.1.0-alpha1007' --notes-file docs/release/github-release-v0.1.0-alpha.1007.md
```

Never force-push or move an existing release tag.

## Docker Hub

Push the reviewed image without rebuilding:

```bash
docker push fischermanch/aria:0.1.0-alpha.1007
docker tag fischermanch/aria:0.1.0-alpha.1007 fischermanch/aria:alpha
docker tag fischermanch/aria:0.1.0-alpha.1007 fischermanch/aria:latest
docker push fischermanch/aria:alpha
docker push fischermanch/aria:latest
```

Verify that all three remote tags resolve to the same digest and that the GitHub release is visible.
