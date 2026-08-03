# laurels + session-wrapup — Design Spec

**Session:** 2026-08-03-1631-laurels-session-wrapup
**Status:** draft, pending Les's review

## Problem

Session memory has a negativity bias. Journals, handoff notes, and corrections all
accumulate what *broke* and what got *fixed* — the failures are load-bearing, so they
get written down. What worked well evaporates. `CLAUDE.md` already asks the opposite —

> Capture validated approaches and surprising successes too, not just failures and
> corrections — the signal should pull toward what works, not just away from what failed.

— but nothing *enforces* that capture or *surfaces* it later, so in practice it
underfires. A session wakes up primed by corrections and open bugs, rarely by "this
approach landed, reuse it."

Two adjacent gaps make it worse:

1. **There is no closure ritual.** `session-handoff` is rigidly forward-looking — it
   says so: *"Not for: finished work — write the outcome to its evergreen home instead."*
   Its whole contract primes a successor. When a thread is simply *done*, there is no
   skill for putting it down properly: recognizing what worked, filing durable lessons,
   and stopping.
2. **Recognition of good work has no home.** A retrospective "that worked" doesn't fit
   handoff's "router, not container" model, so it lands nowhere.

This design draws the idea of *laurels* and *closure* from Steve Yegge's "Model Welfare"
essay, but deliberately keeps the pragmatic half and drops the metaphysics. Laurels here
are **calibration, not vibes**: durable notes about work that turned out good, surfaced
back as reusable signal — not a happiness dispenser.

## Goal

1. **Laurels** — a lightweight, ungameable mechanism to capture work that landed well and
   surface a little of it, project-relevant, at the start of future sessions.
2. **session-wrapup** — evolve `session-handoff` into a single wrap-up entry point that
   forks into *handoff* (work continues) or *closure* (work is done), sharing a spine that
   includes laurel adjudication.

## Non-goals

Explicitly out of scope, and easy to add later:

- **A per-turn judging hook.** A hook can only run a dumb heuristic (which fires on every
  green test — the farmable, meaningless proxy) or shell out to an LLM every turn (real
  cost and latency for a sparse signal). Capture is done by the agent, which has judgment
  and context, not by a hook. See Component 2.
- **A subagent-judge pre-filter.** Noted as a future lever if nominations inflate; not
  built now.
- **Durable-outcome detection** (a fix that stayed fixed, a skill reused later, a commit
  that survived N days). Ungameable but needs cross-session tracking machinery. Deferred.
- **Harvesting external praise.** Yegge harvests a player base; there is no equivalent
  external signal source here.
- **Backfill** of laurels for past work, and affective "sitting with accomplishments"
  sessions. Not built.

## Architecture

Four pieces plus one refactor. The through-line: the agent *nominates* in-the-moment, Les
*adjudicates* at wrap-up, accepted laurels *surface* at the next wake.

```
  during a session
        │  agent notices a genuinely good result
        ▼
  [ capture ]  laurels.py add  ──►  ~/.claude/laurels/pending.md   (project-tagged)
        │
        ▼  at session end
  [ session-wrapup ]  mode = continuing? → handoff tail
        │             mode = done?       → closure tail
        │  shared spine: gather state · promote lessons · ADJUDICATE laurels
        ▼
  accepted  ──►  ~/.claude/laurels/laurels.md   (the durable pool)
        │
        ▼  next session start (any project)
  [ SessionStart hook ]  laurels.py show --cwd $PWD
        │  project-matched first + occasional cross-project
        ▼
  injected into context as calibration ("worked well, nothing to act on")
```

The ungameable properties hold regardless of source, and are the reason the farmable
self-nomination source is acceptable:

- A laurel grants **no work and no priority** — there is nothing to farm.
- Laurels are surfaced **retrospectively** — by the time a session sees one, there is
  nothing to act on.
- Nominations pass an **adjudication gate** (Les now; a subagent judge later if needed).

The adjudication step is itself the *witnessing* — Les looking at the work and blessing it
is the recognition, so dropping unprompted praise loses nothing.

## Component 1: Laurels store

Global store, each entry tagged with the project it came from.

```
~/.claude/laurels/
  pending.md    # nominated, awaiting adjudication (a scratchpad)
  laurels.md    # accepted pool (durable, the forever-team's record)
```

Runtime data, **not** repo content. The scripts create the directory and files on first
use. Only the schema is specified here.

### Entry format

One markdown line, human-editable and machine-parseable:

```
- [2026-08-03] (obsidian/main) egress-integrity: bidi-only check was the missing invariant
```

- `[YYYY-MM-DD]` — capture date (accept date for entries in `laurels.md`).
- `(project-slug)` — the project the work happened in; the parse key for filtering.
- free text — one line: *what worked*, and enough of *why* to make it reusable.

### Project slug

Derived from the session's `cwd`, matching the `standup-digest` convention: path relative
to `~/devel` if under it, else relative to `~`, else the basename. Worktree paths resolve
to their real repo first (`git rev-parse --path-format=absolute --git-common-dir`) so
`.worktrees/foo` tags as the parent project, not as a stray directory.

### pending vs accepted

`pending.md` is project-tagged too. Adjudication filters pending entries to the current
project, so a session that ends without wrap-up simply leaves its captures for the next
wrap-up *in that project* — captures never get adjudicated under the wrong project's eyes.

## Component 2: Capture

The agent appends a candidate to `pending.md` when — and only when — it notices a
genuinely good result mid-session. It is a cheap file append; the agent already holds the
context and the judgment, so no extra model call and no hook are involved.

**Mechanism.** `laurels/scripts/laurels.py add "<text>" --cwd "$PWD"` appends a formatted,
project-tagged line to `pending.md`. Centralizing this in the script keeps the format and
slug derivation consistent and testable. (An agent *could* append the line by hand; the
script exists so it doesn't have to get the format right each time.)

**Restraint is the whole game.** The guidance instructs the agent to nominate *sparingly*
— a genuinely satisfying fix, a non-obvious approach that paid off — not every passing
test. Over-nomination doesn't corrupt the pool (the gate stops that) but it burns Les's
adjudication attention, which is the scarce resource.

**Always-on trigger.** Capture must happen unprompted during ordinary work, so a terse
pointer lives in `~/.claude/CLAUDE.md` (Les's file — edit requires his approval), with the
full protocol and format in `laurels/SKILL.md`. The SessionStart hook (Component 4) also
carries a one-line reminder of the protocol, so a session is aware of it from wake.

## Component 3: session-wrapup skill (refactor of session-handoff)

`git mv session-handoff → session-wrapup`. The skill becomes the single wrap-up entry
point and forks on one question.

**Trigger / mode.** Invoked when a session is ending, or on "wrap up / hand off / close
out / done for now / bank state." First it determines mode:

- **continuing** — work is unfinished, a successor is needed → *handoff tail*.
- **done** — the thread is finished or being put down, no successor → *closure tail*.

Ask when ambiguous; the invoking phrasing usually decides it.

**Shared spine** (runs in both modes, in order):

1. **Gather from commands, not memory** — `git status -sb`, `git log`, `gh pr/issue list`,
   the session dir. (Preserved verbatim from `session-handoff` step 1.)
2. **Promote before drafting** — each durable lesson goes to its evergreen home now, then
   is linked. (Preserved verbatim from step 2.)
3. **Adjudicate laurels** *(new)* — `laurels.py pending --cwd "$PWD"` lists this project's
   captured candidates; the agent presents them; Les prunes / edits / blesses; survivors
   move to `laurels.md` with the accept date via `laurels.py accept`, the rest are dropped.
   Low-friction because the list is short and was captured in-the-moment. If there are no
   pending candidates, this step is silent.

**Handoff tail** (continuing) — the existing `session-handoff` contract, preserved:
Purpose / Corrections to inherit / State / The task / Open decisions / Opening move /
Launcher prompt, written to the OS temp dir, thrown away next session. The "router, not
container," "link don't restate," and Corrections discipline all carry over unchanged.

**Closure tail** (done):

1. `journal-note` the outcome (composes the existing skill; does not reimplement it).
2. Confirm durable lessons were promoted in spine step 2.
3. **No launcher doc** — there is no successor to prime.
4. Stop. Optionally note the session is closed.

The old `session-handoff` SKILL.md content is *forked*, not rewritten — the handoff tail is
the current skill nearly verbatim; the new surface is the mode fork, the adjudication spine
step, and the closure tail.

## Component 4: Surface — SessionStart hook

A `SessionStart` hook injects a little project-relevant calibration at wake.

**Command.** The hook runs `laurels.py show --cwd "$CLAUDE_PROJECT_DIR"` (falling back to
`$PWD`), configured in `~/.claude/settings.json`. Its stdout is added to session context.

**Selection** (`laurels.py show`):

- Filter `laurels.md` to entries matching the current project slug; take the most recent,
  capped at **2**.
- With a 1-in-N chance (`$RANDOM`/seedable rng, default N=3), also include **1** random
  cross-project laurel, clearly tagged `(elsewhere)`.
- If fewer than 2 project matches exist, do **not** pad with cross-project entries beyond
  the single optional one — silence is fine and saves context.
- If there are no laurels at all for the project and the cross-project roll misses, print
  nothing.

**Output shape:**

```
Laurels — past work that landed well (calibration; nothing to act on):
- [2026-08-03] (obsidian/main) egress-integrity: bidi-only check was the missing invariant
- (elsewhere) [2026-07-30] (tabs-project/pilo) SPA snapshot guard: wait on readiness, not load

To nominate: laurels.py add "<what worked + why>" — sparingly.
```

The trailing reminder is the always-on capture pointer from Component 2.

## Component 5: `laurels.py`

`laurels/scripts/laurels.py`, Python 3.11+, standard library only, matching the
`standup-digest` portability stance. Subcommands:

| Command | Behavior |
|---|---|
| `add "<text>" [--cwd PATH] [--project SLUG]` | Append a project-tagged, dated line to `pending.md`. |
| `pending [--cwd PATH \| --project SLUG \| --all]` | List pending candidates (project-filtered by default) with stable indices for adjudication. |
| `accept <index...>` | Move the named pending entries into `laurels.md` with the accept date; remove from pending. |
| `drop <index...>` | Remove the named pending entries without accepting. |
| `show [--cwd PATH]` | Emit the SessionStart surface block (Component 4 selection). |

The `show` selection logic is the main reason this is code rather than freehand file edits
— filtering, recency, and the seeded cross-project roll want to be deterministic and
tested. `add` is thin by comparison but shares the format/slug helpers.

Appends use append mode so concurrent sessions writing to `pending.md` mostly interleave
cleanly at line granularity; note the small race, don't over-engineer a lock.

## Error handling

- **Store files absent** — create the dir and files on first write; `show`/`pending` on a
  missing file print nothing and exit 0.
- **Malformed line in a store** — skip it, continue; never abort the surface on one bad
  line (the files are hand-editable).
- **`--cwd` not in a git repo / slug underivable** — fall back to the basename; still tag,
  never crash.
- **`accept`/`drop` with a stale index** — report which indices didn't resolve, apply the
  rest, exit non-zero only if none resolved.

The surface hook must never fail a session start; on any unexpected error it prints nothing
and exits 0.

## Testing

`pytest`, following the repo precedent, against a temp store (no writes to the real
`~/.claude/laurels/`):

- format round-trip: `add` then parse yields the same fields
- project-slug derivation, including worktree → parent-repo resolution
- `pending` project filtering
- `accept`/`drop` moves and stale-index handling
- `show` selection: project-match cap, the seeded cross-project roll (inject the rng),
  empty-store silence

## Deliverables

```
laurels/
  SKILL.md            # capture protocol + format, adjudication reference, surface explanation
  README.md
  scripts/
    laurels.py
    test_laurels.py
session-wrapup/        # git mv from session-handoff/
  SKILL.md             # mode fork + shared spine (incl. adjudication) + handoff & closure tails
```

Plus, outside the repo tree:

- **`~/.claude/skills/` symlinks** — remove `session-handoff`, add `session-wrapup` and
  `laurels` pointing at the repo dirs.
- **`.claude-plugin/marketplace.json`** — add `./session-wrapup` and `./laurels` to the
  skills list. (`session-handoff` was symlink-only and never listed; bring both in for
  discoverability — see Open decisions.)
- **`~/.claude/settings.json`** — a `SessionStart` hook running `laurels.py show`. Exact
  hook JSON confirmed during planning.
- **`~/.claude/CLAUDE.md`** — a terse always-on pointer to the laurels capture protocol.
  Les's file; the edit is proposed for his approval, not made unilaterally.
- **Runtime (not committed)** — `~/.claude/laurels/{pending,laurels}.md`, created on first
  use.

Must pass `make lint` (ruff) once PR #6 (`chore/make-lint-ruff`) lands.

## Open decisions, already made

- **Source: agent self-nomination, Les adjudicates.** Not unprompted praise (Les won't
  issue it); not durable-outcome detection (deferred). Farmable in principle, bounded by
  the no-work/no-priority property and the adjudication gate.
- **Scope: global store, project-tagged.** Not per-project pools (cross-project wins stay
  visible) and not a flat global pool (surfacing stays project-relevant).
- **Capture: in-session by the agent, sparingly.** Not a per-turn judging hook.
- **Adjudication: at wrap-up, inline over the session's own captures.** Not a deferred
  opt-out queue.
- **session-wrapup: a refactor of session-handoff**, one entry point forking continue/done,
  adjudication in the shared spine. Not a separate `closure` skill beside handoff.
- **Two skill dirs** (`session-wrapup`, `laurels`); branch `session-wrapup-laurels`.
- **marketplace.json: list both** new skills, resolving the current session-handoff
  inconsistency rather than propagating it.

## Future (not this session)

- **Subagent-judge pre-filter** — an independent judge scores nominations against the
  transcript before Les sees them, protecting his attention if nominations inflate.
- **Durable-outcome sources** — laurels earned by outcomes that resolve after a session
  (fix survived, skill reused), which are ungameable by the nominating session.
