#!/usr/bin/env python3
"""Content-Extractor: Retrieve a bundle's content or metadata."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cf_lib import LIBRARY_DIR
from lib.index import read_entries
from lib.storage import read_meta, read_content


def _find_bundle_path(entry_id):
    """Find the bundle directory for a given entry ID."""
    entries = read_entries()
    for e in entries:
        if e.get("id") == entry_id:
            bundle_dir = e.get("bundle_dir")
            if bundle_dir:
                path = os.path.join(LIBRARY_DIR, bundle_dir)
                if os.path.isdir(path):
                    return path
    return None


def main():
    parser = argparse.ArgumentParser(description="Get content from library")
    parser.add_argument("--id", required=True, dest="entry_id", help="Entry ID (e.g. cf-0001)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--meta", action="store_true", help="Show metadata (JSON)")
    group.add_argument("--content", action="store_true", help="Show content text")
    group.add_argument("--summary", action="store_true", help="Show summary (default)")
    args = parser.parse_args()

    bundle_path = _find_bundle_path(args.entry_id)
    if not bundle_path:
        print(f"Error: Entry {args.entry_id} not found.", file=sys.stderr)
        sys.exit(1)

    if args.meta:
        meta = read_meta(bundle_path)
        if meta:
            print(json.dumps(meta, indent=2))
        else:
            print("No meta.json found.", file=sys.stderr)
            sys.exit(1)
    elif args.content:
        content = read_content(bundle_path)
        if content:
            print(content)
        else:
            print("No content.md found.", file=sys.stderr)
            sys.exit(1)
    else:
        # Summary (default)
        meta = read_meta(bundle_path)
        content = read_content(bundle_path)

        if meta:
            print(f"ID: {meta.get('id', '?')}")
            print(f"Title: {meta.get('title', 'Untitled')}")
            print(f"Type: {meta.get('type', '?')}")
            print(f"URL: {meta.get('url') or '(none)'}")
            print(f"Domain: {meta.get('domain', '?')}")
            print(f"Captured: {meta.get('captured_at', '?')}")
            print(f"Status: {'OK' if meta.get('success') else 'FAILED'}")
            tags = meta.get("tags", [])
            if tags:
                print(f"Tags: {', '.join(tags)}")
            print(f"Content: {meta.get('content_bytes', 0)} bytes")

            # Artifacts
            artifacts = meta.get("artifacts", {})
            if artifacts:
                parts = [k for k, v in artifacts.items() if v]
                if parts:
                    print(f"Artifacts: {', '.join(parts)}")

        if content:
            preview = content[:500]
            if len(content) > 500:
                preview += "\n... (truncated)"
            print(f"\n--- Content Preview ---\n{preview}")


if __name__ == "__main__":
    main()
