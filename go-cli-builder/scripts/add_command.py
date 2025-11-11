#!/usr/bin/env python3
"""
Add a new command to an existing Go CLI project.

Usage:
    python add_command.py <command-name> [--path <project-dir>]
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime


def add_command(command_name, project_dir="."):
    """Add a new command file to the cmd/ directory."""
    project_path = Path(project_dir)

    # Verify we're in a Go project
    cmd_dir = project_path / "cmd"
    if not cmd_dir.exists():
        print(f"❌ cmd/ directory not found in {project_path}")
        print("   Make sure you're running this from a Go CLI project root")
        sys.exit(1)

    # Check if command already exists
    command_file = cmd_dir / f"{command_name}.go"
    if command_file.exists():
        print(f"❌ Command already exists: {command_file}")
        sys.exit(1)

    # Find and read the template
    script_dir = Path(__file__).parent
    template_path = script_dir.parent / "assets" / "templates" / "command.go.template"

    if not template_path.exists():
        print(f"❌ Template not found: command.go.template")
        sys.exit(1)

    with open(template_path, 'r') as f:
        template_content = f.read()

    # Prepare replacements
    command_name_capitalized = command_name.capitalize()
    replacements = {
        "COMMAND_NAME": command_name,
        "COMMAND_NAME_CAPITALIZED": command_name_capitalized,
    }

    # Perform replacements
    content = template_content
    for key, value in replacements.items():
        content = content.replace(f"{{{{{key}}}}}", value)

    # Write the new command file
    with open(command_file, 'w') as f:
        f.write(content)

    print(f"✅ Created command: cmd/{command_name}.go")
    print(f"\nNext steps:")
    print(f"1. Edit cmd/{command_name}.go to implement your command logic")
    print(f"2. Update the Short and Long descriptions")
    print(f"3. Add any flags or configuration specific to this command")
    print(f"4. Run: make format && make lint")


def main():
    parser = argparse.ArgumentParser(description="Add a new command to a Go CLI project")
    parser.add_argument("command_name", help="Name of the command (e.g., 'fetch', 'export')")
    parser.add_argument("--path", default=".", help="Project directory (default: current directory)")

    args = parser.parse_args()
    add_command(args.command_name, args.path)


if __name__ == "__main__":
    main()
