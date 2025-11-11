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

## Installation

### For Claude Code

#### Install entire collection:

```bash
# Clone to your skills directory
git clone https://github.com/lmorchard/lmorchard-agent-skills.git ~/.claude/skills/lmorchard-agent-skills
```

#### Install specific skill only:

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

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Test your changes locally
4. Submit a pull request

## License

MIT License - see [LICENSE.txt](LICENSE.txt) for details.

## About

These skills are created and maintained by [Les Orchard](https://github.com/lmorchard).

Built with guidance from [Anthropic's example skills](https://github.com/anthropics/skills).
