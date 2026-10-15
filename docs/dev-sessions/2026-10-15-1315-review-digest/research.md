# review-digest — research

## Repo patterns (documentarian pass over standup-digest, someday-triage, laurels)

- **Stdlib-only scripts.** `standup-digest/scripts/standup_digest.py:4,9-17` — "Standard
  library only. Shells out to `git` and `gh`, imports neither." No pyproject; scripts run
  as `python3 ~/.claude/skills/<skill>/scripts/<x>.py` (standup-digest/SKILL.md:21).
- **Single subprocess seam.** `_run(cmd, timeout=20)` (:500-510) returns `None` on any
  failure; callers turn `None` into `warnings` entries ("gh unavailable for R#N; reported
  as unverified", :575-627). In-memory caches only (:564, :629-633, :788-789).
- **Warnings vs notes.** Degradation → `warnings`; bookkeeping → `notes` (:703, :773-793).
- **Window logic.** `resolve_window` (:59-82), frozen `Window(since, until, rule)` (:24-28),
  local-midnight + DST-safe `_shift_days` (:43-51). `--date` / `--since` / `--until`.
- **Output.** Default JSON (`schema_version`, :951) or `--format llm` condensed text
  (`format_llm`, :1057-1138) because raw JSON exceeds context (SKILL.md:28-30).
- **Tests.** Colocated `scripts/test_*.py`; pin `TZ=UTC` before importing datetime
  (test_standup_digest.py:5-6; `.ruff.toml` E402 exemption). Fake `_run` via
  `monkeypatch.setattr(sd, "_run", fake)` dispatching on `cmd[0]` / substrings
  (:954-981); `boom` fakes assert no subprocess (:570-575). Schema key sets locked by
  test (:946-1000). Fixtures are small files in `scripts/fixtures/`.
- **Vault path convention.** someday-triage: env var with default,
  `SOMEDAY_VAULT` → `~/Documents/Obsidian/main` (someday.py:184-198); tests point it at
  `tmp_path` (test_someday.py:157ff). Other skills hardcode the path in SKILL.md.
- **Make.** `make test` lists script dirs explicitly (Makefile `test:`) — a new skill's
  scripts dir must be added. `make check` = ruff lint + tests. `make link` symlinks
  every `*/SKILL.md` dir into `~/.claude/skills`.
- **Skill layout.** `SKILL.md` (frontmatter: `name`, `description` starting "Use
  when…"), `README.md`, `scripts/`, `docs/dev-sessions/`. No `references/` in the
  script-bearing skills (go-cli-builder and dev-session have one).

## Evidence sources (probed 2026-10-15)

- **Journals:** `journals/YYYY/YYYY-MM-DD.md`, ~178 files / ~142k words for a half. Fixed
  template top-level headings (`# daily`, `# today`, `# tonight`, `# tomorrow`,
  `# this week`, `# [[someday]]`, `# followup`, `# TIL`, `# notes`); substance lives in
  `##` sections under `# notes`. Standup sections recur (~43 in H2) with `###`
  subheadings. Sections mix work, work-tooling, personal projects, and private
  (health/family/therapy) material → filtering is load-bearing.
- **Standup digests:** `standup-digests/YYYY-MM-DD.md`, exist from late July; dense,
  evidence-checked, linked from run-day journals.
- **GitHub:** `gh search prs --author=@me|--reviewed-by=@me --updated ">=DATE"
  --json repository` works; returns hundreds across work orgs and personal repos.
- **Linear:** MCP `list_issues(assignee="me", updatedAt=…)` returns structured issues
  with `statusType`, `completedAt`, `project`, `team`. Not every issue referenced in
  commits is assigned to the user → also query `creator="me"`. MCP is agent-side only
  (not callable from a stdlib script).
- **Google Docs:** no Workspace CLI installed; `gcloud` is authenticated but Drive
  access would need extra scopes/setup. Unverified whether that's feasible.
- **Prior self-review + levelling guide:** saved in the vault under `pages/reviews/`
  (not in this repo).
