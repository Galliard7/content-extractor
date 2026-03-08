#!/usr/bin/env python3
"""Content-Extractor: Delete a library entry."""

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cf_lib import LIBRARY_DIR
from lib.index import read_entries, remove_entry


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
    parser = argparse.ArgumentParser(description="Delete a library entry")
    parser.add_argument("--id", required=True, dest="entry_id", help="Entry ID (e.g. cf-0001)")
    parser.add_argument("--confirm", action="store_true", help="Skip confirmation")
    args = parser.parse_args()

    bundle_path = _find_bundle_path(args.entry_id)
    if not bundle_path:
        print(f"Error: Entry {args.entry_id} not found.", file=sys.stderr)
        sys.exit(1)

    if not args.confirm:
        print(f"Will delete: {args.entry_id} ({os.path.basename(bundle_path)})")
        print("Re-run with --confirm to proceed.")
        return

    # Remove bundle directory
    shutil.rmtree(bundle_path, ignore_errors=True)

    # Remove index entry
    removed = remove_entry(args.entry_id)

    if removed:
        print(f"Deleted: [{args.entry_id}] {removed.get('title', 'Untitled')}")
    else:
        print(f"Deleted bundle directory. Index entry not found (may have been already removed).")


if __name__ == "__main__":
    main()
