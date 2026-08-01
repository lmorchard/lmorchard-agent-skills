# Notes — digest fuller capture

## Phase 1 — harvest cd/git -C dirs (done)

- `harvest_dirs()` pulls absolute `cd`/`git -C` targets from Bash tool-use; fed into the
  `build_digest` commit scan after the session-cwd pass, deduped by `seen_paths`/`seen_shas`.
- `commits(..., warn_non_repo=False)` for harvested dirs so a stray `cd` into a non-repo
  doesn't mark the run degraded.
- **Finding (plan `[!]`):** the spec's motivating case assumed `~/devel/zoo-service` had no
  GitHub remote. By the time Phase 1 ran, it had gained a `Mozilla-Ocho/zoo-service`
  origin, so live data resolves it to that repo, not `repo: null`. Not a failure — the
  remote-less path is still exercised by `test_build_digest_counts_harvested_remoteless_commit`.
  Real-world win confirmed anyway: **61** zoo-service commits now counted for 2026-07-29
  (was 0), with zero new "not a git repository" warnings.

## Phase 2 — assistant-prose signal (done)

- `extract_assistant_notes()` keeps the final text block per assistant turn; per-turn cap
  600, per-session budget 3000. On real 2026-07-29 data every session stayed bounded
  (max ~2994 chars); the zoo session captured 7 turns / 2467 chars of real design arc.
- Schema bumped to v2; `SESSION_KEYS` + contract updated. Budgets left at 600/3000 — Les
  signed off on the resulting texture, so not tuned further.

## Phase 3 — renderer + firewall (done)

- SKILL.md: register-firewall rule (conversation = descriptive signal, outcome language
  needs a commit/confirmed ref); Output restructured to tl;dr-first detail file with a
  per-session "what you worked through" vs "what shipped" split; remote-less commits group
  by directory basename; optional `_threads today:_` terminal line.
- Regenerated 2026-07-29 digest as the sign-off artifact. Les approved texture + split.

## Environment

- **No lint tooling** in this repo: no `pyproject.toml`/`ruff`/`make lint`/`make check`.
  `make test` (pytest via uv) is the automated gate; `python3 -m py_compile` used as a
  cheap syntax check. Worth scaffolding a `make lint` (ruff) in a future session — noted,
  not done here (out of scope).

## Carried from setup

- Part 1 (relocate detail output to `~/Documents/Obsidian/main/standup-digests/`) was done
  before the dev-session and is carried on this branch as its own commit.
- One direct commit landed on `main` during setup: `chore: ignore .worktrees/`.

## Retrospective

**Recap.** Shipped as PR #3 (merged): the standup digest now (1) writes its detail file to
the Obsidian vault, (2) harvests `cd`/`git -C` dirs from Bash tool-use so commits in
sibling/cd'd directories count, (3) counts remote-less local repos, (4) captures a bounded
assistant-prose signal, and (5) renders a tl;dr-first detail file with a "what you worked
through" vs "what shipped" split behind a register firewall. Tests 70 → 83.

**Scope drift — large but healthy.** The request opened as "write the digest to a section
in my journal" and moved twice before any code: journal-section → vault directory, and a
one-file relocation → a four-part capture overhaul. Each turn added a constraint
(config-free; count remote-less repos; mine assistant replies, not just prompts; tl;dr on
top). The right call was *not* to start the dev-session until scope stabilized — the
brainstorming happened conversationally, and `start` ran only once the shape held. Formal
brainstorm was effectively pre-done, so the session went straight to a written spec.

**Surprises.**
- The motivating case (`zoo-service`) gained a GitHub remote *between* spec-writing and
  execution, so live data resolved it to `Mozilla-Ocho/zoo-service` and never exercised the
  `repo: null` path — that path is proven by unit test instead. Spec assumptions about live
  repo state can go stale within a day; anchor behavior on tests, not on a live snapshot.
- The "richer narrative" gap was mostly a *rendering* problem — prompts were already
  captured in full — but the assistant side needed genuine new extractor data.
- Once discovery was fixed, the zoo session went from "designed… worked on a prototype"
  (no refs, no commits) to 61 commits + 3 merged `the_zoo` PRs. The blind spot was hiding a
  large fraction of a real day.

**Workflow friction.**
- The repo has **no `make lint`/`check`** — the dev-session plan/pr templates assume them;
  fell back to `python3 -m py_compile`. Worth scaffolding `make lint` (ruff).
- Committing the `.worktrees/` gitignore chore directly to `main` at setup created a
  local-main divergence that needed a post-merge `reset --hard`. Next time, put that chore
  on the feature branch, not main.
- `gh pr merge --rebase` tripped because the `main` branch was held by the primary
  worktree; the merge still succeeded server-side. Minor, but the post-merge local sync had
  to be done by hand.

**Misses.** Didn't check whether `zoo-service` had a remote before writing the spec's
`repo: null` framing — a 5-second `git -C … remote -v` would have set expectations. No harm
done (unit test covers it), but it's the kind of live-state check worth doing during
research.

**Memory candidates.** Nothing that isn't derivable from the repo. The lint-absence is a
real gotcha but lives in the Makefile; the skill's new behavior is in `SKILL.md`. The one
soft candidate is a *feedback* fact — Les consistently prioritizes tools that don't
overclaim (this session's register firewall echoes the existing standup language rules) —
offered to Les rather than auto-saved.

**Skill candidates.**
- **Harvest-from-tool-use** is a reusable pattern for any transcript-analysis skill: the
  structured fields (here, `cwd`) capture only part of the story; mining the Bash inputs
  recovers what the harness didn't record. Could generalize beyond standup-digest.
- The dev-session workflow handled "requirements arrive incrementally mid-turn" well by
  deferring `start` until scope stabilized. Worth making explicit in the skill: brainstorm
  in conversation first, formalize once the shape holds.
