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
