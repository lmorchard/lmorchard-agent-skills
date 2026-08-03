#!/usr/bin/env python3
"""
Parse an existing daily blog post file and extract structured information.

This script parses YYYY-MM-DD.md files with the multi-post format:
- Extracts posts and their metadata
- Lists covered URLs and Mastodon post IDs
- Returns structured data for intelligent merging
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def parse_daily_post(file_path: Path) -> dict[str, Any]:
    """Parse a daily post file and extract structured information."""

    if not file_path.exists():
        return {
            "exists": False,
            "posts": [],
            "covered_urls": [],
            "covered_mastodon_ids": [],
            "themes": [],
        }

    content = file_path.read_text()

    # Split by post dividers
    # Pattern: 8<--- { json metadata }
    divider_pattern = r"^8<---\s+(\{[^}]+\})\s*$"

    posts = []
    covered_urls = set()
    covered_mastodon_ids = set()
    themes = set()

    # Split content by dividers
    parts = re.split(divider_pattern, content, flags=re.MULTILINE)

    # First part is any content before first divider (should be empty)
    # Then alternating: metadata, content, metadata, content, ...
    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            metadata_str = parts[i]
            post_content = parts[i + 1]

            try:
                metadata = json.loads(metadata_str)
                posts.append({"metadata": metadata, "content": post_content.strip()})

                # Track theme from non-miscellanea posts
                if metadata.get("type") != "miscellanea":
                    title = metadata.get("title", "")
                    slug = metadata.get("slug", "")
                    themes.add(slug if slug else title.lower().replace(" ", "-"))

            except json.JSONDecodeError as e:
                print(
                    f"Warning: Failed to parse metadata: {metadata_str}",
                    file=sys.stderr,
                )
                print(f"Error: {e}", file=sys.stderr)

    # Extract URLs from all content
    # Match markdown links: [text](url)
    url_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    for post in posts:
        for match in re.finditer(url_pattern, post["content"]):
            url = match.group(2)
            covered_urls.add(url)

            # Extract Mastodon post IDs from URLs
            # Pattern: https://masto.server/@user/12345
            mastodon_match = re.search(r"/@[^/]+/(\d+)", url)
            if mastodon_match:
                covered_mastodon_ids.add(mastodon_match.group(1))

    return {
        "exists": True,
        "post_count": len(posts),
        "posts": posts,
        "covered_urls": sorted(list(covered_urls)),
        "covered_mastodon_ids": sorted(list(covered_mastodon_ids)),
        "themes": sorted(list(themes)),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Parse daily blog post file and extract structured information"
    )
    parser.add_argument("file_path", type=Path, help="Path to YYYY-MM-DD.md file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--summary", action="store_true", help="Output summary only (default)"
    )

    args = parser.parse_args()

    result = parse_daily_post(args.file_path)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        # Summary output
        if not result["exists"]:
            print(f"File does not exist: {args.file_path}")
            print("Starting fresh daily post.")
        else:
            print(f"Parsed: {args.file_path}")
            print(f"Posts: {result['post_count']}")
            print(f"Covered URLs: {len(result['covered_urls'])}")
            print(f"Covered Mastodon IDs: {len(result['covered_mastodon_ids'])}")
            print(
                f"Themes: {', '.join(result['themes']) if result['themes'] else 'none'}"
            )
            print()
            print("Post list:")
            for i, post in enumerate(result["posts"], 1):
                metadata = post["metadata"]
                title = metadata.get("title", "Untitled")
                time = metadata.get("time", "")
                post_type = metadata.get("type", "")
                type_label = f" ({post_type})" if post_type else ""
                print(f"  {i}. {title}{type_label} - {time}")


if __name__ == "__main__":
    main()
