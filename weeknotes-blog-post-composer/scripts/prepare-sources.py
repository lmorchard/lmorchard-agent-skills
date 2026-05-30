#!/usr/bin/env python3
"""
Prepare fetched source data for composition.

This script reads the fetched markdown files and displays them for Claude
to read and compose into a cohesive weeknotes blog post.
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path


def get_current_week_dates():
    """Calculate dates for the last 7 days (7 days ago to today)."""
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)
    return seven_days_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Prepare fetched source data for weeknotes composition"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        help="Input directory with fetched data (default: ~/.claude/cache/weeknotes-blog-post-composer/data/latest)",
    )
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")

    args = parser.parse_args()

    # Set default input directory
    if not args.input_dir:
        home = Path.home()
        args.input_dir = home / ".claude" / "cache" / "weeknotes-blog-post-composer" / "data" / "latest"

    print("╔════════════════════════════════════════╗")
    print("║   Weeknotes Source Preparation        ║")
    print("╚════════════════════════════════════════╝")
    print()

    # Check if input directory exists
    if not args.input_dir.exists():
        print(f"❌ Input directory not found: {args.input_dir}")
        print("   Please run fetch-sources.sh first")
        sys.exit(1)

    # Determine dates
    if not args.start or not args.end:
        args.start, args.end = get_current_week_dates()

    week_range = f"{args.start} to {args.end}"
    print(f"📅 Date range: {week_range}")
    print()

    # Check for source files
    # The me-to-markdown orchestrator writes a single combined.md with
    # per-source sections (Mastodon, Linkding, GitHub, Spotify, YouTube,
    # Pocket Casts).
    combined_file = args.input_dir / "combined.md"

    if not combined_file.exists():
        print("❌ No source data found!")
        print(f"   Expected combined.md in: {args.input_dir}")
        print("   Run fetch-sources.sh first.")
        sys.exit(1)

    size = combined_file.stat().st_size
    print("📂 Available source data:")
    print(f"   ✅ Combined sources: {combined_file} ({size:,} bytes)")
    print("      Sections: Mastodon, Linkding, GitHub, Spotify, YouTube, Pocket Casts")

    print()
    print("╔════════════════════════════════════════╗")
    print("║   Ready for Composition                ║")
    print("╚════════════════════════════════════════╝")
    print()
    print("Source data is ready to be read and composed into a weeknotes post.")
    print()
    print("Next steps:")
    print(f"1. Read: {combined_file}")
    print(f"2. Compose conversational weeknotes for {week_range}")
    print("3. Write the composed post with Jekyll frontmatter")
    print()


if __name__ == "__main__":
    main()
