# Navigation, Menus, and Extended View

Updated: 2026-07-09

## Purpose

ARIA's navigation is split into areas so daily work and technical maintenance do not compete in the same menu. The header, account menu, and section navigation follow the same structure.

## Header

The header shows the main navigation for the area you are currently using. Subpages should not suddenly switch to another main menu:

- Settings subpages keep Settings navigation.
- Admin subpages keep Admin navigation.
- Memory subpages keep Memory navigation.
- Recipes and Connections keep their own area context.

Detail functions live as cards or page content, not as changing special header menus.

## Account Menu

The account menu is the entry point for the large areas:

- Chat
- Memory
- Notes
- Settings
- Statistics
- Updates, when relevant
- Help

When **Extended view** is active, **Settings** becomes an expandable account-menu entry with **Settings** and **Admin**. This keeps Admin reachable without overloading daily navigation.

## Extended View

**Extended view** replaces the older Admin Mode wording in the normal UI. It makes technical areas visible, but it does not change your role by itself.

Important:

- Only authorized admins can use admin functions.
- When Extended view is off, normal work areas remain visible.
- Technical system pages are hidden so daily use stays quieter.
- You can toggle the option under `/config/admin-mode`.

## Settings

`/config` is the calm Settings hub. It contains daily and operational options such as:

- LLM and embeddings
- appearance and language
- connections and recipes
- updates
- logs and backup
- access and security

Many technical details only appear when Extended view is active.

## Admin

`/config/admin` is the Admin overview. Admin is split into real groups:

- **System configuration**
- **Recipes & Learning**
- **Memory**
- **Operations**

Each group has its own page. Clicking an Admin group visibly changes the content instead of jumping to an anchor inside one long page.

## Memory

Memory is its own area:

- `/memories` shows the graphical Memory browser.
- `/memories/import` imports documents and memory data.
- `/memories/create` captures manual memories.
- `/memories/auto-memory` explains Auto-memory and learning.
- `/memories/maintenance` collects technical maintenance.

Memory maintenance is no longer duplicated as a global Admin shortcut; it stays in the Memory context.

## Recipes

Recipes are structured as their own area:

- `/recipes` is the Recipes hub.
- `/recipes/mine` is the worklist for saved recipes.
- `/recipes/start` and `/recipes/templates` help with creation and import.
- `/recipes/learned` is the normal Learned Recipes view.
- `/recipes/learned/maintenance` is the Admin maintenance page for learned recipes.

System recipes and maintenance functions intentionally stay in the Admin context.

## Connections

Connections are reachable through Settings, but keep their own area context. The overview is intentionally not a live status dashboard; operational signals belong in Stats or dedicated status pages.

## Mobile and iOS

On narrow viewports, menus, tabs, and help links may wrap. The account entry remains the central path when header navigation cannot show everything at once.

## Useful Update Tests

- open the account menu with and without Extended view
- check `/config`, `/config/admin`, `/config/admin/memory`, and `/config/admin/operations`
- check `/memories`, `/memories/import`, `/memories/auto-memory`, and `/memories/maintenance`
- check `/recipes`, `/recipes/mine`, `/recipes/learned`, and `/recipes/learned/maintenance`
- check the same paths on iPhone width
