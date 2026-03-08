"""Bundle storage — create bundles, write meta.json and content.md."""

import json
import os

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cf_lib import LIBRARY_DIR, now_iso, today_stamp, next_id

from .util import slugify


def create_bundle(type_tag, name_hint, url=None):
    """Create a new bundle directory and return (bundle_id, bundle_path).

    Directory format: {date}__{type}__{slug}__{cf-NNNN}
    """
    bundle_id = next_id()
    slug = slugify(name_hint, 30)
    date = today_stamp()
    folder_name = f"{date}__{type_tag}__{slug}__{bundle_id}"
    bundle_path = os.path.join(LIBRARY_DIR, folder_name)
    os.makedirs(bundle_path, exist_ok=True)
    return bundle_id, bundle_path


def write_meta(bundle_path, meta):
    """Write meta.json into a bundle (atomic)."""
    path = os.path.join(bundle_path, "meta.json")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def write_content(bundle_path, text, filename="content.md"):
    """Write content file into a bundle."""
    path = os.path.join(bundle_path, filename)
    with open(path, "w") as f:
        f.write(text)


def ensure_subdir(bundle_path, *parts):
    """Create a subdirectory inside a bundle and return its path."""
    sub = os.path.join(bundle_path, *parts)
    os.makedirs(sub, exist_ok=True)
    return sub


def read_meta(bundle_path):
    """Read meta.json from a bundle. Returns dict or None."""
    path = os.path.join(bundle_path, "meta.json")
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def read_content(bundle_path, filename="content.md"):
    """Read content file from a bundle. Returns str or None."""
    path = os.path.join(bundle_path, filename)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return f.read()
