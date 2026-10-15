---
name: review-digest
description: Use when Les is preparing a performance self-review or promo packet, or wants a cited summary of a half-year's work — gathers evidence from the Obsidian vault (journals, standup digests), GitHub PRs, Linear issues, and Google Docs, and drafts the review against a career-levelling guide at current and target level.
---

# Review Digest

## Overview

This skill turns a half-year of work records into three drafts:

1. **A self-review draft** with every viable example, written in the shape of the prior
   self-review. Les cuts it down to the best one to three.
2. **A levelling evidence matrix:** each dimension of the levelling guide, scored at the
   current and target level, with citations.
3. **A gap report:** where target-level evidence is thin, progress against the prior
   review's commitments, and what to do with the rest of the half.

The work splits into deterministic gathering (`scripts/gather.py`) and judgment
(subagent month extracts, then synthesis), held to an evidence firewall.

**This repo is public.** The skill holds method only. The levelling guide, prior
reviews, config, cache, and every draft live in the vault or the cache, never in this
repo.

## Where things live

| What | Where |
|---|---|
| Config | `<vault>/pages/reviews/review-digest.config.json` (copy `config.example.json`) |
| Levelling guide, prior review | vault paths named in the config (`clg_path`, `prior_review_path`) |
| Optional hand-kept docs list | `<vault>/pages/reviews/<cycle> docs.md`, lines like `- [title](url) — note (YYYY-MM-DD)` |
| Ledger, slices, extracts | `~/.cache/review-digest/<cycle>/` (disposable, rebuildable) |
| Outputs | `<vault>/pages/reviews/<cycle> self-review draft.md`, `<cycle> CLG evidence.md`, `<cycle> gap report.md` |

`<vault>` is `$REVIEW_DIGEST_VAULT`, defaulting to `~/Documents/Obsidian/main`. Read the
config before starting. It names the levels, the work orgs, the tooling repos, the
heading denylist, the classification overrides, and `secret_patterns`.

**Secrets are redacted when read, not in the vault.** Journals sometimes hold pasted
tokens. `gather.py` replaces well-known credential formats (GitHub, Anthropic, OpenAI,
Google, AWS, and Slack) plus any regexes in `secret_patterns` with `[redacted secret]`
before anything reaches the cache or a subagent, and notes the count. Don't edit the
journals themselves. If an extract or a subagent spots a credential that wasn't
redacted, add its format to `secret_patterns` and re-gather.

## Run

A cycle is `YYYY-H1` (Jan 1–Jul 1) or `YYYY-H2` (Jul 1–Jan 1). The window ends at
tomorrow if the half isn't over.

### 1. Linear pull (you, via the Linear MCP)

The script can't call MCP tools, so you write the Linear data for it:

- Call `list_issues` twice, with `assignee: "me"` and then `creator: "me"`. Pass
  `updatedAt: "<window start>"`, `limit: 250`, and
  `fields: ["id", "title", "statusType", "completedAt", "project", "team", "url"]`.
  Follow `cursor` while `hasNextPage` is true.
- Dedupe by `id` and write the combined JSON list to
  `~/.cache/review-digest/<cycle>/linear.json`.
- **Getting results onto disk.** A large page goes to a tool-results file instead of
  coming back inline. Load that file with a short Python script; never transcribe it.
  Pages that do come back inline have to be written out. Write them compactly, one
  `id|statusType|completed-date|project|team|title` line per issue, parsed by the same
  script. If you don't have the URL, use `https://linear.app/<workspace>/issue/<ID>`,
  which redirects. Issues created by the user and issues assigned to them overlap but
  differ, so pull both.
- Don't filter by status here. The script drops `canceled` and `duplicate` issues and
  anything completed outside the window.

### 2. Gather

```bash
python3 ~/.claude/skills/review-digest/scripts/gather.py --cycle <cycle>
```

This takes about a minute. It runs `gh search prs` month by month, plus Drive lookups if
`gws` is installed and authenticated. It prints item counts, `WARNING:` lines,
`note:` lines, and an extract status per month (`missing`, `stale`, or `fresh`).

- **Warnings** mean degradation: a source that should have been reachable wasn't (gh
  failed, gws unavailable, no Linear data). Carry them into the outputs (see below).
- **Notes** are bookkeeping: sections dropped by the denylist, excluded repos, a
  missing optional docs list. Notes are not degradation.

Flags: `--since` and `--until` override the window. `--no-github` and `--no-gws` skip
those sources (useful offline). `--linear PATH` points at a different Linear file.

### 3. Month extracts (parallel subagents)

For each month whose status is `missing` or `stale`, dispatch one `general-purpose`
subagent. Send them **all in a single message** so they run in parallel. Give each:

> Read `~/.claude/skills/review-digest/prompts/month-extract.md` and follow it exactly.
> Input slice: `~/.cache/review-digest/<cycle>/months/<month>.input.md`.
> Levelling guide: `<vault>/<clg_path>`; current level `<current>`, target `<target>`.
> Write your output to `~/.cache/review-digest/<cycle>/months/<month>.extract.md`.

Skip `fresh` months: their extracts already match their inputs. When the subagents
finish, re-run gather and confirm every month shows `fresh`. A month still `stale` means
its extract didn't copy the `input_hash` correctly.

### 4. Synthesis (you)

Read every `months/*.extract.md`, the prior review, the levelling guide, and the config
levels. **Don't read `ledger.json` or the raw slices.** They're too big, and the extracts
already distilled them. Go back to a specific slice only to check a particular claim.

Then write the three outputs.

**`<cycle> self-review draft.md`**
- Open with a one-line note: generated by review-digest on `<date>`, plus the degraded-run
  line if gather printed warnings.
- Answer the review prompt the prior review answered. Write **every** viable example,
  ranked by target-level signal, strongest first. Les cuts; you don't.
- Each example uses the prior review's shape: **Outcome / progress made** (concrete
  bullets), **CLG behaviors demonstrated** (dimension-named bullets), and **What I'll
  carry forward and do next**. Match the prior review's voice: first person, plain,
  specific.
- Every Outcome bullet ends with backticked evidence ids (see "Citations"). `cite.py`
  turns them into links afterwards.
- Prefer themes that span months over single events. Use each extract's "Notes for
  synthesis" to stitch threads together.

**`<cycle> CLG evidence.md`**
- A table: one row per levelling-guide dimension, and columns
  `current level | target level`. Each cell lists two to four of the strongest citations
  with a short clause each, or says **no evidence**.
- After the table, add a short paragraph naming the strongest target-level dimensions and
  the weakest.

**`<cycle> gap report.md`**
- **Commitments check:** for each "carry forward / do next" item in the prior review, say
  what the evidence shows (progressed, done, not visible), with citations.
- **Thin target-level dimensions:** what kind of evidence would close each gap.
- **Suggestions for the rest of the half:** concrete and small, tied to work already in
  flight. If the half is already over, frame them for the next half.
- **Possible misclassifications:** items labelled personal that might be work, or the
  reverse, listed as override lines Les can paste into the config.

### 5. Iterate

Les edits the drafts directly. To change what counts as evidence:

- Add overrides to the config, `"<evidence id>": "work" | "tooling" | "personal"`. Ids
  are stable across runs.
- Re-run gather. Only months whose slices changed show `stale`. Re-extract just those,
  then redo synthesis.
- Changing `prompts/month-extract.md` means bumping its `prompt_version` line **and**
  `PROMPT_VERSION` in `gather.py` together, which marks every month stale. A test
  enforces that the two match.

## Evidence firewall

The outputs are a review someone will sign. Inflation is the failure mode, so these
rules are binding:

| Evidence | Permitted phrasing |
|---|---|
| merged PR, completed Linear issue, doc owned by Les | shipped, built, wrote, landed, completed, led (with the artifact) |
| open PR, started Linear issue | opened, in progress, in review |
| journal or standup narrative only | worked on, investigated, proposed, discussed, drove the discussion of |
| plans and intentions | intends to, plans to, aimed to |
| others' comments on a doc Les owns | sought and received feedback on |

- **Outcome bullets need an artifact.** Narrative alone can appear in an Outcome section
  only in narrative phrasing.
- **Level mapping is interpretation.** Phrase it as "this demonstrates…", never as a
  verdict. When evidence is current-level only, say so plainly in the matrix and the gap
  report. Don't stretch it to the target.
- **The tooling tier** (personal projects used as work tooling) is evidence of practice,
  of influence on standards, and of agent-workflow expertise. Never present it as a
  product deliverable.
- **Peer-review counts are not a gap.** The team relies on AI review. Look instead for
  evidence that Les shaped review and agent-delivery practice.
- **Degraded runs say so.** If gather printed warnings, the first line of each output
  says the run was degraded and names the missing sources. A partial draft must never
  read as a complete one.
- Anything not in the extracts never appears as an accomplishment.

## Citations

Write citations as **backticked evidence ids**, copied exactly from the extracts:
`gh:owner/repo#12`, `j:2026-08-14#some-heading`, `lin:ABC-123`, `doc:<id>`. Don't
hand-write links. After writing the three outputs, run:

```bash
python3 ~/.claude/skills/review-digest/scripts/cite.py --cycle <cycle> \
  "<vault>/pages/reviews/<cycle> self-review draft.md" \
  "<vault>/pages/reviews/<cycle> CLG evidence.md" \
  "<vault>/pages/reviews/<cycle> gap report.md"
```

This rewrites each id in place. Journal, task, and digest ids become Obsidian links
(heading anchors where the heading allows it). GitHub, Linear, and Doc ids become URL
links with titles from the ledger. **It is also the grounding check.** Any id the ledger
doesn't know is left untouched and printed as `unresolved:`, and the exit status is 1.
Treat an unresolved id as a claim with no evidence: fix the id or drop the claim, then
re-run.

Ids inside code blocks or quotes (the override lines in the gap report) aren't
backticked one by one, so they stay as plain ids. That's what you want for lines meant
to be pasted into the config.

Cite two or three of the strongest items per bullet, not every item. For runs of PRs,
cite one or two and give the count ("31 PRs, e.g. `gh:owner/repo#12`").
