---
name: content-extractor
description: "Content ingestion skill for URLs, articles, PDFs, YouTube transcripts, OCR, and raw text. Activate when a user shares a URL and wants to save/extract its content, sends images for OCR, shares text to archive, or asks to search/browse their content library. NOT for: general web browsing, answering questions about URLs, or link previews."
---

# Content-Extractor

Ingest and archive content from URLs, text, images, and documents into a searchable library with full-text extraction, image mirroring, and metadata.

## Activation

Activate when the user:

- Shares a URL and wants to **save**, **extract**, or **archive** its content
- Sends images with "OCR" in the caption or asks for text extraction from images
- Wants to save raw text or a file to the library
- Asks to **search**, **list**, **browse**, or **get** items from their content library
- Asks to **tag**, **delete**, or manage library entries

Do NOT activate for:

- General web browsing or answering questions about a URL's content
- Link previews or summaries without archiving
- NoteFlow captures (those go to NoteFlow, not here)

## Guided Ingestion Flow

When a user shares a URL or content to ingest:

1. **Detect type** — the dispatcher auto-detects (article, PDF, YouTube, text, OCR)
2. **Run ingestion** — execute the appropriate `cf_ingest.py` command
3. **Report result** — show the confirmation with ID, title, type, and status
4. **Offer follow-up** — "Tagged? Want to add tags or notes?"

For YouTube URLs, ask if they want:
- Full transcript or a time clip (`--from`/`--to`)
- Frame extraction (`--frames N --frame-mode scene|uniform`)

## Scripts

Base path: `~/skill-backends/content-extractor`

### Ingest content

```bash
# Article/webpage
python3 ~/skill-backends/content-extractor/cf_ingest.py "<url>"

# PDF (auto-detected, or forced)
python3 ~/skill-backends/content-extractor/cf_ingest.py "<url>" --type pdf

# YouTube transcript
python3 ~/skill-backends/content-extractor/cf_ingest.py "<youtube-url>"

# YouTube with time clip + frames
python3 ~/skill-backends/content-extractor/cf_ingest.py "<youtube-url>" \
  --from "5:30" --to "10:00" --frames 6 --frame-mode scene

# Raw text
python3 ~/skill-backends/content-extractor/cf_ingest.py --text "<content>" --title "Title"

# Text from stdin
echo "content" | python3 ~/skill-backends/content-extractor/cf_ingest.py --text-stdin --title "Title"

# Text from file
python3 ~/skill-backends/content-extractor/cf_ingest.py --text-file /path/to/file.txt --title "Title"

# OCR from images (Telegram)
python3 ~/skill-backends/content-extractor/cf_ingest.py \
  --telegram-images "/path/img1.jpg,/path/img2.jpg" \
  --message-text "OCR: Document Title" --ocr-lang eng
```

### PDF options

| Flag | Default | Purpose |
|---|---|---|
| `--pdf-images` | on | Extract embedded images via pdfimages |
| `--no-pdf-images` | — | Disable image extraction |
| `--pdf-render-pages "1-3"` | off | Render specific pages as JPEG images |
| `--pdf-render-dpi 150` | 150 | DPI for page rendering |

### List entries

```bash
python3 ~/skill-backends/content-extractor/cf_list.py
python3 ~/skill-backends/content-extractor/cf_list.py --recent 20
python3 ~/skill-backends/content-extractor/cf_list.py --type article
python3 ~/skill-backends/content-extractor/cf_list.py --tag research --all
```

### Search entries

```bash
python3 ~/skill-backends/content-extractor/cf_search.py --query "machine learning"
python3 ~/skill-backends/content-extractor/cf_search.py --query "arxiv" --type pdf
```

### Get entry content

```bash
python3 ~/skill-backends/content-extractor/cf_get.py --id cf-0001               # summary (default)
python3 ~/skill-backends/content-extractor/cf_get.py --id cf-0001 --meta        # full metadata JSON
python3 ~/skill-backends/content-extractor/cf_get.py --id cf-0001 --content     # full content text
```

### Tag management

```bash
python3 ~/skill-backends/content-extractor/cf_tag.py --id cf-0001 --add "research,ml"
python3 ~/skill-backends/content-extractor/cf_tag.py --id cf-0001 --remove "ml"
python3 ~/skill-backends/content-extractor/cf_tag.py --id cf-0001 --list
```

### Delete entry

```bash
python3 ~/skill-backends/content-extractor/cf_delete.py --id cf-0001              # dry run
python3 ~/skill-backends/content-extractor/cf_delete.py --id cf-0001 --confirm     # actually delete
```

## Confirmation Format

After ingestion:

```
[cf-NNNN] Title
  Type: article | Status: OK | 12345 bytes
  Artifacts: images_saved, images_count=5
```

After list: table format with ID, date, type, status, title, tags.

## Content Types

| Type | Detected when | What it does |
|---|---|---|
| `article` | Any HTTP(S) URL | Fetch HTML, extract readable text, mirror images (up to 30) |
| `pdf` | URL ends in .pdf or Content-Type is application/pdf | Download, verify magic bytes, extract text (pdftotext/pypdf), optional image extraction |
| `youtube` | youtube.com or youtu.be URL | Download transcript via yt-dlp, thumbnail, optional frame extraction |
| `text` | `--text`, `--text-stdin`, or `--text-file` flag | Direct text ingestion with 2MB cap |
| `ocr` | `--telegram-images` flag | Tesseract OCR on image files, multi-page with separators |

## Security

All URLs pass through a security gate before any fetch:

- Only `http`/`https` schemes allowed
- Blocks `localhost`, `127.0.0.1`, `::1`, `0.0.0.0`
- Blocks `.local` domains
- DNS resolution + private IP range blocking (10.x, 172.16-31.x, 192.168.x, link-local)
- Blocked URLs produce a bundle with the block reason recorded

**Never bypass the security gate.** Do not manually fetch URLs that were blocked.

## Data Location

**Canonical data path:** `~/.openclaw/workspace/data/content-extractor/`

- Library bundles: `library/{date}__{type}__{slug}__{cf-NNNN}/`
- Index: `index.ndjson` (append-only, one JSON object per line)
- State: `state.json` (ID counter)

Each bundle contains:
- `meta.json` — full metadata (ID, URL, type, title, tags, artifacts, type-specific data)
- `content.md` — extracted text content
- `assets/` — images, thumbnails, frames, PDF pages (optional)
- `source/` — original files (PDF, OCR source images) (optional)

**Always use the scripts** to read and modify the library. Never write to data files directly via file tools.

## Limits

| Limit | Value |
|---|---|
| General download | 15 MB |
| PDF download | 60 MB |
| Image download | 15 MB per image |
| Images per item | 30 |
| Text ingestion | 2 MB |
| OCR images per request | 10 |
| Frame extraction | 24 frames max |
| Clip duration | 30 minutes max |

## Graceful Degradation

Missing optional tools produce clear errors, not crashes:

- **yt-dlp missing:** YouTube ingestion reports "yt-dlp not available"
- **ffmpeg missing:** Frame extraction reports "ffmpeg not available"
- **tesseract missing:** OCR reports "tesseract not available"
- **pdftotext missing:** Falls back to pypdf; if both missing, reports "text extraction unavailable"
- **pdfimages/pdftoppm missing:** Skips PDF image/page extraction silently
