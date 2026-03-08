#!/usr/bin/env python3
"""Content-Extractor: Search library entries."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.index import search_entries


def main():
    parser = argparse.ArgumentParser(description="Search content library")
    parser.add_argument("--query", "-q", required=True, help="Search query (case-insensitive)")
    parser.add_argument("--type", dest="content_type", help="Filter by type")
    parser.add_argument("--tag", help="Filter by tag")
    parser.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    args = parser.parse_args()

    results = search_entries(
        query=args.query,
        content_type=args.content_type,
        tag=args.tag,
        limit=args.limit,
    )

    if not results:
        print(f"No matches for '{args.query}'.")
        return

    for e in results:
        status = "OK" if e.get("success") else "FAIL"
        tags = ", ".join(e.get("tags", [])) if e.get("tags") else ""
        tag_str = f" [{tags}]" if tags else ""
        title = e.get("title", "Untitled")
        etype = e.get("type", "?")
        eid = e.get("id", "?")
        date = e.get("captured_at", "")[:10]

        print(f"{eid}  {date}  {etype:8s}  {status:4s}  {title}{tag_str}")

    print(f"\n{len(results)} matches.")


if __name__ == "__main__":
    main()
