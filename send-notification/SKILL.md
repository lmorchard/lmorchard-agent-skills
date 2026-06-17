---
name: send-notification
description: Use when Les asks to be pinged, alerted, or notified on his phone — e.g. "ping me when the build passes", "alert me if the tests break", "let me know when this finishes", "text me when you need input", or any request for an intentional push notification at a chosen urgency. Distinct from the automatic Stop/Notification hooks.
---

# Send Notification

## Overview

Sends a deliberate push notification to Les's phone via his self-hosted ntfy
(`https://ntfy.lmorchard.com`, topic `cc-claude`). Use for **on-request, intentional**
alerts — separate from the automatic per-turn `Stop` and needs-input `Notification`
hooks in `~/.claude/hooks/`, which fire on their own and can't be tuned per-message.

Reach for this when Les wants to walk away and be pulled back at a specific moment,
or wants an alert louder/quieter than the automatic ones.

## How

Run the helper; it shares the hook's credentials (`~/.claude/hooks/notify.env`):

```bash
~/.claude/skills/send-notification/send.sh --priority high --title "Build passed" --tags white_check_mark "All 142 tests green on main"
```

For a "ping me when X happens" request: do/await the work, then send at the moment
X actually happens — not when the request is made.

## Priority — match the urgency in Les's words

| Les says…                                  | `--priority` | ntfy effect (Android)            |
|--------------------------------------------|--------------|----------------------------------|
| "urgent", "emergency", "wake me", "asap"   | `urgent`     | Loud + bypasses some DND         |
| "alert me", "flag", "important", "heads-up"| `high`       | Vibrate + sound                  |
| "ping", "notify", "let me know"            | `default`    | Normal notification              |
| "fyi", "note", "quietly", "no rush"        | `low`        | Silent, no vibrate               |

Default to `high` for "alert"-flavored asks and `default` for plain "ping me". When in
doubt between two levels, pick the lower one — false-urgent alerts train Les to ignore them.

## Tags (optional, render as emoji before the title)

`white_check_mark` done · `warning` needs attention · `rotating_light` urgent/broken ·
`hourglass` waiting · `tada` finished-big. Run with no tag if none fits.

## Common mistakes

- **Sending at request time instead of event time** — "ping me when the deploy finishes"
  means send *after* the deploy, not now.
- **Over-escalating priority** — reserve `urgent` for genuinely drop-everything events.
- **Forgetting this is one-way** — Les can't reply to a push; put the answer/context in
  the message body, don't ask a question expecting a response there.
- **Editing the topic/token here** — they live in `~/.claude/hooks/notify.env`; this
  script reads them.
