# ARIA UI clarity pattern

Status: mandatory design rule for new and revised authenticated ARIA pages.

## Purpose and hierarchy

Every page that needs orientation starts with one page-specific, plain-language
sentence that answers “What can I do here?”. Self-explanatory pages may omit it;
the Chat deliberately does. Never inject a generic fallback sentence. A purpose
sentence must not be copied verbatim to unrelated pages. The primary action must
be visible without scrolling at a 1280 × 800 desktop viewport. Use the shared
macros from `aria/templates/_ui_clarity.html` and the matching classes in
`aria/static/style.css`; do not imitate their appearance with unrelated card
classes.

The four blocks have deliberately different meaning and visual weight:

1. **INFO** is muted, neutral and collapsible. It uses the `ℹ` marker, contains no buttons and must never look like an action.
2. **ACTION** starts with a verb phrase, follows with one sentence describing the effect and has exactly one primary action. Optional fields or choices remain visually subordinate.
3. **SETTINGS** groups labelled fields and help text. Each section has exactly one primary save button.
4. **DANGER ZONE** is red, visibly separated and always the final section on a page. Each destructive operation states short consequences and requires typed confirmation on both client and server paths.

## Component roles and theme boundary

Component meaning is independent of the selected theme. The central role layer
in `aria/static/style.css` owns shape, padding, weight, border/fill semantics and
interaction states. A theme may set colour tokens, an optional font family and
decorative page backgrounds only; it must never restyle an individual button,
tab, field, chip or card.

| Role | Required presentation | Central tokens / classes |
| --- | --- | --- |
| Primary action | Filled accent, at most one per section and never in a repeated item | `--accent`, `--accent-strong`, `--button-text`, `.ui-primary-action` |
| Secondary action | Visible outline, subtle or transparent surface, accent text | `--border`, `--surface-pill-soft`, `.ui-secondary-action` |
| Tertiary action | Text-link affordance with underline; no button fill | `.ui-tertiary-action` |
| Danger action | Red outline for inline actions; red fill only for final danger-zone confirmation | `--ui-danger`, `--ui-danger-strong`, `.ui-danger-action`, `.danger-btn` |
| Tab / filter | Underline or segmented selection, never primary-button fill | `.ui-tab`, `[role="tab"]`, `.personal-claim-filter` |
| Chip / badge | Compact status pill, never an action | `.ui-chip`, `.meta-chip`, `.status-badge`, `.status-chip` |
| Field | One radius, border and focus ring for input, select, textarea and checkbox controls | `--ui-control-radius`, `--ui-control-border-width`, `--ui-focus-ring` |
| Info / action / settings / danger container | The semantic four-block hierarchy described above | `.ui-info-panel`, `.ui-action-card`, `.ui-settings-section`, `.ui-danger-zone` |

All controls share `--ui-control-padding-y`, `--ui-control-padding-x` and
`--ui-control-weight`. Hover, active, disabled and keyboard-focus states remain
visible in every palette. Normal text must reach WCAG AA 4.5:1 contrast;
component boundaries and large text must reach at least 3:1.

## Collapsed settings

SETTINGS sections on settings pages and other overloaded pages are collapsed by
default. Their accessible `<summary>` contains a one-line summary of the current
values or status, for example “Main model: claude-sonnet · 16000 tokens · 300 s”.
Opening the section reveals its labelled fields and its single save button.
ARIA may remember open/closed state in browser `localStorage`; unavailable or
blocked storage must degrade safely to the normal native `<details>` behavior.

ACTION cards and the page's primary action are never collapsed. INFO remains a
native collapsible `<details>` block. A SETTINGS summary is not a submit control,
and all fields and forms remain keyboard and screen-reader accessible.

## Markup examples

Import the macros once:

```jinja
{% from "_ui_clarity.html" import ui_info_panel, ui_action_card, ui_settings_section, ui_danger_zone %}
```

Information:

```jinja
{% call ui_info_panel("What is included?", "Technical details") %}
  <ul><li>Configuration</li></ul>
{% endcall %}
```

Action:

```jinja
{% call ui_action_card("Download backup", "Creates one portable configuration file.", "backup-download") %}
  <a class="button-like ui-primary-action" href="/config/backup/export">Download backup</a>
{% endcall %}
```

Settings:

```jinja
{% call ui_settings_section("Agent traces", "Choose how long diagnostic metadata is retained.", "trace-settings", "7 days · minimal · 50 MiB") %}
  <form class="config-form-grid">
    <label for="retention">Retention</label>
    <input id="retention" name="retention" type="number">
    <button class="ui-primary-action" type="submit">Save settings</button>
  </form>
{% endcall %}
```

Danger zone:

```jinja
{% call ui_danger_zone("Danger zone", "These operations remove local data.", "danger-zone") %}
  <article class="ui-danger-card">
    <h3>Reset statistics</h3>
    <ul class="ui-danger-consequences"><li>Deletes local usage history.</li></ul>
    <label for="confirm-reset">Type RESET</label>
    <input id="confirm-reset" name="confirm_text">
    <button class="danger-btn" type="submit">Reset statistics</button>
  </article>
{% endcall %}
```

## Review checklist

- The page-purpose sentence appears immediately after the page header.
- Purpose text is page-specific; Chat has none and no generic fallback is injected.
- The primary action is visible at 1280 × 800 and is unambiguous.
- INFO has no links styled as buttons and no form controls.
- Every ACTION has exactly one primary button or button-like link.
- Every SETTINGS section has exactly one save button.
- SETTINGS on settings/overloaded pages use a one-line summary and are collapsed by default.
- The DANGER ZONE is last, red, separated and uses typed confirmation.
- Labels and help are available in German and English.
- Existing authorization, CSRF, confirmation and runtime behavior remain server-authoritative.

## Page types

### Inherited page-type templates

Every authenticated page inherits exactly one of these templates; login and
session-expired are the only shell-level exceptions:

- `page_types/overview_page.html`
- `page_types/detail_page.html`
- `page_types/create_page.html`
- `page_types/settings_page.html`
- `page_types/tool_page.html`

The base owns the stable slot order: header, type-specific main content,
information, and the final danger slot. A concrete page fills `page_body` and,
when needed, the named header, statistics, action, information, or danger
blocks. It must not extend the global `base.html` directly or invent another
page shell. A connection template may select one of the five bases from its
server-authoritative `connection_page_type`; the selected base still provides
the same rendered marker and slot order.

The four blocks describe meaning inside a page. Every authenticated route also
has one primary page type. A page may contain subordinate blocks of another
kind, but it must not merge the responsibilities of two page types merely to
save a route.

### Overview / list

An overview answers “what exists?” It contains:

- one purpose sentence;
- an inventory or neutral navigation list;
- one primary `New …` action when users may create items;
- optional, collapsed INFO statistics.

It contains no item editor. Selecting an item opens its detail route. Counts,
health and last-check summaries are information, not buttons.

### Detail / edit

A detail page represents exactly one selected item. Its title is the item's
display name and it provides a back link to the overview. It contains:

- SETTINGS with only fields that remain meaningful after creation;
- one save button per independently persisted section;
- separate ACTION cards for tests, reconnection, credential rotation or other
  explicit operations;
- read-only INFO for status, fingerprints and last checks;
- a final DANGER ZONE for deleting the item.

Secret values are never returned to the browser. The page may only say
“configured / not configured” and offer a separate “set new credential”
action. Inputs used only during first-time setup never appear in edit SETTINGS.

### Create

A create page represents one bounded creation flow, as either a single form or
a short wizard. It contains only fields and one-time setup choices needed to
create the item. The item identifier is chosen here. Successful creation ends
on the new item's detail page; validation errors stay on the create page with
entered non-secret values preserved. A create page has no delete control.

### Settings

A settings page groups durable options by independent persistence boundary.
Every section contains one save button. Tests, cleanup, imports and resets are
not additional save buttons: they use ACTION or DANGER blocks. Explanatory and
diagnostic material is collapsed INFO.

### Tool / action

A tool page starts with its principal ACTION cards. Each action has one verb
title, one sentence explaining the effect and exactly one primary control.
Instructions, scope and generated statistics follow as collapsible INFO.
Destructive tools remain in a final DANGER ZONE.

## URL conventions

Collection-like resources use stable, readable path segments:

```text
/config/connections/<kind>             overview
/config/connections/<kind>/new         create
/config/connections/<kind>/<ref>       detail / edit
```

The same convention applies to other resource families where practical:
`/<family>`, `/<family>/new`, `/<family>/<id>`. Identifiers in paths are URL
encoded and resolved by the owning module; display names never become routing
authority.

Legacy URLs remain accepted during migration but do not render a second page
truth:

- `?ref=<ref>`, provider-specific variants such as `?ssh_ref=<ref>`, and
  `#manage-existing` redirect to the canonical detail route;
- create flags such as `?mode=create`, `?new=1` or `?create=1` redirect to
  `/new`;
- a legacy POST keeps the original authorization, CSRF, hidden fields and
  confirmation contract, then redirects to the canonical detail or overview;
- redirects preserve safe `return_to`, feedback and focus parameters, but
  discard obsolete fragments;
- permanent redirects are introduced only after clients and tests no longer
  depend on the legacy URL. The first rollout uses temporary redirects.

There is one route owner and one source authority for every resource. A redirect
must not read, copy or revalidate connection data itself.

Connection references are read-only in normal detail settings. The separate
rename action deliberately unlocks that field. The existing connection-save
boundary performs the profile and secret-key rename, but refuses it when a
recipe returned by the runtime recipe port still contains the old
`connection_ref`. The page asks the user to adjust that recipe first. This
fail-closed choice prevents silently broken recipes without introducing a
second recipe writer in the connection module.

## Navigation registry rules

- Every registered page has exactly one canonical parent section. That parent
  determines the section header and section navigation rendered by the page.
  A link may appear in additional menus, but those appearances are shortcuts;
  they never create another parent or change the target page's header. Help
  documents, Qdrant guidance and licenses therefore all render under the Help
  header even when Settings links to them.
- Register overview pages as navigation nodes. Create and detail routes inherit
  the overview node and do not add menu entries.
- Breadcrumbs are derived from registry parentage, never duplicated manually:
  `Settings → Connections → SSH → <item>` or `… → New connection`.
- A detail or create page always provides a visible back link to its overview.
  `return_to` may refine that destination only when it resolves to an allowed
  registered route.
- The active navigation state matches canonical paths and their create/detail
  descendants. Legacy URLs resolve to the same node before redirecting.
- Module owners contribute their own kind label, routes and breadcrumb label;
  the navigation shell must not add fixed provider IDs.
- Tool and settings pages remain children of their existing hub. Moving a
  control does not silently move authorization or route ownership.

## Migration review checklist

- Overview, create and detail responsibilities are on distinct canonical URLs.
- Old query URLs redirect without creating a second rendering path.
- All moved POST forms retain authorization, CSRF, hidden identifiers,
  confirmation scope and success/error return paths.
- Creation-only inputs are absent from edit HTML.
- Secret fields render empty on edit and disclose only configured state.
- Browser checks cover 1280 × 800 in one dark and one light theme.

## Rendered page linter

The isolated browser harness renders every authenticated route with seeded
data and passes text/DOM snapshots to
`python -m aria.modules.config_ui.page_linter`. The gate writes Markdown and
JSON reports for the current internal build. A violation blocks export unless its route/rule pair
has a reviewed reason in `tests/e2e/page_linter_allowlist.json`.

The permanent rules are:

- R1 page-type inheritance; R2 one title and a specific adjacent purpose;
  R3 no chat filler; R4 visible overview inventory and collapsed statistics;
  R5 no overview controls on details; R6 no duplicated prose, including text
  repeated between a collapsed summary and its section body;
  R7 technical IDs only in collapsed expert details; R8 real German umlauts;
  R9 no stray English UI vocabulary; R10 semantic, styled actions and valid
  internal links; R11 effective subordinate filter/tab styling; R12 at most one
  effectively primary-styled action per section, none inside repeated list
  items, and correctly styled danger actions in the final danger zone; R13 no
  rendered secrets; R14 correct count labels; R15 no raw config keys; R16 sane
  chip/button dimensions; R17 no editable item identifier on detail pages; R18
  rendered section header/navigation matches the canonical navigation parent.

The theme pass renders SSH overview, SSH detail, Personal model, LLM settings,
Backup, Logs, Help and Chat in all eleven supported themes. R19 requires a
visible outlined secondary role; R20 checks the primary-role count; R21 checks
inline and final danger semantics; R22 rejects filled tabs; R23 checks computed
WCAG AA contrast; R24 compares role geometry across themes. Any violation is an
export blocker unless the theme/path/rule tuple has a written reviewed reason.

The browser collector records computed presentation (including the effective
background/emphasis), not only element names or declared intent classes. Each
live miss becomes a failing regression fixture before the rule is changed.
