#!/usr/bin/env python3
"""Content-Extractor: List library entries."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.index import read_entries


def main():
    parser = argparse.ArgumentParser(description="List content library entries")
    parser.add_argument("--recent", type=int, default=10, help="Show N most recent (default: 10)")
    parser.add_argument("--type", dest="content_type", help="Filter by type (article, pdf, youtube, text, ocr)")
    parser.add_argument("--tag", help="Filter by tag")
    parser.add_argument("--all", action="store_true", help="Show all entries")
    args = parser.parse_args()

    entries = read_entries()

    # Apply filters
    if args.content_type:
        entries = [e for e in entries if e.get("type") == args.content_type]
    if args.tag:
        entries = [e for e in entries if args.tag in e.get("tags", [])]

    # Limit
    if not args.all:
        entries = entries[-args.recent:]

    if not entries:
        print("No entries found.")
        return

    # Format output
    for e in entries:
        status = "OK" if e.get("success") else "FAIL"
        tags = ", ".join(e.get("tags", [])) if e.get("tags") else ""
        tag_str = f" [{tags}]" if tags else ""
        title = e.get("title", "Untitled")
        etype = e.get("type", "?")
        eid = e.get("id", "?")
        date = e.get("captured_at", "")[:10]

        print(f"{eid}  {date}  {etype:8s}  {status:4s}  {title}{tag_str}")

    print(f"\n{len(entries)} entries shown.")


if __name__ == "__main__":
    main()
