"""Text extractor — raw text, stdin, and file ingestion."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from cf_lib import LIMITS, now_iso


def extract_text(text_content, source="arg", title=None, original_path=None):
    """Process raw text content.

    Args:
        text_content: The text string to ingest.
        source: One of "arg", "stdin", "file".
        title: Optional explicit title.
        original_path: Original file path (for source="file").

    Returns extractor result dict.
    """
    original_bytes = len(text_content.encode("utf-8"))
    truncated = False

    if original_bytes > LIMITS["MAX_TEXT_BYTES"]:
        # Truncate at byte boundary (approximate via char slice)
        text_content = text_content[: LIMITS["MAX_TEXT_BYTES"]]
        truncated = True

    content_bytes = len(text_content.encode("utf-8"))

    # Auto-title from first line
    if not title:
        first_line = text_content.split("\n")[0].strip()
        words = first_line.split()[:8]
        title = " ".join(words) if words else "Untitled Text"

    type_specific = {
        "source": source,
        "truncated": truncated,
        "original_bytes": original_bytes,
    }
    if source == "file" and original_path:
        type_specific["original_path"] = original_path

    return {
        "success": True,
        "title": title,
        "content": text_content,
        "type": "text",
        "domain": "text",
        "artifacts": {},
        "type_specific": type_specific,
        "error": None,
    }
