# Task 8 notes — end-to-end rehearsal

Run against real transcripts on 2026-07-29, window 2026-07-28 (previous workday, a
Tuesday). `gh auth status` showed an active, logged-in account, so this was a fully
verified run, not a `--no-verify` or offline rehearsal.

This session ran in two passes: a first rehearsal that surfaced a real bug in the
extractor, and a second rehearsal after the bug was fixed. Both are recorded below,
because the difference between them is itself useful evidence about what the
verification layer is for.

## Pass 1: first run, before the fix

```
python3 standup-digest/scripts/standup_digest.py --out /tmp/task8-digest.json
```

Took about 23 seconds. Result: `stats` = `{"sessions": 10, "projects": 3,
"malformed_lines": 0, "prompt_chars_dropped": 1439, "gh_calls": 27}`, 27 commits, 27
warnings, and — this turned out to be the interesting part — every single issue-kind
ref came back `verification: "unavailable"`.

Headline I produced from that first pass:

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

### The bug

`GhVerifier.verify_ref` in `standup_digest.py` called, for every ref regardless of kind:

```
gh <noun> view <n> --repo <repo> --json state,title,url,mergedAt,closedAt
```

`gh issue view` has no `mergedAt` field — only PRs do:

```
$ gh issue view 97 --repo Mozilla-Ocho/pilo-evals-judge --json state,title,url,mergedAt,closedAt
Unknown JSON field: "mergedAt"

$ gh issue view 97 --repo Mozilla-Ocho/pilo-evals-judge --json state,title,url,closedAt
{"closedAt":"2026-07-28T23:59:30Z","state":"CLOSED","title":"Move cloud-eval secret management off the laptop...","url":"..."}
```

The command exits 1, `_run()` treats any nonzero exit as `None`, and the verifier logs a
"gh unavailable" warning and reports `unavailable` — indistinguishable from a real
network or auth problem. It wasn't one: `gh auth status` was active throughout, and PR
lookups against the same repos succeeded in the same run. Under the old code, **no issue
ref could ever verify as `confirmed`**, regardless of network, auth, or rate limits —
only PR refs could. Issue #97 above is genuinely `CLOSED`; the digest could only ever
have said "worked on" for it.

This traced back to the plan: it specified one `--json` field list for both nouns, and
`gh` simply rejects that list for issues. Not a judgment call — `gh` was right and the
plan was wrong.

## The fix

Applied directly (the coordinator judged this a hole in the tool's central promise, not
a deferred item):

**`standup_digest.py`** — `GhVerifier.verify_ref` now sends per-noun field lists:

```python
noun = "pr" if ref.kind == "pr" else "issue"
# Issues have no mergedAt field; gh rejects the PR field list for them.
fields = (
    "state,title,url,mergedAt,closedAt"
    if noun == "pr"
    else "state,title,url,closedAt"
)
```

`merged_at` stays in the returned dict shape for both kinds (issues just get `None` from
`data.get("mergedAt")`, since the key is absent from the response); `_UNVERIFIED` is
unchanged. The renderer-facing digest shape doesn't move.

**`test_standup_digest.py`** — added two tests:

- `test_gh_verifier_requests_pr_and_issue_field_lists_separately` — calls `verify_ref`
  once for a PR ref and once for an issue ref against a patched `sd._run`, captures the
  actual `cmd` list passed each time, and asserts `mergedAt` is present in the PR
  command's `--json` argument and absent from the issue command's — plus an explicit
  `issue_fields != pr_fields` assertion so the test fails if the two lists get merged
  back into one.
- `test_gh_verifier_confirms_closed_issue` — feeds a `state: "CLOSED"` issue payload
  (no `mergedAt` key, matching what `gh` actually returns) through `verify_ref` and
  asserts `verification == "confirmed"`, `state == "CLOSED"`, and `merged_at is None`.

```
$ make test
uv run --with pytest pytest standup-digest/scripts -q
............................................................             [100%]
60 passed in 0.09s
```

60 passed (58 original + 2 new). No existing test needed changing — the fix only
narrows what field list gets sent per noun; the response-parsing and caching code paths
were already noun-agnostic.

**`SKILL.md`** — the worked example under Output previously read "Refreshed + landed
stale PR #446 (pilo)" / "Cleared a batch of evals-judge issues (#97, #100, #101, ...)"
with no way for a reader to see why either phrasing was licensed. Rewrote it to use
`mozilla/pilo#446`'s real state (confirmed OPEN, the actual trap this project is built
around) and to annotate each bullet with the ref state driving its phrasing:

```
- Refreshed PR #446 (pilo), still open, up for review     (confirmed, OPEN — not landed)
- Cleared a batch of evals-judge issues (#97, #100, #101, ...)   (confirmed, CLOSED)
- Zoo eval sandbox stood up, CDP flakiness still blocking clean runs   (no ref — from commits/prompts)
```

Added a paragraph directly under the example naming #446 as the trap and warning that
"cleared" for a batch is only honest when every number in it is independently
`confirmed`/`CLOSED` — one confirmed closure must not license the whole batch. `spec.md`
and `plan.md` were left untouched; they're dated session artifacts, and this file is
where their PR #446 mistake gets recorded (see "What the spec/plan got wrong" below).

## Pass 2: re-run after the fix

```
python3 standup-digest/scripts/standup_digest.py --out /tmp/task8-digest-v2.json
```

Same window, same 10 sessions, same 27 commits, same 27 `gh_calls`. What changed:
warnings dropped from 27 to 21 (the 6 "gh unavailable for issue #N" warnings are gone;
the 21 "not a git repository, commits skipped" worktree warnings remain, unrelated to
this fix), and every issue ref now verifies:

```
lmorchard/agent-sessions      #4    confirmed CLOSED
Mozilla-Ocho/pilo-evals-judge #97   confirmed CLOSED
Mozilla-Ocho/pilo-evals-judge #96   confirmed CLOSED
Mozilla-Ocho/pilo-evals-judge #100  confirmed OPEN
Mozilla-Ocho/pilo-evals-judge #101  confirmed CLOSED
Mozilla-Ocho/pilo-evals-judge #99   confirmed CLOSED
```

Issue #100 turned out to be genuinely still open (a Helm-usage survey question, not a
piece of shippable work) — a good reminder that "confirmed" doesn't mean "confirmed
done," it means the state is known. #96 resolved a small mystery from pass 1: the
prose-only mention was "please file a pilo-evals-judge issue to fix the Booking evals,"
and I couldn't previously tell whether that filing had succeeded. It had — #96 exists,
titled "WebVoyagerX Booking tasks fail on stale hardcoded dates," and is now closed.

Headline from the second pass:

```
## Tue Jul 28

- pilo-evals-judge: closed the GSM secret migration (issue #97) — Secret Manager
  cutover, hardening, and cleanup PRs all merged
- pilo-evals-judge: closed three more issues — Booking evals date drift (#96),
  WebVoyagerX date/criteria robustness (#99), and IaC coverage/GCP drift detection
  (#101) — each with matching PRs merged; issue #100 (a Helm survey) is still open
- mozilla/pilo: SPA readiness guard and no-tool-call diagnosis shipped; PR #446 (page
  exploration tools) was refreshed but remains open, up for review
- agent-sessions: a driver-launched run closed issue #4 unattended (PR #10 merged);
  board rename and design-doc split done by hand

Run was degraded: commit history was unavailable for several cleaned-up
pilo-evals-judge worktree paths; all PR and issue ref verification succeeded.

_full digest: ~/.claude/standup/2026-07-28.md_
```

Detail file rewritten at `~/.claude/standup/2026-07-28.md` to match (grepped for
"None" — zero hits).

## Rule-by-rule verification (against the pass-2, post-fix run)

**1. No `unavailable` ref described with shipped/landed/merged/closed language.** After
the fix there are no `unavailable` refs left in this dataset at all — every PR and issue
ref verified. That's itself worth stating plainly: this rule had nothing left to catch
in pass 2, because the thing that used to trigger it (the `mergedAt` bug) is gone. Pass 1
above is the record of the rule actually firing correctly against real `unavailable`
data before the fix.

**2. `mozilla/pilo#446` trap.** Unaffected by the fix (it's a PR, not an issue — the bug
never touched PR verification). Still `confirmed` + `OPEN`. Headline: "PR #446 (page
exploration tools) was refreshed but remains open, up for review" — no landed/merged
word near it. `spec.md:249` and `plan.md:1550` both write "Refreshed + landed stale PR
#446 (pilo)" as their example headline output — the exact fabrication this check exists
to catch, sitting in the project's own planning history, written before anyone checked
the real PR state.

**3. Driver-launched sessions.** One session has `launch: "driver"`
(`8b30bcad-24a6-4969-bc35-323e5fb9f495`, the unattended run against issue #4). Headline:
"a driver-launched run closed issue #4 unattended (PR #10 merged)." Detail file:
"Launch: driver — kicked off unattended, not hand-worked." Neither uses hand-worked
phrasing.

**4. `launch: "unknown"` sessions.** One real session has this value
(`e59d7cef-77ee-4929-9058-d19469674b7a`, empty prompts, no refs, in the pilo project on
`fix/spa-snapshot-readiness-guard`). Detail file: "Launch: unknown — no human prompts
recorded to judge how this session started." Not called hand-worked, not called
delegated.

**5. Null titles.** Two real sessions have `title: null`: the driver session above and
the unknown-launch session. `grep -n None ~/.claude/standup/2026-07-28.md` — zero hits,
both passes. For the unknown-launch session I used the SKILL.md-literal fallback almost
verbatim: "pilo (fix/spa-snapshot-readiness-guard): session with no recorded prompts."
For the driver session I used "agent-sessions (main, fix/4-nested-skill-dir-guard):
driver run, no ai-title recorded" — see the ambiguity note below for why I moved off the
literal first-prompt-trim fallback for this one.

**6. Prose-ref noise.** The task brief expected a session with five or more `prose`
refs. Real data never does this — the max observed in any single session is one prose
ref. What actually happens is five *different* sessions on the same day, each carrying
one prose-only issue reference (`#96`, `#97`, `#99`, `#100`, `#101`) into the same repo,
plus several `pr-link` refs each. I folded three of the now-confirmed-closed ones
(`#96`, `#99`, `#101`) into one headline bullet, gave `#97` (the larger GSM migration)
its own bullet as the bigger single body of work, and called out `#100` separately since
it's still open — not the same treatment as the closed ones. This matches the rule's
intent (don't over-enumerate) but not its literal trigger condition (a single session
with 5+ prose refs).

**7. Warnings.** Pass 2: 21 warnings, all "not a git repository, commits skipped" for
`pilo-evals-judge` driver worktrees under `.claude/worktrees/...` that were cleaned up
after their sessions ended — real, expected worktree churn, not a bug. Non-empty, so the
headline carries: "Run was degraded: commit history was unavailable for several
cleaned-up pilo-evals-judge worktree paths; all PR and issue ref verification
succeeded." That last clause matters — a reader shouldn't have to guess whether "degraded"
means the whole digest is untrustworthy or just that some commit history is thin.

**8. Detail file.** Exists at `~/.claude/standup/2026-07-28.md`, rewritten for pass 2.

All 8 checks pass against the post-fix run.

## What surprised me about the real transcript shape

- **Sessions span multiple `cwds` and many `branches`, often across worktrees.** The
  spec's fixtures model one cwd, one branch per session. Real sessions here routinely
  list 5-10 `cwds` and 4-8 `branches`, because Les's actual workflow spins up
  `.claude/worktrees/<slug>` subdirectories per sub-task inside a single Claude Code
  session. The digest's `session.branches` and `session.cwds` fields already handle this
  fine (they're lists), but composing a readable one-line label from 8 branches is
  harder than the SKILL.md's `pilo (feat/retry-backoff): ...` example implies — that
  example assumes one branch.
- **Many of the "not a git repository" warnings are just worktree churn, not a real
  problem.** In pass 1, 21 of 27 warnings were this; in pass 2, they're 21 of 21. This is
  correct, expected behavior — the extractor should warn when it can't `git -C <cwd>` —
  but a bare warning count without a breakdown makes "the run was degraded" read scarier
  than it is.
- **Prompt fragments used as fallback titles for driver sessions are boilerplate, not
  task summaries.** See the ambiguity note below.
- **A session can genuinely have zero prompts** (`e59d7cef`, `launch: "unknown"`). The
  spec anticipated this case abstractly; seeing it land in real data with a completely
  empty `prompts: []` and no way to know what happened beyond `cwds`/`branches` is a
  useful confirmation that the fallback rule is necessary, not just defensive.
- **A confirmed ref isn't automatically good news.** Issue #100 came back `confirmed` +
  `OPEN` — a still-open survey question, not a landed piece of work. Fixing the
  verification bug didn't make everything read as "done"; it just made the true state
  visible either way. That's the point of the split between "the extractor decides
  what's true" and "the renderer decides what's interesting," working as intended.

## Ambiguity: fallback title for a null-titled, non-empty-prompt session

The "Missing titles" section gives two fallback paths: (a) prompts non-empty → use the
first prompt entry trimmed to a short phrase, with project/branch context; (b) prompts
empty → drop the prompt fragment, use project/branches alone with the literal phrase
"session with no recorded prompts."

Path (b) is unambiguous and worked cleanly (see rule 5 above). Path (a) assumes the
first prompt is a human sentence that describes intent. For driver-launched sessions,
the "first prompt" is often the driver's own boilerplate instruction block ("You are
running unattended, invoked by the agent-session board-driver. Read .../SKILL.md ...
Stop at the merge gate and report the verdict...") — dozens of lines of operating
instructions, not a task description. Trimming that "to a short phrase" doesn't produce
something informative the way "fix the flaky retry test" does in the SKILL.md example.

Suggested fix: split path (a) into two cases based on `launch`. When `launch ==
"driver"` and the title is null, skip the first-prompt fallback entirely and build the
label from `project` + `branches` + the driver framing, the same way path (b) does for
empty prompts — e.g. "agent-sessions (fix/4-nested-skill-dir-guard): driver run, no
ai-title recorded." That's what I used in the end for this session's detail file. The
first-prompt-trim fallback should stay reserved for `launch: "human"` sessions, where
the first prompt is much more likely to be an actual task description written by Les.

## What the spec/plan got wrong

- The PR #446 example (`spec.md:249`, `plan.md:1550`) models the exact fabrication this
  task exists to catch: "Refreshed + landed stale PR #446 (pilo)" for a PR whose real
  state is `OPEN`. This was presumably a template placeholder written before the digest
  or verifier existed, but it's exactly the kind of confident-sounding wrong answer the
  whole verification layer is built to prevent, and it sat in the project's own design
  history unflagged until this task. `spec.md` and `plan.md` are left as-is (dated
  session artifacts); this is the record that they were wrong.
- The plan specified one `--json` field list for both `gh pr view` and `gh issue view`.
  `gh` rejects `mergedAt` for issues outright — this wasn't a judgment call or an edge
  case, the plan was simply incompatible with the tool it was driving. Fixed in this
  task (see "The fix" above).
- No fixture or fallback logic distinguished `launch: "driver"` + null title from
  `launch: "human"` + null title, even though the two need different fallback strategies
  (see ambiguity note above). Not fixed in code this task — SKILL.md is the renderer's
  contract, and I addressed it there by using the driver-appropriate framing directly;
  the underlying fallback rule in SKILL.md still needs the wording change proposed
  above.
- The spec's fixture sessions are simpler than reality on `cwds`/`branches` cardinality
  (see "What surprised me" above) — not wrong, just optimistic about how tidy real
  session data would be.

## Commits

This task's commits:

- `standup_digest.py`: per-noun `--json` field lists in `GhVerifier.verify_ref`, so
  issue refs can verify as `confirmed` instead of always downgrading to `unavailable`.
- `test_standup_digest.py`: two new tests covering the fix (see "The fix" above).
- `SKILL.md`: rewrote the Output section's worked example to use PR #446's real `OPEN`
  state and to annotate each bullet with the ref state licensing its phrasing.
- `notes.md` (this file).

`make test` — 60 passed, 0 failed, after the fix.
