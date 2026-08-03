---
name: session-handoff
description: Use when work must continue in a fresh session — context is degrading, the token budget is tight, a long session is ending, or the user asks to hand off, bank state, wrap up, or prime a new session.
---

# Session Handoff

## Overview

**The handoff is a router, not a container.** It is read once, at low context, then thrown away. Anything worth keeping belongs in an evergreen document *before* the handoff is written; the handoff carries a link to it.

Write to the OS temp directory and report the path. Never the workspace, never committed.

## When to use

A session is ending with work unfinished; context is degrading and you are re-deriving what you already established; or the user says hand off, bank state, wrap up, prime a new session.

**Not for:** finished work — write the outcome to its evergreen home instead. Or a session short enough that the next one can re-read the diff.

## Step 1 — Gather from commands, not memory

Run them; paste no remembered values. Name the command beside each value.

Usually: `git status -sb`, `git log --oneline <base>..HEAD`, `gh pr list`, `gh issue list`, `gh project item-list`, the project's run/state logs, the session directory.

## Step 2 — Promote, before drafting

For each thing this session learned, ask: **does it outlive the resume?**

- **Yes** → write it to its evergreen home now — findings/lessons doc, design doc, an issue, the project's instructions file — then link it.
- **No** → it belongs in the handoff.

This step is what keeps the document short. A handoff that has nowhere to put a durable lesson grows until it contains everything.

## Step 3 — Draft to this contract

The document IS these parts, in this order. Each is one paragraph or a short list.

1. **Purpose** — what the next session is for, in one sentence, from the invoking argument.
2. **Corrections to inherit** — claims this session made that turned out wrong. Draft these yourself; you are the session that made them. Say what was claimed, what is true, and how it was established.
3. **State** — a pointer plus the command that prints it. Branch, tree, PRs, board, spend.
4. **The task** — what to do next, and what done looks like.
5. **Open decisions** — each with the default if nobody decides.
6. **Opening move** — the skill, mode, or command to start with, and the files to read first.
7. **Launcher prompt** — a fenced block to paste into the fresh session.

**Every part follows the same rule: if it already lives somewhere durable, link it.** Promoted lessons, standing rules, an open decision already recorded in a design doc — a pointer, never a restatement. Only what exists nowhere else gets written out here.

Redact credentials and personal data.

## Example — a Corrections entry

```markdown
- I said `gh pr checks --watch` closed the review-waiting issue. It does not: that
  issue is about waiting for a *review*, and its own body already records `--watch`
  as the CI-only survivor. Established by reading the issue body.
```

Specific claim, correction, and how it was checked — so the next session can trust or re-verify it.

## Common mistakes

| Mistake | Instead |
|---|---|
| Transcribing state into prose | Name the command that prints it |
| Omitting Corrections because nothing "big" was wrong | The small wrong claims are the ones that get inherited silently |
| Growing past ~100 lines | Something in it wants to be an evergreen doc — promote it |
| Absorbing planning for later work | The Purpose argument bounds the document |
| Committing it | Temp directory; the durable half was promoted in step 2 |
