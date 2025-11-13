#!/usr/bin/env python3
"""
Compose weeknotes blog post from fetched source data.

This script reads markdown files from data sources (Mastodon, Linkding) and
combines them into a Jekyll-style blog post with YAML frontmatter.
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


def compose_weeknotes(
    input_dir: Path,
    output_file: Path | None,
    title: str | None,
    start_date: str | None,
    end_date: str | None,
) -> str:
    """
    Compose weeknotes from fetched data.

    Args:
        input_dir: Directory containing fetched markdown files
        output_file: Output file path (None for stdout)
        title: Custom title for the post
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        The composed weeknotes content
    """
    print("╔════════════════════════════════════════╗")
    print("║   Weeknotes Composer                   ║")
    print("╚════════════════════════════════════════╝")
    print()

    # Check if input directory exists
    if not input_dir.exists():
        print(f"❌ Input directory not found: {input_dir}")
        print("   Please run fetch-sources.sh first")
        sys.exit(1)

    # Read source files
    mastodon_file = input_dir / "mastodon.md"
    linkding_file = input_dir / "linkding.md"

    if mastodon_file.exists():
        mastodon_content = mastodon_file.read_text()
    else:
        print(f"⚠️  Warning: {mastodon_file} not found")
        mastodon_content = "*No Mastodon activity found for this period.*"

    if linkding_file.exists():
        linkding_content = linkding_file.read_text()
    else:
        print(f"⚠️  Warning: {linkding_file} not found")
        linkding_content = "*No bookmarks found for this period.*"

    # Determine dates
    if not start_date or not end_date:
        start_date, end_date = get_current_week_dates()

    week_range = f"{start_date} to {end_date}"

    # Use custom title if provided
    if not title:
        title = f"Weeknotes for {week_range}"

    # Post date is typically the end date of the week
    post_date = end_date

    print(f"📅 Date range: {start_date} to {end_date}")
    print(f"📝 Title: {title}")
    print()

    # Load template
    template_file = Path(__file__).parent.parent / "assets" / "weeknotes-template.md"
    if not template_file.exists():
        print(f"❌ Template not found: {template_file}")
        sys.exit(1)

    template = template_file.read_text()

    # Replace placeholders
    output_content = template.replace("{{WEEK_RANGE}}", week_range)
    output_content = output_content.replace("{{POST_DATE}}", post_date)
    output_content = output_content.replace("{{START_DATE}}", start_date)
    output_content = output_content.replace("{{END_DATE}}", end_date)
    output_content = output_content.replace("{{TITLE}}", title)
    output_content = output_content.replace("{{MASTODON_CONTENT}}", mastodon_content)
    output_content = output_content.replace("{{LINKDING_CONTENT}}", linkding_content)

    # Output to file or stdout
    if output_file:
        output_file.write_text(output_content)
        print(f"✅ Weeknotes post saved to: {output_file}")
        print()
    else:
        print(output_content)

    print("╔════════════════════════════════════════╗")
    print("║   Composition Complete!                ║")
    print("╚════════════════════════════════════════╝")
    print()

    return output_content


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Compose weeknotes blog post from fetched source data"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        help="Input directory with fetched data (default: data/latest)",
    )
    parser.add_argument(
        "--output", "-o", type=Path, help="Output file (default: stdout)"
    )
    parser.add_argument("--title", help="Custom title for the post")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")

    args = parser.parse_args()

    # Set default input directory
    if not args.input_dir:
        args.input_dir = Path(__file__).parent.parent / "data" / "latest"

    compose_weeknotes(
        input_dir=args.input_dir,
        output_file=args.output,
        title=args.title,
        start_date=args.start,
        end_date=args.end,
    )


if __name__ == "__main__":
    main()
