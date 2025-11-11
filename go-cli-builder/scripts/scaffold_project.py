#!/usr/bin/env python3
"""
Scaffold a new Go CLI project with the standard structure.

Usage:
    python scaffold_project.py <project-name> [--path <output-dir>]
"""

import argparse
import os
import sys
from pathlib import Path
import shutil
from datetime import datetime


def create_directory_structure(project_path):
    """Create the standard directory structure for a Go CLI project."""
    directories = [
        "cmd",
        "internal/config",
        "internal/database",
        ".github/workflows",
        "docs/dev-sessions",
    ]

    for directory in directories:
        dir_path = project_path / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}/")


def copy_template(template_name, dest_path, replacements=None):
    """Copy a template file and perform variable substitutions."""
    script_dir = Path(__file__).parent
    template_path = script_dir.parent / "assets" / "templates" / template_name

    if not template_path.exists():
        print(f"❌ Template not found: {template_name}")
        return False

    # Read template content
    with open(template_path, 'r') as f:
        content = f.read()

    # Perform replacements if provided
    if replacements:
        for key, value in replacements.items():
            content = content.replace(f"{{{{{key}}}}}", value)

    # Write to destination
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, 'w') as f:
        f.write(content)

    print(f"✅ Created: {dest_path.relative_to(dest_path.parents[len(dest_path.parents) - 2])}")
    return True


def scaffold_project(project_name, output_dir="."):
    """Scaffold a complete Go CLI project."""
    # Create project directory
    project_path = Path(output_dir) / project_name
    if project_path.exists():
        print(f"❌ Directory already exists: {project_path}")
        sys.exit(1)

    project_path.mkdir(parents=True, exist_ok=True)
    print(f"🚀 Scaffolding Go CLI project: {project_name}")
    print(f"   Location: {project_path.absolute()}\n")

    # Prepare replacements
    replacements = {
        "PROJECT_NAME": project_name,
        "MODULE_NAME": f"github.com/yourusername/{project_name}",  # User should update this
        "YEAR": str(datetime.now().year),
    }

    # Create directory structure
    create_directory_structure(project_path)

    # Copy template files
    templates = [
        ("main.go", project_path / "main.go"),
        ("go.mod.template", project_path / "go.mod"),
        ("Makefile.template", project_path / "Makefile"),
        ("gitignore.template", project_path / ".gitignore"),
        ("config.yaml.example", project_path / f"{project_name}.yaml.example"),
        ("root.go.template", project_path / "cmd" / "root.go"),
        ("version.go.template", project_path / "cmd" / "version.go"),
        ("constants.go.template", project_path / "cmd" / "constants.go"),
        ("config.go.template", project_path / "internal" / "config" / "config.go"),
        ("database.go.template", project_path / "internal" / "database" / "database.go"),
        ("migrations.go.template", project_path / "internal" / "database" / "migrations.go"),
        ("schema.sql.template", project_path / "internal" / "database" / "schema.sql"),
        ("ci.yml.template", project_path / ".github" / "workflows" / "ci.yml"),
        ("release.yml.template", project_path / ".github" / "workflows" / "release.yml"),
        ("rolling-release.yml.template", project_path / ".github" / "workflows" / "rolling-release.yml"),
    ]

    for template_name, dest_path in templates:
        copy_template(template_name, dest_path, replacements)

    print(f"\n✅ Project '{project_name}' scaffolded successfully!\n")
    print("Next steps:")
    print(f"1. cd {project_name}")
    print("2. Update go.mod with your actual module name")
    print("3. Update GitHub Actions workflows with your Docker Hub username (if needed)")
    print("4. Run: make setup")
    print("5. Run: go mod tidy")
    print("6. Start adding commands in cmd/")


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new Go CLI project")
    parser.add_argument("project_name", help="Name of the project")
    parser.add_argument("--path", default=".", help="Output directory (default: current directory)")

    args = parser.parse_args()
    scaffold_project(args.project_name, args.path)


if __name__ == "__main__":
    main()
