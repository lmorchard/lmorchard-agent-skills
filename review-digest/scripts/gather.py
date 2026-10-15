#!/usr/bin/env python3
"""Gather a review cycle's evidence into a cited ledger plus per-month slices.

Standard library only. Reads the Obsidian vault directly; shells out to `gh` and
`gws` through `_run`, imports neither. Writes everything to a cache directory
outside the vault.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

SCHEMA_VERSION = 1
PROMPT_VERSION = 1  # must match the line in prompts/month-extract.md
TOOLING_SAMPLES = 5
VAULT_ENV = "REVIEW_DIGEST_VAULT"
DEFAULT_VAULT = Path.home() / "Documents" / "Obsidian" / "main"
CONFIG_REL = Path("pages/reviews/review-digest.config.json")
CACHE_ROOT = Path.home() / ".cache" / "review-digest"
SECTION_CHAR_LIMIT = 6000
TRUNCATED = "\n[…truncated]"

TASK_SECTIONS = {"today", "tomorrow", "this week", "followup"}
_CYCLE_RE = re.compile(r"^(\d{4})-H([12])$")
_JOURNAL_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
_TASK_RE = re.compile(r"^\s*- \[[xX]\] (.+)$")
_LINK_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]")
_GDOC_RE = re.compile(
    r"https://docs\.google\.com/(document|spreadsheets|presentation)/d/([A-Za-z0-9_-]+)"
)
_DOCS_MD_RE = re.compile(
    r"^\s*-\s*\[(?P<title>[^\]]+)\]\((?P<url>[^)\s]+)\)"
    r"(?:\s*[—–-]\s*(?P<note>.*?))?"
    r"(?:\s*\((?P<date>\d{4}-\d{2}-\d{2})\))?\s*$"
)


@dataclass(frozen=True)
class Window:
    since: date  # inclusive
    until: date  # exclusive


@dataclass
class Config:
    levels: dict = field(default_factory=dict)
    clg_path: str = ""
    prior_review_path: str = ""
    work_orgs: list[str] = field(default_factory=list)
    tooling_repos: list[str] = field(default_factory=list)
    linear_teams: list[str] = field(default_factory=list)
    heading_denylist: list[str] = field(default_factory=list)
    overrides: dict[str, str] = field(default_factory=dict)
    secret_patterns: list[str] = field(default_factory=list)


def resolve_cycle(
    cycle: str, today: date, since: str | None = None, until: str | None = None
) -> Window:
    """`YYYY-H1` is Jan 1 to Jul 1, `YYYY-H2` is Jul 1 to Jan 1, capped at tomorrow."""
    m = _CYCLE_RE.match(cycle)
    if not m:
        raise ValueError(f"cycle must look like 2026-H1 or 2026-H2, not {cycle!r}")
    year, half = int(m.group(1)), int(m.group(2))
    if half == 1:
        start, end = date(year, 1, 1), date(year, 7, 1)
    else:
        start, end = date(year, 7, 1), date(year + 1, 1, 1)
    end = min(end, today + timedelta(days=1))
    if since:
        start = date.fromisoformat(since)
    if until:
        end = date.fromisoformat(until)
    if end <= start:
        raise ValueError("window is empty: until must be after since")
    return Window(start, end)


def vault_root() -> Path:
    return Path(os.environ.get(VAULT_ENV, str(DEFAULT_VAULT)))


def load_config(path: Path) -> Config:
    data = json.loads(path.read_text())
    known = Config.__dataclass_fields__
    return Config(**{k: v for k, v in data.items() if k in known})


def slugify(heading: str) -> str:
    text = _LINK_RE.sub(r"\1", heading).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:60].rstrip("-")


def _cap(text: str) -> tuple[str, bool]:
    """Cut long text at the last whitespace before the limit, so a token is either
    kept whole or dropped whole, never left as a fragment redaction can't match."""
    if len(text) <= SECTION_CHAR_LIMIT:
        return text, False
    cut = max(
        text.rfind(" ", 0, SECTION_CHAR_LIMIT), text.rfind("\n", 0, SECTION_CHAR_LIMIT)
    )
    if cut <= 0:
        # No boundary at all: drop the whole unbroken run rather than slice a token.
        cut = len(re.sub(r"\S+$", "", text[:SECTION_CHAR_LIMIT]))
    return text[:cut] + TRUNCATED, True


def _item(source, item_id, day, title, text, meta):
    text, truncated = _cap(text.strip("\n"))
    if truncated:
        meta = {**meta, "truncated": True}
    return {
        "id": item_id,
        "source": source,
        "date": day.isoformat() if day else None,
        "tier": "unclassified",
        "title": title,
        "text": text,
        "url": None,
        "meta": meta,
    }


_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")


def parse_journal(
    day: date,
    text: str,
    denylist: list[re.Pattern],
    secrets: re.Pattern | None = None,
) -> tuple[list[dict], int]:
    """Split one daily journal into evidence items.

    Under `# notes` and `# TIL`, each `## ` section becomes its own item, and any
    loose text before the first section becomes `#notes` / `#til`. Completed
    tasks from the task sections become one item. Everything else in the daily
    template is dropped. A `## ` heading, or a completed task, matching the
    denylist is dropped before anything downstream sees it. Lines inside code
    fences are never read as headings.
    """
    meta = {"path": f"journals/{day.year}/{day.isoformat()}"}
    prefix = f"j:{day.isoformat()}"
    tasks: list[str] = []
    loose: dict[str, list[str]] = {"til": [], "notes": []}
    sections: list[tuple[str, list[str]]] = []
    dropped = 0
    h1 = None
    current: list[str] | None = None  # body of the current kept ## section
    dropping = False  # inside a denylisted ## section
    fence: str | None = None  # opening delimiter of the open code fence

    for line in text.splitlines():
        m = _FENCE_RE.match(line)
        if fence is not None:
            # Close only on the same character, at least as long, nothing after.
            closes = (
                m is not None
                and m.group(1)[0] == fence[0]
                and len(m.group(1)) >= len(fence)
                and not m.group(2).strip()
            )
            if closes:
                fence = None
            in_fence = True
        elif m:
            fence, in_fence = m.group(1), True
        else:
            in_fence = False
        if in_fence:
            pass
        elif line.startswith("# "):
            h1 = line[2:].strip().lower()
            current, dropping = None, False
            continue
        elif h1 in loose and line.startswith("## "):
            heading = line[3:].strip()
            if secrets is not None:
                heading = secrets.sub(REDACTED, heading)
            dropping = any(p.search(heading) for p in denylist)
            if dropping:
                dropped += 1
                current = None
            else:
                current = []
                sections.append((heading, current))
            continue
        if h1 in loose:
            if not dropping:
                (current if current is not None else loose[h1]).append(line)
        elif h1 in TASK_SECTIONS:
            m = _TASK_RE.match(line)
            if m and any(p.search(m.group(1)) for p in denylist):
                dropped += 1
            elif m:
                tasks.append(f"- {m.group(1)}")

    items = []
    if tasks:
        items.append(
            _item(
                "tasks",
                f"t:{day.isoformat()}",
                day,
                "completed tasks",
                "\n".join(tasks),
                meta,
            )
        )
    used: set[str] = set()
    for name, title in (("til", "TIL"), ("notes", "notes")):
        if "\n".join(loose[name]).strip():
            used.add(name)
            items.append(
                _item(
                    "journal",
                    f"{prefix}#{name}",
                    day,
                    title,
                    "\n".join(loose[name]),
                    meta,
                )
            )
    for heading, body in sections:
        base = slugify(heading) or "section"
        slug, n = base, 1
        while slug in used:
            n += 1
            slug = f"{base}-{n}"
        used.add(slug)
        items.append(
            _item("journal", f"{prefix}#{slug}", day, heading, "\n".join(body), meta)
        )
    return items, dropped


def discover_journals(vault: Path, window: Window) -> list[tuple[date, Path]]:
    found = []
    for path in sorted((vault / "journals").glob("*/*.md")):
        if not _JOURNAL_NAME_RE.match(path.name):
            continue
        day = date.fromisoformat(path.stem)
        if window.since <= day < window.until:
            found.append((day, path))
    return found


def collect_journals(
    vault: Path, window: Window, config: Config, notes: list[str]
) -> list[dict]:
    denylist = [re.compile(p, re.IGNORECASE) for p in config.heading_denylist]
    secrets = compile_secret_patterns(config.secret_patterns)
    items: list[dict] = []
    dropped = 0
    for day, path in discover_journals(vault, window):
        day_items, day_dropped = parse_journal(day, path.read_text(), denylist, secrets)
        items.extend(day_items)
        dropped += day_dropped
    if dropped:
        notes.append(f"dropped {dropped} journal sections by heading_denylist")
    truncated = sum(1 for i in items if i["meta"].get("truncated"))
    if truncated:
        notes.append(f"truncated {truncated} sections at {SECTION_CHAR_LIMIT} chars")
    return items


def collect_digests(vault: Path, window: Window) -> list[dict]:
    items = []
    for path in sorted((vault / "standup-digests").glob("*.md")):
        if not _JOURNAL_NAME_RE.match(path.name):
            continue
        day = date.fromisoformat(path.stem)
        if window.since <= day < window.until:
            meta = {"path": f"standup-digests/{path.stem}"}
            items.append(
                _item(
                    "digest",
                    f"sd:{path.stem}",
                    day,
                    "standup digest",
                    path.read_text(),
                    meta,
                )
            )
    return items


def _doc_item(doc_id, day, title, text, url, meta, tier="unclassified"):
    item = _item("doc", f"doc:{doc_id}", day, title, text, meta)
    item["url"] = url
    item["tier"] = tier
    return item


def extract_doc_links(items: list[dict]) -> list[dict]:
    """One doc item per Google Doc linked from kept journal or task items."""
    docs: dict[str, dict] = {}
    for item in sorted(items, key=lambda i: (i["date"] or "", i["id"])):
        if item["source"] not in ("journal", "tasks"):
            continue
        for line in item["text"].splitlines():
            for kind, doc_id in _GDOC_RE.findall(line):
                if doc_id in docs:
                    if item["id"] not in docs[doc_id]["meta"]["mentions"]:
                        docs[doc_id]["meta"]["mentions"].append(item["id"])
                    continue
                docs[doc_id] = _doc_item(
                    doc_id,
                    date.fromisoformat(item["date"]),
                    f"{kind} {doc_id[:8]}",
                    line.strip(),
                    f"https://docs.google.com/{kind}/d/{doc_id}",
                    {"kind": kind, "mentions": [item["id"]], "origin": "journal"},
                )
    return list(docs.values())


def parse_docs_md(text: str) -> list[dict]:
    """Hand-kept list: `- [title](url) — note (YYYY-MM-DD)`; note and date optional."""
    docs = []
    for line in text.splitlines():
        m = _DOCS_MD_RE.match(line)
        if not m:
            continue
        url = m.group("url")
        gdoc = _GDOC_RE.search(url)
        doc_id = gdoc.group(2) if gdoc else hashlib.sha1(url.encode()).hexdigest()[:10]
        try:
            day = date.fromisoformat(m.group("date")) if m.group("date") else None
        except ValueError:
            day = None
        meta = {
            "kind": gdoc.group(1) if gdoc else "link",
            "mentions": [],
            "origin": "docs.md",
        }
        docs.append(
            _doc_item(
                doc_id,
                day,
                m.group("title").strip(),
                m.group("note") or "",
                url,
                meta,
                "work",
            )
        )
    return docs


def merge_docs(found: list[dict], listed: list[dict]) -> list[dict]:
    """Merge hand-listed docs into journal-found ones by id; the list's title,
    note, and tier win, the journal's first-mention date and mentions are kept."""
    by_id = {d["id"]: d for d in found}
    for doc in listed:
        existing = by_id.get(doc["id"])
        if existing is None:
            by_id[doc["id"]] = doc
            continue
        existing["title"] = doc["title"]
        existing["tier"] = doc["tier"]
        if doc["text"]:
            existing["text"] = doc["text"]
        existing["date"] = existing["date"] or doc["date"]
        existing["meta"]["origin"] = "journal+docs.md"
    return list(by_id.values())


def _run(cmd: list[str], timeout: int = 60) -> str | None:
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


GH_FIELDS = "number,repository,state,title,url,closedAt,createdAt,author"
GH_LIMIT = 1000


def month_ranges(window: Window) -> list[tuple[date, date]]:
    """Calendar-month chunks clipped to the window, with inclusive end dates."""
    ranges = []
    start = window.since
    while start < window.until:
        next_month = date(start.year + start.month // 12, start.month % 12 + 1, 1)
        end = min(next_month, window.until) - timedelta(days=1)
        ranges.append((start, end))
        start = next_month
    return ranges


def _gh_search(args: list[str], label: str, warnings: list[str]) -> list[dict]:
    out = _run(
        ["gh", "search", "prs", *args, "--limit", str(GH_LIMIT), "--json", GH_FIELDS]
    )
    if out is None:
        warnings.append(f"gh search failed ({label}); GitHub evidence incomplete")
        return []
    try:
        results = json.loads(out)
    except json.JSONDecodeError:
        warnings.append(f"gh search returned unparseable JSON ({label})")
        return []
    if len(results) >= GH_LIMIT:
        warnings.append(
            f"gh search hit the {GH_LIMIT}-result cap ({label}); some PRs missing"
        )
    return results


def _repo_tier(repo: str, config: Config) -> str | None:
    repo = repo.lower()
    if repo.split("/")[0] in {o.lower() for o in config.work_orgs}:
        return "work"
    if repo in {r.lower() for r in config.tooling_repos}:
        return "tooling"
    return None


def collect_github(
    config: Config, window: Window, warnings: list[str], notes: list[str]
) -> list[dict]:
    """Merged PRs authored or reviewed, month by month, plus open authored PRs."""
    found: list[tuple[dict, str]] = []
    for start, end in month_ranges(window):
        rng = f"{start}..{end}"
        for flag, role in (
            ("--author=@me", "author"),
            ("--reviewed-by=@me", "reviewer"),
        ):
            for pr in _gh_search(
                [flag, "--merged-at", rng], f"{role}, {rng}", warnings
            ):
                found.append(({**pr, "state": "merged"}, role))
    for pr in _gh_search(["--author=@me", "--state", "open"], "author, open", warnings):
        if window.since <= date.fromisoformat(pr["createdAt"][:10]) < window.until:
            found.append((pr, "author"))

    items: dict[str, dict] = {}
    excluded: dict[str, int] = {}
    for pr, role in found:
        repo = pr["repository"]["nameWithOwner"]
        tier = _repo_tier(repo, config)
        if tier is None:
            excluded[repo] = excluded.get(repo, 0) + 1
            continue
        item_id = f"gh:{repo}#{pr['number']}"
        if item_id in items and items[item_id]["meta"]["role"] == "author":
            continue
        merged = pr["state"] == "merged"
        stamp = pr["closedAt"] if merged else pr["createdAt"]
        meta = {
            "role": role,
            "state": "merged" if merged else "open",
            "repo": repo,
            "pr_author": (pr.get("author") or {}).get("login"),
        }
        item = _item(
            "github", item_id, date.fromisoformat(stamp[:10]), pr["title"], "", meta
        )
        item["url"] = pr["url"]
        item["tier"] = tier
        items[item_id] = item
    if excluded:
        notes.append(
            f"excluded {sum(excluded.values())} PRs from {len(excluded)} repos "
            "not in work_orgs/tooling_repos"
        )
    return list(items.values())


def load_linear(
    path: Path, config: Config, notes: list[str], warnings: list[str]
) -> list[dict]:
    """Merge the agent-written Linear pull: a JSON list of
    {id, title, statusType, completedAt, project, team, url}."""
    try:
        issues = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        warnings.append(f"{path.name} is not valid JSON ({exc}); Linear skipped")
        return []
    items = []
    canceled = other_team = malformed = 0
    for issue in issues:
        if not (
            isinstance(issue, dict)
            and isinstance(issue.get("id"), str)
            and isinstance(issue.get("title"), str)
        ):
            malformed += 1
            continue
        if issue.get("statusType") in ("canceled", "duplicate"):
            canceled += 1
            continue
        if config.linear_teams and issue.get("team") not in config.linear_teams:
            other_team += 1
            continue
        try:
            completed = issue.get("completedAt")
            day = date.fromisoformat(completed[:10]) if completed else None
        except (TypeError, ValueError):
            malformed += 1
            continue
        meta = {
            "status": issue.get("statusType"),
            "project": issue.get("project"),
            "team": issue.get("team"),
        }
        item = _item("linear", f"lin:{issue['id']}", day, issue["title"], "", meta)
        item["url"] = issue.get("url")
        item["tier"] = "work"
        items.append(item)
    if canceled:
        notes.append(f"skipped {canceled} canceled or duplicate Linear issues")
    if other_team:
        notes.append(f"skipped {other_team} from teams not in linear_teams")
    if malformed:
        notes.append(f"skipped {malformed} malformed Linear entries")
    return items


def month_key(item: dict) -> str:
    return item["date"][:7] if item["date"] else "undated"


def _sort_key(item: dict) -> tuple[str, str]:
    return (item["date"] or "", item["id"])


def _header(item: dict) -> str:
    return (
        f"### {item['id']} — {item['date'] or 'undated'} — {item['title']} "
        f"[tier: {item['tier']}]"
    )


def _pr_line(item: dict) -> str:
    meta = item["meta"]
    who = f", by {meta['pr_author']}" if meta["role"] == "reviewer" else ""
    return (
        f"- {item['id']} — {item['date']} — {item['title']} "
        f"({meta['state']}{who}) {item['url']}"
    )


_HEADING_RE = re.compile(r"^(#{1,6}) ", re.MULTILINE)


def demote_headings(text: str) -> str:
    """Push markdown headings in item text down three levels (capped at six) so
    they can't be mistaken for the slice's own `##` / `###` structure."""
    return _HEADING_RE.sub(lambda m: "#" * min(len(m.group(1)) + 3, 6) + " ", text)


def render_month(cycle: str, month: str, items: list[dict]) -> str:
    """The subagent's input for one month: fixed section order, stable sort."""
    items = sorted(items, key=_sort_key)
    by_source: dict[str, list[dict]] = {}
    for item in items:
        by_source.setdefault(item["source"], []).append(item)
    prs = by_source.get("github", [])
    authored = [i for i in prs if i["tier"] == "work" and i["meta"]["role"] == "author"]
    reviewed = [
        i for i in prs if i["tier"] == "work" and i["meta"]["role"] == "reviewer"
    ]
    tooling = [i for i in prs if i["tier"] == "tooling"]

    out = [f"# Evidence for {month} ({cycle})", ""]

    def block(title, lines):
        if lines:
            out.extend([f"## {title}", "", *lines, ""])

    def full(item):
        return [_header(item), "", demote_headings(item["text"]), ""]

    block(
        "Journal sections", [ln for i in by_source.get("journal", []) for ln in full(i)]
    )
    block("Completed tasks", [ln for i in by_source.get("tasks", []) for ln in full(i)])
    block(
        "Standup digests", [ln for i in by_source.get("digest", []) for ln in full(i)]
    )
    block("GitHub PRs — authored (work)", [_pr_line(i) for i in authored])
    block("GitHub PRs — reviewed", [_pr_line(i) for i in reviewed])
    collapsed = []
    for repo in sorted({i["meta"]["repo"] for i in tooling}):
        repo_prs = [i for i in tooling if i["meta"]["repo"] == repo]
        collapsed.append(f"- {repo}: {len(repo_prs)} PRs, e.g.:")
        collapsed.extend(f"  {_pr_line(i)}" for i in repo_prs[:TOOLING_SAMPLES])
    block("GitHub PRs — tooling (collapsed)", collapsed)
    block(
        "Linear issues",
        [
            f"- {i['id']} — {i['date'] or 'undated'} — {i['title']} "
            f"[{i['meta']['status']}, {i['meta']['project']}] [tier: {i['tier']}] "
            f"{i['url']}"
            for i in by_source.get("linear", [])
        ],
    )
    docs = []
    for i in by_source.get("doc", []):
        docs.extend([_header(i), "", i["url"] or "", demote_headings(i["text"])])
        meta = i["meta"]
        if "owned" in meta:
            docs.append("owned by me" if meta["owned"] else f"owner: {meta['owner']}")
        if meta.get("comments"):
            c = meta["comments"]
            docs.append(f"comments: {c['by_others']} from others, {c['by_me']} from me")
        if i["meta"].get("mentions"):
            docs.append("mentioned in: " + ", ".join(i["meta"]["mentions"]))
        docs.append("")
    block("Docs", docs)
    return "\n".join(out).rstrip() + "\n"


def input_hash(body: str, context: str = "") -> str:
    """`context` is everything else an extract depends on: the configured levels and
    the levelling guide's contents. Changing either marks every month stale."""
    payload = f"{PROMPT_VERSION}\n{context}\n{body}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def write_months(
    cache: Path, cycle: str, items: list[dict], context: str = ""
) -> dict[str, dict]:
    months_dir = cache / "months"
    months_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict]] = {}
    for item in items:
        grouped.setdefault(month_key(item), []).append(item)
    index = {}
    for month, month_items in sorted(grouped.items()):
        body = render_month(cycle, month, month_items)
        digest = input_hash(body, context)
        front = (
            f"---\ncycle: {cycle}\nmonth: {month}\ninput_hash: {digest}\n"
            f"prompt_version: {PROMPT_VERSION}\n---\n\n"
        )
        (months_dir / f"{month}.input.md").write_text(front + body)
        index[month] = {"input_hash": digest, "items": len(month_items)}
    for old in [*months_dir.glob("*.input.md"), *months_dir.glob("*.extract.md")]:
        month = old.name.removesuffix(".input.md").removesuffix(".extract.md")
        if month not in index:
            old.unlink()
    return index


_HASH_LINE_RE = re.compile(r"^input_hash:\s*(\S+)\s*$", re.MULTILINE)


def month_status(cache: Path, months: dict[str, dict]) -> dict[str, str]:
    status = {}
    for month, info in months.items():
        extract = cache / "months" / f"{month}.extract.md"
        if not extract.exists():
            status[month] = "missing"
            continue
        m = _HASH_LINE_RE.search(extract.read_text())
        status[month] = "fresh" if m and m.group(1) == info["input_hash"] else "stale"
    return status


GWS_FILE_FIELDS = (
    "id,name,mimeType,createdTime,modifiedTime,webViewLink,owners(displayName,me)"
)
GWS_COMMENT_FIELDS = (
    "comments(author(me),createdTime,replies(author(me),createdTime)),nextPageToken"
)
GWS_DOC_TYPES = [
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
]


GWS_REQUIRED = {"id", "name", "mimeType", "createdTime", "modifiedTime"}


def _parse_gws_pages(out: str) -> list[dict] | None:
    """gws prints one JSON object per page with --page-all, but a single response
    may be pretty-printed across lines. Accept either; None if neither parses."""
    try:
        return [json.loads(line) for line in out.splitlines() if line.strip()]
    except json.JSONDecodeError:
        pass
    try:
        whole = json.loads(out)
    except json.JSONDecodeError:
        return None
    return [whole] if isinstance(whole, dict) else None


def _gws(args: list[str], params: dict) -> str | None:
    return _run(["gws", *args, "--params", json.dumps(params)], timeout=120)


def _gws_comments(file_id: str, window: Window) -> dict | None:
    out = _gws(
        ["drive", "comments", "list"],
        {"fileId": file_id, "pageSize": 100, "fields": GWS_COMMENT_FIELDS},
    )
    if out is None:
        return None
    try:
        comments = json.loads(out).get("comments", [])
    except json.JSONDecodeError:
        return None
    since, until = window.since.isoformat(), window.until.isoformat()
    entries = comments + [r for c in comments for r in c.get("replies", [])]
    authors = [
        e["author"].get("me", False)
        for e in entries
        if since <= (e.get("createdTime") or "")[:10] < until
    ]
    return {"by_me": sum(authors), "by_others": len(authors) - sum(authors)}


def _gws_doc(f: dict, window: Window) -> dict:
    created = date.fromisoformat(f["createdTime"][:10])
    day = (
        created
        if created >= window.since
        else date.fromisoformat(f["modifiedTime"][:10])
    )
    owner = next(iter(f.get("owners") or []), {})
    meta = {
        "kind": f["mimeType"].rsplit(".", 1)[-1],
        "origin": "gws",
        "owned": bool(owner.get("me")),
        "owner": owner.get("displayName"),
        "created": f["createdTime"][:10],
        "modified": f["modifiedTime"][:10],
        "comments": _gws_comments(f["id"], window),
        "mentions": [],
    }
    return _doc_item(f["id"], day, f["name"], "", f.get("webViewLink"), meta)


def collect_gws_docs(
    window: Window, known: list[dict], warnings: list[str], notes: list[str]
) -> list[dict]:
    """Docs the user owns that changed in the window, plus title, owner, and
    comment counts for docs already known from journals or docs.md."""
    query = (
        f"'me' in owners and modifiedTime >= '{window.since}T00:00:00Z' "
        f"and modifiedTime < '{window.until}T00:00:00Z' and trashed = false and ("
        + " or ".join(f"mimeType = '{m}'" for m in GWS_DOC_TYPES)
        + ")"
    )
    out = _run(
        [
            "gws",
            "drive",
            "files",
            "list",
            "--params",
            json.dumps(
                {
                    "q": query,
                    "pageSize": 100,
                    "fields": f"files({GWS_FILE_FIELDS}),nextPageToken",
                }
            ),
            "--page-all",
        ],
        timeout=120,
    )
    if out is None:
        warnings.append(
            "gws unavailable; Docs come from journal links and docs.md only"
        )
        return []
    pages = _parse_gws_pages(out)
    if pages is None:
        warnings.append(
            "gws returned unparseable output; Docs come from journal links and docs.md only"
        )
        return []
    files = {f["id"]: f for page in pages for f in page.get("files", []) if "id" in f}
    unreadable = 0
    for doc in known:
        file_id = doc["id"].removeprefix("doc:")
        if doc["meta"].get("kind") == "link" or file_id in files:
            continue
        got = _parse_gws_pages(
            _gws(
                ["drive", "files", "get"],
                {"fileId": file_id, "fields": GWS_FILE_FIELDS},
            )
            or ""
        )
        if not got:
            unreadable += 1
            continue
        files[file_id] = got[0]
    docs = []
    for f in files.values():
        if not GWS_REQUIRED <= f.keys():
            unreadable += 1
            continue
        docs.append(_gws_doc(f, window))
    if unreadable:
        notes.append(
            f"gws could not read {unreadable} known docs (no access, deleted, or incomplete)"
        )
    return docs


def merge_gws_docs(docs: list[dict], gws_docs: list[dict]) -> list[dict]:
    """Fold Drive metadata into known docs by id. A docs.md title wins over the
    Drive title; the journal's first-mention date and mentions are kept."""
    by_id = {d["id"]: d for d in docs}
    for doc in gws_docs:
        existing = by_id.get(doc["id"])
        if existing is None:
            by_id[doc["id"]] = doc
            continue
        if "docs.md" not in existing["meta"].get("origin", ""):
            existing["title"] = doc["title"]
        for key in ("owned", "owner", "created", "modified", "comments"):
            if key in doc["meta"]:
                existing["meta"][key] = doc["meta"][key]
        existing["meta"]["origin"] = existing["meta"].get("origin", "") + "+gws"
        existing["date"] = existing["date"] or doc["date"]
        existing["url"] = existing["url"] or doc["url"]
    return list(by_id.values())


# Well-known credential formats, redacted from every item before it reaches the
# cache or a subagent. Employer-specific formats go in the config's
# `secret_patterns` instead of here.
BUILTIN_SECRET_PATTERNS = [
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"gh[pousr]_[A-Za-z0-9]{30,}",
    r"sk-ant-[A-Za-z0-9_-]{20,}",
    r"sk-(?:proj|svcacct|admin)-[A-Za-z0-9_-]{20,}",
    r"sk-[A-Za-z0-9]{32,}",
    r"AIza[0-9A-Za-z_-]{35}",
    r"AKIA[A-Z0-9]{16}",
    r"xox[abprs]-[A-Za-z0-9-]{10,}",
]
REDACTED = "[redacted secret]"


def compile_secret_patterns(extra: list[str]) -> re.Pattern:
    return re.compile("|".join(f"(?:{p})" for p in BUILTIN_SECRET_PATTERNS + extra))


def redact_secrets(text: str, pattern: re.Pattern) -> tuple[str, int]:
    return pattern.subn(REDACTED, text)


def _redact_value(value, pattern: re.Pattern) -> tuple[object, int]:
    """Redact strings anywhere inside a JSON-shaped value."""
    if isinstance(value, str):
        return redact_secrets(value, pattern)
    if isinstance(value, list):
        pairs = [_redact_value(v, pattern) for v in value]
        return [v for v, _ in pairs], sum(n for _, n in pairs)
    if isinstance(value, dict):
        pairs = {k: _redact_value(v, pattern) for k, v in value.items()}
        return {k: v for k, (v, _) in pairs.items()}, sum(n for _, n in pairs.values())
    return value, 0


def extraction_context(vault: Path, config: Config) -> str:
    """What month extracts depend on besides their slice: the levels and the
    levelling guide. Folded into each month's input hash."""
    guide = vault / config.clg_path if config.clg_path else None
    guide_text = guide.read_text() if guide and guide.is_file() else ""
    return json.dumps(config.levels, sort_keys=True) + "\n" + guide_text


def build_ledger(
    config: Config,
    window: Window,
    cycle: str,
    items: list[dict],
    warnings: list[str],
    notes: list[str],
) -> dict:
    since, until = window.since.isoformat(), window.until.isoformat()
    outside = [i for i in items if i["date"] and not since <= i["date"] < until]
    if outside:
        notes.append(f"dropped {len(outside)} items dated outside the window")
        items = [i for i in items if i not in outside]
    secrets = compile_secret_patterns(config.secret_patterns)
    redacted = 0
    for item in items:
        if item["id"] in config.overrides:
            item["tier"] = config.overrides[item["id"]]
        for key in ("title", "text", "url", "meta"):
            item[key], n = _redact_value(item[key], secrets)
            redacted += n
    if redacted:
        notes.append(f"redacted {redacted} secrets from items")
    return {
        "schema_version": SCHEMA_VERSION,
        "cycle": cycle,
        "window": {
            "since": window.since.isoformat(),
            "until": window.until.isoformat(),
        },
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "items": items,
        "warnings": warnings,
        "notes": notes,
        "months": {},
    }


def main(argv: list[str] | None = None, today: date | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cycle", required=True, help="e.g. 2026-H2")
    parser.add_argument("--since", help="YYYY-MM-DD, overrides the cycle start")
    parser.add_argument(
        "--until", help="YYYY-MM-DD (exclusive), overrides the cycle end"
    )
    parser.add_argument("--config", help="config path (default: in the vault)")
    parser.add_argument(
        "--cache", help="output directory (default: ~/.cache/review-digest/<cycle>)"
    )
    parser.add_argument("--no-github", action="store_true", help="skip gh searches")
    parser.add_argument(
        "--linear", help="Linear pull JSON (default: <cache>/linear.json)"
    )
    parser.add_argument(
        "--no-gws", action="store_true", help="skip the gws Drive lookup"
    )
    args = parser.parse_args(argv)

    try:
        window = resolve_cycle(
            args.cycle, today or date.today(), args.since, args.until
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    vault = vault_root()
    config_path = Path(args.config) if args.config else vault / CONFIG_REL
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        print(
            f"error: no config at {config_path}; copy config.example.json there and edit it",
            file=sys.stderr,
        )
        return 2

    cache = Path(args.cache) if args.cache else CACHE_ROOT / args.cycle
    warnings: list[str] = []
    notes: list[str] = []
    items = collect_journals(vault, window, config, notes)
    found_docs = extract_doc_links(items)
    items.extend(collect_digests(vault, window))
    docs_md = vault / "pages" / "reviews" / f"{args.cycle} docs.md"
    listed_docs = parse_docs_md(docs_md.read_text()) if docs_md.exists() else []
    if not docs_md.exists():
        notes.append(f"no {docs_md.name} (optional hand-kept docs list)")
    docs = merge_docs(found_docs, listed_docs)
    if args.no_gws:
        notes.append("gws skipped (--no-gws)")
    else:
        docs = merge_gws_docs(docs, collect_gws_docs(window, docs, warnings, notes))
    items.extend(docs)
    linear = Path(args.linear) if args.linear else cache / "linear.json"
    if linear.exists():
        items.extend(load_linear(linear, config, notes, warnings))
    else:
        warnings.append("no Linear data (run the Linear pull first)")
    if args.no_github:
        notes.append("GitHub skipped (--no-github)")
    else:
        items.extend(collect_github(config, window, warnings, notes))

    ledger = build_ledger(config, window, args.cycle, items, warnings, notes)
    cache.mkdir(parents=True, exist_ok=True)
    ledger["months"] = write_months(
        cache, args.cycle, ledger["items"], extraction_context(vault, config)
    )
    (cache / "ledger.json").write_text(json.dumps(ledger, indent=2, ensure_ascii=False))

    print(f"ledger: {cache / 'ledger.json'}")
    print(f"window: {window.since} .. {window.until} (exclusive)")
    print(f"items: {len(ledger['items'])}")
    for w in warnings:
        print(f"WARNING: {w}")
    for n in notes:
        print(f"note: {n}")
    print("months (extract status):")
    for month, state in month_status(cache, ledger["months"]).items():
        print(f"  {month}  {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
