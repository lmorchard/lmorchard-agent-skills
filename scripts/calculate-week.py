#!/usr/bin/env python3
"""
Calculate the current ISO week number and generate the weeknotes filename.

Usage:
    ./scripts/calculate-week.py [--date YYYY-MM-DD]

If no date is provided, uses today's date.
"""

import argparse
import os
from datetime import datetime


def calculate_week_info(date=None):
    """Calculate week information for the given date (or today)."""
    if date is None:
        date = datetime.now()
    elif isinstance(date, str):
        date = datetime.strptime(date, '%Y-%m-%d')

    week_number = date.isocalendar()[1]
    year = date.year
    date_str = date.strftime('%Y-%m-%d')

    return {
        'date': date_str,
        'year': year,
        'week': week_number,
        'filename': f"content/posts/{year}/{date_str}-w{week_number:02d}.md",
        'title': f"Weeknotes: {year} Week {week_number}"
    }


def main():
    parser = argparse.ArgumentParser(description='Calculate weeknotes week number and filename')
    parser.add_argument('--date', type=str, help='Date in YYYY-MM-DD format (default: today)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    info = calculate_week_info(args.date)

    if args.json:
        import json
        print(json.dumps(info, indent=2))
    else:
        print(f"Date: {info['date']}")
        print(f"ISO Week: {info['week']}")
        print(f"Title: {info['title']}")
        print(f"Filename: {info['filename']}")


if __name__ == '__main__':
    main()
