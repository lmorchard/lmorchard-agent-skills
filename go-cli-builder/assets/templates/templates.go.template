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
