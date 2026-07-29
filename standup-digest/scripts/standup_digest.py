#!/usr/bin/env python3
"""Survey Claude Code transcripts and emit a structured standup digest.

Standard library only. Shells out to `git` and `gh`, imports neither.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

MONDAY = 0

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


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
    return bool(UUID_RE.match(path.stem))


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
                records.append(parsed)
            else:
                malformed += 1
    return Transcript(path=path, records=records, malformed=malformed)


def record_timestamp(rec: dict) -> datetime | None:
    raw = rec.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _is_mainline(rec: dict) -> bool:
    return rec.get("isSidechain") is not True


def touches_window(records: list[dict], window: Window) -> bool:
    for rec in records:
        if not _is_mainline(rec):
            continue
        moment = record_timestamp(rec)
        if moment is not None and window.since <= moment < window.until:
            return True
    return False


def discover_transcripts(root: Path) -> list[Path]:
    """Every top-level session transcript under ~/.claude/projects."""
    return sorted(p for p in root.glob("*/*.jsonl") if is_session_transcript(p))


PROMPT_CHAR_LIMIT = 1500
TRUNCATION_MARKER = "… [truncated]"

_WRAPPER_RE = re.compile(
    r"<(local-command-caveat|system-reminder|command-name|command-message|command-args)>"
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
        if window is not None:
            moment = record_timestamp(rec)
            if moment is None or not (window.since <= moment < window.until):
                continue
        text = _prompt_text(rec)
        if not text:
            continue
        if len(text) > PROMPT_CHAR_LIMIT:
            dropped += len(text) - PROMPT_CHAR_LIMIT
            text = text[:PROMPT_CHAR_LIMIT] + TRUNCATION_MARKER
        prompts.append(text)
    return prompts, dropped


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
                return base[len(prefix):]
        return base
    return dirname.replace("-", "/").lstrip("/")


def _distinct(values) -> list[str]:
    return list(dict.fromkeys(v for v in values if v))


_GH_URL_RE = re.compile(
    r"https?://github\.com/([\w.-]+/[\w.-]+)/(pull|issues)/(\d+)"
)


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
        self.warnings: list[str] = []
        self.gh_calls = 0

    def verify_ref(self, ref: Ref) -> dict:
        return dict(_UNVERIFIED)

    def commits(self, cwd: str, window: Window) -> list[dict]:
        return []

    def repo_for(self, cwd: str) -> str | None:
        return None


class GhVerifier:
    """Checks claims against real git and gh state."""

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.gh_calls = 0
        self._ref_cache: dict[tuple, dict] = {}
        self._emails: dict[str, str] = {}
        self._repos: dict[str, str | None] = {}

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
                "gh", noun, "view", str(ref.number),
                "--repo", ref.repo,
                "--json", fields,
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
                self.warnings.append(f"gh returned unparseable JSON for {ref.repo}#{ref.number}")
                result = dict(_UNVERIFIED)

        self._ref_cache[key] = result
        return dict(result)

    def _author_email(self, repo_root: str) -> str | None:
        if repo_root not in self._emails:
            out = _run(["git", "-C", repo_root, "config", "user.email"])
            self._emails[repo_root] = out.strip() if out else ""
        return self._emails[repo_root] or None

    def commits(self, cwd: str, window: Window) -> list[dict]:
        """Les's commits in `cwd`'s repository inside the window."""
        common = _run(
            ["git", "-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"]
        )
        if common is None:
            self.warnings.append(f"not a git repository, commits skipped: {cwd}")
            return []
        repo_root = str(Path(common.strip()).parent)

        email = self._author_email(repo_root)
        if not email:
            self.warnings.append("git user.email unset; commit authorship not filtered")

        cmd = [
            "git", "-C", repo_root, "log",
            f"--since={window.since.isoformat()}",
            f"--until={window.until.isoformat()}",
            f"--pretty=format:%h{GIT_LOG_SEP}%s{GIT_LOG_SEP}%cI",
            "--all", "--no-merges",
        ]
        if email:
            cmd.append(f"--author={email}")

        out = _run(cmd)
        if out is None:
            self.warnings.append(f"git log failed, commits skipped: {repo_root}")
            return []
        if not out.strip():
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
        return commits


_BARE_REF_RE = re.compile(r"(?<![\w/#])#(\d+)\b")


@dataclass(frozen=True)
class Ref:
    kind: str            # "pr" | "issue"
    repo: str | None
    number: int
    source: str          # "pr-link" | "prose"
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
        if current is None or (
            current.source == "prose" and ref.source == "pr-link"
        ):
            best[key] = ref
    return sorted(best.values(), key=lambda r: (r.repo or "", r.kind, r.number))


def distill_session(transcript: Transcript, window: Window, verifier) -> dict:
    """Neutral facts about one session. No editorial judgment."""
    records = transcript.records
    in_window = [
        rec
        for rec in records
        if _is_mainline(rec)
        and (moment := record_timestamp(rec)) is not None
        and window.since <= moment < window.until
    ]
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
        "branches": _distinct(r.get("gitBranch") for r in records),
        "launch": infer_launch(all_prompts),
        "started_at": moments[0].astimezone().isoformat() if moments else None,
        "ended_at": moments[-1].astimezone().isoformat() if moments else None,
        "prompt_count": len(prompts),
        "prompt_chars_dropped": dropped,
        "prompts": prompts,
        "refs": [vars(r) for r in refs],
    }


SCHEMA_VERSION = 1
DEFAULT_ROOT = Path.home() / ".claude" / "projects"


def build_digest(root: Path, window: Window, verifier) -> dict:
    sessions: list[dict] = []
    malformed = 0
    dropped = 0
    warnings: list[str] = []

    for path in discover_transcripts(root):
        try:
            transcript = read_transcript(path)
        except OSError as err:
            warnings.append(f"unreadable transcript {path}: {err}")
            continue

        malformed += transcript.malformed
        if not touches_window(transcript.records, window):
            continue

        session = distill_session(transcript, window, verifier)
        dropped += session["prompt_chars_dropped"]

        for ref in session["refs"]:
            ref.update(
                verifier.verify_ref(
                    Ref(
                        kind=ref["kind"], repo=ref["repo"], number=ref["number"],
                        source=ref["source"], url=ref["url"],
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
        "sessions": sessions,
        "commits": commits,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit a structured digest of recent Claude Code sessions."
    )
    parser.add_argument("--date", help="a single calendar day, YYYY-MM-DD")
    parser.add_argument("--since", help="window start, YYYY-MM-DD")
    parser.add_argument("--until", help="window end (exclusive), YYYY-MM-DD")
    parser.add_argument("--no-verify", action="store_true", help="skip git and gh")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="projects directory")
    parser.add_argument("--out", help="write JSON here instead of stdout")
    args = parser.parse_args(argv)

    try:
        window = resolve_window(
            datetime.now().astimezone(), args.date, args.since, args.until
        )
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    verifier = NullVerifier() if args.no_verify else GhVerifier()
    digest = build_digest(Path(args.root), window, verifier)
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
