# Digest fuller capture — Implementation Plan

**Goal:** Make the digest count commits in `cd`'d / remote-less dirs and add a bounded,
firewalled conversational narrative — so a day's real work stops being invisible.

**Approach:** Harvest absolute `cd`/`git -C` targets from Bash tool-use and feed them into
the existing commit scan (config-free); let the scan's repo/email/window filters gate
noise; capture a truncated per-turn assistant-prose signal for the renderer; and update
`SKILL.md` to lead with a tl;dr, add a per-session descriptive narrative kept behind a
register firewall, and group remote-less commits by directory.

**Tech stack:** Python 3 (stdlib only), pytest via `uv`, Markdown skill doc.

Repo-relative paths below are under `standup-digest/`. Commit each phase as `Phase N: <name>`.

---

## Phase 1: Harvest cd/git -C dirs so their commits count (incl. remote-less repos)

Delivers end-to-end: after this phase, running the extractor over a day where work
happened in a `cd`'d sibling dir (e.g. `~/devel/zoo-service`, no GitHub remote) includes
those commits in `commits[]` with `repo: null` + a real `path`, and a stray `cd /tmp`
produces no "not a git repository" warning. No schema change (harvest is internal to
`build_digest`; commit shape is unchanged, and `repo: null` is already legal).

**Files:**
- Modify: `scripts/standup_digest.py` — add `harvest_dirs()` + `_bash_commands()` +
  `_normalize_dir()`; add `warn_non_repo` param to `Verifier.commits` and
  `GhVerifier.commits`; wire harvested dirs into `build_digest`.
- Test: `scripts/test_standup_digest.py` — harvester unit tests, warn-suppression test,
  build_digest integration test.

**Key changes:**
- `harvest_dirs(records: list[dict]) -> list[str]` — new; absolute `cd`/`git -C` targets, deduped, order-preserving.
- `_bash_commands(records) -> Iterator[str]` — new; yields Bash tool-use command strings.
- `_normalize_dir(raw: str) -> str | None` — new; expands `~`, keeps absolute only, drops `node_modules`/`.git` internals.
- `Verifier.commits(self, cwd, window, warn_non_repo=True)` and
  `GhVerifier.commits(self, cwd, window, warn_non_repo=True)` — add param; only warn on non-repo when `warn_non_repo`.

```python
# module scope, near _WRAPPER_RE
_CD_RE = re.compile(r"""\bcd\s+(?:'([^']+)'|"([^"]+)"|([^\s;&|<>]+))""")
_GIT_C_RE = re.compile(r"""\bgit\s+(?:-\S+\s+)*-C\s+(?:'([^']+)'|"([^"]+)"|([^\s;&|<>]+))""")

def _bash_commands(records):
    for rec in records:
        content = rec.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if (isinstance(block, dict) and block.get("type") == "tool_use"
                    and block.get("name") == "Bash"):
                cmd = (block.get("input") or {}).get("command")
                if isinstance(cmd, str):
                    yield cmd

def _normalize_dir(raw):
    if raw.startswith("~"):
        raw = str(Path(raw).expanduser())
    if not raw.startswith("/"):
        return None                      # relative/var paths: can't resolve, skip
    if "/node_modules/" in raw or "/.git/" in raw:
        return None
    return raw.rstrip("/") or "/"

def harvest_dirs(records):
    """Absolute dirs reached via `cd`/`git -C` in Bash calls.

    The transcript's `cwd` field only records the session launch dir; work done in a
    sibling dir via `cd`/`git -C` is otherwise invisible. Absolute paths only --
    resolving relative cds means simulating shell state across &&/; chains, and the
    absolute form dominates in practice.
    """
    dirs = {}
    for cmd in _bash_commands(records):
        for regex in (_CD_RE, _GIT_C_RE):
            for m in regex.finditer(cmd):
                raw = next(g for g in m.groups() if g is not None)
                path = _normalize_dir(raw)
                if path:
                    dirs.setdefault(path, None)
    return list(dirs)
```

```python
# GhVerifier.commits: signature + the non-repo branch
def commits(self, cwd, window, warn_non_repo=True):
    if not Path(cwd).exists():
        return []
    common = _run([...])                 # unchanged
    if common is None:
        if warn_non_repo:
            self.warnings.append(f"not a git repository, commits skipped: {cwd}")
        return []
    ...                                  # rest unchanged (email scope, log, repo_from_cwd)
```

```python
# build_digest: collect harvested dirs in the transcript loop, scan them after cwds
harvested = {}
for path in discover_transcripts(root):
    ...
    session = distill_session(transcript, window, verifier)
    for d in harvest_dirs(transcript.records):
        harvested.setdefault(d, None)
    ...
    sessions.append(session)

# after the existing session-cwds commit loop (which keeps warn_non_repo=True):
for cwd in harvested:
    if cwd in seen_paths:
        continue
    seen_paths.add(cwd)
    for commit in verifier.commits(cwd, window, warn_non_repo=False):
        if commit["sha"] in seen_shas:
            continue
        seen_shas.add(commit["sha"])
        commits.append(commit)
```

**Tests (write first, watch fail):**
```python
def test_harvest_dirs_finds_absolute_cd_and_git_C():
    recs = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input":
            {"command": "cd /Users/me/devel/zoo-service && git add -A"}},
        {"type": "tool_use", "name": "Bash", "input":
            {"command": "git -c x=y -C /Users/me/devel/other status"}},
    ]}}]
    assert sd.harvest_dirs(recs) == ["/Users/me/devel/zoo-service", "/Users/me/devel/other"]

def test_harvest_dirs_ignores_relative_vars_and_node_modules():
    recs = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command":
            'cd zoo-service; cd "$WT/x"; cd /a/node_modules/pkg'}},
    ]}}]
    assert sd.harvest_dirs(recs) == []

def test_commits_suppresses_non_repo_warning_when_asked(tmp_path, monkeypatch):
    d = tmp_path / "plain"; d.mkdir()
    monkeypatch.setattr(sd, "_run", lambda cmd, timeout=20: None)  # rev-parse -> None
    v = sd.GhVerifier()
    assert v.commits(str(d), WINDOW, warn_non_repo=False) == [] and v.warnings == []
    assert v.commits(str(d), WINDOW) == [] and len(v.warnings) == 1  # default warns

def test_build_digest_counts_harvested_remoteless_commit(tmp_path, monkeypatch):
    # transcript whose session cwd is /launch but whose Bash cd's into /work (no remote)
    work = tmp_path / "work"; work.mkdir()
    # write a minimal transcript under a tmp root (proj dir + <id>.jsonl), session
    # cwd=/launch, one assistant Bash record: "cd {work} && git commit ...", in window.
    def fake_run(cmd, timeout=20):
        if "rev-parse" in cmd: return f"{cmd[cmd.index('-C')+1]}/.git"
        if "remote" in cmd:    return None                 # no origin -> repo None
        if "config" in cmd:    return "me@example.com"
        if "log" in cmd and cmd[cmd.index('-C')+1] == str(work):
            return "abc1234\x1ffeat: thing\x1f2026-07-29T12:00:00-07:00"
        return None
    monkeypatch.setattr(sd, "_run", fake_run)
    digest = sd.build_digest(<tmp root>, <window incl 2026-07-29>, sd.GhVerifier())
    shas = {c["sha"] for c in digest["commits"]}
    assert "abc1234" in shas
    hit = next(c for c in digest["commits"] if c["sha"] == "abc1234")
    assert hit["repo"] is None and hit["path"] == str(work)
    assert not any("not a git repository" in w for w in digest["warnings"])
```
(Mirror `test_commits_scopes_author_email_per_repo:684` for the fake_run shape and the
real-dir requirement; mirror the fixture-root usage in `test_digest_matches_documented_schema:859`
for writing/pointing at a tmp transcript root. Define `WINDOW`/window via
`sd.resolve_window(local(2026,7,30), date="2026-07-29")`.)

**Verification — automated:**
- [x] `make test` passes — **76 passed** (70 prior + 6 new); no `make lint`/`check`
  target exists in this repo, `python3 -m py_compile` clean.
- [x] `uv run --with pytest pytest standup-digest/scripts -q -k "harvest or non_repo or harvested"` — **6 passed, 70 deselected**

**Verification — manual:**
- [x] Re-ran `python3 scripts/standup_digest.py --date 2026-07-29`: `commits[]` now
  contains **61** `~/devel/zoo-service` entries (was 0); the only two "not a git
  repository" warnings are pre-existing real session cwds (`~/Documents/Obsidian/main`,
  `~/devel`) — harvested dirs added **zero** spurious warnings.
- [!] "…with `repo: null`" — **does not hold on live data, not a failure.** zoo-service
  gained a `Mozilla-Ocho/zoo-service` origin remote since the spec was written, so it now
  resolves to that repo. The remote-less (`repo is None`) path is proven instead by the
  unit test `test_build_digest_counts_harvested_remoteless_commit`.

---

## Phase 2: Capture a bounded assistant-prose signal (schema v2)

Delivers: each session in the JSON carries `assistant_notes` — a short, truncated list of
the closing prose of assistant turns — giving the renderer material to describe what was
discussed/debated/decided. Bumps the schema to v2.

**Files:**
- Modify: `scripts/standup_digest.py` — add `ASSISTANT_TURN_CHAR_LIMIT`,
  `ASSISTANT_NOTES_BUDGET`, `extract_assistant_notes()`; add `assistant_notes` to
  `distill_session`; set `SCHEMA_VERSION = 2`.
- Modify: `SKILL.md` — add `assistant_notes` to the digest-contract session field list
  and note `schema_version` is now 2. (Rendering guidance is Phase 3.)
- Test: `scripts/test_standup_digest.py` — extractor unit tests; distill_session field
  test; update `SESSION_KEYS` and `test_main_writes_json_to_out` version expectation.

**Key changes:**
- `extract_assistant_notes(records, window=None, turn_limit=ASSISTANT_TURN_CHAR_LIMIT, budget=ASSISTANT_NOTES_BUDGET) -> list[str]` — new.
- `distill_session` returns new key `"assistant_notes"`.
- `SCHEMA_VERSION = 2`.
- Constants (tune in Phase 3): `ASSISTANT_TURN_CHAR_LIMIT = 600`, `ASSISTANT_NOTES_BUDGET = 3000`.

```python
def _final_text_block(rec):
    """Closing prose of one assistant record: last type=='text' block, or ''."""
    if rec.get("type") != "assistant":
        return ""
    content = rec.get("message", {}).get("content")
    if not isinstance(content, list):
        return ""
    texts = [b.get("text", "") for b in content
             if isinstance(b, dict) and b.get("type") == "text" and b.get("text")]
    return strip_wrappers(texts[-1]) if texts else ""

def extract_assistant_notes(records, window=None,
                            turn_limit=ASSISTANT_TURN_CHAR_LIMIT,
                            budget=ASSISTANT_NOTES_BUDGET):
    """Bounded per-turn assistant prose for narrative context -- NOT a transcript dump.

    The final text block of each assistant turn is where conclusions/questions land.
    Truncated per turn and capped by a total char budget so a huge transcript stays a
    paragraph or two. This is topic signal only; the renderer must not treat it as
    proof of an outcome (see SKILL.md language rules).
    """
    notes, total = [], 0
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
```
```python
# distill_session return dict: add after "prompts"
"assistant_notes": extract_assistant_notes(records, window),
```

**Tests (write first, watch fail):**
```python
def test_extract_assistant_notes_takes_final_text_block_per_turn():
    recs = [{"type": "assistant", "message": {"content": [
        {"type": "thinking", "thinking": "ignore me"},
        {"type": "text", "text": "first"},
        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
        {"type": "text", "text": "the conclusion"}]}}]
    assert sd.extract_assistant_notes(recs) == ["the conclusion"]

def test_extract_assistant_notes_truncates_and_respects_budget():
    big = "x" * 5000
    recs = [{"type": "assistant", "message": {"content": [{"type": "text", "text": big}]}}
            for _ in range(3)]
    notes = sd.extract_assistant_notes(recs, turn_limit=600, budget=1000)
    assert all(n.endswith(sd.TRUNCATION_MARKER) for n in notes)
    assert sum(len(n) for n in notes) <= 1000 + len(sd.TRUNCATION_MARKER)

def test_distill_session_includes_assistant_notes():
    # a transcript with one in-window assistant text turn
    got = sd.distill_session(t, window, sd.NullVerifier())
    assert got["assistant_notes"] == ["...the turn's closing prose..."]
```
```python
# update the conformance contract
SESSION_KEYS = { ... , "prompts", "assistant_notes", "refs" }
# test_main_writes_json_to_out already asserts == sd.SCHEMA_VERSION (now 2), no edit needed
```

**Verification — automated:**
- [x] `make test` passes — **81 passed** (76 prior + 5 new); `SESSION_KEYS` updated;
  `test_digest_matches_documented_schema` green with `assistant_notes`. `py_compile` clean.
- [x] `uv run --with pytest pytest standup-digest/scripts -q -k "assistant_notes or documented_schema or main_writes"` — **7 passed**

**Verification — manual:**
- [x] Re-ran over 2026-07-29 (`--no-verify`, since `assistant_notes` is verifier-
  independent): zoo session = **7 turns / 2467 chars**, capturing the design arc
  (brainstorm → repo read → "network appliance with two ports" reframe). Every session
  is bounded — max **2994 chars** across all 16, the budget cap holding. No ballooning.

---

## Phase 3: Renderer + language firewall in SKILL.md (doc-only, TDD opt-out)

Delivers the reader-facing change: the detail file opens with a tl;dr; each session gets
a descriptive "what you worked through" narrative separated from commit/ref-backed "what
shipped"; remote-less commits group by directory; the terminal carries more texture; and
a register-firewall rule keeps conversational text from ever licensing an outcome claim.

*TDD opt-out:* prose/skill-doc change with no runtime behavior; verified by regenerating a
real digest and eyeballing, not by unit tests.

**Files:**
- Modify: `SKILL.md` — `## The digest contract` (already notes `assistant_notes`/v2 from
  Phase 2); `## Language rules` (+register firewall); `## Output` (tl;dr-first detail
  file, per-session narrative, remote-less grouping, richer terminal).

**Key changes (SKILL.md edits):**
- **Language rules — add:**
  > **Conversation is topic signal, not proof.** `prompts` and `assistant_notes` describe
  > what was discussed, debated, and decided — render them in a *descriptive* register
  > ("worked through", "went back and forth on", "landed on X in discussion"). They never,
  > on their own, license outcome language ("shipped/landed/merged/fixed/closed"), which
  > still requires a `commits[]` entry or a `confirmed` ref. `assistant_notes` in
  > particular may contain aspirational completion claims — treat them as claims, not
  > facts.
- **Output — detail file:** lead with `## tl;dr` (the same significance-ranked bullets as
  the terminal), then per-project sections. Each session gets two labeled parts:
  *"what you worked through"* (descriptive, from `prompts` + `assistant_notes`) and
  *"what shipped"* (only commit/ref-backed items). Group `commits[]` with `repo: null`
  under a heading from the directory basename of `path`, e.g.
  `zoo-service (local, no remote)`.
- **Output — terminal:** keep 3-4 significance-ranked, ref-annotated bullets, but allow a
  short themes line ("threads today: …") drawn from conversation signal, clearly
  descriptive. The terminal bullets are exactly what leads the detail file's tl;dr.
- Refresh the worked example to show a remote-less project and a "what you worked
  through" block, replacing the stale `~/.claude/standup` example line.

**Verification — automated:**
- [x] `make test` still passes — **81 passed** (SKILL.md-only change; guards clean).

**Verification — manual:**
- [x] Regenerated the 2026-07-29 digest end-to-end into
  `~/Documents/Obsidian/main/standup-digests/2026-07-29.md`: tl;dr on top; zoo-service
  leads it as a commit-backed item (61 commits + the_zoo PRs #123/#609/#638); each
  session splits "what you worked through" (descriptive) from "what shipped"
  (commit/ref-backed). (zoo-service resolved to a real remote, so it grouped under
  `Mozilla-Ocho/zoo-service` rather than the "local, no remote" heading — that path is
  still covered by the unit test.)
- [x] Spot-checked descussion-only content: the "what you worked through" bullets use only
  descriptive verbs ("debated", "resisted", "worked the naming"); no outcome verbs leak in.
- [x] Les eyeballed the regenerated digest and signed off on texture + register split
  (2026-07-31).

---

## Plan self-review

- **Spec coverage:** end-state (1) relocation = already on branch (Part 1), reaffirmed in
  P3 example; (2) harvest = P1; (3) remote-less counts = P1 (data) + P3 (grouping);
  (4) assistant narrative = P2; (5) renderer/tl;dr/firewall/terminal = P3; (6) schema v2
  = P2. All covered.
- **Placeholder scan:** no TBD/TODO; constants have concrete starting values (tuned in
  P3); every test shows real assertions.
- **Type consistency:** `harvest_dirs`/`_bash_commands`/`_normalize_dir` (P1),
  `extract_assistant_notes`/`_final_text_block` + `assistant_notes` key + `SCHEMA_VERSION=2`
  (P2), `SESSION_KEYS` updated once (P2) — names consistent across phases and matching the
  conformance test.
- **Open question:** char budgets (`ASSISTANT_TURN_CHAR_LIMIT`/`ASSISTANT_NOTES_BUDGET`)
  start at 600/3000 and are dialed in during P3 manual verification — non-blocking as the
  spec states.
