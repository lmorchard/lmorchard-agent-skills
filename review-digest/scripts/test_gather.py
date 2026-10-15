import json
import re
from datetime import date
from pathlib import Path

import gather as g
import pytest

TEMPLATE = """# daily
- [ ] exercise for 30 minutes

# today
- [x] ship it
- [ ] not yet

# tonight

# [[someday]]
- [ ] someday thing

# TIL
- learned a thing

# notes
- loose note before any section

## alpha
alpha body

## beta
beta body
"""

CONFIG = {
    "levels": {"current": "L4", "target": "L5"},
    "clg_path": "pages/reviews/levels.md",
    "prior_review_path": "pages/reviews/prior.md",
    "work_orgs": ["work-org"],
    "tooling_repos": ["me/tool"],
    "linear_teams": [],
    "heading_denylist": ["^therapy$"],
    "overrides": {},
}

D = date(2026, 8, 14)


@pytest.fixture(autouse=True)
def no_real_subprocess(monkeypatch):
    """Any test that reaches _run without faking it fails instead of calling
    the real gh or gws."""

    def refuse(cmd, timeout=60):
        raise AssertionError(f"unfaked subprocess: {cmd}")

    monkeypatch.setattr(g, "_run", refuse)


def deny(*patterns):
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def ids(items):
    return [i["id"] for i in items]


def make_vault(tmp_path, monkeypatch, config=None, journals=None):
    vault = tmp_path / "vault"
    (vault / "pages" / "reviews").mkdir(parents=True)
    if config is not False:
        (vault / g.CONFIG_REL).write_text(json.dumps(config or CONFIG))
    for day, text in (journals or {}).items():
        path = vault / "journals" / day[:4] / f"{day}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    monkeypatch.setenv(g.VAULT_ENV, str(vault))
    return vault


# --- resolve_cycle ---------------------------------------------------------


def test_resolve_cycle_h2_caps_at_tomorrow():
    w = g.resolve_cycle("2026-H2", date(2026, 10, 15))
    assert (w.since, w.until) == (date(2026, 7, 1), date(2026, 10, 16))


def test_resolve_cycle_h1_full():
    w = g.resolve_cycle("2026-H1", date(2026, 12, 1))
    assert (w.since, w.until) == (date(2026, 1, 1), date(2026, 7, 1))


def test_resolve_cycle_overrides():
    w = g.resolve_cycle(
        "2026-H2", date(2026, 12, 1), since="2026-08-01", until="2026-09-01"
    )
    assert (w.since, w.until) == (date(2026, 8, 1), date(2026, 9, 1))


@pytest.mark.parametrize("bad", ["2026-Q3", "H2", "2026-H3"])
def test_resolve_cycle_rejects_bad_string(bad):
    with pytest.raises(ValueError):
        g.resolve_cycle(bad, date(2026, 10, 15))


def test_resolve_cycle_rejects_empty_window():
    with pytest.raises(ValueError):
        g.resolve_cycle(
            "2026-H2", date(2026, 10, 15), since="2026-09-01", until="2026-09-01"
        )


# --- parse_journal ---------------------------------------------------------


def test_parse_journal_keeps_notes_sections_and_til():
    items, dropped = g.parse_journal(D, TEMPLATE, deny())
    assert ids(items) == [
        "t:2026-08-14",
        "j:2026-08-14#til",
        "j:2026-08-14#notes",
        "j:2026-08-14#alpha",
        "j:2026-08-14#beta",
    ]
    assert dropped == 0
    assert not any("exercise" in i["text"] or "someday" in i["text"] for i in items)
    alpha = items[3]
    assert alpha["title"] == "alpha"
    assert alpha["text"].strip() == "alpha body"
    assert alpha["source"] == "journal"
    assert alpha["date"] == "2026-08-14"
    assert alpha["meta"]["path"] == "journals/2026/2026-08-14"


def test_parse_journal_collects_completed_tasks():
    items, _ = g.parse_journal(D, TEMPLATE, deny())
    tasks = [i for i in items if i["source"] == "tasks"]
    assert len(tasks) == 1
    assert "ship it" in tasks[0]["text"]
    assert "not yet" not in tasks[0]["text"]


def test_parse_journal_denylist_drops_section():
    text = TEMPLATE + "\n## Therapy\nprivate stuff\n\n## gamma\ngamma body\n"
    items, dropped = g.parse_journal(D, text, deny("^therapy$"))
    assert dropped == 1
    assert not any("private stuff" in i["text"] for i in items)
    assert "j:2026-08-14#gamma" in ids(items)


def test_parse_journal_slug_handles_wikilinks_and_dupes():
    text = "# notes\n## 1:1 w/ [[people/x|x y]]\na\n## standup\nb\n## standup\nc\n"
    items, _ = g.parse_journal(D, text, deny())
    assert ids(items) == [
        "j:2026-08-14#1-1-w-x-y",
        "j:2026-08-14#standup",
        "j:2026-08-14#standup-2",
    ]


def test_slugify():
    assert g.slugify("[[zoo-service]] staging") == "zoo-service-staging"
    assert g.slugify("  Hello, World!  ") == "hello-world"
    assert len(g.slugify("x" * 100)) == 60


def test_parse_journal_truncates_long_section():
    text = "# notes\n## long\n" + ("y" * 7000) + "\n"
    items, _ = g.parse_journal(D, text, deny())
    assert items[0]["text"].endswith("[…truncated]")
    assert items[0]["meta"]["truncated"] is True
    assert len(items[0]["text"]) < 7000


def test_parse_journal_empty_template_yields_nothing():
    text = "# daily\n- [ ] x\n\n# TIL\n\n# notes\n\n"
    items, _ = g.parse_journal(D, text, deny())
    assert items == []


# --- ledger / main ---------------------------------------------------------


def test_override_sets_tier():
    items, _ = g.parse_journal(D, TEMPLATE, deny())
    config = g.Config(**{**CONFIG, "overrides": {"j:2026-08-14#alpha": "personal"}})
    window = g.Window(date(2026, 7, 1), date(2026, 10, 16))
    ledger = g.build_ledger(config, window, "2026-H2", items, [], [])
    tiers = {i["id"]: i["tier"] for i in ledger["items"]}
    assert tiers["j:2026-08-14#alpha"] == "personal"
    assert tiers["j:2026-08-14#beta"] == "unclassified"


def test_main_writes_ledger(tmp_path, monkeypatch):
    make_vault(
        tmp_path,
        monkeypatch,
        journals={"2026-08-14": TEMPLATE, "2026-06-30": TEMPLATE},
    )
    cache = tmp_path / "cache"
    rc = g.main(
        [
            "--cycle",
            "2026-H2",
            "--until",
            "2026-10-16",
            "--cache",
            str(cache),
            "--no-github",
            "--no-gws",
        ],
        today=date(2026, 10, 15),
    )
    assert rc == 0
    ledger = json.loads((cache / "ledger.json").read_text())
    assert ledger["schema_version"] == 1
    assert ledger["cycle"] == "2026-H2"
    assert ledger["window"] == {"since": "2026-07-01", "until": "2026-10-16"}
    assert all(i["date"] >= "2026-07-01" for i in ledger["items"] if i["date"])
    assert "j:2026-08-14#alpha" in ids(ledger["items"])


def test_main_missing_config_exits_2(tmp_path, monkeypatch, capsys):
    make_vault(tmp_path, monkeypatch, config=False)
    rc = g.main(
        [
            "--cycle",
            "2026-H2",
            "--cache",
            str(tmp_path / "c"),
            "--no-github",
            "--no-gws",
        ]
    )
    assert rc == 2
    assert "config.example.json" in capsys.readouterr().err


def test_main_denylist_note(tmp_path, monkeypatch):
    make_vault(
        tmp_path,
        monkeypatch,
        journals={"2026-08-14": TEMPLATE + "\n## therapy\nsecret\n"},
    )
    cache = tmp_path / "cache"
    g.main(
        ["--cycle", "2026-H2", "--cache", str(cache), "--no-github", "--no-gws"],
        today=date(2026, 10, 15),
    )
    ledger = json.loads((cache / "ledger.json").read_text())
    assert any("heading_denylist" in n for n in ledger["notes"])
    assert "secret" not in json.dumps(ledger)


LEDGER_KEYS = {
    "schema_version",
    "cycle",
    "window",
    "generated_at",
    "items",
    "warnings",
    "notes",
    "months",
}


def test_ledger_top_level_keys():
    window = g.Window(date(2026, 7, 1), date(2026, 10, 16))
    ledger = g.build_ledger(g.Config(**CONFIG), window, "2026-H2", [], [], [])
    assert set(ledger) == LEDGER_KEYS


# --- digests and docs (phase 2) --------------------------------------------

GDOC = "https://docs.google.com/document/d/AbC123_xyz-9/edit?usp=sharing"


def test_collect_digests_in_window_only(tmp_path):
    d = tmp_path / "standup-digests"
    d.mkdir()
    (d / "2026-08-14.md").write_text("## tl;dr\n- did a thing\n")
    (d / "2026-06-30.md").write_text("old")
    (d / "notes.md").write_text("not a digest")
    window = g.Window(date(2026, 7, 1), date(2026, 10, 16))
    items = g.collect_digests(tmp_path, window)
    assert ids(items) == ["sd:2026-08-14"]
    assert items[0]["source"] == "digest"
    assert "did a thing" in items[0]["text"]
    assert items[0]["meta"]["path"] == "standup-digests/2026-08-14"


def test_extract_doc_links_dedupes_and_records_mentions():
    a, _ = g.parse_journal(
        date(2026, 8, 14), f"# notes\n## rfc\nwrote {GDOC} today\n", deny()
    )
    b, _ = g.parse_journal(
        date(2026, 9, 2), f"# notes\n## followup\nsee {GDOC}\n", deny()
    )
    docs = g.extract_doc_links(a + b)
    assert ids(docs) == ["doc:AbC123_xyz-9"]
    doc = docs[0]
    assert doc["date"] == "2026-08-14"
    assert doc["url"] == "https://docs.google.com/document/d/AbC123_xyz-9"
    assert doc["meta"]["mentions"] == ["j:2026-08-14#rfc", "j:2026-09-02#followup"]
    assert doc["meta"]["origin"] == "journal"
    assert "wrote" in doc["text"]


def test_extract_doc_links_ignores_denylisted_sections():
    items, _ = g.parse_journal(
        date(2026, 8, 14), f"# notes\n## therapy\n{GDOC}\n", deny("therapy")
    )
    assert g.extract_doc_links(items) == []


def test_parse_docs_md_with_and_without_date():
    text = (
        "# my docs\n"
        f"- [Design RFC]({GDOC}) — the big one (2026-09-12)\n"
        "- [Wiki page](https://wiki.example.com/x) — notes\n"
        "not a list line\n"
    )
    docs = g.parse_docs_md(text)
    assert len(docs) == 2
    rfc, wiki = docs
    assert rfc["id"] == "doc:AbC123_xyz-9"
    assert rfc["title"] == "Design RFC"
    assert rfc["date"] == "2026-09-12"
    assert rfc["text"] == "the big one"
    assert rfc["tier"] == "work"
    assert wiki["id"].startswith("doc:") and len(wiki["id"]) == 14
    assert wiki["date"] is None
    assert wiki["meta"]["origin"] == "docs.md"


def test_merge_docs_prefers_docs_md_title_and_keeps_mentions():
    journal, _ = g.parse_journal(
        date(2026, 8, 14), f"# notes\n## rfc\n{GDOC}\n", deny()
    )
    found = g.extract_doc_links(journal)
    listed = g.parse_docs_md(f"- [Design RFC]({GDOC}) — the big one\n")
    merged = g.merge_docs(found, listed)
    assert len(merged) == 1
    doc = merged[0]
    assert doc["title"] == "Design RFC"
    assert doc["text"] == "the big one"
    assert doc["date"] == "2026-08-14"
    assert doc["meta"]["mentions"] == ["j:2026-08-14#rfc"]
    assert doc["tier"] == "work"


def test_main_includes_digests_and_docs(tmp_path, monkeypatch):
    vault = make_vault(
        tmp_path,
        monkeypatch,
        journals={"2026-08-14": f"# notes\n## rfc\n{GDOC}\n"},
    )
    (vault / "standup-digests").mkdir()
    (vault / "standup-digests" / "2026-08-15.md").write_text("digest body")
    cache = tmp_path / "cache"
    g.main(
        ["--cycle", "2026-H2", "--cache", str(cache), "--no-github", "--no-gws"],
        today=date(2026, 10, 15),
    )
    ledger = json.loads((cache / "ledger.json").read_text())
    assert {"sd:2026-08-15", "doc:AbC123_xyz-9"} <= set(ids(ledger["items"]))
    assert any("docs.md" in n for n in ledger["notes"])


# --- github (phase 3) ------------------------------------------------------


def pr(
    repo,
    number,
    state="merged",
    closed="2026-08-20T10:00:00Z",
    created="2026-08-19T10:00:00Z",
    author="me",
):
    owner, name = repo.split("/")
    return {
        "number": number,
        "repository": {"name": name, "nameWithOwner": repo},
        "state": state,
        "title": f"PR {number}",
        "url": f"https://github.com/{repo}/pull/{number}",
        "closedAt": closed if state == "merged" else None,
        "createdAt": created,
        "author": {"login": author},
    }


def fake_gh(merged_author=(), merged_reviewed=(), open_author=(), fail=False):
    calls = []

    def fake(cmd, timeout=60):
        calls.append(cmd)
        if fail:
            return None
        assert cmd[:3] == ["gh", "search", "prs"]
        if "--state" in cmd:
            return json.dumps(list(open_author))
        rng = cmd[cmd.index("--merged-at") + 1]
        role_list = merged_author if "--author=@me" in cmd else merged_reviewed
        return json.dumps([p for p in role_list if rng.startswith(p["closedAt"][:7])])

    fake.calls = calls
    return fake


WINDOW = g.Window(date(2026, 7, 1), date(2026, 10, 16))


def test_month_ranges_clips_to_window():
    assert g.month_ranges(WINDOW) == [
        (date(2026, 7, 1), date(2026, 7, 31)),
        (date(2026, 8, 1), date(2026, 8, 31)),
        (date(2026, 9, 1), date(2026, 9, 30)),
        (date(2026, 10, 1), date(2026, 10, 15)),
    ]


def test_collect_github_tiers_and_excludes(monkeypatch):
    fake = fake_gh(
        merged_author=[pr("work-org/api", 1), pr("me/tool", 2), pr("me/hobby", 3)],
        merged_reviewed=[pr("work-org/api", 9, author="colleague")],
    )
    monkeypatch.setattr(g, "_run", fake)
    warnings, notes = [], []
    items = g.collect_github(g.Config(**CONFIG), WINDOW, warnings, notes)
    by_id = {i["id"]: i for i in items}
    assert set(by_id) == {"gh:work-org/api#1", "gh:me/tool#2", "gh:work-org/api#9"}
    assert by_id["gh:work-org/api#1"]["tier"] == "work"
    assert by_id["gh:me/tool#2"]["tier"] == "tooling"
    reviewed = by_id["gh:work-org/api#9"]
    assert reviewed["meta"]["role"] == "reviewer"
    assert reviewed["meta"]["pr_author"] == "colleague"
    assert reviewed["date"] == "2026-08-20"
    assert reviewed["source"] == "github"
    assert reviewed["url"] == "https://github.com/work-org/api/pull/9"
    assert any("excluded 1 PRs from 1 repos" in n for n in notes)
    assert warnings == []
    assert len(fake.calls) == 9  # 4 months x 2 roles + 1 open search


def test_collect_github_open_prs_dated_by_created(monkeypatch):
    open_prs = [
        pr("work-org/api", 5, state="open", created="2026-10-01T00:00:00Z"),
        pr("work-org/api", 6, state="open", created="2026-10-20T00:00:00Z"),
    ]
    monkeypatch.setattr(g, "_run", fake_gh(open_author=open_prs))
    items = g.collect_github(g.Config(**CONFIG), WINDOW, [], [])
    assert ids(items) == ["gh:work-org/api#5"]
    assert items[0]["date"] == "2026-10-01"
    assert items[0]["meta"]["state"] == "open"


def test_collect_github_failure_warns(monkeypatch):
    monkeypatch.setattr(g, "_run", fake_gh(fail=True))
    warnings = []
    assert g.collect_github(g.Config(**CONFIG), WINDOW, warnings, []) == []
    assert warnings and all("gh search failed" in w for w in warnings)


def test_collect_github_cap_warns(monkeypatch):
    many = [pr("work-org/api", n) for n in range(1000)]
    monkeypatch.setattr(g, "_run", fake_gh(merged_author=many))
    warnings = []
    g.collect_github(g.Config(**CONFIG), WINDOW, warnings, [])
    assert any("1000-result cap" in w for w in warnings)


def test_collect_github_bad_json_warns(monkeypatch):
    monkeypatch.setattr(g, "_run", lambda cmd, timeout=60: "not json")
    warnings = []
    g.collect_github(g.Config(**CONFIG), WINDOW, warnings, [])
    assert any("unparseable" in w for w in warnings)


def test_main_no_github_never_calls_run(tmp_path, monkeypatch):
    make_vault(tmp_path, monkeypatch, journals={"2026-08-14": TEMPLATE})

    def boom(cmd, timeout=60):
        raise AssertionError(f"unexpected subprocess: {cmd}")

    monkeypatch.setattr(g, "_run", boom)
    rc = g.main(
        [
            "--cycle",
            "2026-H2",
            "--cache",
            str(tmp_path / "c"),
            "--no-github",
            "--no-gws",
        ],
        today=date(2026, 10, 15),
    )
    assert rc == 0


def test_collect_github_skips_open_prs_created_before_window(monkeypatch):
    stale = pr("work-org/api", 7, state="open", created="2014-01-24T00:00:00Z")
    monkeypatch.setattr(g, "_run", fake_gh(open_author=[stale]))
    assert g.collect_github(g.Config(**CONFIG), WINDOW, [], []) == []


# --- linear (phase 4) ------------------------------------------------------


def linear_issue(
    id_, status="completed", completed="2026-09-01T10:00:00Z", team="Core"
):
    return {
        "id": id_,
        "title": f"issue {id_}",
        "statusType": status,
        "completedAt": completed,
        "project": "Proj",
        "team": team,
        "url": f"https://linear.app/x/issue/{id_}",
    }


def test_load_linear_skips_canceled_and_other_teams(tmp_path):
    path = tmp_path / "linear.json"
    path.write_text(
        json.dumps(
            [
                linear_issue("ABC-1"),
                linear_issue("ABC-2", status="canceled", completed=None),
                linear_issue("XYZ-3", team="Other"),
            ]
        )
    )
    notes = []
    config = g.Config(**{**CONFIG, "linear_teams": ["Core"]})
    items = g.load_linear(path, config, notes, [])
    assert ids(items) == ["lin:ABC-1"]
    item = items[0]
    assert item["source"] == "linear"
    assert item["date"] == "2026-09-01"
    assert item["tier"] == "work"
    assert item["url"] == "https://linear.app/x/issue/ABC-1"
    assert item["meta"] == {"status": "completed", "project": "Proj", "team": "Core"}
    assert any("1 canceled or duplicate" in n for n in notes)
    assert any("1 from teams not in linear_teams" in n for n in notes)


def test_load_linear_all_teams_when_list_empty(tmp_path):
    path = tmp_path / "linear.json"
    path.write_text(json.dumps([linear_issue("XYZ-3", team="Other")]))
    assert ids(g.load_linear(path, g.Config(**CONFIG), [], [])) == ["lin:XYZ-3"]


def test_load_linear_undated_when_not_completed(tmp_path):
    path = tmp_path / "linear.json"
    path.write_text(
        json.dumps([linear_issue("ABC-9", status="started", completed=None)])
    )
    items = g.load_linear(path, g.Config(**CONFIG), [], [])
    assert items[0]["date"] is None
    assert items[0]["meta"]["status"] == "started"


def test_main_warns_without_linear(tmp_path, monkeypatch):
    make_vault(tmp_path, monkeypatch, journals={"2026-08-14": TEMPLATE})
    cache = tmp_path / "cache"
    g.main(
        ["--cycle", "2026-H2", "--cache", str(cache), "--no-github", "--no-gws"],
        today=date(2026, 10, 15),
    )
    ledger = json.loads((cache / "ledger.json").read_text())
    assert any("no Linear data" in w for w in ledger["warnings"])


def test_main_reads_linear_from_cache(tmp_path, monkeypatch):
    make_vault(tmp_path, monkeypatch, journals={"2026-08-14": TEMPLATE})
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "linear.json").write_text(json.dumps([linear_issue("ABC-1")]))
    g.main(
        ["--cycle", "2026-H2", "--cache", str(cache), "--no-github", "--no-gws"],
        today=date(2026, 10, 15),
    )
    ledger = json.loads((cache / "ledger.json").read_text())
    assert "lin:ABC-1" in ids(ledger["items"])
    assert not any("no Linear data" in w for w in ledger["warnings"])


# --- month slices (phase 5) ------------------------------------------------


def sample_items():
    journal, _ = g.parse_journal(date(2026, 8, 14), TEMPLATE, deny())
    gh_work = {
        "id": "gh:work-org/api#1",
        "source": "github",
        "date": "2026-08-20",
        "tier": "work",
        "title": "Add thing",
        "text": "",
        "url": "https://x/1",
        "meta": {
            "role": "author",
            "state": "merged",
            "repo": "work-org/api",
            "pr_author": "me",
        },
    }
    gh_review = {
        **gh_work,
        "id": "gh:work-org/api#2",
        "title": "Their thing",
        "meta": {**gh_work["meta"], "role": "reviewer", "pr_author": "pal"},
    }
    tooling = [
        {
            **gh_work,
            "id": f"gh:me/tool#{n}",
            "tier": "tooling",
            "title": f"tool {n}",
            "meta": {**gh_work["meta"], "repo": "me/tool"},
        }
        for n in range(8)
    ]
    undated = {
        "id": "lin:ABC-9",
        "source": "linear",
        "date": None,
        "tier": "work",
        "title": "open issue",
        "text": "",
        "url": "https://l/9",
        "meta": {"status": "started", "project": "P", "team": "T"},
    }
    return journal + [gh_work, gh_review, undated] + tooling


def test_month_key():
    assert g.month_key({"date": "2026-08-14"}) == "2026-08"
    assert g.month_key({"date": None}) == "undated"


def test_render_month_is_deterministic():
    items = sample_items()
    a = g.render_month("2026-H2", "2026-08", items)
    b = g.render_month("2026-H2", "2026-08", list(reversed(items)))
    assert a == b


def test_render_month_orders_and_collapses_prs():
    body = g.render_month("2026-H2", "2026-08", sample_items())
    sections = [line for line in body.splitlines() if line.startswith("## ")]
    assert sections == [
        "## Journal sections",
        "## Completed tasks",
        "## GitHub PRs — authored (work)",
        "## GitHub PRs — reviewed",
        "## GitHub PRs — tooling (collapsed)",
        "## Linear issues",
    ]
    assert "### j:2026-08-14#alpha — 2026-08-14 — alpha [tier: unclassified]" in body
    assert "gh:work-org/api#1" in body
    assert "pal" in body  # reviewed PR author shown
    assert "me/tool: 8 PRs" in body
    assert body.count("tool ") <= 5 + 1  # at most 5 sample titles


def test_input_hash_changes_with_override():
    items = sample_items()
    before = g.input_hash(g.render_month("2026-H2", "2026-08", items))
    items[0]["tier"] = "personal"
    after = g.input_hash(g.render_month("2026-H2", "2026-08", items))
    assert before != after


def test_input_hash_changes_with_prompt_version(monkeypatch):
    body = g.render_month("2026-H2", "2026-08", sample_items())
    before = g.input_hash(body)
    monkeypatch.setattr(g, "PROMPT_VERSION", g.PROMPT_VERSION + 1)
    assert g.input_hash(body) != before


def test_write_months_and_status(tmp_path):
    months = g.write_months(tmp_path, "2026-H2", sample_items())
    assert set(months) == {"2026-08", "undated"}
    path = tmp_path / "months" / "2026-08.input.md"
    text = path.read_text()
    assert text.startswith("---\ncycle: 2026-H2\nmonth: 2026-08\n")
    assert f"input_hash: {months['2026-08']['input_hash']}" in text
    assert months["2026-08"]["items"] == len(sample_items()) - 1

    status = g.month_status(tmp_path, months)
    assert status == {"2026-08": "missing", "undated": "missing"}

    extract = tmp_path / "months" / "2026-08.extract.md"
    extract.write_text(
        f"---\ninput_hash: {months['2026-08']['input_hash']}\n---\nbody\n"
    )
    (tmp_path / "months" / "undated.extract.md").write_text(
        "---\ninput_hash: old\n---\n"
    )
    assert g.month_status(tmp_path, months) == {"2026-08": "fresh", "undated": "stale"}


def test_write_months_removes_slices_no_longer_present(tmp_path):
    g.write_months(tmp_path, "2026-H2", sample_items())
    stale = tmp_path / "months" / "2026-07.input.md"
    stale.write_text("old slice")
    g.write_months(tmp_path, "2026-H2", sample_items())
    assert not stale.exists()


def test_prompt_file_version_matches_constant():
    prompt = (
        Path(g.__file__).parent.parent / "prompts" / "month-extract.md"
    ).read_text()
    assert f"prompt_version: {g.PROMPT_VERSION}" in prompt


def test_main_writes_months_and_ledger_index(tmp_path, monkeypatch, capsys):
    make_vault(tmp_path, monkeypatch, journals={"2026-08-14": TEMPLATE})
    cache = tmp_path / "cache"
    g.main(
        ["--cycle", "2026-H2", "--cache", str(cache), "--no-github", "--no-gws"],
        today=date(2026, 10, 15),
    )
    ledger = json.loads((cache / "ledger.json").read_text())
    assert set(ledger["months"]) == {"2026-08"}
    assert (cache / "months" / "2026-08.input.md").exists()
    assert "2026-08  missing" in capsys.readouterr().out


def test_parse_journal_splits_til_sections_like_notes():
    text = "# TIL\n- loose til\n\n## wideboi deadlock\nbody\n\n## therapy\nx\n\n# notes\n## alpha\na\n"
    items, dropped = g.parse_journal(D, text, deny("therapy"))
    assert ids(items) == [
        "j:2026-08-14#til",
        "j:2026-08-14#wideboi-deadlock",
        "j:2026-08-14#alpha",
    ]
    assert dropped == 1


def test_parse_journal_til_and_notes_slugs_dont_collide():
    text = "# TIL\n## standup\na\n# notes\n## standup\nb\n"
    items, _ = g.parse_journal(D, text, deny())
    assert ids(items) == ["j:2026-08-14#standup", "j:2026-08-14#standup-2"]


def test_render_month_demotes_embedded_headings():
    item = {
        "id": "sd:2026-08-14",
        "source": "digest",
        "date": "2026-08-14",
        "tier": "unclassified",
        "title": "standup digest",
        "text": "# Title\n## tl;dr\n#### deep\nplain #hashtag",
        "url": None,
        "meta": {},
    }
    body = g.render_month("2026-H2", "2026-08", [item])
    assert [ln for ln in body.splitlines() if ln.startswith("## ")] == [
        "## Standup digests"
    ]
    assert "#### Title" in body
    assert "##### tl;dr" in body
    assert "###### deep" in body
    assert "plain #hashtag" in body


# --- gws docs (phase 8, moved ahead of the real run) -----------------------


def drive_file(
    fid,
    name,
    created="2026-08-01T00:00:00Z",
    modified="2026-09-01T00:00:00Z",
    me=True,
    owner="Me",
):
    return {
        "id": fid,
        "name": name,
        "mimeType": "application/vnd.google-apps.document",
        "createdTime": created,
        "modifiedTime": modified,
        "webViewLink": f"https://docs.google.com/document/d/{fid}/edit",
        "owners": [{"displayName": owner, "me": me}],
    }


def fake_gws(owned=(), files=None, comments=None, fail_list=False):
    files = files or {}
    comments = comments or {}

    def fake(cmd, timeout=60):
        assert cmd[0] == "gws"
        params = json.loads(cmd[cmd.index("--params") + 1])
        if cmd[1:4] == ["drive", "files", "list"]:
            if fail_list:
                return None
            assert "--page-all" in cmd
            return (
                "\n".join(
                    json.dumps({"files": list(owned)[i : i + 1]})
                    for i in range(len(owned))
                )
                + "\n"
            )
        if cmd[1:4] == ["drive", "files", "get"]:
            f = files.get(params["fileId"])
            return json.dumps(f) if f else None
        if cmd[1:4] == ["drive", "comments", "list"]:
            return json.dumps({"comments": comments.get(params["fileId"], [])})
        raise AssertionError(cmd)

    return fake


def comment(me, replies=(), created="2026-08-01T00:00:00Z"):
    return {
        "author": {"me": me},
        "createdTime": created,
        "replies": [{"author": {"me": r}, "createdTime": created} for r in replies],
    }


def test_collect_gws_docs_lists_owned_with_comment_counts(monkeypatch):
    owned = [drive_file("RFC1", "RFC — fleet design", created="2026-09-10T00:00:00Z")]
    monkeypatch.setattr(
        g,
        "_run",
        fake_gws(
            owned=owned,
            comments={"RFC1": [comment(False, [True]), comment(False), comment(True)]},
        ),
    )
    warnings, notes = [], []
    docs = g.collect_gws_docs(WINDOW, [], warnings, notes)
    assert ids(docs) == ["doc:RFC1"]
    doc = docs[0]
    assert doc["title"] == "RFC — fleet design"
    assert doc["date"] == "2026-09-10"
    assert doc["tier"] == "unclassified"
    assert doc["url"] == "https://docs.google.com/document/d/RFC1/edit"
    assert doc["meta"]["origin"] == "gws"
    assert doc["meta"]["owned"] is True
    assert doc["meta"]["comments"] == {"by_me": 2, "by_others": 2}
    assert warnings == []


def test_collect_gws_docs_dates_by_modified_when_created_before_window(monkeypatch):
    owned = [
        drive_file(
            "OLD",
            "old doc",
            created="2025-01-01T00:00:00Z",
            modified="2026-08-05T00:00:00Z",
        )
    ]
    monkeypatch.setattr(g, "_run", fake_gws(owned=owned))
    docs = g.collect_gws_docs(WINDOW, [], [], [])
    assert docs[0]["date"] == "2026-08-05"


def test_collect_gws_docs_enriches_known_docs(monkeypatch):
    known, _ = g.parse_journal(
        date(2026, 9, 24), f"# notes\n## strat\n{GDOC}\n", deny()
    )
    journal_docs = g.extract_doc_links(known)
    files = {
        "AbC123_xyz-9": drive_file(
            "AbC123_xyz-9", "Strategy rec", me=False, owner="Pal"
        )
    }
    monkeypatch.setattr(
        g, "_run", fake_gws(files=files, comments={"AbC123_xyz-9": [comment(True)]})
    )
    docs = g.collect_gws_docs(WINDOW, journal_docs, [], [])
    assert ids(docs) == ["doc:AbC123_xyz-9"]
    meta = docs[0]["meta"]
    assert docs[0]["title"] == "Strategy rec"
    assert meta["owned"] is False
    assert meta["owner"] == "Pal"
    assert meta["comments"] == {"by_me": 1, "by_others": 0}


def test_collect_gws_missing_warns(monkeypatch):
    monkeypatch.setattr(g, "_run", fake_gws(fail_list=True))
    warnings = []
    assert g.collect_gws_docs(WINDOW, [], warnings, []) == []
    assert warnings == [
        "gws unavailable; Docs come from journal links and docs.md only"
    ]


def test_collect_gws_counts_per_file_failures(monkeypatch):
    known, _ = g.parse_journal(
        date(2026, 9, 24), f"# notes\n## strat\n{GDOC}\n", deny()
    )
    monkeypatch.setattr(g, "_run", fake_gws(files={}))
    notes = []
    docs = g.collect_gws_docs(WINDOW, g.extract_doc_links(known), [], notes)
    assert docs == []
    assert any("gws could not read 1 known docs" in n for n in notes)


def test_merge_gws_docs_keeps_docs_md_title_and_journal_mentions():
    journal, _ = g.parse_journal(
        date(2026, 9, 24), f"# notes\n## strat\n{GDOC}\n", deny()
    )
    docs = g.merge_docs(
        g.extract_doc_links(journal), g.parse_docs_md(f"- [My title]({GDOC}) — n\n")
    )
    gws_doc = g._doc_item(
        "AbC123_xyz-9",
        date(2026, 9, 1),
        "Drive title",
        "",
        "https://x",
        {
            "origin": "gws",
            "owned": True,
            "owner": "Me",
            "comments": {"by_me": 0, "by_others": 3},
        },
    )
    merged = g.merge_gws_docs(docs, [gws_doc])
    assert len(merged) == 1
    doc = merged[0]
    assert doc["title"] == "My title"
    assert doc["meta"]["mentions"] == ["j:2026-09-24#strat"]
    assert doc["meta"]["comments"] == {"by_me": 0, "by_others": 3}
    assert doc["meta"]["owned"] is True
    assert doc["date"] == "2026-09-24"


def test_render_month_shows_doc_ownership_and_comments():
    doc = g._doc_item(
        "RFC1",
        date(2026, 9, 10),
        "RFC",
        "",
        "https://x",
        {
            "origin": "gws",
            "owned": True,
            "owner": "Me",
            "comments": {"by_me": 1, "by_others": 4},
            "mentions": [],
        },
    )
    body = g.render_month("2026-H2", "2026-09", [doc])
    assert "owned by me" in body
    assert "comments: 4 from others, 1 from me" in body


def test_load_linear_skips_duplicates_like_canceled(tmp_path):
    path = tmp_path / "linear.json"
    path.write_text(
        json.dumps([linear_issue("ABC-1", status="duplicate", completed=None)])
    )
    notes = []
    assert g.load_linear(path, g.Config(**CONFIG), notes, []) == []
    assert any("1 canceled or duplicate" in n for n in notes)


def test_build_ledger_drops_dated_items_outside_window():
    window = g.Window(date(2026, 7, 1), date(2026, 10, 16))

    def issue(id_, day):
        return {
            "id": id_,
            "date": day,
            "tier": "work",
            "title": "t",
            "text": "",
            "url": None,
            "meta": {},
        }

    items = [
        issue("lin:OLD-1", "2026-02-12"),
        issue("lin:NEW-1", "2026-08-01"),
        issue("lin:OPEN-1", None),
    ]
    notes = []
    ledger = g.build_ledger(g.Config(**CONFIG), window, "2026-H2", items, [], notes)
    assert ids(ledger["items"]) == ["lin:NEW-1", "lin:OPEN-1"]
    assert any("1 items dated outside the window" in n for n in notes)


# --- secret redaction (phase 7) --------------------------------------------

FAKE_SECRETS = [
    "ghp_" + "A" * 36,
    "github_pat_" + "B" * 40,
    "sk-ant-api03-" + "C" * 40,
    "AIza" + "D" * 35,
    "AKIA" + "E" * 16,
    "xoxb-" + "1234567890-" + "F" * 20,
]


@pytest.mark.parametrize("secret", FAKE_SECRETS)
def test_redact_secrets_builtin_patterns(secret):
    text, n = g.redact_secrets(
        f"token: {secret} and more", g.compile_secret_patterns([])
    )
    assert secret not in text
    assert "[redacted secret]" in text
    assert text.endswith("and more")
    assert n == 1


def test_redact_secrets_config_patterns():
    patterns = g.compile_secret_patterns([r"tsk_[A-Za-z0-9_-]{20,}"])
    text, n = g.redact_secrets("key tsk_" + "x" * 43, patterns)
    assert text == "key [redacted secret]"
    assert n == 1


def test_redact_secrets_leaves_ordinary_text():
    text = "see https://github.com/org/repo/pull/12 and doc AbC123_xyz-9"
    assert g.redact_secrets(text, g.compile_secret_patterns([])) == (text, 0)


def test_build_ledger_redacts_and_notes_count():
    secret = "ghp_" + "Z" * 36
    items, _ = g.parse_journal(
        D, f"# notes\n## setup\nPAT {secret}\n## other\nfine\n", deny()
    )
    window = g.Window(date(2026, 7, 1), date(2026, 10, 16))
    notes = []
    ledger = g.build_ledger(g.Config(**CONFIG), window, "2026-H2", items, [], notes)
    assert secret not in json.dumps(ledger)
    assert any("redacted 1 secrets" in n for n in notes)


# --- adversarial review findings (pr phase) --------------------------------


def test_ids_unique_when_loose_text_and_a_notes_section_coexist():
    text = "# TIL\nloose til\n## TIL\nsection til\n# notes\nloose\n## Notes\nsection\n"
    items, _ = g.parse_journal(D, text, deny())
    assert len(ids(items)) == len(set(ids(items)))


def test_ids_unique_when_suffix_collides_with_a_real_heading():
    text = "# notes\n## foo\na\n## foo\nb\n## Foo 2\nc\n"
    items, _ = g.parse_journal(D, text, deny())
    assert len(set(ids(items))) == 3


def test_hash_lines_inside_code_fences_are_not_headings():
    text = (
        "# notes\n## ok\nbefore\n```\n# comment in code\n```\nafter\n"
        "## therapy\n```\n# notes\n```\nleaked?\n"
    )
    items, dropped = g.parse_journal(D, text, deny("therapy"))
    ok = next(i for i in items if i["id"] == "j:2026-08-14#ok")
    assert "after" in ok["text"]
    assert dropped == 1
    assert not any("leaked?" in i["text"] for i in items)


def test_redaction_covers_url_and_meta():
    secret = "ghp_" + "Q" * 36
    doc = g._doc_item(
        "x",
        date(2026, 8, 14),
        "t",
        "",
        f"https://host/?token={secret}",
        {"owner": f"me {secret}", "mentions": [f"j:{secret}"]},
    )
    window = g.Window(date(2026, 7, 1), date(2026, 10, 16))
    ledger = g.build_ledger(g.Config(**CONFIG), window, "2026-H2", [doc], [], [])
    assert secret not in json.dumps(ledger)


def test_truncation_never_leaves_a_partial_secret():
    secret = "ghp_" + "R" * 36
    body = "y" * (g.SECTION_CHAR_LIMIT - 10) + " " + secret + " tail"
    items, _ = g.parse_journal(D, f"# notes\n## long\n{body}\n", deny())
    window = g.Window(date(2026, 7, 1), date(2026, 10, 16))
    ledger = g.build_ledger(g.Config(**CONFIG), window, "2026-H2", items, [], [])
    assert "ghp_" not in json.dumps(ledger)


def test_linear_override_changes_the_slice():
    issue = {
        "id": "lin:ABC-1",
        "source": "linear",
        "date": "2026-08-14",
        "tier": "work",
        "title": "x",
        "text": "",
        "url": "u",
        "meta": {"status": "completed", "project": "P", "team": "T"},
    }
    before = g.render_month("2026-H2", "2026-08", [issue])
    after = g.render_month("2026-H2", "2026-08", [{**issue, "tier": "personal"}])
    assert before != after


def test_tooling_samples_carry_citable_ids():
    body = g.render_month("2026-H2", "2026-08", sample_items())
    assert "gh:me/tool#0" in body


def test_collect_gws_accepts_pretty_printed_output(monkeypatch):
    page = json.dumps({"files": [drive_file("P1", "pretty")]}, indent=2)

    def fake(cmd, timeout=60):
        if cmd[1:4] == ["drive", "files", "list"]:
            return page + "\n"
        if cmd[1:4] == ["drive", "comments", "list"]:
            return json.dumps({"comments": []})
        return None

    monkeypatch.setattr(g, "_run", fake)
    assert ids(g.collect_gws_docs(WINDOW, [], [], [])) == ["doc:P1"]


def test_collect_gws_garbage_output_warns_instead_of_crashing(monkeypatch):
    monkeypatch.setattr(g, "_run", lambda cmd, timeout=60: "Using keyring\n{oops")
    warnings = []
    assert g.collect_gws_docs(WINDOW, [], warnings, []) == []
    assert any("gws returned unparseable output" in w for w in warnings)


def test_collect_gws_skips_files_missing_fields(monkeypatch):
    owned = [{"id": "X", "name": "no times"}]
    monkeypatch.setattr(g, "_run", fake_gws(owned=owned))
    notes = []
    assert g.collect_gws_docs(WINDOW, [], [], notes) == []
    assert any("could not read" in n for n in notes)


def test_load_linear_malformed_warns(tmp_path):
    path = tmp_path / "linear.json"
    path.write_text('[{"title": null}, not json')
    warnings, notes = [], []
    assert g.load_linear(path, g.Config(**CONFIG), notes, warnings) == []
    assert any("linear.json" in w for w in warnings)


def test_load_linear_skips_entries_missing_fields(tmp_path):
    path = tmp_path / "linear.json"
    path.write_text(json.dumps([{"title": None}, linear_issue("ABC-1")]))
    notes = []
    assert ids(g.load_linear(path, g.Config(**CONFIG), notes, [])) == ["lin:ABC-1"]
    assert any("malformed" in n for n in notes)


def test_merged_query_results_are_merged_whatever_state_says(monkeypatch):
    closed = {**pr("work-org/api", 1), "state": "closed"}
    monkeypatch.setattr(g, "_run", fake_gh(merged_author=[closed]))
    items = g.collect_github(g.Config(**CONFIG), WINDOW, [], [])
    assert items[0]["meta"]["state"] == "merged"
    assert items[0]["date"] == "2026-08-20"


def test_repo_tier_is_case_insensitive():
    config = g.Config(
        **{**CONFIG, "work_orgs": ["Work-Org"], "tooling_repos": ["Me/Tool"]}
    )
    assert g._repo_tier("work-org/api", config) == "work"
    assert g._repo_tier("me/tool", config) == "tooling"


def test_completed_tasks_accept_capital_x_and_honor_the_denylist():
    text = "# today\n- [X] ship it\n- [x] therapy session\n"
    items, _ = g.parse_journal(D, text, deny("therapy"))
    assert "ship it" in items[0]["text"]
    assert "therapy" not in items[0]["text"]


def test_parse_docs_md_invalid_date_is_undated():
    docs = g.parse_docs_md(f"- [t]({GDOC}) — n (2026-13-01)\n")
    assert docs[0]["date"] is None


def test_render_month_demotes_headings_in_doc_text():
    doc = g._doc_item(
        "D1",
        date(2026, 8, 14),
        "t",
        "### Spec https://x",
        "https://x",
        {"mentions": []},
    )
    body = g.render_month("2026-H2", "2026-08", [doc])
    assert "\n### Spec" not in body


def test_main_prints_the_count_actually_written(tmp_path, monkeypatch, capsys):
    make_vault(tmp_path, monkeypatch, journals={"2026-08-14": TEMPLATE})
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "linear.json").write_text(
        json.dumps([linear_issue("OLD-1", completed="2026-02-01T00:00:00Z")])
    )
    g.main(
        ["--cycle", "2026-H2", "--cache", str(cache), "--no-github", "--no-gws"],
        today=date(2026, 10, 15),
    )
    written = len(json.loads((cache / "ledger.json").read_text())["items"])
    assert f"items: {written}\n" in capsys.readouterr().out


# --- Copilot review findings (pr phase) ------------------------------------

SECRETS = g.compile_secret_patterns([])


def test_cap_without_whitespace_never_leaves_a_token_fragment():
    secret = "ghp_" + "S" * 36
    items, _ = g.parse_journal(
        D, "# notes\n## x\n" + "y" * 5990 + secret + "\n", deny()
    )
    window = g.Window(date(2026, 7, 1), date(2026, 10, 16))
    ledger = g.build_ledger(g.Config(**CONFIG), window, "2026-H2", items, [], [])
    assert "ghp_" not in json.dumps(ledger)


def test_secrets_in_headings_never_reach_ids():
    secret = "ghp_" + "t" * 36
    items, _ = g.parse_journal(
        D, f"# notes\n## token {secret}\nbody\n", deny(), SECRETS
    )
    assert all("t" * 36 not in i["id"] and secret not in i["title"] for i in items)


def test_doc_link_text_is_not_cut_before_redaction():
    secret = "ghp_" + "U" * 36
    line = "x" * 280 + " " + secret + " " + GDOC
    journal, _ = g.parse_journal(D, f"# notes\n## d\n{line}\n", deny())
    docs = g.extract_doc_links(journal)
    window = g.Window(date(2026, 7, 1), date(2026, 10, 16))
    ledger = g.build_ledger(g.Config(**CONFIG), window, "2026-H2", docs, [], [])
    assert "ghp_" not in json.dumps(ledger)


@pytest.mark.parametrize("prefix", ["sk-proj-", "sk-svcacct-"])
def test_openai_project_and_service_keys_are_redacted(prefix):
    secret = prefix + "Ab_c-" * 10
    text, n = g.redact_secrets(f"k {secret}", SECRETS)
    assert n == 1 and secret not in text


def test_fences_close_only_on_a_matching_delimiter():
    text = "# notes\n## therapy\n````\n```\n# notes\n```\nleak?\n````\n## ok\nfine\n"
    items, _ = g.parse_journal(D, text, deny("therapy"))
    assert not any("leak?" in i["text"] for i in items)
    assert "j:2026-08-14#ok" in ids(items)


def test_tooling_samples_show_state_and_author():
    items = sample_items()
    items[-1]["meta"] = {
        **items[-1]["meta"],
        "state": "open",
        "role": "reviewer",
        "pr_author": "pal",
    }
    body = g.render_month("2026-H2", "2026-08", items)
    sample_lines = [ln for ln in body.splitlines() if "gh:me/tool#" in ln]
    assert all("(merged" in ln or "(open" in ln for ln in sample_lines)


def test_input_hash_covers_extraction_context():
    body = g.render_month("2026-H2", "2026-08", sample_items())
    assert g.input_hash(body, "levels A") != g.input_hash(body, "levels B")


def test_write_months_removes_orphan_extracts(tmp_path):
    months = tmp_path / "months"
    months.mkdir()
    (months / "2026-06.extract.md").write_text("old")
    g.write_months(tmp_path, "2026-H2", sample_items())
    assert not (months / "2026-06.extract.md").exists()


def test_gws_comment_counts_only_cover_the_window(monkeypatch):
    owned = [drive_file("D1", "doc")]
    old, new = "2024-01-01T00:00:00Z", "2026-08-01T00:00:00Z"
    comments = {
        "D1": [
            {
                "author": {"me": False},
                "createdTime": old,
                "replies": [{"author": {"me": True}, "createdTime": new}],
            },
            {"author": {"me": False}, "createdTime": new, "replies": []},
        ]
    }
    monkeypatch.setattr(g, "_run", fake_gws(owned=owned, comments=comments))
    docs = g.collect_gws_docs(WINDOW, [], [], [])
    assert docs[0]["meta"]["comments"] == {"by_me": 1, "by_others": 1}


def test_gws_discovery_is_limited_to_google_documents(monkeypatch):
    seen = {}

    def fake(cmd, timeout=60):
        if cmd[1:4] == ["drive", "files", "list"]:
            seen["q"] = json.loads(cmd[cmd.index("--params") + 1])["q"]
            return '{"files": []}\n'
        return None

    monkeypatch.setattr(g, "_run", fake)
    g.collect_gws_docs(WINDOW, [], [], [])
    assert "application/vnd.google-apps.document" in seen["q"]
    assert "mimeType" in seen["q"]
