# ARIA 0.1.0-alpha1006

Alpha1006 is a substantial public alpha candidate built from the internal work since Alpha983.

## Highlights

- A private, user-scoped Activity Journal records compact summaries of completed Tool activity and Agent Jobs without raw Tool output, document text, images, prompts or secrets.
- `/stats` restores the public Alpha983 owner checks and model roles in the newer layout. Group headers and concrete linked problems render immediately; status tiles load only when a collapsed group is opened, and bounded Qdrant checks never delay the first page response.
- Background Agent Jobs deliver completion notices durably, render safe Markdown and remain controllable from chat and the Jobs page.
- iPhone Safari uses normal page scrolling, a non-wrapping one-row header and a safe-area-aware sticky composer in portrait and landscape.
- The Activity Journal has explicit period choices and shares one configurable display time zone with Jobs, statistics, chat timestamps and its native read Tool.
- Shared page templates, a bilingual page linter and eleven-theme computed-style checks make the browser UI more consistent.
- MCP discovery and recovery no longer consume the first-turn budget; persistent recipe catalogs use the same non-blocking startup principle.
- Configuration backups are secret-free by default, with an explicit passphrase-encrypted credentials option.
- A deterministic, isolated demo provides public-safe screenshots and a reproducible product tour without a model provider.

The complete, honest rollup is in `docs/release/public-release-summary-alpha1006.md`.

## Upgrade

Back up ARIA configuration and keep the existing data/config mounts and Qdrant volume. Then replace only the ARIA image with `fischermanch/aria:0.1.0-alpha.1006`. The normal update path does not delete memories, documents, notes, recipes, users or volumes. Existing legacy context rollups are preserved until the user explicitly handles them in the Activity Journal.

This remains alpha software for trusted LAN/VPN or homelab use. Direct public internet exposure and production team/RBAC use are outside the current product boundary.
