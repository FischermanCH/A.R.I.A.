# Isolated ARIA browser E2E gate

The production-shaped browser gate is intentionally separate from the default
pytest suite. It runs an existing ARIA image with a strict fake Anthropic
Messages API, a controllable Blender-like MCP server, and Playwright Chromium:

```bash
.venv/bin/python -m pip install -r requirements-e2e.txt
PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/ms-playwright" \
  .venv/bin/python -m playwright install chromium
PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/ms-playwright" \
  scripts/e2e/run.sh fischermanch/aria:0.1.0-alpha.975
```

The runner creates only uniquely named `aria-e2e-*` containers and an internal
Docker network. It bind-mounts generated temporary config, prompts and data;
it never mounts `config/config.yaml`, `config/secrets.env`, repository `data/`,
Docker volumes, or a Qdrant store. ARIA-under-test can reach only the two fakes.
Cleanup is registered for success, failure, SIGINT and SIGTERM. Artifacts are
written below `test-results/e2e/` and never to release-export storage.

Before every future BUILD export:

1. Build the candidate ARIA image.
2. Run `scripts/e2e/run.sh <fresh-image-tag>` before creating the TAR.
3. Record the scenario table and every strict-fake violation in the work-order's
   `verification.e2e` section.
4. Treat any failing scenario as an export blocker unless that work-order
   explicitly changes the scenario expectation.

Playwright and its browser cache are development-only. `requirements-e2e.txt`
is not copied or installed by the production Dockerfile.
