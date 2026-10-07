# ARIA 0.1.0-alpha.982

This is the first public ARIA release candidate since `0.1.0-alpha604`. The browser interface remains familiar—only the GUI still looks much like before—but the application underneath has been rebuilt around modular ownership, a native Tool agent and explicit safety boundaries.

> **About the version numbers:** ARIA's version numbers deliberately count development iterations. Alpha604 to Alpha982 are 378 iterations of building ARIA together with AI — the number is kept transparent on purpose and will keep counting, past 1000 if need be.

## Highlights

- **Modular core:** chat, connections, recipes, memory, documents, release handling and UI composition now have explicit module owners instead of sharing a monolithic runtime truth.
- **Self-learning memory:** repeated personal preferences can become an explicit, user-approved memory suggestion; casual statements are not silently stored.
- **Self-learning recipes:** recurring actionable sequences can become reviewable inactive recipes and supported cross-connection copies.
- **MCP agent and background jobs:** enabled MCP servers join ARIA's native Tool catalog; long jobs support pause, resume, correction, cancellation, budget extension, confirmations and Tool-image vision.
- **Memory cleanup boundary:** core memories remain, while obsolete learning collections can be removed explicitly from the Maintenance page.

## Added

- HTTP/SSE MCP servers with admin configuration, masked headers, discovery status, reconnect, per-server call timeout, trust control and confirmation previews.
- Persistent user-scoped Agent Jobs with progress, token/cost details and idempotent controls.
- Native preference and recipe recurrence, rolling Tool-image vision and conservative output honesty guards.
- An isolated strict-fake browser test harness for release validation.

## Changed

- Public installs now run `aria`, `aria-updater` and `qdrant`; provider-native web capabilities replace the old web-search sidecar.
- Configuration, connection targets, personal claims, recipes and runtime actions pass through explicit module contracts and authority checks.
- Model profiles may omit temperature; long agent tasks can use larger output/token/time budgets without tying the browser request to the full run.

## Removed

- SearXNG and Valkey from the supported fresh-install stack.
- Dead legacy-learning workers, review UI and data writers.
- Obsolete monolithic compatibility modules whose live owners moved into modules.

## Fixed

- MCP discovery, sessions, confirmation turns and failures no longer block or crash unrelated chat turns.
- Job pause/completion events are one-shot, confirmation state survives resume, and long vision jobs keep a rolling four-image live window.
- Memory capture and recurrence are more reliable across phrasing while retaining explicit user authority.

## Security

- Untrusted mutating MCP/native Tools use the confirmation kernel with frozen arguments and a one-shot ledger claim.
- Job and maintenance controls are authenticated, CSRF-protected and owner-scoped.
- Output guards refuse fabricated resource contents and action-completion claims without same-turn Tool evidence.
- MCP headers, local config, secrets, runtime data and developer state are excluded or redacted by the release hygiene gate.

## Upgrade Notes from Alpha604

1. Back up the ARIA config/data mounts or volumes and Qdrant volume before replacing the image.
2. Use the same persistent mounts with Alpha982. The automated upgrade test verifies that users, auth, connections, chat history, personal facts/preferences, memories and recipes remain readable; legacy learning collections are intentionally retained until an administrator opts in to cleanup.
3. Log in as each user and open **Memories → Maintenance → Clean up old learning collections**. Only that user's obsolete learning candidate/evaluation/event/hint/reflection collections are deleted; memories, facts, preferences, documents and recipe experience are untouched.
4. Old SearXNG and Valkey containers are not removed by ARIA. After backup and verification, remove them manually as described in `docs/release/alpha981-upgrade-note.md`.
5. Models that reject temperature may leave it empty. For long Agent/Blender jobs, try `16000` maximum output tokens and `300` seconds model timeout, then tune for model and cost; set MCP call timeout per server.
6. LiteLLM proxy compatibility no longer sends `tool_choice=none`. See `docs/setup/mcp-and-blender.md` for MCP and Blender setup.

## Known Limitations

- Vision on Tool-result images currently requires a Claude-family model.
- AI 3D generation through a Blender MCP add-on requires the user's own paid generator keys.
- The Blender MCP bridge runs on the user's machine and must be reachable from the ARIA container.
- Budgets, latency and cost depend on the chosen provider/model.
- The strict E2E harness is a development tool and not a production service.

## Images and tags

- Release title: `ARIA 0.1.0-alpha982`
- Git tag: `v0.1.0-alpha.982`
- Immutable Docker tag: `fischermanch/aria:0.1.0-alpha.982`
- Moving Docker tags after approval: `fischermanch/aria:alpha` and `fischermanch/aria:latest`

## What to test after upgrade

- both existing user logins and one normal chat turn
- Memories browser, one recall and legacy-learning cleanup
- one stored recipe preview/execution confirmation
- one configured MCP server, including a mutating Tool confirmation
- `/stats`, `/help`, `/product-info` and `/updates`
