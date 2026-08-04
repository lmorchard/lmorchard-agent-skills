---
name: session-wrapup
description: Use when a session is ending — whether work continues (handoff) or the thread is done (closure). Forks on that question; shares a spine that gathers state, promotes durable lessons, and adjudicates laurels. Triggers: wrap up, hand off, close out, done for now, bank state, prime a new session.
---

# Session Wrap-up

Wrapping a session forks on one question: **is this work continuing, or is it done?**

- **continuing** — work is unfinished, a successor session is needed → **handoff tail**.
- **done** — the thread is finished or being put down, no successor → **closure tail**.

Ask when ambiguous; the invoking phrasing usually decides it.

Both modes run the shared spine first.

## Shared spine

### 1 — Gather from commands, not memory

Run them; paste no remembered values. Name the command beside each value.
Usually: `git status -sb`, `git log --oneline <base>..HEAD`, `gh pr list`, `gh issue
list`, `gh project item-list`, the project's run/state logs, the session directory.

### 2 — Promote, before drafting

For each thing this session learned, ask: **does it outlive the resume?**

- **Yes** → write it to its evergreen home now — findings/lessons doc, design doc, an
  issue, the project's instructions file — then link it.
- **No** → it belongs in the handoff (or, in closure, it is transient and dropped).

### 3 — Adjudicate laurels

List this project's in-session nominations and let Les judge them:

    laurels.py pending --cwd "$PWD"

Present the candidates. Les prunes / edits / blesses. Move survivors into the pool and
discard the rest:

    laurels.py accept <index...>
    laurels.py drop <index...>

If there are no pending candidates, this step is silent. Never nominate on Les's behalf
here — adjudication is his; capture happened live during the session.

---

## Handoff tail (work continues)

**The handoff is a router, not a container.** It is read once, at low context, then
thrown away. Anything worth keeping was promoted in spine step 2; the handoff carries a
link to it. Write to the OS temp directory and report the path. Never the workspace,
never committed.

Draft to this contract — each part one paragraph or a short list, in this order:

1. **Purpose** — what the next session is for, in one sentence.
2. **Corrections to inherit** — claims this session made that turned out wrong. Say what
   was claimed, what is true, and how it was established.
3. **State** — a pointer plus the command that prints it. Branch, tree, PRs, board, spend.
4. **The task** — what to do next, and what done looks like.
5. **Open decisions** — each with the default if nobody decides.
6. **Opening move** — the skill, mode, or command to start with, and files to read first.
7. **Launcher prompt** — a fenced block to paste into the fresh session.

Every part follows the same rule: if it already lives somewhere durable, link it. Redact
credentials and personal data.

### Example — a Corrections entry

    - I said `gh pr checks --watch` closed the review-waiting issue. It does not: that
      issue is about waiting for a *review*, and its own body already records `--watch`
      as the CI-only survivor. Established by reading the issue body.

---

## Closure tail (work is done)

No successor to prime — so no launcher doc. Instead:

1. **Journal the outcome** — invoke the `journal-note` skill to record what this session
   accomplished (composes it; does not reimplement journaling).
2. **Confirm promotion** — durable lessons were written to their evergreen homes in spine
   step 2. Verify nothing worth keeping is left only in this conversation.
3. **Stop.** Note the session is closed.

---

## Common mistakes

| Mistake | Instead |
|---|---|
| Transcribing state into prose | Name the command that prints it |
| Omitting Corrections because nothing "big" was wrong | The small wrong claims get inherited silently |
| Growing a handoff past ~100 lines | Something wants to be an evergreen doc — promote it |
| Writing a launcher doc in closure | Closure has no successor; skip it |
| Nominating laurels for Les in adjudication | Capture is the agent's; adjudication is Les's |
| Committing a handoff | Temp directory; the durable half was promoted in step 2 |
