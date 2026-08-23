# lmorchard's Agent Skills

A collection of skills for Claude Code and Claude.ai that extend Claude's capabilities with specialized knowledge, workflows, and tools.

## Available Skills

### go-cli-builder

Build production-ready Go command-line tools following established patterns with Cobra CLI framework, Viper configuration, SQLite database, and automated GitHub Actions workflows.

**Features:**
- Scaffold complete Go CLI projects with one command
- Pre-configured with Cobra, Viper, SQLite, Logrus
- Database migration system included
- GitHub Actions workflows for CI and multi-platform releases
- Makefile with lint, format, test, build targets
- Add new commands with simple script

**Use when:**
- Creating a new Go CLI tool from scratch
- Adding commands to existing Go CLI projects
- Setting up GitHub Actions for Go releases

[View detailed documentation →](./go-cli-builder/SKILL.md)

### weeknotes-blog-post-composer

Composes conversational weeknotes blog posts from multiple data sources (Mastodon and Linkding).

- **Description**: Automatically fetches content and composes readable, Jekyll-style blog posts with proper voice and narrative structure
- **Data Sources**: Mastodon posts, Linkding bookmarks
- **Output**: Jekyll Markdown with YAML frontmatter
- **Documentation**: [weeknotes-blog-post-composer/README.md](weeknotes-blog-post-composer/README.md)

**Quick usage:**
```
User: Draft weeknotes for this week             # Uses last 7 days
User: Create weeknotes from November 4-10      # Specific date range
```

## Output Styles

Output styles change how Claude talks to you. Claude Code appends them to the
system prompt, so they apply to every response in a session.

### eli5

Small words, short sentences, and only what is necessary — written for the end
of a long day. Caps decisions at two options with a recommendation. Keeps paths
and commands exact.

### simple-english

The rules of [ASD-STE100 Simplified Technical
English](https://asd-ste100.org/) applied to conversation: short sentences,
active voice, simple tenses, one word one meaning, and conditions before
commands. Adapted from the separate `simple-english` skill (not part of this
repo), which handles full document rewrites; this style only governs the voice
of replies.

Both styles set `keep-coding-instructions: true`, so Claude's built-in software
engineering behavior stays intact.

### Selecting a style

Run `/config` and choose **Output style**, or set the field directly in a
settings file:

```json
{ "outputStyle": "Simple English" }
```

The value is the `name` from the file's frontmatter, not the file name. A style
change takes effect on `/clear` or in the next session, because Claude Code
reads the system prompt once at session start.

> **Note:** the standalone `/output-style` command was deprecated in Claude
> Code v2.1.73 and removed in v2.1.91. Use `/config` instead.

Output styles apply to the main conversation only. Subagents run their own
system prompt and ignore them.

## Installation

### For Claude Code

#### Recommended: Install as Plugin

1. Register this marketplace in Claude Code:
   ```
   /plugin marketplace add lmorchard/lmorchard-agent-skills
   ```

2. Install via UI:
   - Select **Browse and install plugins**
   - Choose **lmorchard-agent-skills**
   - Click **Install now**

3. Or install directly via command:
   ```
   /plugin install lmorchard-agent-skills
   ```

#### Alternative: Manual Installation

If you prefer to install manually or need to work on the skills locally:

##### Install entire collection:
```bash
# Clone to your skills directory
git clone https://github.com/lmorchard/lmorchard-agent-skills.git ~/.claude/skills/lmorchard-agent-skills
```

##### Install specific skill only:
```bash
# Clone with sparse checkout for just one skill
git clone --depth 1 --filter=blob:none --sparse https://github.com/lmorchard/lmorchard-agent-skills.git ~/.claude/skills/lmorchard-agent-skills
cd ~/.claude/skills/lmorchard-agent-skills
git sparse-checkout set go-cli-builder
```

### For Claude.ai

These skills can be uploaded to Claude.ai projects via the Skills API (requires API access).

## Usage

Once installed, Claude will automatically detect when to use these skills based on your requests. For example:

```
You: "Create a new Go CLI tool called feed-analyzer"
Claude: [Uses go-cli-builder skill to scaffold the project]
```

You can also explicitly invoke skills:
```
You: "Use the go-cli-builder skill to add an export command to my project"
```

## Development

**Philosophy:**
- Skills should solve real, recurring problems
- Prefer simple, maintainable solutions
- Use existing tools and CLIs where possible
- Document everything for Claude and humans

### Checks

```bash
make check     # the full gate: lint + test
make lint      # ruff check + format check, no writes
make format    # apply safe lint fixes, then reformat
make test      # pytest suite (standup-digest)
```

Linting is [ruff](https://docs.astral.sh/ruff/), pulled in on demand via
`uvx ruff@0.16.1` — there's nothing to install. Configuration lives in
`.ruff.toml`; it covers Python scripts only, deliberately excluding Markdown so
that documentation snippets and archived dev-session notes aren't reformatted.

### Local Install

Skills and output styles are developed in place and symlinked into `~/.claude`:

```bash
make link      # symlink skills and output styles into ~/.claude
make links     # show the current link state of each one
make unlink    # remove this repo's symlinks
```

`make link` sends each skill directory to `~/.claude/skills/` and each
`output-styles/*.md` file to `~/.claude/output-styles/`. Both are load paths
Claude Code scans at startup. The target refuses to replace a real directory or
file, removes only links that point back at this repo, and prunes links
orphaned by a rename.

A plugin install snapshots the repo at a commit, so edits here would not take
effect until committed and the plugin updated. Symlinks are live, which is why
local development uses them.

### Adding a New Skill

1. Create a new directory for your skill:
   ```bash
   mkdir my-new-skill
   ```

2. Add required files:
   ```
   my-new-skill/
   ├── SKILL.md          # Required: skill metadata and instructions
   ├── scripts/          # Optional: executable scripts
   ├── references/       # Optional: reference documentation
   └── assets/           # Optional: templates and resources
   ```

3. Update `.claude-plugin/marketplace.json`:
   ```json
   {
     "plugins": [
       {
         "skills": [
           "./go-cli-builder",
           "./my-new-skill"
         ]
       }
     ]
   }
   ```

4. Run `make link` to symlink it into `~/.claude/skills/`. The target
   discovers skills from `*/SKILL.md`, so there is no list to edit.

### Adding an Output Style

1. Create a Markdown file in `output-styles/`:
   ```
   output-styles/my-style.md
   ```

2. Add frontmatter and instructions:
   ```markdown
   ---
   name: My Style
   description: Shown in the /config picker
   keep-coding-instructions: true
   ---

   Your instructions here.
   ```

   Set `keep-coding-instructions: true` to keep Claude's software engineering
   behavior. Leave it out when the style is not for coding work.

3. Run `make link`. The target discovers styles from `output-styles/*.md`, so
   there is no list to edit. `.claude-plugin/marketplace.json` needs no entry
   either: Claude Code loads a plugin's output styles from its `output-styles/`
   directory automatically.

4. Select it with `/config`, then `/clear` for it to take effect.

### Skill Structure

Each skill must contain a `SKILL.md` file with YAML frontmatter:

```markdown
---
name: skill-name
description: Brief description of what the skill does and when to use it
---

# Skill Name

[Detailed instructions for Claude...]
```

See [Anthropic's skill documentation](https://github.com/anthropics/skills) for more details.

## Security & Privacy

Skills that require API credentials (like weeknotes-blog-post-composer) store them in gitignored config files. All credentials and personal data remain local on your machine. No telemetry or data sharing.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Test your changes locally and confirm `make check` is green
4. Submit a pull request

## Related Resources

- [Claude Code Documentation](https://docs.claude.com/claude-code)
- [Building Skills Guide](https://docs.claude.com/claude-code/skills)
- [Marketplace Plugin System](https://docs.claude.com/claude-code/plugins)
- [Anthropic's example skills](https://github.com/anthropics/skills)

## License

MIT License - see [LICENSE.txt](LICENSE.txt) for details.

## About

These skills are created and maintained by [Les Orchard](https://github.com/lmorchard).
