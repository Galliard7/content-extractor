"""Image downloading with magic-byte validation and HTML image URL extraction."""

import os
import struct
import tempfile

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .security import validate_url

# Timeout for image downloads (seconds)
_DOWNLOAD_TIMEOUT = 20

# Magic byte signatures
_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG": "image/png",
    b"GIF": "image/gif",
}


def _detect_content_type(header_bytes):
    """Detect image content type from magic bytes. Returns MIME type or None."""
    for sig, mime in _SIGNATURES.items():
        if header_bytes[: len(sig)] == sig:
            return mime
    # WebP: RIFF....WEBP
    if len(header_bytes) >= 12 and header_bytes[:4] == b"RIFF" and header_bytes[8:12] == b"WEBP":
        return "image/webp"
    # SVG detection
    start = header_bytes[:200].lstrip()
    if start.startswith(b"<svg") or start.startswith(b"<?xml"):
        return "image/svg+xml"
    return None


def download_image(url, dest_path, max_bytes=15 * 1024 * 1024):
    """Download an image, validate via magic bytes, save to dest_path.

    Returns dict: {"success", "bytes", "content_type", "error"}
    """
    # Security gate
    validation = validate_url(url)
    if not validation["allowed"]:
        return {
            "success": False,
            "bytes": 0,
            "content_type": None,
            "error": f"Security gate blocked: {validation['reason']}",
        }

    # Skip SVG by URL
    url_lower = url.lower()
    if url_lower.endswith(".svg") or ".svg?" in url_lower:
        return {
            "success": False,
            "bytes": 0,
            "content_type": "image/svg+xml",
            "error": "SVG skipped by policy",
        }

    tmp_path = dest_path + ".tmp"
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_DOWNLOAD_TIMEOUT,
            stream=True,
        )
        resp.raise_for_status()

        downloaded = 0
        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                downloaded += len(chunk)
                if downloaded > max_bytes:
                    break
                f.write(chunk)

        if downloaded == 0:
            _cleanup(tmp_path)
            return {"success": False, "bytes": 0, "content_type": None, "error": "Empty download"}

        # Validate magic bytes
        with open(tmp_path, "rb") as f:
            header = f.read(200)

        content_type = _detect_content_type(header)
        if content_type == "image/svg+xml":
            _cleanup(tmp_path)
            return {"success": False, "bytes": 0, "content_type": "image/svg+xml", "error": "SVG detected and skipped"}
        if not content_type:
            _cleanup(tmp_path)
            return {"success": False, "bytes": downloaded, "content_type": None, "error": "Not a recognized image format"}

        os.replace(tmp_path, dest_path)
        return {"success": True, "bytes": downloaded, "content_type": content_type, "error": None}

    except Exception as e:
        _cleanup(tmp_path)
        return {"success": False, "bytes": 0, "content_type": None, "error": str(e)}


def _cleanup(path):
    try:
        if os.path.exists(path):
            os.unlink(path)
    except OSError:
        pass


def extract_image_urls(html_text, page_url):
    """Extract image URLs from HTML using BeautifulSoup.

    Returns list of absolute URLs (deduplicated).
    """
    soup = BeautifulSoup(html_text, "lxml")
    urls = set()

    # <img> tags — src, data-src, data-original, data-lazy-src
    for img in soup.find_all("img"):
        for attr in ("src", "data-src", "data-original", "data-lazy-src"):
            val = img.get(attr)
            if val:
                urls.add(val)

        # srcset — pick largest
        srcset = img.get("srcset")
        if srcset:
            best_url, best_mult = None, 0
            for item in srcset.split(","):
                parts = item.strip().split()
                if not parts:
                    continue
                u = parts[0]
                mult = 1.0
                if len(parts) > 1:
                    try:
                        mult = float(parts[1].rstrip("xw"))
                    except ValueError:
                        pass
                if mult > best_mult:
                    best_mult = mult
                    best_url = u
            if best_url:
                urls.add(best_url)

    # og:image
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        urls.add(og["content"])

    # twitter:image
    tw = soup.find("meta", attrs={"name": "twitter:image"})
    if tw and tw.get("content"):
        urls.add(tw["content"])

    # Resolve relative URLs and deduplicate
    resolved = []
    seen = set()
    for u in urls:
        try:
            absolute = urljoin(page_url, u)
            if absolute not in seen:
                seen.add(absolute)
                resolved.append(absolute)
        except Exception:
            pass

    return resolved
