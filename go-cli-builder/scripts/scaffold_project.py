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


def create_directory_structure(project_path, include_database=True, include_templates=False):
    """Create the standard directory structure for a Go CLI project."""
    directories = [
        "cmd",
        "internal/config",
        ".github/workflows",
        "docs/dev-sessions",
    ]

    if include_database:
        directories.append("internal/database")

    if include_templates:
        directories.append("internal/templates")

    for directory in directories:
        dir_path = project_path / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}/")


def copy_template(template_name, dest_path, replacements=None, modify_content=None):
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

    # Allow custom content modification
    if modify_content:
        content = modify_content(content)

    # Write to destination
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, 'w') as f:
        f.write(content)

    print(f"✅ Created: {dest_path.relative_to(dest_path.parents[len(dest_path.parents) - 2])}")
    return True


def scaffold_project(project_name, output_dir=".", include_database=True, include_templates=False):
    """Scaffold a complete Go CLI project."""
    # Create project directory
    project_path = Path(output_dir) / project_name
    if project_path.exists():
        print(f"❌ Directory already exists: {project_path}")
        sys.exit(1)

    project_path.mkdir(parents=True, exist_ok=True)
    print(f"🚀 Scaffolding Go CLI project: {project_name}")
    print(f"   Location: {project_path.absolute()}")
    print(f"   Database support: {'Yes' if include_database else 'No'}")
    print(f"   Template support: {'Yes' if include_templates else 'No'}\n")

    # Prepare replacements
    replacements = {
        "PROJECT_NAME": project_name,
        "MODULE_NAME": f"github.com/yourusername/{project_name}",  # User should update this
        "YEAR": str(datetime.now().year),
    }

    # Create directory structure
    create_directory_structure(project_path, include_database, include_templates)

    # Helper functions for conditional content modification
    def remove_sqlite_from_gomod(content):
        """Remove SQLite dependency from go.mod if database not needed."""
        lines = content.split('\n')
        filtered = [line for line in lines if 'go-sqlite3' not in line]
        return '\n'.join(filtered)

    def remove_database_from_root(content):
        """Remove database-related code from root.go."""
        lines = content.split('\n')
        # Remove database flag and its binding
        filtered = []
        skip_next = False
        for line in lines:
            if 'Database flag' in line or 'database' in line and 'rootCmd.PersistentFlags()' in line:
                continue
            if '"database"' in line and 'BindPFlag' in line:
                continue
            if 'viper.SetDefault("database"' in line:
                continue
            if 'Database: viper.GetString("database")' in line:
                continue
            filtered.append(line)
        return '\n'.join(filtered)

    def remove_database_from_config(content):
        """Remove Database field from config struct."""
        lines = content.split('\n')
        filtered = [line for line in lines if 'Database string' not in line]
        return '\n'.join(filtered)

    def remove_cgo_from_makefile(content):
        """Remove CGO_ENABLED from Makefile."""
        content = content.replace('CGO_ENABLED=1 ', '')
        # Remove SQLite-related comments
        lines = content.split('\n')
        filtered = []
        in_sqlite_comment = False
        for line in lines:
            if 'SQLite requires CGO' in line or 'static linking' in line.lower() and 'sqlite' in line.lower():
                in_sqlite_comment = True
                continue
            if in_sqlite_comment and (line.strip() == '' or not line.startswith('#')):
                in_sqlite_comment = False
            if not in_sqlite_comment:
                filtered.append(line)
        return '\n'.join(filtered)

    # Copy core template files
    copy_template("main.go", project_path / "main.go", replacements)

    # go.mod - conditionally include SQLite
    copy_template("go.mod.template", project_path / "go.mod", replacements,
                  modify_content=None if include_database else remove_sqlite_from_gomod)

    # Makefile - conditionally include CGO
    copy_template("Makefile.template", project_path / "Makefile", replacements,
                  modify_content=None if include_database else remove_cgo_from_makefile)

    copy_template("gitignore.template", project_path / ".gitignore", replacements)
    copy_template("config.yaml.example", project_path / f"{project_name}.yaml.example", replacements)

    # root.go - conditionally include database flags
    copy_template("root.go.template", project_path / "cmd" / "root.go", replacements,
                  modify_content=None if include_database else remove_database_from_root)

    copy_template("version.go.template", project_path / "cmd" / "version.go", replacements)
    copy_template("constants.go.template", project_path / "cmd" / "constants.go", replacements)

    # config.go - conditionally include Database field
    copy_template("config.go.template", project_path / "internal" / "config" / "config.go", replacements,
                  modify_content=None if include_database else remove_database_from_config)

    copy_template("ci.yml.template", project_path / ".github" / "workflows" / "ci.yml", replacements)
    copy_template("release.yml.template", project_path / ".github" / "workflows" / "release.yml", replacements)
    copy_template("rolling-release.yml.template", project_path / ".github" / "workflows" / "rolling-release.yml", replacements)

    # Add database templates if requested
    if include_database:
        copy_template("database.go.template", project_path / "internal" / "database" / "database.go", replacements)
        copy_template("migrations.go.template", project_path / "internal" / "database" / "migrations.go", replacements)
        copy_template("schema.sql.template", project_path / "internal" / "database" / "schema.sql", replacements)

    # Add template support files if requested
    if include_templates:
        copy_template("init.go.template", project_path / "cmd" / "init.go", replacements)
        copy_template("templates.go.template", project_path / "internal" / "templates" / "templates.go", replacements)
        copy_template("default.md.template", project_path / "internal" / "templates" / "default.md", replacements)

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
    parser.add_argument("--no-database", action="store_true", help="Exclude database support (SQLite)")
    parser.add_argument("--templates", action="store_true", help="Include template support (for generating formatted output)")

    args = parser.parse_args()
    scaffold_project(
        args.project_name,
        args.path,
        include_database=not args.no_database,
        include_templates=args.templates
    )


if __name__ == "__main__":
    main()
