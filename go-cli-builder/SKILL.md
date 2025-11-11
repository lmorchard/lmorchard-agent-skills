---
name: go-cli-builder
description: Build Go-based command-line tools following established patterns with Cobra CLI framework, Viper configuration, SQLite database, and automated GitHub Actions workflows for releases. Use when creating new Go CLI projects or adding features to existing ones that follow the Cobra/Viper/SQLite stack.
---

# Go CLI Builder

## Overview

This skill provides templates, scripts, and patterns for building production-ready Go command-line tools. It follows established patterns from projects like feedspool-go, feed-to-mastodon, and linkding-to-opml.

The skill generates projects with:
- **Cobra** for CLI framework
- **Viper** for configuration management (YAML files with CLI overrides)
- **SQLite** with a naive migration system
- **Logrus** for structured logging
- **Makefile** for common tasks (lint, format, test, build)
- **GitHub Actions** workflows for CI, tagged releases, and rolling releases
- Strict code formatting with gofumpt and linting with golangci-lint

## When to Use This Skill

Use this skill when:
- Creating a new Go CLI tool from scratch
- Adding commands to an existing Go CLI project that follows these patterns
- Needing reference material about Cobra/Viper integration
- Setting up GitHub Actions workflows for multi-platform Go releases

Example user requests:
- "Create a new Go CLI tool called feed-analyzer"
- "Scaffold a Go project for processing log files"
- "Add a new 'export' command to my Go CLI project"
- "Help me set up GitHub Actions for releasing my Go tool"

## Quick Start

### Creating a New Project

To scaffold a complete new project:

```bash
python scripts/scaffold_project.py my-cli-tool
```

This creates a directory `my-cli-tool/` with:
- Complete directory structure (`cmd/`, `internal/config/`, `internal/database/`)
- Entry point (`main.go`)
- Root command with Cobra/Viper integration (`cmd/root.go`)
- Version command (`cmd/version.go`)
- Database layer with migrations (`internal/database/`)
- Makefile with standard targets
- GitHub Actions workflows (CI, release, rolling-release)
- Example configuration file

**Next steps after scaffolding:**
1. Update `go.mod` with the actual module name
2. Customize the example config file
3. Define initial database schema in `internal/database/schema.sql`
4. Run `make setup` to install development tools
5. Run `go mod tidy` to download dependencies

### Adding Commands to Existing Projects

To add a new command to an existing project:

```bash
python scripts/add_command.py fetch
```

This creates `cmd/fetch.go` with:
- Command boilerplate
- Access to logger and config
- Flag binding examples
- TODO comments for implementation

## Project Structure

Generated projects follow this structure:

```
my-cli-tool/
├── main.go                          # Entry point
├── go.mod                           # Dependencies
├── Makefile                         # Build automation
├── my-cli-tool.yaml.example         # Example configuration
├── cmd/                             # Command definitions
│   ├── root.go                      # Root command + Cobra/Viper setup
│   ├── version.go                   # Version command
│   ├── constants.go                 # Application constants
│   └── [command].go                 # Individual commands
├── internal/
│   ├── config/
│   │   └── config.go                # Configuration struct
│   └── database/
│       ├── database.go              # Connection + initialization
│       ├── migrations.go            # Migration system
│       └── schema.sql               # Initial schema (embedded)
└── .github/workflows/
    ├── ci.yml                       # PR linting and testing
    ├── release.yml                  # Tagged releases
    └── rolling-release.yml          # Main branch rolling releases
```

## Configuration System

Projects use a three-tier configuration hierarchy:

1. **Config file** (`my-tool.yaml`): Base configuration in YAML
2. **Environment variables**: Automatic via Viper
3. **CLI flags**: Override everything

See `references/cobra-viper-integration.md` for detailed patterns on:
- Binding flags to Viper keys
- Adding new configuration options
- Command-specific vs. global configuration
- Environment variable mapping

## Database Layer

The generated database layer includes:

1. **Initial schema** (`internal/database/schema.sql`): Embedded SQL for first-time setup
2. **Migration tracking**: `schema_migrations` table tracks applied versions
3. **Migration execution**: Automatic on database initialization
4. **Idempotent operations**: Safe to run multiple times

**To add a new migration:**

1. Edit `internal/database/migrations.go`
2. Add to the `getMigrations()` map with the next version number:
   ```go
   func getMigrations() map[int]string {
       return map[int]string{
           2: `CREATE TABLE IF NOT EXISTS settings (
               key TEXT PRIMARY KEY,
               value TEXT NOT NULL
           );`,
       }
   }
   ```
3. Migrations run automatically on next database initialization

## Makefile Targets

All generated projects include these targets:

- `make setup`: Install development tools (gofumpt, golangci-lint)
- `make build`: Build the binary with version information
- `make run`: Build and run the application
- `make lint`: Run golangci-lint
- `make format`: Format code with go fmt and gofumpt
- `make test`: Run tests with race detection
- `make clean`: Remove build artifacts

## GitHub Actions Workflows

Three workflows are included:

### 1. CI (`ci.yml`)
- **Triggers**: Pull requests to main, manual workflow calls
- **Actions**: Lint with golangci-lint, test with race detection
- **Skip**: Commits starting with `[noci]`

### 2. Release (`release.yml`)
- **Triggers**: Tags matching `v*` (e.g., `v1.0.0`)
- **Platforms**: Linux (amd64, arm64), macOS (amd64, arm64), Windows (amd64)
- **Outputs**: Compressed binaries, checksums, GitHub release
- **Docker**: Optional (commented out by default)

### 3. Rolling Release (`rolling-release.yml`)
- **Triggers**: Pushes to main branch
- **Actions**: Same as Release but creates a "latest" prerelease
- **Purpose**: Testing builds from the latest commit

**To customize:**
- Update Docker Hub username in workflows if using Docker
- Adjust Go version if needed (default: 1.21)
- Modify build matrix to add/remove platforms

## Typical Workflow

### Starting a New Project

1. Use this skill to scaffold the project
2. Customize the initial schema in `internal/database/schema.sql`
3. Update configuration struct in `internal/config/config.go`
4. Add domain-specific packages in `internal/` (see `references/internal-organization.md`)
5. Add commands using the add_command script
6. Implement command logic, calling into `internal/` packages

### Adding a Feature

1. Determine if it needs a new command or extends existing one
2. If new command: use `add_command.py` script
3. Add any required configuration to config struct and root flags
4. Implement logic in `internal/` packages
5. Update command to call the internal logic
6. Add tests
7. Run `make format && make lint && make test`

## Reference Documentation

For detailed patterns and guidelines, refer to:

- **`references/cobra-viper-integration.md`**: Complete guide to configuration system
  - Flag binding patterns
  - Adding new configuration options
  - Environment variable mapping
  - Best practices

- **`references/internal-organization.md`**: Internal package structure
  - Package organization principles
  - Dependency rules
  - Common patterns (Option pattern, error wrapping)
  - When to create new packages

## Templates Available

All templates are in `assets/templates/`:

- `main.go`: Minimal entry point
- `go.mod.template`: Pre-configured dependencies
- `Makefile.template`: Standard build targets
- `gitignore.template`: Go-specific ignores
- `config.yaml.example`: Example configuration
- `root.go.template`: Cobra/Viper integration
- `version.go.template`: Version command
- `constants.go.template`: Application constants
- `command.go.template`: New command template
- `config.go.template`: Configuration struct
- `database.go.template`: Database layer
- `migrations.go.template`: Migration system
- `schema.sql.template`: Initial schema
- `ci.yml.template`: CI workflow
- `release.yml.template`: Release workflow
- `rolling-release.yml.template`: Rolling release workflow

## Best Practices

1. **Keep commands thin**: Business logic belongs in `internal/` packages
2. **Use the config struct**: Access configuration through `GetConfig()` rather than calling Viper directly
3. **Wrap errors**: Always add context with `fmt.Errorf("context: %w", err)`
4. **Format before committing**: Run `make format && make lint`
5. **Test with race detection**: `go test -race ./...`
6. **Version your releases**: Use semantic versioning tags (v1.0.0, v1.1.0, etc.)
7. **Document in .yaml.example**: Keep example config updated

## Common Customizations

After scaffolding, projects typically need:

1. **Module name update**: Change `github.com/yourusername/project` in `go.mod` to actual path
2. **Additional dependencies**: Add with `go get` and run `go mod tidy`
3. **Custom schema**: Define tables in `internal/database/schema.sql`
4. **Domain packages**: Create packages in `internal/` for business logic
5. **Command implementations**: Fill in the TODOs in command files
6. **Docker configuration**: Uncomment Docker sections in workflows if needed

## Troubleshooting

**"gofumpt not found" or "golangci-lint not found"**
- Run `make setup` to install development tools

**"Failed to initialize schema"**
- Check database file path and permissions
- Ensure directory exists or is creatable

**"Missing migration for version N"**
- Migrations must be sequential; add any missing versions

**GitHub Actions failing on cross-compilation**
- Ensure CGO is enabled for SQLite
- Linux ARM64 builds require cross-compilation tools (handled in workflow)
