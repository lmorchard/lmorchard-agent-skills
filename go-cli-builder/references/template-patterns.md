# Template Patterns for Go CLI Tools

This guide covers patterns for implementing customizable output templates in Go CLI tools, based on successful patterns from `linkding-to-markdown` and `mastodon-to-markdown`.

## Overview

CLI tools that generate formatted output (Markdown, HTML, XML, etc.) benefit from:
1. **Embedded default templates** - Work out of the box, single binary
2. **User customization** - Users can modify templates for their needs
3. **Init command** - Easy way to get started with configuration and templates

## Architecture

### Directory Structure

```
my-cli-tool/
├── cmd/
│   ├── init.go          # Init command to bootstrap config/templates
│   └── fetch.go         # Command that uses templates
├── internal/
│   ├── templates/
│   │   ├── templates.go # Template loader with embedded defaults
│   │   └── default.md   # Default template (embedded via //go:embed)
│   └── generator/       # Or markdown/, formatter/, etc.
│       └── generator.go # Template renderer and data structures
```

## Implementation Steps

### 1. Create Template Package

**File: `internal/templates/templates.go`**

```go
package templates

import (
    _ "embed"
)

//go:embed default.md
var defaultTemplate string

// GetDefaultTemplate returns the embedded default template content
func GetDefaultTemplate() (string, error) {
    return defaultTemplate, nil
}
```

**File: `internal/templates/default.md`**

Create your default template using Go's `text/template` syntax:

```markdown
# {{ .Title }}

_Generated: {{ .Generated }}_

---

{{ range .Items -}}
## {{ .Name }}

{{ .Description }}

{{ if .Tags -}}
Tags: {{ join .Tags ", " }}
{{ end -}}

---
{{ end -}}
```

### 2. Create Generator/Renderer

**File: `internal/generator/generator.go`**

```go
package generator

import (
    "fmt"
    "io"
    "os"
    "strings"
    "text/template"
    "time"

    "yourproject/internal/templates"
)

type Generator struct {
    template *template.Template
}

// NewGenerator creates a generator with the default embedded template
func NewGenerator() (*Generator, error) {
    defaultTmpl, err := templates.GetDefaultTemplate()
    if err != nil {
        return nil, fmt.Errorf("failed to get default template: %w", err)
    }
    return NewGeneratorWithTemplate(defaultTmpl)
}

// NewGeneratorFromFile creates a generator from a template file
func NewGeneratorFromFile(templatePath string) (*Generator, error) {
    content, err := os.ReadFile(templatePath)
    if err != nil {
        return nil, fmt.Errorf("failed to read template file: %w", err)
    }
    return NewGeneratorWithTemplate(string(content))
}

// NewGeneratorWithTemplate creates a generator with a custom template string
func NewGeneratorWithTemplate(tmplStr string) (*Generator, error) {
    // Define template functions
    funcMap := template.FuncMap{
        "formatDate": func(t time.Time, format string) string {
            return t.Format(format)
        },
        "join": strings.Join,
        "hasContent": func(s string) bool {
            return strings.TrimSpace(s) != ""
        },
    }

    tmpl, err := template.New("output").Funcs(funcMap).Parse(tmplStr)
    if err != nil {
        return nil, fmt.Errorf("failed to parse template: %w", err)
    }

    return &Generator{template: tmpl}, nil
}

// TemplateData holds data passed to templates
type TemplateData struct {
    Title     string
    Generated string
    Items     []Item
    // Add your domain-specific fields here
}

// Generate executes the template with data and writes to writer
func (g *Generator) Generate(w io.Writer, data TemplateData) error {
    if err := g.template.Execute(w, data); err != nil {
        return fmt.Errorf("failed to execute template: %w", err)
    }
    return nil
}
```

### 3. Create Init Command

Use the `init.go.template` from the skill, customizing the `defaultConfigContent` for your project's needs.

Key features:
- Creates config file with documented options
- Creates customizable template file from embedded default
- Supports `--force` to overwrite
- Supports `--template-file` to specify custom filename
- Provides helpful next steps

### 4. Integrate with Commands

**In your command that generates output:**

```go
func runFetch(cmd *cobra.Command, args []string) error {
    logger := GetLogger()

    // ... fetch your data ...

    // Create generator with custom template or default
    templatePath := viper.GetString("fetch.template")
    var generator *generator.Generator
    var err error

    if templatePath != "" {
        logger.Infof("Using custom template: %s", templatePath)
        generator, err = generator.NewGeneratorFromFile(templatePath)
        if err != nil {
            return fmt.Errorf("failed to load custom template: %w", err)
        }
    } else {
        generator, err = generator.NewGenerator()
        if err != nil {
            return fmt.Errorf("failed to create generator: %w", err)
        }
    }

    // Prepare template data
    data := generator.TemplateData{
        Title:     viper.GetString("fetch.title"),
        Generated: time.Now().Format(time.RFC3339),
        Items:     fetchedItems,
    }

    // Determine output destination
    outputPath := viper.GetString("fetch.output")
    var output *os.File
    if outputPath != "" {
        output, err = os.Create(outputPath)
        if err != nil {
            return fmt.Errorf("failed to create output file: %w", err)
        }
        defer output.Close()
        logger.Infof("Writing output to %s", outputPath)
    } else {
        output = os.Stdout
    }

    // Generate output
    if err := generator.Generate(output, data); err != nil {
        return fmt.Errorf("failed to generate output: %w", err)
    }

    return nil
}
```

### 5. Add Configuration Support

**In `internal/config/config.go`:**

```go
type Config struct {
    // ... other config ...

    Fetch struct {
        Output   string
        Title    string
        Template string  // Path to custom template file
    }
}
```

**In your command's flags:**

```go
fetchCmd.Flags().String("template", "", "Custom template file (default: built-in template)")
_ = viper.BindPFlag("fetch.template", fetchCmd.Flags().Lookup("template"))
```

**In config YAML:**

```yaml
fetch:
  output: "output.md"
  title: "My Output"
  template: "my-custom-template.md"  # Optional
```

## Template Functions

Provide helpful template functions for common operations:

```go
funcMap := template.FuncMap{
    // Date formatting
    "formatDate": func(t time.Time, format string) string {
        return t.Format(format)
    },

    // String operations
    "join": strings.Join,
    "hasContent": func(s string) bool {
        return strings.TrimSpace(s) != ""
    },
    "truncate": func(s string, length int) string {
        if len(s) <= length {
            return s
        }
        return s[:length] + "..."
    },

    // Conditional helpers
    "default": func(defaultVal, val interface{}) interface{} {
        if val == nil || val == "" {
            return defaultVal
        }
        return val
    },
}
```

## User Workflow

### First-Time Setup

```bash
# User initializes config and template
$ my-tool init
✅ Initialization complete!

Next steps:
  1. Edit my-tool.yaml and add your configuration
  2. (Optional) Customize my-tool.md for your preferred output format
  3. Run: my-tool fetch --help for usage information
```

### Using Default Template

```bash
# Just works with embedded default
$ my-tool fetch --output result.md
```

### Using Custom Template

```bash
# After editing my-tool.md
$ my-tool fetch --template my-tool.md --output result.md

# Or via config file
$ cat my-tool.yaml
fetch:
  template: "my-tool.md"

$ my-tool fetch --output result.md
```

## Best Practices

1. **Always provide a sensible default template** - Tool should work without customization
2. **Document template variables** - In README and/or generated template comments
3. **Validate templates early** - Parse template when creating generator, not during execution
4. **Provide helpful error messages** - Template parse errors should show line numbers
5. **Include examples** - Show template snippets in documentation
6. **Support both stdout and file output** - Enables piping and integration
7. **Make template optional** - Config file should work without template field set

## Template Documentation

In your README, document:

### Available Variables

```markdown
### Template Variables

- `.Title` - Document title (string)
- `.Generated` - Generation timestamp (string)
- `.Items` - Array of items to include

### Item Fields

Each item has:
- `.Name` - Item name (string)
- `.Description` - Item description (string)
- `.Tags` - Array of tags ([]string)
```

### Available Functions

```markdown
### Template Functions

- `formatDate <time> <format>` - Format time.Time with Go time format
- `join <slice> <separator>` - Join string slice
- `hasContent <string>` - Check if string is non-empty
```

### Example Template

Include a complete working example users can copy/paste.

## Testing Templates

```go
func TestTemplateExecution(t *testing.T) {
    tmpl := `{{ .Title }}
{{ range .Items }}{{ .Name }}{{ end }}`

    gen, err := NewGeneratorWithTemplate(tmpl)
    if err != nil {
        t.Fatalf("failed to create generator: %v", err)
    }

    data := TemplateData{
        Title: "Test",
        Items: []Item{{Name: "Item1"}, {Name: "Item2"}},
    }

    var buf bytes.Buffer
    if err := gen.Generate(&buf, data); err != nil {
        t.Fatalf("failed to generate: %v", err)
    }

    expected := "Test\nItem1Item2"
    if buf.String() != expected {
        t.Errorf("expected %q, got %q", expected, buf.String())
    }
}
```

## Common Pitfalls

1. **Not using `//go:embed`** - Requires users to distribute template files separately
2. **No template validation** - Errors appear late during execution
3. **Poor error messages** - Template errors can be cryptic, add context
4. **Forgetting `defer file.Close()`** - When writing to files
5. **Not supporting stdout** - Reduces composability with other tools
6. **Hardcoded paths** - Use relative paths or make configurable

## Examples in the Wild

- **linkding-to-markdown** - Bookmarks to Markdown with grouping options
- **mastodon-to-markdown** - Posts to Markdown with media handling
- **feedspool-go** - RSS/Atom feed processing with custom templates
