#!/usr/bin/env python3
"""Content-Extractor: Ingest content from URLs, text, or files into the library."""

import argparse
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cf_lib import LIMITS, now_iso
from lib.storage import create_bundle, write_meta, write_content
from lib.index import append_entry
from lib.util import extract_domain, check_tool


def _detect_type(url):
    """Detect content type from URL. Returns 'youtube', 'pdf', or 'article'."""
    if not url:
        return "article"

    url_lower = url.lower()

    # YouTube
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"

    # PDF by extension
    if re.search(r"\.pdf(\?|$)", url_lower):
        return "pdf"

    # PDF by HEAD Content-Type
    try:
        import requests
        resp = requests.head(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=LIMITS["BASE_TIMEOUT"],
            allow_redirects=True,
        )
        ct = resp.headers.get("Content-Type", "").lower()
        if "application/pdf" in ct:
            return "pdf"
    except Exception:
        pass

    return "article"


def _ingest_text(args):
    """Handle text ingestion modes."""
    from lib.extractors.text import extract_text

    if args.text:
        source, content = "arg", args.text
        original_path = None
    elif args.text_stdin:
        source, content = "stdin", sys.stdin.read()
        original_path = None
    elif args.text_file:
        if not os.path.exists(args.text_file):
            print(f"Error: File not found: {args.text_file}", file=sys.stderr)
            sys.exit(1)
        with open(args.text_file, "r") as f:
            content = f.read()
        source = "file"
        original_path = os.path.abspath(args.text_file)
    else:
        return None  # Not a text mode

    result = extract_text(content, source=source, title=args.title, original_path=original_path)
    return _finalize(result, url=None, args=args)


def _ingest_url(url, args):
    """Handle URL ingestion — route to appropriate extractor."""
    content_type = args.type or _detect_type(url)

    if content_type == "youtube":
        from lib.extractors.youtube import extract_youtube
        result = extract_youtube(
            url,
            bundle_path=None,  # Will be created by the extractor
            from_time=args.from_time,
            to_time=args.to_time,
            frames=args.frames,
            frame_mode=args.frame_mode,
            debug=args.debug,
        )
    elif content_type == "pdf":
        # Create bundle first since PDF extractor saves files into it
        bundle_id, bundle_path = create_bundle("pdf", extract_domain(url), url=url)
        from lib.extractors.pdf import extract_pdf
        result = extract_pdf(
            url, bundle_path,
            pdf_images=args.pdf_images,
            pdf_render_pages=args.pdf_render_pages,
            pdf_render_dpi=args.pdf_render_dpi,
            debug=args.debug,
        )
        return _finalize(result, url=url, args=args, bundle_id=bundle_id, bundle_path=bundle_path)
    else:
        # Article — create bundle first for image downloads
        bundle_id, bundle_path = create_bundle("article", extract_domain(url), url=url)
        from lib.extractors.article import extract_article
        result = extract_article(url, bundle_path, debug=args.debug)
        return _finalize(result, url=url, args=args, bundle_id=bundle_id, bundle_path=bundle_path)

    return _finalize(result, url=url, args=args)


def _ingest_ocr(args):
    """Handle OCR ingestion mode."""
    from lib.extractors.ocr import extract_ocr
    result = extract_ocr(
        args.telegram_images.split(","),
        title=args.title,
        message_text=args.message_text,
        ocr_lang=args.ocr_lang,
        debug=args.debug,
    )
    return _finalize(result, url=None, args=args)


def _finalize(result, url, args, bundle_id=None, bundle_path=None):
    """Create bundle, write files, update index. Returns bundle_id."""
    if not bundle_id:
        bundle_id, bundle_path = create_bundle(
            result["type"],
            result.get("title", "untitled"),
            url=url,
        )

    # For YouTube extractor, it creates its own bundle — relocate if needed
    if result.get("_bundle_path"):
        bundle_path = result.pop("_bundle_path")
        bundle_id = result.pop("_bundle_id")

    # Build meta
    meta = {
        "id": bundle_id,
        "url": url,
        "captured_at": now_iso(),
        "type": result["type"],
        "title": result["title"],
        "domain": result.get("domain", ""),
        "success": result["success"],
        "error": result.get("error"),
        "content_bytes": len(result.get("content", "").encode("utf-8")),
        "tags": [],
        "artifacts": result.get("artifacts", {}),
        "type_specific": result.get("type_specific", {}),
        "debug": args.debug if hasattr(args, "debug") else False,
    }

    write_meta(bundle_path, meta)
    write_content(bundle_path, result.get("content", ""))

    # Index entry
    index_entry = {
        "id": bundle_id,
        "title": result["title"],
        "type": result["type"],
        "domain": result.get("domain", ""),
        "url": url,
        "captured_at": meta["captured_at"],
        "success": result["success"],
        "tags": [],
        "bundle_dir": os.path.basename(bundle_path),
    }
    append_entry(index_entry)

    # Output
    status = "OK" if result["success"] else "FAILED"
    print(f"[{bundle_id}] {result['title']}")
    print(f"  Type: {result['type']} | Status: {status} | {meta['content_bytes']} bytes")
    if result.get("error"):
        print(f"  Error: {result['error']}")
    if result.get("artifacts"):
        parts = []
        for k, v in result["artifacts"].items():
            if v and v is not True:
                parts.append(f"{k}={v}")
            elif v:
                parts.append(k)
        if parts:
            print(f"  Artifacts: {', '.join(parts)}")

    return bundle_id


def main():
    parser = argparse.ArgumentParser(description="Content-Extractor: Ingest content")
    parser.add_argument("url", nargs="?", help="URL to ingest")

    # Text modes
    parser.add_argument("--text", help="Ingest raw text string")
    parser.add_argument("--text-stdin", action="store_true", help="Read text from stdin")
    parser.add_argument("--text-file", help="Read text from file path")
    parser.add_argument("--title", help="Override title")

    # Type override
    parser.add_argument("--type", choices=["article", "pdf", "youtube", "ocr", "text"],
                        help="Force content type")

    # PDF options
    parser.add_argument("--pdf-images", action="store_true", default=True,
                        help="Extract embedded PDF images (default: on)")
    parser.add_argument("--no-pdf-images", action="store_false", dest="pdf_images")
    parser.add_argument("--pdf-render-pages", help="Render pages as images (e.g. '1-3')")
    parser.add_argument("--pdf-render-dpi", type=int, default=150)

    # YouTube options
    parser.add_argument("--from", dest="from_time", help="Start time MM:SS or HH:MM:SS")
    parser.add_argument("--to", dest="to_time", help="End time MM:SS or HH:MM:SS")
    parser.add_argument("--frames", type=int, default=0, help="Number of frames to extract")
    parser.add_argument("--frame-mode", choices=["scene", "uniform"], default="scene")

    # OCR options
    parser.add_argument("--telegram-images", help="Comma-separated image paths for OCR")
    parser.add_argument("--message-text", help="Original message text (for OCR title/lang)")
    parser.add_argument("--ocr-lang", default="eng", help="OCR language (default: eng)")

    # General
    parser.add_argument("--debug", action="store_true", help="Keep extra artifacts")

    args = parser.parse_args()

    # Route to appropriate handler
    if args.telegram_images:
        _ingest_ocr(args)
    elif args.text or args.text_stdin or args.text_file:
        result = _ingest_text(args)
        if result is None:
            parser.print_help()
            sys.exit(1)
    elif args.url:
        _ingest_url(args.url, args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
