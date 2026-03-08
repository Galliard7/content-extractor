"""Utility functions — slugify, domain extraction, title extraction, tool checks."""

import html
import re
import shutil
from urllib.parse import urlparse


def slugify(text, max_len=40):
    """Convert text to URL-safe slug."""
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s[:max_len]


def extract_domain(url):
    """Extract domain from URL, stripping www. prefix."""
    try:
        hostname = urlparse(url).hostname or "unknown"
        return re.sub(r"^www\.", "", hostname)
    except Exception:
        return "unknown"


def extract_title(text):
    """Extract a title from markdown/text content."""
    # Try markdown heading first
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if m:
        return m.group(1).strip()

    # Fall back to first non-empty line
    for line in text.split("\n"):
        line = line.strip()
        if line:
            return re.sub(r"^#+\s*", "", line)[:80]

    return "Untitled"


def extract_html_title(html_text):
    """Extract <title> from HTML."""
    m = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    if m:
        return html.unescape(m.group(1)).strip()
    return ""


def fix_mojibake(text):
    """Attempt to fix UTF-8 mojibake (latin1-misencoded text)."""
    if not text:
        return text
    if re.search(r"\u00e2\u0080[\u0090-\u009f]", text):
        try:
            return text.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
    return text


def time_to_seconds(time_str):
    """Convert MM:SS or HH:MM:SS to seconds."""
    parts = [int(p) for p in time_str.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return 0


def seconds_to_time(seconds):
    """Convert seconds to HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def check_tool(name):
    """Check if a CLI tool is available on PATH."""
    return shutil.which(name) is not None
