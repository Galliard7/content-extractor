"""PDF extractor — download, verify, extract text (pdftotext/pypdf), optional images."""

import os
import subprocess
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from cf_lib import LIMITS

from ..util import extract_domain, check_tool, slugify
from ..security import validate_url


def _is_pdf_magic(file_path):
    """Check if file starts with %PDF- magic bytes."""
    try:
        with open(file_path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except Exception:
        return False


def extract_pdf(url, bundle_path, pdf_images=True, pdf_render_pages=None, pdf_render_dpi=150, debug=False):
    """Download and extract text from a PDF.

    Args:
        url: PDF URL.
        bundle_path: Bundle directory path.
        pdf_images: If True, extract embedded images via pdfimages.
        pdf_render_pages: Page spec string like "1-3" for pdftoppm rendering.
        pdf_render_dpi: DPI for page rendering.
        debug: Keep extra artifacts.

    Returns extractor result dict.
    """
    domain = extract_domain(url)

    # Security gate
    validation = validate_url(url)
    if not validation["allowed"]:
        return {
            "success": False,
            "title": "Blocked PDF",
            "content": f"PDF blocked: {validation['reason']}",
            "type": "pdf",
            "domain": domain,
            "artifacts": {"blocked": True, "blocked_reason": validation["reason"]},
            "type_specific": {"resolved_ip": validation["resolved_ip"]},
            "error": validation["reason"],
        }

    # Download PDF
    source_dir = os.path.join(bundle_path, "source")
    os.makedirs(source_dir, exist_ok=True)
    pdf_path = os.path.join(source_dir, "document.pdf")

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=LIMITS["BASE_TIMEOUT"],
            stream=True,
        )
        resp.raise_for_status()

        downloaded = 0
        with open(pdf_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                downloaded += len(chunk)
                if downloaded > LIMITS["MAX_PDF_BYTES"]:
                    break
                f.write(chunk)
    except Exception as e:
        return {
            "success": False,
            "title": domain,
            "content": f"Error downloading PDF: {e}",
            "type": "pdf",
            "domain": domain,
            "artifacts": {},
            "type_specific": {"resolved_ip": validation.get("resolved_ip")},
            "error": str(e),
        }

    # Verify magic bytes
    if not _is_pdf_magic(pdf_path):
        os.unlink(pdf_path)
        return {
            "success": False,
            "title": domain,
            "content": "Downloaded file is not a PDF",
            "type": "pdf",
            "domain": domain,
            "artifacts": {},
            "type_specific": {"resolved_ip": validation.get("resolved_ip")},
            "error": "Not a PDF (magic bytes mismatch)",
        }

    pdf_bytes = os.path.getsize(pdf_path)

    # Extract text
    text, text_method, text_error = _extract_text(pdf_path, bundle_path)

    # Title from URL filename
    import re
    url_match = re.search(r"/([^/]+\.pdf)$", url, re.IGNORECASE)
    if url_match:
        from urllib.parse import unquote
        title = unquote(url_match.group(1)).replace(".pdf", "").replace(".PDF", "")
    else:
        title = domain

    # Image extraction
    artifacts = {"source_pdf": True}
    pdf_images_meta = _extract_pdf_images(pdf_path, bundle_path, pdf_images, pdf_render_pages, pdf_render_dpi)
    if pdf_images_meta.get("embedded_found", 0) > 0:
        artifacts["pdf_images_saved"] = True
    if pdf_images_meta.get("render_saved", 0) > 0:
        artifacts["pdf_pages_saved"] = True

    type_specific = {
        "resolved_ip": validation.get("resolved_ip"),
        "pdf_bytes": pdf_bytes,
        "text_method": text_method,
        "text_error": text_error,
        "pdf_images": pdf_images_meta,
    }

    return {
        "success": True,
        "title": title,
        "content": text,
        "type": "pdf",
        "domain": domain,
        "artifacts": artifacts,
        "type_specific": type_specific,
        "error": None,
    }


def _extract_text(pdf_path, bundle_path):
    """Try pdftotext then pypdf. Returns (text, method, error)."""
    # Try pdftotext
    if check_tool("pdftotext"):
        try:
            content_path = os.path.join(bundle_path, "_pdf_text.tmp")
            subprocess.run(
                ["pdftotext", "-layout", pdf_path, content_path],
                capture_output=True, timeout=30, check=True,
            )
            if os.path.exists(content_path) and os.path.getsize(content_path) > 0:
                with open(content_path, "r", errors="replace") as f:
                    text = f.read()
                os.unlink(content_path)
                return text, "pdftotext", None
            if os.path.exists(content_path):
                os.unlink(content_path)
        except Exception as e:
            pass

    # Try pypdf
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        text = "\n\n".join(pages)
        if text.strip():
            return text, "pypdf", None
    except ImportError:
        pass
    except Exception as e:
        pass

    return "PDF saved locally; text extraction unavailable on this system.", "none", "No text extraction tool available"


def _extract_pdf_images(pdf_path, bundle_path, pdf_images, pdf_render_pages, pdf_render_dpi):
    """Extract embedded images and/or render pages. Returns metadata dict."""
    meta = {
        "embedded_found": 0,
        "embedded_bytes": 0,
        "render_requested": bool(pdf_render_pages),
        "render_saved": 0,
        "render_bytes": 0,
        "method": "none",
        "error": None,
    }

    if not pdf_images:
        return meta

    # A) pdfimages for embedded images
    if check_tool("pdfimages"):
        try:
            img_dir = os.path.join(bundle_path, "assets", "pdf_images")
            os.makedirs(img_dir, exist_ok=True)
            subprocess.run(
                ["pdfimages", "-all", pdf_path, os.path.join(img_dir, "img")],
                capture_output=True, timeout=60, check=True,
            )
            files = os.listdir(img_dir)
            meta["embedded_found"] = len(files)
            if files:
                meta["method"] = "pdfimages"
                total = sum(os.path.getsize(os.path.join(img_dir, f)) for f in files)
                meta["embedded_bytes"] = total
        except Exception as e:
            meta["error"] = f"pdfimages failed: {e}"

    # B) pdftoppm for page rendering
    if pdf_render_pages and check_tool("pdftoppm"):
        try:
            pages_dir = os.path.join(bundle_path, "assets", "pdf_pages")
            os.makedirs(pages_dir, exist_ok=True)

            page_list = _parse_page_spec(pdf_render_pages)
            rendered = 0
            total_bytes = 0

            for page_num in page_list[:10]:
                out_prefix = os.path.join(pages_dir, f"page_{page_num:03d}")
                try:
                    subprocess.run(
                        ["pdftoppm", "-jpeg", "-f", str(page_num), "-l", str(page_num),
                         "-r", str(pdf_render_dpi), pdf_path, out_prefix],
                        capture_output=True, timeout=30, check=True,
                    )
                    for f in os.listdir(pages_dir):
                        if f.startswith(f"page_{page_num:03d}"):
                            total_bytes += os.path.getsize(os.path.join(pages_dir, f))
                            rendered += 1
                except Exception:
                    pass

            meta["render_saved"] = rendered
            meta["render_bytes"] = total_bytes
            if meta["method"] == "pdfimages":
                meta["method"] = "pdfimages+pdftoppm"
            else:
                meta["method"] = "pdftoppm"
        except Exception as e:
            prev = meta.get("error")
            meta["error"] = f"{prev}; pdftoppm: {e}" if prev else f"pdftoppm: {e}"

    return meta


def _parse_page_spec(spec):
    """Parse page spec like '1-3' or '5,7' into list of ints."""
    pages = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            for p in range(int(start), int(end) + 1):
                pages.append(p)
        else:
            pages.append(int(part))
    return pages
