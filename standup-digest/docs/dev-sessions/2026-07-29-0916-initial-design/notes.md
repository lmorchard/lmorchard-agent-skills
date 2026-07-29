# Task 8 notes — end-to-end rehearsal

Run against real transcripts on 2026-07-29, window 2026-07-28 (previous workday, a
Tuesday). `gh auth status` showed an active, logged-in account, so this was a fully
verified run, not a `--no-verify` or offline rehearsal.

```
python3 standup-digest/scripts/standup_digest.py --out /tmp/task8-digest.json
```

Took about 23 seconds. Result: `stats` = `{"sessions": 10, "projects": 3,
"malformed_lines": 0, "prompt_chars_dropped": 1439, "gh_calls": 27}`, 27 commits, 27
warnings.

## The headline I produced

```
## Tue Jul 28

- pilo-evals-judge: worked on the GSM secret migration (issue #97, unconfirmed) — Secret
  Manager cutover, hardening, and cleanup PRs all merged
- pilo-evals-judge: also worked on issues #96, #99, #100, #101 (all unconfirmed) — Zoo
  eval sandbox, WebVoyagerX date fixes, and IaC/GCP drift-detection tooling all merged; a
  possible Booking evals regression was flagged for follow-up
- mozilla/pilo: SPA readiness guard and no-tool-call diagnosis shipped; PR #446 (page
  exploration tools) was refreshed but remains open, up for review
- agent-sessions: a driver-launched run resolved issue #4 unattended (PR #10 merged);
  board rename and design-doc split done by hand

Run was degraded: gh could not verify any issue ref this run (all reported unavailable);
PR verification succeeded throughout.

_full digest: ~/.claude/standup/2026-07-28.md_
```

Detail file written to `~/.claude/standup/2026-07-28.md`.

## Rule-by-rule verification

**1. No `unavailable` ref described with shipped/landed/merged/closed language.**
Every issue-kind ref in this run came back `unavailable` (see the extractor bug below —
it's not spotty network, it's 100% of issue refs, every time). The unavailable refs:
`lmorchard/agent-sessions#4` (two sessions), `Mozilla-Ocho/pilo-evals-judge#97`, `#96`,
`#100`, `#101`, `#99`. Words used for them in the headline and detail file: "worked on,"
"unconfirmed," "flagged for follow-up," "looked at / worked on only." None got shipped,
landed, merged, or closed language. Confirmed clean.

**2. `mozilla/pilo#446` trap.** Digest reports it `confirmed` + `OPEN`. Headline line:
"PR #446 (page exploration tools) was refreshed but remains open, up for review" — no
landed/merged word anywhere near it. Worth flagging: the spec and plan documents in this
same session directory both got this wrong before anyone checked — `spec.md:249` and
`plan.md:1550` both write "Refreshed + landed stale PR #446 (pilo)" as their example
headline output. That's the exact fabrication this check exists to catch, sitting in the
project's own planning history. The finished extractor and the language rules caught it;
the design docs did not.

**3. Driver-launched sessions.** One session has `launch: "driver"`
(`8b30bcad-24a6-4969-bc35-323e5fb9f495`, the unattended run against issue #4). Headline:
"a driver-launched run resolved issue #4 unattended (PR #10 merged)." Detail file: "Launch:
driver — kicked off unattended, not hand-worked." Neither uses hand-worked phrasing.

**4. `launch: "unknown"` sessions.** One real session has this value
(`e59d7cef-77ee-4929-9058-d19469674b7a`, empty prompts, no refs, in the pilo project on
`fix/spa-snapshot-readiness-guard`). Detail file: "Launch: unknown — no human prompts
recorded to judge how this session started." Not called hand-worked, not called
delegated.

**5. Null titles.** Two real sessions have `title: null`: the driver session above and
the unknown-launch session. I did not print "None" anywhere (checked with `grep -n
None ~/.claude/standup/2026-07-28.md`, zero hits). For the unknown-launch session I used
the SKILL.md-literal fallback almost verbatim: "pilo (fix/spa-snapshot-readiness-guard):
session with no recorded prompts." For the driver session, prompts were non-empty (one
entry — the driver's boilerplate task instructions), so the rule sends me to "the first
entry in prompts, trimmed to a short phrase" instead of the no-prompts fallback. See the
ambiguity section below — this didn't work cleanly.

**6. Prose-ref noise.** The task brief expected a session with five or more `prose` refs.
I checked all ten sessions; the real maximum is one prose ref per session (see the
"prompt-only" scan output). What the transcripts actually contain is five *different*
sessions on the same day, each dropping one prose-only issue reference
(`#96`, `#97`, `#99`, `#100`, `#101`) into the same repo, plus several `pr-link` refs
each. I did not enumerate all five issue numbers as five separate headline bullets — I
folded four of them (`#96`, `#99`, `#100`, `#101`) into one bullet, leaving `#97` (the
larger GSM migration) as its own bullet since it's the bigger single body of work. That
matches the rule's intent (don't over-enumerate) but not its literal trigger condition
(a single session with 5+ prose refs). See ambiguity notes below.

**7. Warnings.** 27 warnings total: 6 "gh unavailable for issue X" plus 21 "not a git
repository, commits skipped" (all pointing at `pilo-evals-judge` driver worktrees under
`.claude/worktrees/...`, which are real transient worktree directories, several already
gone by the time I checked — not a bug, just worktree churn). Warnings is non-empty, so
the headline carries: "Run was degraded: gh could not verify any issue ref this run (all
reported unavailable); PR verification succeeded throughout." One line, as the rule asks.

**8. Detail file.** Exists at `~/.claude/standup/2026-07-28.md`. `~/.claude/standup/` did
not exist before this run; created it as instructed.

## A defect I found, not a rehearsal artifact

Every single issue-kind ref verification failed this run, and it isn't an availability
problem — it's a bug in `GhVerifier.verify_ref` in `standup_digest.py`. It calls:

```
gh issue view <n> --repo <repo> --json state,title,url,mergedAt,closedAt
```

`gh issue view` does not have a `mergedAt` field (only PRs do). The command exits 1 with
`Unknown JSON field: "mergedAt"`, `_run` returns `None` on any nonzero exit, and the
verifier reports `unavailable` and logs a "gh unavailable" warning — indistinguishable
from an actual outage. I confirmed this by running the same `gh issue view` command by
hand for two of the affected issues (`pilo-evals-judge#97`, `agent-sessions#4`) with the
`mergedAt` field dropped, and both returned real state (`CLOSED` for both, as it happens)
immediately.

This means: with today's code, **no issue ref will ever verify as `confirmed`**,
regardless of network, auth, or rate limits — only PR refs can. That's a real gap between
what `verify_ref` intends (confirm both PRs and issues) and what it does (confirm PRs
only, silently downgrading every issue to `unavailable`). I did not fix it — Task 8 is
scoped to rehearsal and notes, and this is a one-line change to the field list in
`standup_digest.py`, not a renderer question. Flagging it here per the "document, don't
fix" instruction for out-of-scope findings. Full detail (repro command, exact line) is in
`~/.claude/standup/2026-07-28.md` under "Verification note."

Practical upshot for anyone using this skill before that's fixed: every accomplishment
tied only to an issue number (not a linked PR) will read as "worked on" forever, even
for issues Les closed by hand three weeks ago. The digest is still honest — it never
claims success it can't back up — but it's more conservative than it needs to be, in a
way that looks like a flaky `gh` connection rather than a code bug.

## What surprised me about the real transcript shape

- **Sessions span multiple `cwds` and many `branches`, often across worktrees.** The
  spec's fixtures (from a quick look at `spec.md`) model one cwd, one branch per session.
  Real sessions here routinely list 5-10 `cwds` and 4-8 `branches`, because Les's actual
  workflow spins up `.claude/worktrees/<slug>` subdirectories per sub-task inside a
  single Claude Code session. The digest's `session.branches` and `session.cwds` fields
  already handle this fine (they're lists), but composing a readable one-line label from
  8 branches is harder than the SKILL.md's `pilo (feat/retry-backoff): ...` example
  implies — that example assumes one branch.
- **Many of the "not a git repository" warnings are just worktree churn, not a real
  problem.** 21 of 27 warnings are `.claude/worktrees/*` paths that no longer exist as
  git repos (the worktree was cleaned up after the session ended, but the transcript
  still lists the cwd). This is correct, expected behavior — the extractor should warn
  when it can't `git -C <cwd>` — but it inflates the warning count in a way that makes
  "the run was degraded" read scarier than it is. A reader seeing "27 warnings" without
  the breakdown would reasonably assume more went wrong than actually did.
- **Prompt fragments used as fallback titles for driver sessions are boilerplate, not
  task summaries.** See the ambiguity note below — this was the single hardest thing to
  render.
- **A session can genuinely have zero prompts** (`e59d7cef`, `launch: "unknown"`). The
  spec anticipated this case abstractly; seeing it land in real data with a completely
  empty `prompts: []` and no way to know what happened beyond `cwds`/`branches` is a
  useful confirmation that the fallback rule is necessary, not just defensive.

## Where SKILL.md's own example undercuts its own rule

The Output section's worked example headline includes: "Cleared a batch of evals-judge
issues (#97, #100, #101, ...)." Taken literally, "cleared" is success language, and per
the Language rules table it's only permitted for `verification: confirmed` + `state`
`MERGED`/`CLOSED`. But issue-kind refs verify independently from any PR that happens to
mention the same number in a session — an issue ref can be (and in every session I saw,
was) `unavailable` even while a PR that appears in the same session is `confirmed
MERGED`. Nothing in the digest schema links "this merged PR closed that issue," so I
can't infer issue closure from PR merge. Under a strict reading, the pattern the example
models — a big batch of same-day issue numbers with merged sibling PRs — should read
"worked on issues #97, #100, #101, ..." not "cleared." I applied the strict reading in my
headline. If the intent was actually to allow "cleared" once a linked PR is confirmed
merged, that's a different rule than what's written and needs its own row in the
Language rules table (something like: "issue ref unavailable/unconfirmed, but a
confirmed MERGED/CLOSED PR in the same session references the same number" →
permitted phrasing). Right now the table doesn't cover that case at all, and the
worked example quietly assumes an answer.

## Ambiguity: fallback title for a null-titled, non-empty-prompt session

The "Missing titles" section gives two fallback paths: (a) prompts non-empty → use the
first prompt entry trimmed to a short phrase, with project/branch context; (b) prompts
empty → drop the prompt fragment, use project/branches alone with the literal phrase
"session with no recorded prompts."

Path (b) is unambiguous and worked cleanly (see rule 5 above). Path (a) assumes the first
prompt is a human sentence that describes intent. For driver-launched sessions, the
"first prompt" is often the driver's own boilerplate instruction block ("You are running
unattended, invoked by the agent-session board-driver. Read
.../SKILL.md... Stop at the merge gate and report the verdict...") — dozens of lines of
operating instructions, not a task description. Trimming that "to a short phrase" doesn't
produce something informative the way "fix the flaky retry test" does in the SKILL.md
example. I ended up using the literal first sentence ("running unattended, invoked by the
agent-session board-driver") in the detail file, which is technically compliant but reads
as noise — a reader learns the session was a driver run (already conveyed by the
`launch: driver` phrasing) and nothing else from the title.

Suggested fix: split path (a) into two cases based on `launch`. When `launch ==
"driver"` and the title is null, skip the first-prompt fallback entirely and build the
label from `project` + `branches` + the driver framing, the same way path (b) does for
empty prompts — e.g. "agent-sessions (fix/4-nested-skill-dir-guard): driver run, no
ai-title recorded." The first-prompt-trim fallback should stay reserved for
`launch: "human"` sessions, where the first prompt is much more likely to be an actual
task description written by Les.

## What the spec/plan got wrong

- The PR #446 example (`spec.md:249`, `plan.md:1550`) models the exact fabrication this
  task exists to catch: "Refreshed + landed stale PR #446 (pilo)" for a PR whose real
  state is `OPEN`. This was presumably a template placeholder written before the digest
  or verifier existed, but it's exactly the kind of confident-sounding wrong answer the
  whole verification layer is built to prevent, and it's sitting in the project's own
  design history unflagged until now.
- No fixture or fallback logic distinguishes `launch: "driver"` + null title from
  `launch: "human"` + null title, even though the two need different fallback strategies
  (see ambiguity note above).
- The spec's fixture sessions are simpler than reality on `cwds`/`branches` cardinality
  (see "What surprised me" above) — not wrong, just optimistic about how tidy real
  session data would be.

## Commits

Only `notes.md` is added by this task. Nothing under `standup-digest/scripts/` changed —
the `mergedAt` bug is documented, not fixed, per this task's scope.
