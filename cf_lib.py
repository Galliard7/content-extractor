"""Content-Extractor shared library — path constants, state management, utilities."""

import json
import os
from datetime import datetime

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
DATA_DIR = os.path.join(WORKSPACE, "data", "content-extractor")
LIBRARY_DIR = os.path.join(DATA_DIR, "library")
INDEX_PATH = os.path.join(DATA_DIR, "index.ndjson")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

LIMITS = {
    "MAX_BYTES": 15 * 1024 * 1024,           # 15MB general download
    "MAX_PDF_BYTES": 60 * 1024 * 1024,        # 60MB PDF
    "MAX_IMAGE_BYTES": 15 * 1024 * 1024,      # 15MB per image
    "MAX_IMAGES_PER_ITEM": 30,                # Max images per content item
    "MAX_TEXT_BYTES": 2 * 1024 * 1024,         # 2MB text ingestion
    "MAX_OCR_IMAGES": 10,                     # Max images per OCR request
    "MAX_OCR_IMAGE_BYTES": 25 * 1024 * 1024,  # 25MB per OCR image
    "BASE_TIMEOUT": 20,                       # Seconds
    "YOUTUBE_TIMEOUT": 60,                    # Seconds
    "YOUTUBE_FRAMES_TIMEOUT": 300,            # 5 minutes
    "MAX_FRAMES": 24,
    "MAX_CLIP_SECONDS": 30 * 60,             # 30 minutes
}


def load_state():
    """Load persistent state (next_id counter). Creates default if missing."""
    if not os.path.exists(STATE_PATH):
        return {"next_id": 1}
    with open(STATE_PATH, "r") as f:
        return json.load(f)


def save_state(state):
    """Write state to disk atomically."""
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    os.replace(tmp, STATE_PATH)


def next_id():
    """Allocate and return the next cf-NNNN ID string."""
    state = load_state()
    num = state["next_id"]
    state["next_id"] = num + 1
    save_state(state)
    return f"cf-{num:04d}"


def now_iso():
    """Current local time in ISO 8601 with timezone offset."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def today_stamp():
    """Today's date as YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")
