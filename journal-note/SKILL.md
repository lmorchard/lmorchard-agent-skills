---
name: journal-note
description: Use when Les asks to log, capture, or journal what was worked on this session, jot a quick note or TIL down for later, or flag something as a blog candidate — anything destined for his daily Obsidian journal.
---

# Journal Note

## Overview

Appends a note to Les's **daily Obsidian journal** in his house style — either a full
`##` entry under `# notes` (session writeups, blog seeds) or a one-line bullet under
`# TIL` (quick learnings). Captured notes are raw material the `daily-blog-post-composer`
and `weeknotes-blog-post-composer` skills compose from later, so favor reusable detail
over polish.

## Locate today's file

```
~/Documents/Obsidian/main/journals/<YYYY>/<YYYY-MM-DD>.md
```

Derive the path from the date: `date "+%Y/%Y-%m-%d"`. The file usually already exists
(Obsidian daily template) with headings: `# daily / today / tonight / tomorrow /
this week / [[someday]] / followup / TIL / notes`. **Always Read it first**, then insert
into the correct existing section — never reorder or rewrite other content (standup,
therapy, tasks stay untouched). If the file is missing, create it with at least `# TIL`
and `# notes` headings.

## Two cases

**1. Session note → `##` subsection appended to the end of `# notes`.** For "log what we
did", writeups, anything blog-worthy.

```markdown
## <lowercase topic>

- problem / context in one line
- what was built + the stack, terse
- the interesting bit — the gotcha, war story, or "aha" (this is the blog hook)
- blog angles: a few bullets to pull from later
```

**2. Quick learning → single bullet under `# TIL`.** No subsection, one line.

```markdown
- tailscale node IP forwarded :8065 but refused :2586 → the service was on the wrong host
```

When unsure which: a paragraph's worth of story → `# notes`; a single fact or lesson →
`# TIL`. A future to-do that came up → bullet under `# followup`.

## House style (match the existing file)

- lowercase `##` headings; terse bullets; first-person lowercase prose ("i ran…")
- `[[wikilinks]]` for projects, tools, people, entities
- nest detail with tab indents
- `*(blog candidate)*` italic tag under the heading when relevant
- blog-seed depth: enough to reconstruct the story weeks later, not a bare one-liner

## Common mistakes

- **Wrong section** — full writeup is a `##` under `# notes`; a single learning is a bullet under `# TIL`. Don't drop a paragraph into TIL.
- **Too shallow for a blog candidate** — capture the narrative hook (the gotcha/war story), not just "set up X".
- **Rewriting the file** — Read and insert into the existing section; leave everything else alone.
- **Over-polishing** — keep it journal-terse; the blog composer skills do the polishing.
