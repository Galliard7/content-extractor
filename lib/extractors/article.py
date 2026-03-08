"""Article extractor — fetch HTML, extract readable text, mirror images."""

import os
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from cf_lib import LIMITS

from ..util import extract_html_title, extract_title, extract_domain
from ..images import extract_image_urls, download_image
from ..security import validate_url


def _extract_readable_text(html_text):
    """Extract readable text from HTML using BeautifulSoup."""
    soup = BeautifulSoup(html_text, "lxml")

    # Remove non-content elements
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()

    # Try <article> or <main> first for focused content
    content_el = soup.find("article") or soup.find("main") or soup.find("body") or soup
    text = content_el.get_text(separator="\n", strip=True)

    # Clean up excessive whitespace
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    text = "\n\n".join(lines)

    readability_warning = len(text) < 500
    return text, readability_warning


def extract_article(url, bundle_path, debug=False):
    """Fetch a URL as an article, extract text and images.

    Args:
        url: The URL to fetch.
        bundle_path: Path to the bundle directory (for saving images).
        debug: If True, save raw.html.

    Returns extractor result dict.
    """
    # Security gate
    validation = validate_url(url)
    if not validation["allowed"]:
        return {
            "success": False,
            "title": "Blocked URL",
            "content": f"URL blocked by security gate: {validation['reason']}",
            "type": "article",
            "domain": extract_domain(url),
            "artifacts": {"blocked": True, "blocked_reason": validation["reason"]},
            "type_specific": {"resolved_ip": validation["resolved_ip"]},
            "error": validation["reason"],
        }

    # Fetch
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=LIMITS["BASE_TIMEOUT"],
            stream=True,
        )
        resp.raise_for_status()

        # Read with size limit
        content_chunks = []
        total = 0
        for chunk in resp.iter_content(8192):
            total += len(chunk)
            if total > LIMITS["MAX_BYTES"]:
                break
            content_chunks.append(chunk)
        html_text = b"".join(content_chunks).decode("utf-8", errors="replace")
    except Exception as e:
        return {
            "success": False,
            "title": "Failed to fetch",
            "content": f"Error: {e}",
            "type": "article",
            "domain": extract_domain(url),
            "artifacts": {},
            "type_specific": {"resolved_ip": validation.get("resolved_ip")},
            "error": str(e),
        }

    # Save raw HTML in debug mode
    artifacts = {}
    if debug:
        raw_path = os.path.join(bundle_path, "raw.html")
        with open(raw_path, "w") as f:
            f.write(html_text)
        artifacts["raw_html"] = True

    # Extract text
    readable_text, readability_warning = _extract_readable_text(html_text)

    # Title
    html_title = extract_html_title(html_text)
    title = html_title or extract_title(readable_text) or extract_domain(url)

    # Extract and download images
    image_urls = extract_image_urls(html_text, url)
    images_meta = _download_article_images(image_urls, bundle_path)
    if images_meta["downloaded"] > 0:
        artifacts["images_saved"] = True
        artifacts["images_count"] = images_meta["downloaded"]

    type_specific = {
        "resolved_ip": validation.get("resolved_ip"),
        "readability_warning": readability_warning,
        "images": images_meta,
    }

    return {
        "success": True,
        "title": title,
        "content": readable_text,
        "type": "article",
        "domain": extract_domain(url),
        "artifacts": artifacts,
        "type_specific": type_specific,
        "error": None,
    }


def _download_article_images(image_urls, bundle_path):
    """Download article images into bundle/assets/images/."""
    max_images = min(len(image_urls), LIMITS["MAX_IMAGES_PER_ITEM"])
    clamped = len(image_urls) > LIMITS["MAX_IMAGES_PER_ITEM"]

    downloaded = 0
    skipped = 0
    failed = 0
    total_bytes = 0
    sample_errors = []

    if not image_urls:
        return {
            "found": 0, "downloaded": 0, "skipped": 0, "failed": 0,
            "bytes_total": 0, "clamped": False, "sample_errors": [],
        }

    images_dir = os.path.join(bundle_path, "assets", "images")
    os.makedirs(images_dir, exist_ok=True)

    for i in range(max_images):
        img_url = image_urls[i]
        ext = img_url.rsplit(".", 1)[-1].split("?")[0].lower()
        ext = ext if ext in ("jpg", "jpeg", "png", "gif", "webp") else "jpg"
        dest = os.path.join(images_dir, f"image_{i+1:03d}.{ext}")

        result = download_image(img_url, dest, max_bytes=LIMITS["MAX_IMAGE_BYTES"])
        if result["success"]:
            downloaded += 1
            total_bytes += result["bytes"]
        elif result.get("error", "").startswith("SVG"):
            skipped += 1
        else:
            failed += 1
            if len(sample_errors) < 3:
                sample_errors.append(result.get("error", "unknown"))

    return {
        "found": len(image_urls),
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "bytes_total": total_bytes,
        "clamped": clamped,
        "sample_errors": sample_errors,
    }
