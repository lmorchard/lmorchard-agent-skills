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
    mastodon_file = args.input_dir / "mastodon.md"
    linkding_file = args.input_dir / "linkding.md"

    has_mastodon = mastodon_file.exists()
    has_linkding = linkding_file.exists()

    if not has_mastodon and not has_linkding:
        print("❌ No source data found!")
        print(f"   Expected files in: {args.input_dir}")
        sys.exit(1)

    print("📂 Available source data:")
    if has_mastodon:
        size = mastodon_file.stat().st_size
        print(f"   ✅ Mastodon posts: {mastodon_file} ({size:,} bytes)")
    else:
        print(f"   ⚠️  No Mastodon data: {mastodon_file}")

    if has_linkding:
        size = linkding_file.stat().st_size
        print(f"   ✅ Linkding bookmarks: {linkding_file} ({size:,} bytes)")
    else:
        print(f"   ⚠️  No Linkding data: {linkding_file}")

    print()
    print("╔════════════════════════════════════════╗")
    print("║   Ready for Composition                ║")
    print("╚════════════════════════════════════════╝")
    print()
    print("Source files are ready to be read and composed into a weeknotes post.")
    print()
    print("Next steps:")
    print(f"1. Read: {mastodon_file}")
    if has_linkding:
        print(f"2. Read: {linkding_file}")
    print(f"3. Compose conversational weeknotes for {week_range}")
    print("4. Write the composed post with Jekyll frontmatter")
    print()


if __name__ == "__main__":
    main()
