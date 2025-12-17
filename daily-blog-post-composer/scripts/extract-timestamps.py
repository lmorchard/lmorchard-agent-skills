#!/usr/bin/env python3
"""
Extract timestamps from Mastodon and Linkding source files.

This script parses mastodon.md and linkding.md files to extract:
- Mastodon post timestamps (created_at)
- Linkding bookmark creation dates (date_added)
- Maps content to timestamps for focused post timing
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


def parse_mastodon_md(file_path: Path) -> List[Dict[str, Any]]:
    """Parse mastodon.md file and extract posts with timestamps."""
    
    if not file_path.exists():
        return []
    
    content = file_path.read_text()
    posts = []
    
    # Pattern for Mastodon post headers
    # Example: ### Post: https://masto.hackers.town/@user/12345
    # Followed by: Created: 2025-12-15T14:23:00Z
    
    post_pattern = r'### Post: (https://[^\s]+)'
    created_pattern = r'Created: ([^\n]+)'
    
    # Split by post headers
    sections = re.split(post_pattern, content)
    
    for i in range(1, len(sections), 2):
        if i + 1 < len(sections):
            url = sections[i].strip()
            post_content = sections[i + 1]
            
            # Extract timestamp
            created_match = re.search(created_pattern, post_content)
            timestamp = None
            if created_match:
                timestamp_str = created_match.group(1).strip()
                try:
                    # Parse ISO format timestamp
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except ValueError:
                    print(f"Warning: Could not parse timestamp: {timestamp_str}", file=sys.stderr)
            
            # Extract post ID from URL
            post_id = None
            id_match = re.search(r'/@[^/]+/(\d+)', url)
            if id_match:
                post_id = id_match.group(1)
            
            posts.append({
                "url": url,
                "post_id": post_id,
                "timestamp": timestamp.isoformat() if timestamp else None,
                "content": post_content.strip()
            })
    
    return posts


def parse_linkding_md(file_path: Path) -> List[Dict[str, Any]]:
    """Parse linkding.md file and extract bookmarks with timestamps."""
    
    if not file_path.exists():
        return []
    
    content = file_path.read_text()
    bookmarks = []
    
    # Pattern for bookmark entries
    # Example: - [Title](https://example.com)
    # Followed by optional: Date Added: 2025-12-15
    
    bookmark_pattern = r'- \[([^\]]+)\]\(([^)]+)\)'
    date_pattern = r'Date Added: ([^\n]+)'
    
    # Find all bookmarks
    for match in re.finditer(bookmark_pattern, content):
        title = match.group(1).strip()
        url = match.group(2).strip()
        
        # Look for date in the text following this bookmark
        # (typically on the next line or nearby)
        start_pos = match.end()
        following_text = content[start_pos:start_pos + 500]
        
        timestamp = None
        date_match = re.search(date_pattern, following_text)
        if date_match:
            date_str = date_match.group(1).strip()
            try:
                # Parse date (format may vary)
                # Try common formats
                for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        timestamp = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
            except Exception as e:
                print(f"Warning: Could not parse date: {date_str}", file=sys.stderr)
        
        bookmarks.append({
            "title": title,
            "url": url,
            "timestamp": timestamp.isoformat() if timestamp else None
        })
    
    return bookmarks


def find_earliest_timestamp(urls: List[str], posts: List[Dict], bookmarks: List[Dict]) -> Optional[str]:
    """Find the earliest timestamp for a list of URLs."""
    
    timestamps = []
    
    # Check Mastodon posts
    for post in posts:
        if post["url"] in urls and post["timestamp"]:
            timestamps.append(post["timestamp"])
    
    # Check bookmarks
    for bookmark in bookmarks:
        if bookmark["url"] in urls and bookmark["timestamp"]:
            timestamps.append(bookmark["timestamp"])
    
    if not timestamps:
        return None
    
    # Return earliest
    return min(timestamps)


def main():
    parser = argparse.ArgumentParser(
        description="Extract timestamps from Mastodon and Linkding source files"
    )
    parser.add_argument(
        "--mastodon",
        type=Path,
        default=Path("data/latest/mastodon.md"),
        help="Path to mastodon.md file (default: data/latest/mastodon.md)"
    )
    parser.add_argument(
        "--linkding",
        type=Path,
        default=Path("data/latest/linkding.md"),
        help="Path to linkding.md file (default: data/latest/linkding.md)"
    )
    parser.add_argument(
        "--urls",
        nargs="+",
        help="Find earliest timestamp for specific URLs"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    
    args = parser.parse_args()
    
    # Parse source files
    mastodon_posts = parse_mastodon_md(args.mastodon)
    linkding_bookmarks = parse_linkding_md(args.linkding)
    
    if args.urls:
        # Find earliest timestamp for provided URLs
        earliest = find_earliest_timestamp(args.urls, mastodon_posts, linkding_bookmarks)
        if earliest:
            # Parse and format for display
            dt = datetime.fromisoformat(earliest)
            print(dt.strftime("%H:%M:%S"))
        else:
            print("No timestamps found for provided URLs", file=sys.stderr)
            sys.exit(1)
    else:
        # Output all extracted data
        result = {
            "mastodon_posts": mastodon_posts,
            "linkding_bookmarks": linkding_bookmarks,
            "mastodon_count": len(mastodon_posts),
            "linkding_count": len(linkding_bookmarks)
        }
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Mastodon posts: {len(mastodon_posts)}")
            print(f"Linkding bookmarks: {len(linkding_bookmarks)}")
            print()
            print("Mastodon post timestamps:")
            for post in mastodon_posts[:5]:  # Show first 5
                timestamp = post["timestamp"] if post["timestamp"] else "No timestamp"
                print(f"  {post['post_id']}: {timestamp}")
            if len(mastodon_posts) > 5:
                print(f"  ... and {len(mastodon_posts) - 5} more")
            print()
            print("Linkding bookmark timestamps:")
            for bookmark in linkding_bookmarks[:5]:  # Show first 5
                timestamp = bookmark["timestamp"] if bookmark["timestamp"] else "No timestamp"
                print(f"  {bookmark['title']}: {timestamp}")
            if len(linkding_bookmarks) > 5:
                print(f"  ... and {len(linkding_bookmarks) - 5} more")


if __name__ == "__main__":
    main()
