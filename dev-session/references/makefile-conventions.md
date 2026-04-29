# Makefile conventions

This skill assumes a project Makefile organizes the common dev tasks. Makefiles work across languages and environments, give every contributor (and agent) the same entry points, and make it easy to add a target the moment a command starts repeating.

## Expected targets

The skill names these by convention. Add them to new projects; align them in existing ones.

| Target | What it does |
|---|---|
| `make lint` | Run linters/formatters (gofmt + vet, ruff, eslint, etc.) |
| `make test` | Run the project's test suite |
| `make check` | Composite gate — typically `lint` + `test` + typecheck. The single command CI runs |
| `make serve` | Start the dev server (or REPL) |
| `make build` | Produce the build artifact |

Phase-specific targets (`make migrate`, `make codegen`, `make e2e`) are welcome — keep names short and memorable.

## When a Makefile exists

- Use `make <target>` rather than the underlying tool. It survives toolchain changes.
- If a target the skill expects (`lint`/`test`/`check`) is missing, add it before relying on it. A 3-line target now beats reconstructing the command in three different phases.

## When a Makefile doesn't exist

- Run the native tool directly (`cargo test`, `npm test`, `pytest`, `go test ./...`).
- Mention it: a Makefile would make this skill (and future you) faster. Offer to scaffold one with the targets above.

## When to add a new target

If you run a multi-flag invocation more than twice in a session, suggest a target. Good signals:

- A test command with specific flags repeated across phases (`go test ./internal/foo -run TestX -v -race`)
- A lint or format invocation that's not just the default
- A multi-step setup or teardown chain
- Anything CI runs that a contributor would want locally

Bad targets: aliases for one-word commands that already work (`make ls`), one-off scripts, anything project-specific that hides the actual command being run.

## Starter Makefile

Minimal scaffold for a new project (adjust per language):

```makefile
.PHONY: lint test check serve build

lint:
	# project-specific linter command(s)

test:
	# project-specific test command

check: lint test
	# add typecheck or other gates here

serve:
	# project-specific dev server

build:
	# project-specific build command
```

`.PHONY` declares targets that don't produce a file by their name — without it, `make` will skip a target if a same-named file exists.

## Notes on use

- **Targets are discovery, not magic.** Anything in the Makefile is one `grep` away from being found by the next agent or contributor.
- **Prefer composition over duplication.** `make check` should call `make lint` and `make test`, not re-invoke their tools.
- **Don't mess around with formatting requirements** of Make: real tabs (not spaces) at the start of recipe lines.
