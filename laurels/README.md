# laurels

Capture work that landed well as calibration signal, surfaced at future session starts.
Agent nominates in-session, Les adjudicates at `session-wrapup`, accepted laurels surface
project-relevant at the next wake. Ungameable by construction: no task or priority
attached, surfaced retrospectively, gated by adjudication.

- `scripts/laurels.py` — CLI: `add`, `pending`, `accept`, `drop`, `show`.
- Store: `~/.claude/laurels/{pending,laurels}.md` (override with `LAURELS_DIR`).
- Design: `docs/dev-sessions/2026-08-03-1631-laurels-session-wrapup/`.
