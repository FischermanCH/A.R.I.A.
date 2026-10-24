# Vibe:Lab

Vibe:Lab is ARIA's development workspace. A project can contain windows for a coding agent, a focused LLM chat and a direct terminal. **Layout** arranges one to four windows. Model and reasoning effort are selected per window.

## Why the agent uses a separate working copy

Every agent run works in its own Git worktree: an isolated copy that keeps your project folder and parallel work safe, and prevents unfinished changes from appearing unnoticed. Changes become visible only after **Apply to project**. This writes locally and does not push. Review **Changes** first. **Discard** resets the working copy.

A continuation builds on the same working copy and context; the **Continues** line makes this explicit. **New run** starts with fresh context.

## Windows and autonomy

- **Agent** edits files and uses tools. L0 asks for approval for every writing or executing action. L1 permits tightly scoped project work, L2 works more independently, and L3 is the broadest available autonomy. ARIA's fixed safety limits always apply.
- **LLM chat** is a focused project conversation without independent file changes.
- **Terminal** runs what you type directly; these commands are not agent actions.

When the current autonomy level does not cover an action, a pinned approval card appears at the bottom and the approval band appears at the top. Allowing or denying applies to that request only. Discord can provide additional notifications.

## Files, images and commands

**Upload file (image, document)** opens the exchange files. You can also paste images; a preview appears before sending and remains available in the message afterwards. `/cls` and `/clear` archive or clear the current window as appropriate for its type.

Vibe:Lab live-syncs running states and new answers across open devices. If the coding host is unreachable, the history remains safe: check the connection, use **Try again**, and only then start a new run. You can still review or discard changes that are already visible.

If a run hangs → **Technical details** → **Copy**. Include the copied details in a fault report; they contain the run state but no secret credentials.
