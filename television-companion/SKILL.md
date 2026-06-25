---
name: television-companion
description: Use when a brainstorming or design question would be clearer shown than told — mockups, wireframes, layout comparisons, architecture diagrams, side-by-side visual options — and Les has Television running. A display-only alternative to the superpowers brainstorming browser server: renders visuals as Television artifacts instead of spinning up a separate web server and tab.
---

# Television Companion

## Overview

A **display-only** visual companion for brainstorming, backed by Television
instead of the superpowers brainstorming browser server. When a design question
is genuinely visual, render it as a Television artifact on a dedicated screen —
Les is already looking at Television, so there's no extra server, port, session
key, or browser tab to manage.

**Display-only:** Television serves artifacts read-only. There is no click-back
channel — the user reads the screen and responds **in the terminal**. (Mockups
can still *show* lettered options; the user just types their pick.) See
[Bi-directional](#bi-directional-future) for why, and what a future version could add.

This is the same *idea* as the superpowers brainstorming Visual Companion, packaged
as a separate skill so it doesn't fork the upstream `superpowers:brainstorming` skill.

## When to Use

Decide **per question**, exactly as the superpowers companion does: would the user
understand this better by *seeing* it than *reading* it?

- **Use it** for: UI mockups, wireframes, layout/navigation comparisons, component
  designs, architecture/data-flow diagrams, side-by-side visual options, look-and-feel
  and spacing questions.
- **Don't** for: requirements, scope, conceptual A/B/C choices, tradeoff lists,
  API/data-model decisions — those are terminal text. A question *about* a UI topic
  is not automatically a visual question.

Prereq: Television must be running (`tv status` → `healthy: true`). If it isn't,
fall back to the superpowers browser companion or plain terminal discussion.

## The Loop

The helper wraps the `tv` CLI. Run `tv-companion.sh` from this skill's directory.

1. **Once per session — `start`:** create and focus a screen for the topic.
   ```bash
   ./tv-companion.sh start "Inspector panel layout"
   ```
   Prints the session slug, screen id (focused), and working dir. Tell Les to look
   at the **Brainstorm: <topic>** screen.

2. **Each visual step — `show`:** write an HTML **fragment** (not a full document) to
   a file using your file-creation tool, then push it as a named card.
   ```bash
   ./tv-companion.sh show "layout-a" /tmp/frag.html
   # or pipe it:
   printf '%s' "$FRAGMENT" | ./tv-companion.sh show "layout-a"
   ```
   The helper wraps the fragment in `frame.html` (dark/light theme + the CSS classes
   below) and serves it as a card. **Never use cat/heredoc to author the fragment** —
   write it to a file with your editor tool, then pass the path.

3. **End your turn:** give a one-line text summary of what's on screen and ask Les to
   respond in the terminal (e.g. *"Showing 3 inspector layouts on the Brainstorm screen
   — which reads cleanest? A/B/C."*).

4. **Iterate vs. add:**
   - **New card per step is the default** — a fresh card name accumulates a gallery you
     can compare at a glance.
   - **Reuse a card name to overwrite in place** when iterating on the *same* mockup
     (e.g. `show "layout-a"` again with revised HTML). Television re-serves the changed
     file automatically — no new card.

5. **`stop`** when done. The screen and cards persist in Television; only the
   active-session pointer is cleared.

## Quick Reference

| Command | Effect |
|---|---|
| `tv-companion.sh start "<topic>"` | Create + focus screen `Brainstorm: <topic>`; begin session |
| `tv-companion.sh show "<card>" <file>` | New card, or overwrite if `<card>` exists |
| `printf … \| tv-companion.sh show "<card>"` | Same, fragment from stdin |
| `tv-companion.sh list` | List the session's cards |
| `tv-companion.sh stop` | End session (screen + cards stay) |

## Writing Fragments

Write **just the body content** — the frame supplies `<html>`, theme CSS, and these
classes. Pass a full `<!doctype>`/`<html>` document only when you need total control
(the helper detects it and serves it verbatim).

```html
<h2>Which inspector layout reads cleanest?</h2>
<p class="subtitle">Same data, two header treatments — side by side</p>
<div class="split">
  <div class="mockup"><div class="mockup-header">A · Stacked</div>
    <div class="mockup-body"><div class="placeholder">title over actions</div></div></div>
  <div class="mockup"><div class="mockup-header">B · Inline</div>
    <div class="mockup-body"><div class="placeholder">title beside actions</div></div></div>
</div>
```

**Design for one narrow column.** Television cards render in a **narrow, portrait**
viewport (think a phone-width column, ~320–460px). Multi-column layouts and side-by-side
panels overflow and get clipped — the user sees only part of the design. So:

- **Default to a single vertical column.** Stack panels/sections top-to-bottom.
- **Avoid side-by-side comparisons in one card.** To compare options, prefer **separate
  cards** (one per option) the user scrolls between, or stack them vertically in one card.
- If you author a **full document**, your own CSS must be single-column and fluid
  (`max-width` ~460px, no fixed multi-column grids). The frame's built-in classes below
  already collapse on narrow widths; custom CSS won't unless you make it.

Pick the right primitive:

- **`.split`** — two things side by side, but it **collapses to stacked** on narrow cards
  (which is most of the time on TV). Fine to use; just expect vertical stacking. For a true
  comparison, separate cards usually read better.
- **`.cards`** — a responsive grid of N options (auto-wraps to one column when narrow).
  Each `.card` wants a `.card-image` (the visual) and `.card-body` with `<h3>`/`<p>`.
- **`.options`** — a vertical list of lettered choices; each `.option` wants a
  `.letter` (A/B/C) + `.content` with `<h3>`/`<p>`. The letter cues what the user types back.
- **`.mockup`** — a framed preview: `.mockup-header` (caption) + `.mockup-body` (the mock).
- **`.pros-cons`** — wrap a `.pros` and a `.cons`, each containing an `<h4>` then a `<ul><li>`.
- **Wireframe bits:** `.placeholder`, `.mock-nav`, `.mock-sidebar`, `.mock-content`,
  `.mock-button`, `.mock-input`. Plus `.subtitle` / `.section` / `.label` for text.

When unsure of a class's expected children, open `frame.html` — the CSS shows what each
class styles.

**Verify the first card rendered.** The helper aborts loudly if a wrapped fragment lands
outside `<body>` (blank-card guard). To eyeball it yourself, the render route
`/artifact/<id>` **301-redirects** to the file, so follow redirects:
```bash
curl -sL -H "Authorization: Bearer $(cat ~/.television/token)" \
  http://localhost:32848/artifact/<artifact-id> | grep -A2 '<body>'
```
Your fragment should appear right after `<body>`, not inside `<style>`.

## Common Mistakes

- **Treating it as a mode, not a tool.** Decide per question. Conceptual/scope questions
  stay in the terminal even mid-session.
- **Waiting for a click.** There is none — always ask for the answer in the terminal.
- **Authoring fragments with heredoc/`cat`.** Dumps noise into the terminal; write to a
  file with your editor tool and pass the path (or pipe a single `printf`).
- **Forgetting to tell Les where to look.** Name the screen ("Brainstorm: …"); the
  screen is focused on `start`, but later `show`s don't move focus.
- **`tv` auth/`Invalid input` errors.** Usually the daemon is a stale version vs. the
  upgraded CLI. Restart it: `launchctl kickstart -k gui/$(id -u)/com.television.server`
  (macOS). The auth token lives at `<storage>/state/token` (find `<storage>` via
  `tv storage-path`); older daemons used `<storage>/token`. The helper auto-bridges
  between the two, so you normally don't touch it.

## Bi-directional (future)

Television serves artifacts read-only and exposes no inbound event endpoint, so a click
inside an artifact has nowhere to post back that the agent can read — unlike the
superpowers companion's `state_dir/events`. v1 is therefore display-only. A future
version could explore: an artifact that POSTs selections to a tiny local sink the agent
polls, or a Television feature that surfaces artifact interactions. Until then, terminal
text is the feedback channel (which the superpowers companion also treats as primary).
