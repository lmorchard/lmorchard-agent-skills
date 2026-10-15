# review-digest

Drafts a half-year performance self-review from cited evidence. A stdlib Python script
gathers the evidence. Subagents classify and summarise it month by month. A synthesis
step writes the drafts. `SKILL.md` is the runbook for the agent.

## Data flow

```
Linear MCP ──(agent)──> linear.json ─┐
journals, standup digests (vault) ───┤
gh search prs ───────────────────────┼─> gather.py ─> ledger.json + months/YYYY-MM.input.md
gws drive (optional) ────────────────┤                               │
"<cycle> docs.md" (optional) ────────┘                     subagent per month
                                                                     │
                                                    months/YYYY-MM.extract.md
                                                                     │
                                              synthesis ─> self-review draft,
                                                           level evidence matrix,
                                                           gap report (in the vault)
                                                                     │
                                              cite.py ─> ids become links; unresolved
                                                         ids fail the grounding check
```

Everything under `~/.cache/review-digest/<cycle>/` is disposable. Config, reference
material, and outputs live in the vault, not in this repo.

## Evidence ids

Ids are stable across runs, which is what lets classification overrides persist:

- `j:2026-08-14#heading-slug`: a journal section (`##` under `# notes` or `# TIL`)
- `t:2026-08-14`: that day's completed tasks
- `sd:2026-08-14`: a standup digest
- `gh:owner/repo#N`: a PR, authored or reviewed
- `lin:ABC-123`: a Linear issue
- `doc:<drive id>`: a Google Doc

## Filtering

1. A heading denylist (config regexes) drops journal sections before any model sees
   them. Daily-template sections other than notes, TIL, and completed tasks are dropped
   too.
2. Repos are tiered from config: `work_orgs` → work, `tooling_repos` → tooling, anything
   else excluded and counted.
3. A subagent labels the remaining sections work, tooling, or personal. Config
   `overrides` always win.

## Known gaps

- Direct commits to a default branch, with no PR, aren't gathered.
- Reviewed PRs are dated by merge date. gh search doesn't expose when the review
  happened.
- Docs need `gws` installed and authenticated. Without it, docs come only from journal
  links and the hand-kept docs list. Comment counts cover the first 100 comments per doc.
- Linear is pulled by the agent (MCP), not the script. The pull doesn't record whether
  the user was assignee or creator, so extracts can't tell "owns" from "filed".
- Duplicate headings on one day get positional suffixes (`#foo`, `#foo-2`). Adding an
  earlier duplicate later renumbers them, which moves any override keyed on a suffix.
- `cite.py` rewrites backticked ids anywhere, including inside code fences.
- Credentials are redacted on read, by pattern only (built-in formats plus config
  `secret_patterns`). A format nobody listed passes through.

## Tests

```bash
make test        # all skill test suites
make check       # ruff lint + tests
```

`scripts/test_gather.py` and `scripts/test_cite.py` cover the two scripts. The gather
tests fake every subprocess, and an autouse fixture fails any test that reaches the
real `gh` or `gws`.
