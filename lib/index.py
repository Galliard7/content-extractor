"""NDJSON index — append-friendly, grep-able content index."""

import json
import os

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cf_lib import INDEX_PATH, DATA_DIR


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def append_entry(entry):
    """Append an entry dict as a single NDJSON line."""
    _ensure_dir()
    with open(INDEX_PATH, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_entries():
    """Read all index entries. Returns list of dicts."""
    if not os.path.exists(INDEX_PATH):
        return []
    entries = []
    with open(INDEX_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def update_entry(entry_id, updates):
    """Update an entry by ID. Rewrites the full index. Returns updated entry or None."""
    entries = read_entries()
    updated = None
    for entry in entries:
        if entry.get("id") == entry_id:
            entry.update(updates)
            updated = entry
            break
    if updated:
        _rewrite(entries)
    return updated


def remove_entry(entry_id):
    """Remove an entry by ID. Rewrites the full index. Returns removed entry or None."""
    entries = read_entries()
    removed = None
    remaining = []
    for entry in entries:
        if entry.get("id") == entry_id:
            removed = entry
        else:
            remaining.append(entry)
    if removed:
        _rewrite(remaining)
    return removed


def search_entries(query=None, content_type=None, tag=None, limit=None):
    """Search entries with optional filters. Returns list of matching entries."""
    entries = read_entries()
    results = []

    for entry in entries:
        if content_type and entry.get("type") != content_type:
            continue
        if tag and tag not in entry.get("tags", []):
            continue
        if query:
            q = query.lower()
            searchable = " ".join([
                entry.get("title", "") or "",
                entry.get("domain", "") or "",
                entry.get("url", "") or "",
                " ".join(entry.get("tags", [])),
            ]).lower()
            if q not in searchable:
                continue
        results.append(entry)

    if limit:
        results = results[-limit:]

    return results


def _rewrite(entries):
    """Rewrite the full index atomically."""
    _ensure_dir()
    tmp = INDEX_PATH + ".tmp"
    with open(tmp, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    os.replace(tmp, INDEX_PATH)
