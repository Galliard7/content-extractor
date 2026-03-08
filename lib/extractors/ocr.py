"""OCR extractor — Tesseract on image files."""

import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from cf_lib import LIMITS

from ..util import check_tool, slugify
from ..storage import create_bundle


def extract_ocr(image_paths, title=None, message_text=None, ocr_lang="eng", debug=False):
    """OCR one or more image files using Tesseract.

    Args:
        image_paths: List of image file paths.
        title: Optional explicit title.
        message_text: Original message text (for parsing "OCR: title" and "lang=xxx").
        ocr_lang: Tesseract language code.
        debug: Keep extra artifacts.

    Returns extractor result dict.
    """
    # Parse title/lang from message text
    if message_text:
        m = re.match(r"^OCR:\s*(.+)", message_text, re.IGNORECASE)
        if m and not title:
            title = re.sub(r"\s+lang=\w+", "", m.group(1), flags=re.IGNORECASE).strip()
        lang_m = re.search(r"lang=(\w+)", message_text, re.IGNORECASE)
        if lang_m:
            ocr_lang = lang_m.group(1)

    if not title:
        title = "OCR Scan"

    # Override with explicit title
    # (already handled above, title param takes precedence if set)

    # Filter valid images
    valid = []
    skipped = 0
    max_images = min(len(image_paths), LIMITS["MAX_OCR_IMAGES"])

    for i in range(max_images):
        path = image_paths[i].strip()
        if not os.path.exists(path):
            skipped += 1
            continue
        if os.path.getsize(path) > LIMITS["MAX_OCR_IMAGE_BYTES"]:
            skipped += 1
            continue
        valid.append(path)

    if not valid:
        return {
            "success": False,
            "title": title,
            "content": "No valid images to process (all skipped or missing)",
            "type": "ocr",
            "domain": "ocr",
            "artifacts": {},
            "type_specific": {"error": "No valid images"},
            "error": "No valid images",
        }

    # Create bundle
    bundle_id, bundle_path = create_bundle("ocr", title)

    # Copy images to source/pages/
    pages_dir = os.path.join(bundle_path, "source", "pages")
    os.makedirs(pages_dir, exist_ok=True)

    copied = []
    for i, img_path in enumerate(valid):
        ext = os.path.splitext(img_path)[1]
        dest = os.path.join(pages_dir, f"page_{i+1:03d}{ext}")
        shutil.copy2(img_path, dest)
        copied.append({"index": i + 1, "path": dest})

    # Run OCR
    if not check_tool("tesseract"):
        return {
            "success": False,
            "title": title,
            "content": "tesseract not available. Install with: brew install tesseract",
            "type": "ocr",
            "domain": "ocr",
            "artifacts": {"ocr_pages_saved": len(copied)},
            "type_specific": {"error": "tesseract not found", "pages": len(copied)},
            "error": "tesseract not available",
            "_bundle_id": bundle_id,
            "_bundle_path": bundle_path,
        }

    page_texts = []
    ocr_error = None

    for page in copied:
        out_base = os.path.join(pages_dir, f"page_{page['index']:03d}_ocr")
        try:
            subprocess.run(
                ["tesseract", page["path"], out_base, "-l", ocr_lang],
                capture_output=True, timeout=60, check=True,
            )
            out_file = f"{out_base}.txt"
            if os.path.exists(out_file):
                text = open(out_file, "r").read().strip()
                if text:
                    page_texts.append({"page": page["index"], "text": text})
                os.unlink(out_file)
        except Exception as e:
            err = f"page {page['index']}: {e}"
            ocr_error = f"{ocr_error}; {err}" if ocr_error else err

    if not page_texts:
        return {
            "success": False,
            "title": title,
            "content": f"OCR failed: {ocr_error or 'No text extracted'}",
            "type": "ocr",
            "domain": "ocr",
            "artifacts": {"ocr_pages_saved": len(copied)},
            "type_specific": {"error": ocr_error, "pages": len(copied), "lang": ocr_lang},
            "error": ocr_error,
            "_bundle_id": bundle_id,
            "_bundle_path": bundle_path,
        }

    # Combine pages
    if len(page_texts) == 1:
        ocr_text = page_texts[0]["text"]
    else:
        parts = []
        for pt in page_texts:
            parts.append(
                f"{'=' * 39}\nPAGE {pt['page']}\n{'=' * 39}\n\n{pt['text']}"
            )
        ocr_text = "\n\n".join(parts)

    clamped = len(image_paths) > LIMITS["MAX_OCR_IMAGES"]

    return {
        "success": True,
        "title": title,
        "content": ocr_text,
        "type": "ocr",
        "domain": "ocr",
        "artifacts": {"ocr_pages_saved": len(copied), "ocr_text_saved": True},
        "type_specific": {
            "pages": len(copied),
            "lang": ocr_lang,
            "clamped": clamped,
            "skipped": skipped,
        },
        "error": None,
        "_bundle_id": bundle_id,
        "_bundle_path": bundle_path,
    }
