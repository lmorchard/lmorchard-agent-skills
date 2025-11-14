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

4. Test locally by symlinking or copying to `~/.claude/skills/`

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
3. Test your changes locally
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
