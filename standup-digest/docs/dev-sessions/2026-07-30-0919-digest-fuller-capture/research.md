# Research — digest fuller capture

Load-bearing facts about the current extractor + renderer. Paths are repo-relative to
`standup-digest/`.

## The two-stage architecture

1. **Extractor** `scripts/standup_digest.py` → emits neutral-facts JSON to stdout.
2. **Renderer** = the model following `SKILL.md`, composing the report from that JSON.
   `SKILL.md:28` binds the renderer: *"compose from it; do not re-read the raw
   transcripts yourself."* Any new narrative signal must therefore be surfaced by the
   extractor, not gathered by the renderer reading transcripts.

## Commit discovery (the blind spot)

- `build_digest` collects commits by iterating **only** `session["cwds"]`
  (`scripts/standup_digest.py:574-583`), deduping by `seen_paths` and `seen_shas`.
- `cwds` comes straight from the transcript's structured `cwd` field:
  `cwds = _distinct(r.get("cwd") for r in records)` (`:513`).
- The harness records the **session launch cwd**, not the target of a `cd`/`git -C`
  inside a Bash command. Verified: session `bdc5d323` ("Design ephemeral sandbox arena
  service") recorded only `/Users/lorchard/devel/the_zoo` as cwd, yet its Bash inputs
  reference `zoo-service` 1,203× (98× as `cd /Users/lorchard/devel/zoo-service`), where
  60+ in-window commits landed. Those commits are invisible to the digest.
- `GhVerifier.commits` (`:360-419`): resolves `repo_root` via
  `git rev-parse --git-common-dir`; on a non-repo dir it appends the warning
  `"not a git repository, commits skipped: {cwd}"` (`:372`) — which marks the run
  degraded. Filters by each repo's own `git config user.email` (`:354-358`, `:390-391`).
  Attributes `repo = repo_from_cwd(repo_root)` (`:402`).
- `repo_from_cwd` (`:434-440`): `git remote get-url origin` → `owner/name`, or **`None`
  when there is no origin remote** (e.g. `~/devel/zoo-service`, a local-only repo).
- Commits already carry `path` (the repo_root) alongside `repo` (`:409-417`), so a
  `repo: None` commit is still directory-identifiable.

## Prompt / conversation capture

- `extract_prompts` (`:185-210`) keeps **only human mainline text** — `_prompt_text`
  (`:170-182`) pulls `type=="text"` blocks from `type=="user"` records and strips
  harness wrappers. **Assistant text is never captured.**
- Per-prompt truncation at `PROMPT_CHAR_LIMIT` with `dropped` char accounting
  (`:206-208`). Session `bdc5d323` dropped 0 chars — its 14 prompts were captured in
  full, yet the renderer still flattened them to one intent line. So the richer-narrative
  gap is partly rendering, but capturing the **assistant side** needs new extractor data.
- `distill_session` (`:503-533`) assembles the per-session dict (fields listed in
  `SKILL.md:37-39`).

## Schema + tests

- `SCHEMA_VERSION = 1` (`:536`).
- `make test` → `uv run --with pytest pytest standup-digest/scripts -q`. Baseline: **70
  passing**.
- Test doubles: `sd.NullVerifier()` (empty results) and `sd.GhVerifier()` (real, with
  `_run` monkeypatched). Records are plain dicts wrapped in
  `sd.Transcript(path=..., records=[...], malformed=0)`.
- Schema-conformance test `test_digest_matches_documented_schema`
  (`scripts/test_standup_digest.py:859`) asserts top-level keys against a documented
  list (`:844`); `assert digest["schema_version"] == sd.SCHEMA_VERSION` recurs
  (`:823`, `:924`, `:952`). Adding fields / bumping the version touches these.
- Existing coverage to mirror: `test_commits_parses_git_log` (`:657`),
  `test_commits_scopes_author_email_per_repo` (`:684`, uses `tmp_path` + real git),
  `test_commits_warns_when_git_log_fails` (`:725`),
  `test_distill_session_repo_is_none_without_resolvable_remote` (`:506`).
