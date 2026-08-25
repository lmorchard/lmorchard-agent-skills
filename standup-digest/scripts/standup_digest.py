#!/usr/bin/env python3
"""Survey Claude Code, Codex, and OpenCode transcripts and emit a structured standup digest.

Standard library only. Shells out to `git` and `gh`, imports neither.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

MONDAY = 0

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@dataclass(frozen=True)
class Window:
    since: datetime
    until: datetime
    rule: str


@dataclass
class Transcript:
    path: Path
    records: list[dict]
    malformed: int


def _midnight(moment: datetime) -> datetime:
    """Local midnight beginning the day that `moment` falls in."""
    return moment.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)


def _shift_days(moment: datetime, days: int) -> datetime:
    """Local midnight `days` away from `moment`, safe across DST transitions.

    Adding/subtracting a `timedelta(days=n)` directly on an aware datetime
    preserves the old UTC offset rather than recomputing it for the new
    date, which silently shifts the boundary by an hour across a DST
    transition. Landing at local noon first and re-truncating avoids that.
    """
    return _midnight(moment + timedelta(days=days, hours=12))


def _parse_day(text: str) -> datetime:
    """Parse YYYY-MM-DD as local midnight."""
    return datetime.strptime(text, "%Y-%m-%d").astimezone()


def resolve_window(
    now: datetime,
    date: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> Window:
    if date and (since or until):
        raise ValueError("--date cannot be combined with --since or --until")

    if date:
        start = _parse_day(date)
        return Window(start, _shift_days(start, 1), "explicit")

    if since or until:
        today = _midnight(now)
        start = _parse_day(since) if since else _shift_days(today, -1)
        end = _parse_day(until) if until else today
        if end <= start:
            raise ValueError("--until must be after --since")
        return Window(start, end, "explicit")

    today = _midnight(now)
    back = 3 if today.weekday() == MONDAY else 1
    return Window(_shift_days(today, -back), today, "previous-workday")


def is_session_transcript(path: Path) -> bool:
    """A top-level session transcript, not a subagent's."""
    if "subagents" in path.parts:
        return False
    stem = path.stem
    if UUID_RE.match(stem):
        return True
    if stem.startswith("rollout-"):
        return True
    return False


def normalize_codex_record(parsed: dict) -> dict:
    if "type" in parsed and "payload" in parsed:
        timestamp = parsed.get("timestamp")
        payload = parsed.get("payload", {})

        if parsed["type"] == "session_meta":
            return {
                "type": "ai-title",
                "sessionId": payload.get("session_id"),
                "cwd": payload.get("cwd"),
                "gitBranch": payload.get("git", {}).get("branch"),
                "timestamp": timestamp,
                "isSidechain": False,
            }

        if parsed["type"] == "response_item":
            role = payload.get("role")
            if role in ("user", "assistant"):
                text_content = []
                for c in payload.get("content", []):
                    if c.get("type") == "input_text" or c.get("type") == "output_text":
                        text_content.append({"type": "text", "text": c.get("text", "")})

                return {
                    "type": role,
                    "timestamp": timestamp,
                    "isSidechain": False,
                    "message": {"content": text_content},
                }
    return parsed


def read_transcript(path: Path) -> Transcript:
    """Parse a JSONL transcript, tolerating partial trailing writes."""
    records: list[dict] = []
    malformed = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if isinstance(parsed, dict):
                records.append(normalize_codex_record(parsed))
            else:
                malformed += 1
    return Transcript(path=path, records=records, malformed=malformed)


def record_timestamp(rec: dict) -> datetime | None:
    raw = rec.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        return None
    # A naive timestamp (no offset/zone) can't be compared against the
    # window's aware bounds; treat it as absent rather than crash the run.
    return moment if moment.tzinfo else None


def _is_mainline(rec: dict) -> bool:
    return rec.get("isSidechain") is not True


def _within(moment: datetime | None, window: Window) -> bool:
    return moment is not None and window.since <= moment < window.until


def _in_window(rec: dict, window: Window) -> bool:
    return _is_mainline(rec) and _within(record_timestamp(rec), window)


def touches_window(records: list[dict], window: Window) -> bool:
    return any(_in_window(rec, window) for rec in records)


def discover_opencode_transcripts(window: Window) -> list[Transcript]:
    db_path = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    except Exception:
        return []

    # We filter by time_created. OpenCode uses ms timestamps.
    start_ms = int(window.since.timestamp() * 1000)
    end_ms = int(window.until.timestamp() * 1000)

    # We fetch all sessions that touch the window.
    # Let's just fetch all sessions updated in the window.
    query = "SELECT * FROM session WHERE time_updated >= ? AND time_created < ?"
    sessions = conn.execute(query, (start_ms, end_ms)).fetchall()

    transcripts = []
    for ses in sessions:
        project = conn.execute(
            "SELECT worktree FROM project WHERE id = ?", (ses["project_id"],)
        ).fetchone()
        cwd = project["worktree"] if project else ""

        messages = conn.execute(
            "SELECT id, data FROM message WHERE session_id = ? ORDER BY time_created",
            (ses["id"],),
        ).fetchall()

        records = []

        # Meta record for session info
        records.append(
            {
                "type": "ai-title",
                "sessionId": ses["id"],
                "cwd": cwd,
                "aiTitle": ses["title"] or ses["slug"],
                "timestamp": datetime.fromtimestamp(
                    ses["time_created"] / 1000.0, tz=timezone.utc
                ).isoformat(),
                "isSidechain": False,
            }
        )

        for msg in messages:
            mdata = json.loads(msg["data"])
            role = mdata.get("role")
            if role not in ("user", "assistant"):
                continue

            parts = conn.execute(
                "SELECT data FROM part WHERE message_id = ? ORDER BY time_created",
                (msg["id"],),
            ).fetchall()

            content_blocks = []
            for part in parts:
                pdata = json.loads(part["data"])
                if pdata.get("type") == "text" and pdata.get("text"):
                    content_blocks.append({"type": "text", "text": pdata.get("text")})
                elif pdata.get("type") == "tool-call":
                    # To allow _bash_commands to harvest dirs
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "name": "Bash"
                            if pdata.get("name") == "default_api:bash"
                            else pdata.get("name"),
                            "input": pdata.get("input", {}),
                        }
                    )

            if content_blocks:
                created_ms = mdata.get("time", {}).get("created", ses["time_created"])
                records.append(
                    {
                        "type": role,
                        "timestamp": datetime.fromtimestamp(
                            created_ms / 1000.0, tz=timezone.utc
                        ).isoformat(),
                        "isSidechain": False,
                        "message": {"content": content_blocks},
                    }
                )

        if records:
            # We use a fake path so the rest of the script can handle it.
            # project_label uses path.parent.name, so we make it look like ~/.claude/projects/ProjectName/SessionId.jsonl
            proj_name = Path(cwd).name if cwd else "OpenCode"
            fake_path = (
                Path.home() / ".claude" / "projects" / proj_name / f"{ses['id']}.jsonl"
            )
            transcripts.append(Transcript(path=fake_path, records=records, malformed=0))

    return transcripts


def discover_transcripts(roots: list[Path]) -> list[Path]:
    """Every top-level session transcript under ~/.claude/projects and ~/.codex/sessions."""
    paths = []
    for root in roots:
        paths.extend(root.glob("*/*.jsonl"))
        paths.extend(
            root.glob("*/*/*/*.jsonl")
        )  # Codex structure: sessions/YYYY/MM/DD/
    return sorted(p for p in paths if is_session_transcript(p))


PROMPT_CHAR_LIMIT = 1500
TRUNCATION_MARKER = "… [truncated]"

# Assistant-prose narrative signal: per-turn truncation + total per-session budget.
# Kept small on purpose -- this is a sense of the conversation, not a transcript dump.
ASSISTANT_TURN_CHAR_LIMIT = 600
ASSISTANT_NOTES_BUDGET = 3000

_WRAPPER_RE = re.compile(
    r"<(local-command-caveat|system-reminder|command-name|command-message|command-args"
    r"|task-notification|local-command-stdout)>"
    r".*?</\1>",
    re.DOTALL,
)

_DRIVER_MARKERS = (
    re.compile(r"You are running unattended", re.IGNORECASE),
    re.compile(r"invoked by the .{0,40}driver", re.IGNORECASE),
    re.compile(r"There is no human watching", re.IGNORECASE),
)


def strip_wrappers(text: str) -> str:
    """Remove harness-injected wrapper blocks from a prompt."""
    return _WRAPPER_RE.sub("", text).strip()


_CD_RE = re.compile(r"""\bcd\s+(?:'([^']+)'|"([^"]+)"|([^\s;&|<>]+))""")
# `-C` is git's dir flag only as a top-level option (before the subcommand). Between
# `git` and `-C` allow only option tokens and `-c key=val` pairs -- never a bare
# subcommand word, so `git commit -C <ref>` (reuse a commit message) isn't mistaken
# for a directory change.
_GIT_C_RE = re.compile(
    r"""\bgit\b(?:\s+-c\s+[^\s;&|]+|\s+-[^\s;&|]+)*?"""
    r"""\s+-C\s+(?:'([^']+)'|"([^"]+)"|([^\s;&|<>]+))"""
)


def _bash_commands(records: list[dict]):
    """Command strings from every Bash tool-use block in the records."""
    for rec in records:
        content = rec.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("name") == "Bash"
            ):
                cmd = (block.get("input") or {}).get("command")
                if isinstance(cmd, str):
                    yield cmd


def _normalize_dir(raw: str) -> str | None:
    """An absolute directory path, or None if it isn't usable as one."""
    if raw.startswith("~"):
        raw = str(Path(raw).expanduser())
    if not raw.startswith("/"):
        return None  # relative or variable-expanded: can't resolve, skip
    cleaned = raw.rstrip("/") or "/"
    parts = cleaned.split("/")
    if "node_modules" in parts or ".git" in parts:
        return None  # dependency tree or git internals -- not a work dir
    return cleaned


def harvest_dirs(records: list[dict]) -> list[str]:
    """Absolute dirs reached via `cd`/`git -C` in Bash calls, deduped in order.

    The transcript's `cwd` field records only the session's launch directory; work
    done in a sibling directory via `cd`/`git -C` inside a Bash command is otherwise
    invisible to the commit scan. Absolute paths only -- resolving relative `cd`s
    would mean simulating shell state across &&/; chains, and the absolute form
    dominates in practice.
    """
    dirs: dict[str, None] = {}
    for cmd in _bash_commands(records):
        for regex in (_CD_RE, _GIT_C_RE):
            for match in regex.finditer(cmd):
                raw = next(g for g in match.groups() if g is not None)
                path = _normalize_dir(raw)
                if path:
                    dirs.setdefault(path, None)
    return list(dirs)


def _prompt_text(rec: dict) -> str:
    """Human-authored text from a user record, excluding tool payloads."""
    content = rec.get("message", {}).get("content")
    if isinstance(content, str):
        return strip_wrappers(content)
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return strip_wrappers("\n".join(parts))
    return ""


def extract_prompts(
    records: list[dict], window: Window | None = None
) -> tuple[list[str], int]:
    """Human prompts, truncated, with dropped chars counted.

    With a window, only in-window prompts are kept. Without one, every
    mainline human prompt in the transcript is kept — used for launch
    attribution, which must not depend on which report window is being run.
    """
    prompts: list[str] = []
    dropped = 0
    for rec in records:
        if rec.get("type") != "user" or rec.get("isMeta") is True:
            continue
        if not _is_mainline(rec):
            continue
        if window is not None and not _within(record_timestamp(rec), window):
            continue
        text = _prompt_text(rec)
        if not text:
            continue
        if len(text) > PROMPT_CHAR_LIMIT:
            dropped += len(text) - PROMPT_CHAR_LIMIT
            text = text[:PROMPT_CHAR_LIMIT] + TRUNCATION_MARKER
        prompts.append(text)
    return prompts, dropped


def _final_text_block(rec: dict) -> str:
    """Closing prose of one assistant turn: its last text block, wrappers stripped."""
    if rec.get("type") != "assistant":
        return ""
    content = rec.get("message", {}).get("content")
    if not isinstance(content, list):
        return ""
    texts = [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
    ]
    return strip_wrappers(texts[-1]) if texts else ""


def extract_assistant_notes(
    records: list[dict],
    window: Window | None = None,
    turn_limit: int = ASSISTANT_TURN_CHAR_LIMIT,
    budget: int = ASSISTANT_NOTES_BUDGET,
) -> list[str]:
    """Bounded per-turn assistant prose for narrative context -- NOT a transcript dump.

    The final text block of each assistant turn is where conclusions, decisions and
    open questions tend to land. Each is truncated to `turn_limit`, and the whole list
    is capped at `budget` characters so even a huge session stays a paragraph or two.
    This is topic/discussion signal only; the renderer must never treat it as proof of
    an outcome (see SKILL.md language rules).
    """
    notes: list[str] = []
    total = 0
    for rec in records:
        if window is not None and not _within(record_timestamp(rec), window):
            continue
        text = _final_text_block(rec)
        if not text:
            continue
        if len(text) > turn_limit:
            text = text[:turn_limit] + TRUNCATION_MARKER
        if total + len(text) > budget:
            break
        notes.append(text)
        total += len(text)
    return notes


def infer_launch(prompts: list[str]) -> str:
    """Whether Les typed this session's first prompt or the board-driver did."""
    if not prompts:
        return "unknown"
    first = prompts[0]
    if any(marker.search(first) for marker in _DRIVER_MARKERS):
        return "driver"
    return "human"


def project_label(dirname: str, cwds: list[str] | None = None) -> str:
    """Short project label. Prefers a recorded cwd; the dirname is lossy."""
    home = str(Path.home())
    if cwds:
        base = cwds[0]
        # A worktree lives at <repo>/.worktrees/<name>; report the repo.
        if "/.worktrees/" in base:
            base = base.split("/.worktrees/")[0]
        for prefix in (f"{home}/devel/", f"{home}/"):
            if base.startswith(prefix):
                return base[len(prefix) :]
        return base
    return dirname.replace("-", "/").lstrip("/")


def _distinct(values) -> list[str]:
    return list(dict.fromkeys(v for v in values if v))


_GH_URL_RE = re.compile(r"https?://github\.com/([\w.-]+/[\w.-]+)/(pull|issues)/(\d+)")


def _run(cmd: list[str], timeout: int = 20) -> str | None:
    """Run a command, returning stdout, or None on any failure."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


GIT_LOG_SEP = "\x1f"

# Immediate-subdirectory cap when expanding a cwd that holds checkouts rather
# than being one. A container like `~/firefox` has a handful of entries; a home
# directory has dozens and isn't what the expansion is for.
CHILD_SCAN_LIMIT = 24

_UNVERIFIED = {
    "verification": "unavailable",
    "state": None,
    "title": None,
    "merged_at": None,
    "closed_at": None,
}


class NullVerifier:
    """Used by --no-verify and by tests. Touches nothing."""

    def __init__(self) -> None:
        self.warnings: list[str] = [
            "verification skipped (--no-verify): refs unverified, commits not collected"
        ]
        self.notes: list[str] = []
        self.gh_calls = 0
        self.worktrees: dict[str, None] = {}

    def verify_ref(self, ref: Ref) -> dict:
        return dict(_UNVERIFIED)

    def commits(self, cwd: str, window: Window, session_cwd: bool = True) -> list[dict]:
        return []

    def working_state(self, toplevel: str) -> dict | None:
        return None

    def repo_for(self, cwd: str) -> str | None:
        return None


class GhVerifier:
    """Checks claims against real git and gh state."""

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.notes: list[str] = []
        self.gh_calls = 0
        # Worktree toplevels seen while collecting commits, in discovery order.
        # Keyed by worktree rather than by repository: `working_state` reports
        # branch and dirt, both of which are per-worktree.
        self.worktrees: dict[str, None] = {}
        self._ref_cache: dict[tuple, dict] = {}
        self._emails: dict[str, str] = {}
        self._repos: dict[str, str | None] = {}
        self._commits_cache: dict[str, list[dict]] = {}

    def repo_for(self, cwd: str) -> str | None:
        """owner/name for `cwd`'s origin remote, cached per cwd."""
        if cwd not in self._repos:
            self._repos[cwd] = repo_from_cwd(cwd)
        return self._repos[cwd]

    def verify_ref(self, ref: Ref) -> dict:
        if not ref.repo:
            return dict(_UNVERIFIED)

        key = (ref.repo, ref.kind, ref.number)
        if key in self._ref_cache:
            return dict(self._ref_cache[key])

        noun = "pr" if ref.kind == "pr" else "issue"
        # Issues have no mergedAt field; gh rejects the PR field list for them.
        fields = (
            "state,title,url,mergedAt,closedAt"
            if noun == "pr"
            else "state,title,url,closedAt"
        )
        self.gh_calls += 1
        raw = _run(
            [
                "gh",
                noun,
                "view",
                str(ref.number),
                "--repo",
                ref.repo,
                "--json",
                fields,
            ]
        )
        if raw is None:
            self.warnings.append(
                f"gh unavailable for {ref.repo}#{ref.number}; reported as unverified"
            )
            result = dict(_UNVERIFIED)
        else:
            try:
                data = json.loads(raw)
                result = {
                    "verification": "confirmed",
                    "state": data.get("state"),
                    "title": data.get("title"),
                    "merged_at": data.get("mergedAt"),
                    "closed_at": data.get("closedAt"),
                }
                if data.get("url"):
                    result["url"] = data["url"]
            except (json.JSONDecodeError, AttributeError):
                self.warnings.append(
                    f"gh returned unparseable JSON for {ref.repo}#{ref.number}"
                )
                result = dict(_UNVERIFIED)

        self._ref_cache[key] = result
        return dict(result)

    def _author_email(self, repo_root: str) -> str | None:
        if repo_root not in self._emails:
            out = _run(["git", "-C", repo_root, "config", "user.email"])
            self._emails[repo_root] = out.strip() if out else ""
        return self._emails[repo_root] or None

    def _resolve(self, cwd: str) -> tuple[str, str] | None:
        """`(repo_root, worktree_toplevel)` for `cwd`, or None if not a checkout.

        The two differ inside a linked worktree: `--git-common-dir` points at
        the main checkout (so `git log --all` there covers every worktree's
        branches, and commits dedupe to one repository), while
        `--show-toplevel` is the worktree itself (which is what carries a
        branch and uncommitted changes).
        """
        out = _run(
            [
                "git",
                "-C",
                cwd,
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
                "--show-toplevel",
            ]
        )
        if out is None:
            return None
        lines = out.strip().splitlines()
        if len(lines) != 2:
            return None
        return str(Path(lines[0]).parent), lines[1]

    def _child_checkouts(self, cwd: str) -> list[str]:
        """Immediate subdirectories of `cwd` that are git checkouts.

        Only ever called on a `cwd` that isn't itself a checkout, and it
        filters to directories that are -- so recursion through `commits`
        bottoms out after one level by construction.

        Hidden directories are skipped and the scan is capped: a session
        launched from `~` or `/` would otherwise fan out into a `rev-parse`
        per entry, and a directory with dozens of children isn't the
        container-of-checkouts case this is for.
        """
        try:
            entries = sorted(
                child
                for child in Path(cwd).iterdir()
                if child.is_dir() and not child.name.startswith(".")
            )
        except OSError:
            return []
        if len(entries) > CHILD_SCAN_LIMIT:
            return []
        return [str(child) for child in entries if self._resolve(str(child))]

    def working_state(self, toplevel: str) -> dict | None:
        """Branch, uncommitted-file count, and Les's last commit in a worktree.

        This is the only signal for work that is real but unlanded: a session
        can spend hours in a checkout and leave the window with nothing in
        `commits[]` -- edits still in the working tree, or a branch whose
        commits predate the window. Reporting it lets the renderer say "worked
        on" with something behind it. It is never evidence of shipping.
        """
        if not Path(toplevel).exists():
            return None

        branch = _run(
            ["git", "-C", toplevel, "symbolic-ref", "--quiet", "--short", "HEAD"]
        )
        status = _run(["git", "-C", toplevel, "status", "--porcelain"])
        if status is None:
            self.notes.append(f"git status failed, working state unknown: {toplevel}")
            dirty = None
        else:
            dirty = len([line for line in status.splitlines() if line.strip()])

        return {
            "repo": repo_from_cwd(toplevel),
            "path": toplevel,
            "branch": branch.strip() if branch else None,
            "dirty_files": dirty,
            "last_commit": self._last_commit(toplevel),
        }

    def _last_commit(self, toplevel: str) -> dict | None:
        """Les's most recent commit reachable from this worktree's HEAD.

        Deliberately unwindowed -- the point is to date a branch whose work
        landed before the window, so the renderer can tell "parked since
        Saturday" from "never started". Authorship-filtered because a shared
        tree's HEAD is somebody else's merge commit.
        """
        email = self._author_email(toplevel)
        cmd = [
            "git",
            "-C",
            toplevel,
            "log",
            "-1",
            f"--pretty=format:%h{GIT_LOG_SEP}%s{GIT_LOG_SEP}%cI",
        ]
        if email:
            cmd.append(f"--author={email}")

        out = _run(cmd)
        if not out or not out.strip():
            return None
        parts = out.strip().splitlines()[0].split(GIT_LOG_SEP)
        if len(parts) != 3:
            return None
        return {"sha": parts[0], "subject": parts[1], "committed_at": parts[2]}

    def commits(self, cwd: str, window: Window, session_cwd: bool = True) -> list[dict]:
        """Les's commits in `cwd`'s repository inside the window.

        `session_cwd` separates where a session actually sat from a directory
        it merely passed through, and three behaviors hang off it. A session
        cwd is deliberate: if it isn't a checkout it may be a directory that
        *holds* them (`~/firefox` holds `firefox/` plus its worktrees), so it
        is expanded one level down, and the worktrees it resolves are recorded
        for `working_state`. A harvested `cd`/`git -C` target is incidental --
        `cd /Users/lorchard/devel` is navigation, not a claim about where work
        happened, and expanding it would pull in every unrelated checkout
        underneath. So harvested paths contribute commits only: no expansion,
        no working state, and no note (a stray `cd` into a plain directory is
        routine and says nothing worth recording).

        Either way, a cwd that isn't a checkout is never run degradation.
        """
        if not Path(cwd).exists():
            # A cleaned-up worktree isn't degradation -- there's nothing to
            # warn about, and the parent repo's commits are still collected
            # via whichever other cwd points at it.
            return []

        resolved = self._resolve(cwd)
        if resolved is None:
            if not session_cwd:
                return []
            children = self._child_checkouts(cwd)
            if children:
                self.notes.append(
                    f"not a checkout but holds {len(children)}, scanned one level "
                    f"down: {cwd}"
                )
            else:
                self.notes.append(f"not a checkout, no commits to collect: {cwd}")
            found: list[dict] = []
            for child in children:
                found.extend(self.commits(child, window))
            return found

        repo_root, toplevel = resolved
        if session_cwd:
            self.worktrees.setdefault(toplevel, None)

        if repo_root in self._commits_cache:
            return self._commits_cache[repo_root]

        email = self._author_email(repo_root)
        if not email:
            self.warnings.append("git user.email unset; commit authorship not filtered")

        cmd = [
            "git",
            "-C",
            repo_root,
            "log",
            f"--since={window.since.isoformat()}",
            f"--until={window.until.isoformat()}",
            f"--pretty=format:%h{GIT_LOG_SEP}%s{GIT_LOG_SEP}%cI",
            "--all",
            "--no-merges",
        ]
        if email:
            cmd.append(f"--author={email}")

        out = _run(cmd)
        if out is None:
            self.warnings.append(f"git log failed, commits skipped: {repo_root}")
            self._commits_cache[repo_root] = []
            return []
        if not out.strip():
            self._commits_cache[repo_root] = []
            return []

        repo = repo_from_cwd(repo_root)
        commits = []
        for line in out.strip().splitlines():
            parts = line.split(GIT_LOG_SEP)
            if len(parts) != 3:
                continue
            sha, subject, committed = parts
            commits.append(
                {
                    "repo": repo,
                    "path": repo_root,
                    "sha": sha,
                    "subject": subject,
                    "committed_at": committed,
                }
            )
        self._commits_cache[repo_root] = commits
        return commits


_BARE_REF_RE = re.compile(r"(?<![\w/#])#(\d+)\b")


@dataclass(frozen=True)
class Ref:
    kind: str  # "pr" | "issue"
    repo: str | None
    number: int
    source: str  # "pr-link" | "prose"
    url: str | None


def repo_from_cwd(cwd: str) -> str | None:
    """owner/name for a checkout's origin remote, or None."""
    out = _run(["git", "-C", cwd, "remote", "get-url", "origin"])
    if out is None:
        return None
    match = re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?$", out.strip())
    return match.group(1) if match else None


def extract_refs(
    records: list[dict], prompts: list[str], default_repo: str | None
) -> list[Ref]:
    refs: list[Ref] = []

    for rec in records:
        if rec.get("type") != "pr-link":
            continue
        number = rec.get("prNumber")
        if not isinstance(number, int):
            continue
        refs.append(
            Ref(
                kind="pr",
                repo=rec.get("prRepository"),
                number=number,
                source="pr-link",
                url=rec.get("prUrl"),
            )
        )

    for text in prompts:
        for repo, kind_word, number in _GH_URL_RE.findall(text):
            refs.append(
                Ref(
                    kind="pr" if kind_word == "pull" else "issue",
                    repo=repo,
                    number=int(number),
                    source="prose",
                    url=f"https://github.com/{repo}/{kind_word}/{number}",
                )
            )
        if default_repo:
            for number in _BARE_REF_RE.findall(text):
                refs.append(
                    Ref(
                        kind="issue",
                        repo=default_repo,
                        number=int(number),
                        source="prose",
                        url=None,
                    )
                )

    return dedupe_refs(refs)


def dedupe_refs(refs: list[Ref]) -> list[Ref]:
    """One ref per (repo, kind, number). pr-link beats prose."""
    best: dict[tuple, Ref] = {}
    for ref in refs:
        key = (ref.repo, ref.kind, ref.number)
        current = best.get(key)
        if current is None or (current.source == "prose" and ref.source == "pr-link"):
            best[key] = ref
    return sorted(best.values(), key=lambda r: (r.repo or "", r.kind, r.number))


def distill_session(transcript: Transcript, window: Window, verifier) -> dict:
    """Neutral facts about one session. No editorial judgment."""
    records = transcript.records
    in_window = [rec for rec in records if _in_window(rec, window)]
    moments = sorted(m for rec in in_window if (m := record_timestamp(rec)))
    prompts, dropped = extract_prompts(records, window)
    all_prompts, _ = extract_prompts(records)  # unwindowed, for launch attribution

    titles = [r.get("aiTitle") for r in records if r.get("type") == "ai-title"]
    session_ids = [r.get("sessionId") for r in records if r.get("sessionId")]
    cwds = _distinct(r.get("cwd") for r in records)

    default_repo = verifier.repo_for(cwds[0]) if cwds else None
    refs = extract_refs(records, prompts, default_repo)

    return {
        "session_id": session_ids[-1] if session_ids else transcript.path.stem,
        "transcript": str(transcript.path),
        "title": titles[-1] if titles else None,
        "project": project_label(transcript.path.parent.name, cwds),
        "cwds": cwds,
        "repo": default_repo,
        "branches": _distinct(r.get("gitBranch") for r in records),
        "launch": infer_launch(all_prompts),
        "started_at": moments[0].astimezone().isoformat() if moments else None,
        "ended_at": moments[-1].astimezone().isoformat() if moments else None,
        "prompt_count": len(prompts),
        "prompt_chars_dropped": dropped,
        "prompts": prompts,
        "assistant_notes": extract_assistant_notes(records, window),
        "refs": [asdict(r) for r in refs],
    }


SCHEMA_VERSION = 3
DEFAULT_ROOT = Path.home() / ".claude" / "projects"


def build_digest(roots: list[Path], window: Window, verifier) -> dict:
    sessions: list[dict] = []
    malformed = 0
    dropped = 0
    warnings: list[str] = []
    harvested: dict[str, None] = {}

    transcripts = []
    for path in discover_transcripts(roots):
        try:
            transcripts.append(read_transcript(path))
        except OSError as err:
            warnings.append(f"unreadable transcript {path}: {err}")
            continue

    transcripts.extend(discover_opencode_transcripts(window))

    for transcript in transcripts:
        malformed += transcript.malformed
        if not touches_window(transcript.records, window):
            continue

        session = distill_session(transcript, window, verifier)
        dropped += session["prompt_chars_dropped"]
        for extra in harvest_dirs(transcript.records):
            harvested.setdefault(extra, None)

        for ref in session["refs"]:
            ref.update(
                verifier.verify_ref(
                    Ref(
                        kind=ref["kind"],
                        repo=ref["repo"],
                        number=ref["number"],
                        source=ref["source"],
                        url=ref["url"],
                    )
                )
            )
        sessions.append(session)

    commits: list[dict] = []
    seen_paths: set[str] = set()
    seen_shas: set[str] = set()
    for session in sessions:
        for cwd in session["cwds"]:
            if cwd in seen_paths:
                continue
            seen_paths.add(cwd)
            for commit in verifier.commits(cwd, window):
                if commit["sha"] in seen_shas:
                    continue
                seen_shas.add(commit["sha"])
                commits.append(commit)

    # Directories the sessions cd'd into but never launched from -- their commits
    # are invisible to the cwd scan above, but the path itself is incidental
    # (see `commits`' session_cwd contract).
    for cwd in harvested:
        if cwd in seen_paths:
            continue
        seen_paths.add(cwd)
        for commit in verifier.commits(cwd, window, session_cwd=False):
            if commit["sha"] in seen_shas:
                continue
            seen_shas.add(commit["sha"])
            commits.append(commit)

    # Every worktree the commit scan resolved, whether or not it produced a
    # commit in the window. A worktree with nothing in `commits[]` is exactly
    # the case this exists for.
    working_state = [
        state
        for toplevel in verifier.worktrees
        if (state := verifier.working_state(toplevel)) is not None
    ]

    warnings.extend(verifier.warnings)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(),
        "window": {
            "since": window.since.isoformat(),
            "until": window.until.isoformat(),
            "rule": window.rule,
        },
        "stats": {
            "sessions": len(sessions),
            "projects": len({s["project"] for s in sessions}),
            "malformed_lines": malformed,
            "prompt_chars_dropped": dropped,
            "gh_calls": verifier.gh_calls,
        },
        "warnings": warnings,
        "notes": list(verifier.notes),
        "sessions": sessions,
        "commits": commits,
        "working_state": working_state,
    }


def format_llm(data: dict) -> str:
    from collections import defaultdict

    lines = []

    def normalize_name(name):
        if not name or name == "unknown":
            return "unknown"
        return name.split("/")[-1]

    window = data.get("window", {})
    start_date = window.get("since", "unknown")[:10]

    lines.append(f"DATE: {start_date}")
    lines.append(f"WARNINGS: {data.get('warnings', [])}")
    lines.append(f"STATS: {data.get('stats', {})}")
    lines.append("")

    commits_by_repo = defaultdict(list)
    for c in data.get("commits", []):
        repo = c.get("repo")
        if not repo:
            repo = c.get("path", "unknown").split("/")[-1] + " (local, no remote)"
        else:
            repo = normalize_name(repo)
        commits_by_repo[repo].append(c)

    ws_map = {}
    for ws in data.get("working_state", []):
        ws_map[ws.get("path")] = ws

    projects = defaultdict(list)
    for s in data.get("sessions", []):
        proj = normalize_name(s.get("project", "unknown"))
        projects[proj].append(s)

    for proj, sessions in projects.items():
        lines.append(f"### PROJECT: {proj}")

        if proj in commits_by_repo:
            lines.append("  COMMITS:")
            for c in commits_by_repo[proj]:
                lines.append(f"    - {c.get('sha')[:7]} {c.get('subject')}")

        for s in sessions:
            title = s.get("title")
            if not title:
                prompts = s.get("prompts", [])
                title = (
                    (prompts[0][:60] + "...")
                    if prompts
                    else "session with no recorded prompts"
                )

            lines.append(f"  * SESSION: {title}")
            lines.append(f"    - Launch: {s.get('launch')}")
            lines.append(f"    - Branches: {s.get('branches')}")

            refs = s.get("refs", [])
            if refs:
                lines.append("    - Refs:")
                for r in refs:
                    lines.append(
                        f"      - {r.get('kind')} #{r.get('number')} ({r.get('state')}) [verified: {r.get('verification')}]"
                    )

            cwds = s.get("cwds", [])
            for cwd in cwds:
                if cwd in ws_map:
                    ws = ws_map[cwd]
                    lines.append(
                        f"    - Working state: path={ws.get('path')}, dirty={ws.get('dirty_files')}, branch={ws.get('branch')}, last_commit={ws.get('last_commit', {}).get('sha') if ws.get('last_commit') else 'null'}"
                    )

            prompts = s.get("prompts", [])
            notes = s.get("assistant_notes", [])
            p_text = prompts[0][:150].replace("\n", " ") if prompts else ""
            n_text = notes[0][:150].replace("\n", " ") if notes else ""
            if p_text or n_text:
                lines.append(f"    - Context: {p_text} | {n_text}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:

    parser = argparse.ArgumentParser(
        description="Emit a structured digest of recent Claude Code, Codex, and OpenCode sessions."
    )
    parser.add_argument("--date", help="a single calendar day, YYYY-MM-DD")
    parser.add_argument("--since", help="window start, YYYY-MM-DD")
    parser.add_argument("--until", help="window end (exclusive), YYYY-MM-DD")
    parser.add_argument("--no-verify", action="store_true", help="skip git and gh")
    parser.add_argument("--root", default=None, help="projects directory")
    parser.add_argument("--out", help="write output here instead of stdout")
    parser.add_argument(
        "--format",
        choices=["json", "llm"],
        default="json",
        help="output format (json or condensed llm summary)",
    )
    args = parser.parse_args(argv)

    try:
        window = resolve_window(
            datetime.now().astimezone(), args.date, args.since, args.until
        )
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    verifier = NullVerifier() if args.no_verify else GhVerifier()

    if args.root:
        roots = [Path(args.root)]
    else:
        roots = [
            Path.home() / ".claude" / "projects",
            Path.home() / ".codex" / "sessions",
        ]
    digest = build_digest(roots, window, verifier)
    if args.format == "llm":
        payload = format_llm(digest)
    else:
        payload = json.dumps(digest, indent=2, ensure_ascii=False)

    if args.out:
        try:
            Path(args.out).write_text(payload, encoding="utf-8")
        except OSError as err:
            print(f"error: cannot write {args.out}: {err}", file=sys.stderr)
            return 1
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
