# Internal Package Organization

This document explains how to organize code in the `internal/` directory of Go CLI projects.

## The `internal/` Directory

The `internal/` directory is a special Go convention. Packages inside `internal/` can only be imported by code in the parent tree. This enforces encapsulation and prevents external projects from depending on internal implementation details.

## Standard Package Structure

A typical Go CLI project has this structure:

```
project/
├── cmd/                    # Command definitions (public API of the CLI)
├── internal/               # Private implementation
│   ├── config/            # Configuration structures
│   ├── database/          # Database access layer
│   └── [domain packages]  # Business logic packages
├── main.go                # Entry point
└── go.mod                 # Dependencies
```

## Package Guidelines

### `cmd/` Package

**Purpose**: Define the CLI commands and their flags

**Contents**:
- `root.go`: Root command and configuration initialization
- `version.go`: Version command
- `constants.go`: CLI-level constants
- One file per command (e.g., `fetch.go`, `export.go`)

**Responsibilities**:
- Parse and validate user input
- Set up configuration and logging
- Call into `internal/` packages to do the work
- Format and display output

**Anti-patterns**:
- Heavy business logic in command handlers
- Direct database access
- Complex algorithms

### `internal/config/` Package

**Purpose**: Define configuration structures

**Contents**:
- `config.go`: Config struct definitions

**Example**:
```go
package config

type Config struct {
    Database string
    Verbose  bool

    Fetch struct {
        Concurrency int
        Timeout     time.Duration
    }
}
```

### `internal/database/` Package

**Purpose**: Encapsulate all database operations

**Contents**:
- `database.go`: Connection management, initialization
- `migrations.go`: Migration system
- `schema.sql`: Initial schema (embedded)
- Optional: `queries.go` for complex queries

**Responsibilities**:
- Database connection lifecycle
- Schema initialization and migrations
- Data access methods
- Transaction management

**Anti-patterns**:
- Business logic in database layer
- Exposing `*sql.DB` directly
- SQL in command files

### Domain-Specific Packages

Create additional packages in `internal/` for each major domain or feature:

```
internal/
├── feeds/          # Feed parsing and processing
├── fetcher/        # HTTP fetching logic
├── renderer/       # Output rendering
└── exporter/       # Export functionality
```

**Guidelines**:
- One package per cohesive responsibility
- Packages should be importable by `cmd/` and by each other
- Keep packages focused and single-purpose
- Use clear, descriptive names

## Layering and Dependencies

Follow these dependency rules:

```
main.go
  └─> cmd/
       └─> internal/config/
       └─> internal/database/
       └─> internal/[domain]/
            └─> internal/[other domains]/
```

**Rules**:
1. `cmd/` can import any `internal/` package
2. `internal/` packages can import each other as needed
3. Avoid circular dependencies between `internal/` packages
4. Keep `cmd/` thin - it orchestrates but doesn't implement

## Example: Adding a New Feature

Let's say you want to add feed fetching functionality:

1. **Create the package**:
   ```
   internal/fetcher/
   ├── fetcher.go      # Main fetching logic
   └── fetcher_test.go # Tests
   ```

2. **Define the API**:
   ```go
   package fetcher

   type Fetcher struct {
       client *http.Client
       // ...
   }

   func New(opts ...Option) *Fetcher { ... }
   func (f *Fetcher) Fetch(url string) ([]byte, error) { ... }
   ```

3. **Use in command**:
   ```go
   // cmd/fetch.go
   package cmd

   import "yourproject/internal/fetcher"

   var fetchCmd = &cobra.Command{
       RunE: func(cmd *cobra.Command, args []string) error {
           f := fetcher.New()
           data, err := f.Fetch(url)
           // ...
       },
   }
   ```

## Common Patterns

### Option Pattern for Configuration

```go
type Fetcher struct {
    timeout time.Duration
}

type Option func(*Fetcher)

func WithTimeout(d time.Duration) Option {
    return func(f *Fetcher) {
        f.timeout = d
    }
}

func New(opts ...Option) *Fetcher {
    f := &Fetcher{timeout: 30 * time.Second}
    for _, opt := range opts {
        opt(f)
    }
    return f
}
```

### Embedding Resources

For SQL, templates, or other resources:

```go
import _ "embed"

//go:embed schema.sql
var schemaSQL string
```

### Error Wrapping

Always wrap errors with context:

```go
if err != nil {
    return fmt.Errorf("failed to fetch feed %s: %w", url, err)
}
```

## Testing

- Put tests in `_test.go` files alongside the code
- Use table-driven tests for multiple cases
- Consider using `internal/database/database_test.go` with in-memory SQLite for database tests

## When to Create a New Package

Create a new `internal/` package when:
- You have a cohesive set of related functionality
- The code would make commands cleaner and more focused
- You want to unit test logic separately from CLI interaction
- Multiple commands need to share the same functionality

Don't create a package when:
- It would only have one small function
- It's tightly coupled to a single command
- It would create circular dependencies
