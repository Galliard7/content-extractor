#!/usr/bin/env python3
"""Content-Extractor: Manage tags on library entries."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cf_lib import LIBRARY_DIR
from lib.index import read_entries, update_entry
from lib.storage import read_meta, write_meta


def _find_bundle_path(entry_id):
    """Find bundle directory for an entry ID."""
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
    parser = argparse.ArgumentParser(description="Manage tags on library entries")
    parser.add_argument("--id", required=True, dest="entry_id", help="Entry ID (e.g. cf-0001)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--add", help="Add tag(s), comma-separated")
    group.add_argument("--remove", help="Remove tag(s), comma-separated")
    group.add_argument("--list", action="store_true", help="List current tags")
    args = parser.parse_args()

    bundle_path = _find_bundle_path(args.entry_id)
    if not bundle_path:
        print(f"Error: Entry {args.entry_id} not found.", file=sys.stderr)
        sys.exit(1)

    meta = read_meta(bundle_path)
    if not meta:
        print(f"Error: No meta.json for {args.entry_id}.", file=sys.stderr)
        sys.exit(1)

    tags = meta.get("tags", [])

    if args.list:
        if tags:
            print(f"[{args.entry_id}] Tags: {', '.join(tags)}")
        else:
            print(f"[{args.entry_id}] No tags.")
        return

    if args.add:
        new_tags = [t.strip() for t in args.add.split(",") if t.strip()]
        for t in new_tags:
            if t not in tags:
                tags.append(t)

    if args.remove:
        rm_tags = {t.strip() for t in args.remove.split(",") if t.strip()}
        tags = [t for t in tags if t not in rm_tags]

    # Update both meta.json and index
    meta["tags"] = tags
    write_meta(bundle_path, meta)
    update_entry(args.entry_id, {"tags": tags})

    print(f"[{args.entry_id}] Tags: {', '.join(tags) if tags else '(none)'}")


if __name__ == "__main__":
    main()
