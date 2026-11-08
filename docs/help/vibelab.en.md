# Vibe:Lab

Vibe:Lab brings several projects and development tools together in one working view.

## Workspaces and projects

A **workspace** is a saved arrangement of up to four windows. It remembers which project is bound to each window, whether windows are placed side by side or stacked, and the splitter sizes. A workspace has no folder of its own. Create, rename or delete one from the top bar; layout changes are saved automatically.

A **project** holds the project folder, its coding-agent and host binding, autonomy level, and LLM or model defaults. Its work data includes uploads, agent runs and history. Manage projects from the **Vibe:Lab projects** tab at `/vibelab/projects`. Coding-agent and SSH connections themselves are configured in the connections or configuration area.

One workspace can run several projects at the same time. For example, you can keep multiple coding-agent windows open and bind each one to a different project.

## Window types

- **LLM chat** is available to everyone for a focused conversation about the bound project.
- **Coding agent** is available to administrators. It edits files and uses tools in the bound project.
- **Terminal** is available to administrators. It is a direct SSH shell to the bound project's coding host, not a standalone window for an arbitrary SSH connection.

## Why the agent uses a separate working copy

Every agent run works in its own Git worktree: an isolated copy that keeps your project folder and parallel work safe, and prevents unfinished changes from appearing unnoticed. Changes become visible only after **Apply to project**. This writes locally and does not push. Review **Changes** first. **Discard** resets the working copy.

A continuation builds on the same working copy and context; the **Continues** line makes this explicit. **New run** starts with fresh context.

## Autonomy and approvals

L0 asks for approval for every agent action that writes or executes. L1 permits tightly scoped project work, L2 works more independently, and L3 is the broadest available autonomy. ARIA's fixed safety limits always apply. Terminal commands are entered directly and are not agent actions.

When the current autonomy level does not cover an action, a pinned approval card appears at the bottom and the approval band appears at the top. Allowing or denying applies to that request only. Discord can provide additional notifications.

## Files, images and commands

**Upload file (image, document)** opens the exchange files. You can also paste images; a preview appears before sending and remains available in the message afterwards. `/cls` and `/clear` archive or clear the current window as appropriate for its type.

Vibe:Lab live-syncs running states and new answers across open devices. If the coding host is unreachable, the history remains safe: check the connection, use **Try again**, and only then start a new run. You can still review or discard changes that are already visible.

If a run hangs → **Technical details** → **Copy**. Include the copied details in a fault report; they contain the run state but no secret credentials.
