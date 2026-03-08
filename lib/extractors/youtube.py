"""YouTube extractor — transcript via yt-dlp, thumbnail, frame extraction."""

import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from cf_lib import LIMITS

from ..util import (
    check_tool, extract_domain, time_to_seconds, seconds_to_time,
    extract_html_title,
)
from ..storage import create_bundle


def _extract_video_id(url):
    """Extract YouTube video ID from URL."""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def _parse_vtt(vtt_content):
    """Parse VTT content into list of cues: [{startTime, endTime, text}]."""
    lines = vtt_content.split("\n")
    cues = []
    i = 0

    # Skip header
    while i < len(lines) and "-->" not in lines[i]:
        i += 1

    while i < len(lines):
        line = lines[i]
        if "-->" in line:
            m = re.match(
                r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})",
                line,
            )
            if m:
                start = _vtt_time_to_seconds(m.group(1))
                end = _vtt_time_to_seconds(m.group(2))
                text_parts = []
                i += 1
                while i < len(lines) and lines[i].strip() and "-->" not in lines[i]:
                    text_parts.append(lines[i].strip())
                    i += 1
                cues.append({"startTime": start, "endTime": end, "text": " ".join(text_parts)})
                continue
        i += 1

    return cues


def _vtt_time_to_seconds(vtt_time):
    """Convert VTT timestamp to seconds."""
    parts = vtt_time.split(":")
    h = int(parts[0])
    m = int(parts[1])
    s = float(parts[2])
    return h * 3600 + m * 60 + s


def _vtt_to_plain(vtt_content):
    """Convert VTT content to plain text."""
    # Strip VTT header, timestamps, cue numbers, and tags
    text = re.sub(r"^WEBVTT\s*\n", "", vtt_content, flags=re.IGNORECASE)
    text = re.sub(r"\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}.*\n", "", text)
    text = re.sub(r"^\d+\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"<[^>]+>", "", text)
    # Clean up
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)


def _slice_transcript(vtt_content, from_sec, to_sec):
    """Slice VTT transcript to a time range."""
    cues = _parse_vtt(vtt_content)
    filtered = [
        c for c in cues
        if (from_sec is None or c["endTime"] >= from_sec)
        and (to_sec is None or c["startTime"] <= to_sec)
    ]
    return "\n".join(c["text"] for c in filtered)


def extract_youtube(url, bundle_path=None, from_time=None, to_time=None,
                    frames=0, frame_mode="scene", debug=False):
    """Extract YouTube transcript, thumbnail, and optional frames.

    Returns extractor result dict. If bundle_path is None, creates one.
    """
    video_id = _extract_video_id(url)
    domain = extract_domain(url)

    # Create bundle
    hint = video_id or domain
    bundle_id, bundle_path = create_bundle("youtube", hint, url=url)

    if not check_tool("yt-dlp"):
        return {
            "success": False,
            "title": f"YouTube ({video_id or 'unknown'})",
            "content": "yt-dlp not available. Install with: brew install yt-dlp",
            "type": "youtube",
            "domain": domain,
            "artifacts": {},
            "type_specific": {"error": "yt-dlp not found"},
            "error": "yt-dlp not available",
            "_bundle_id": bundle_id,
            "_bundle_path": bundle_path,
        }

    # Download transcript
    transcript_text, vtt_files, yt_error = _download_transcript(url, bundle_path)

    # Get title from yt-dlp metadata
    title = _get_video_title(url) or f"YouTube ({video_id or 'unknown'})"

    # Apply time slicing
    clip_info = None
    if from_time or to_time:
        from_sec = time_to_seconds(from_time) if from_time else None
        to_sec = time_to_seconds(to_time) if to_time else None

        # Re-read the VTT for slicing
        if vtt_files:
            with open(vtt_files[0], "r") as f:
                vtt_content = f.read()
            transcript_text = _slice_transcript(vtt_content, from_sec, to_sec)

        clip_info = {
            "from": from_time or "0:00",
            "to": to_time or "end",
            "duration_seconds": (to_sec - (from_sec or 0)) if to_sec else None,
        }

    # Clean up VTT files unless debug
    if not debug and vtt_files:
        for f in vtt_files:
            if os.path.exists(f):
                os.unlink(f)

    artifacts = {}

    # Download thumbnail
    thumb_result = _download_thumbnail(video_id, bundle_path)
    if thumb_result.get("success"):
        artifacts["thumbnail_saved"] = True

    # Frame extraction
    frames_result = None
    if frames > 0:
        frames_result = _extract_frames(url, bundle_path, from_time, to_time, frames, frame_mode, debug)
        if frames_result.get("saved", 0) > 0:
            artifacts["frames_saved"] = True
            artifacts["frames_count"] = frames_result["saved"]

    type_specific = {
        "video_id": video_id,
        "transcript_success": bool(transcript_text and not yt_error),
        "transcript_bytes": len(transcript_text.encode("utf-8")) if transcript_text else 0,
    }
    if clip_info:
        type_specific["clip"] = clip_info
    if frames_result:
        type_specific["frames"] = frames_result
    if thumb_result:
        type_specific["thumbnail"] = thumb_result
    if yt_error:
        type_specific["transcript_error"] = yt_error

    return {
        "success": True,
        "title": title,
        "content": transcript_text or f"Transcript unavailable: {yt_error or 'unknown error'}",
        "type": "youtube",
        "domain": domain,
        "artifacts": artifacts,
        "type_specific": type_specific,
        "error": None,
        "_bundle_id": bundle_id,
        "_bundle_path": bundle_path,
    }


def _get_video_title(url):
    """Get video title via yt-dlp."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--get-title", "--no-download", url],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _download_transcript(url, bundle_path):
    """Download subtitles via yt-dlp. Returns (text, vtt_file_paths, error)."""
    try:
        subprocess.run(
            [
                "yt-dlp", "--skip-download",
                "--write-auto-subs", "--write-subs",
                "--sub-langs", "en", "--sub-format", "vtt",
                "-o", os.path.join(bundle_path, "%(id)s.%(ext)s"),
                url,
            ],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        return None, [], str(e)

    # Find VTT files
    vtt_files = [
        os.path.join(bundle_path, f) for f in os.listdir(bundle_path) if f.endswith(".vtt")
    ]

    if not vtt_files:
        return None, [], "No subtitle files generated"

    # Prefer .en.vtt
    selected = next((f for f in vtt_files if ".en." in f), vtt_files[0])
    with open(selected, "r") as f:
        vtt_content = f.read()

    plain_text = _vtt_to_plain(vtt_content)
    return plain_text, vtt_files, None


def _download_thumbnail(video_id, bundle_path):
    """Download YouTube thumbnail. Returns result dict."""
    if not video_id:
        return {"success": False, "error": "No video ID"}

    import requests

    assets_dir = os.path.join(bundle_path, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    thumb_path = os.path.join(assets_dir, "thumbnail.jpg")

    urls = [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/default.jpg",
    ]

    for thumb_url in urls:
        try:
            resp = requests.get(thumb_url, timeout=10)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(thumb_path, "wb") as f:
                    f.write(resp.content)
                return {"success": True, "error": None}
        except Exception:
            pass

    return {"success": False, "error": "Failed to download thumbnail"}


def _extract_frames(url, bundle_path, from_time, to_time, num_frames, frame_mode, debug):
    """Extract video frames from a time segment. Returns result dict."""
    if not from_time or not to_time:
        return {
            "requested": num_frames, "saved": 0, "mode": frame_mode,
            "success": False, "error": "Frame extraction requires --from and --to",
        }

    from_sec = time_to_seconds(from_time)
    to_sec = time_to_seconds(to_time)
    duration = to_sec - from_sec

    if duration > LIMITS["MAX_CLIP_SECONDS"]:
        return {
            "requested": num_frames, "saved": 0, "mode": frame_mode,
            "success": False, "error": f"Clip {duration}s exceeds max {LIMITS['MAX_CLIP_SECONDS']}s",
        }

    clamped = False
    if num_frames > LIMITS["MAX_FRAMES"]:
        num_frames = LIMITS["MAX_FRAMES"]
        clamped = True

    if not check_tool("yt-dlp") or not check_tool("ffmpeg"):
        missing = []
        if not check_tool("yt-dlp"):
            missing.append("yt-dlp")
        if not check_tool("ffmpeg"):
            missing.append("ffmpeg")
        return {
            "requested": num_frames, "saved": 0, "mode": frame_mode,
            "success": False, "error": f"Missing: {' '.join(missing)}",
        }

    tmp_dir = os.path.join(bundle_path, "tmp")
    frames_dir = os.path.join(bundle_path, "assets", "frames")
    os.makedirs(tmp_dir, exist_ok=True)
    os.makedirs(frames_dir, exist_ok=True)

    try:
        from_ts = seconds_to_time(from_sec)
        to_ts = seconds_to_time(to_sec)
        segment_path = os.path.join(tmp_dir, "segment")

        # Download segment (capped at 480p)
        fmt = "bv*[height<=480]/bestvideo[height<=480]/best[height<=480]"
        subprocess.run(
            [
                "yt-dlp",
                "--download-sections", f"*{from_ts}-{to_ts}",
                "-f", fmt,
                "-o", f"{segment_path}.%(ext)s",
                url,
            ],
            capture_output=True, text=True, timeout=60, check=True,
        )

        # Find downloaded segment
        seg_file = None
        for f in os.listdir(tmp_dir):
            if f.startswith("segment."):
                seg_file = os.path.join(tmp_dir, f)
                break

        if not seg_file:
            return {
                "requested": num_frames, "saved": 0, "mode": frame_mode,
                "success": False, "error": "Segment download failed",
            }

        # Extract frames
        if frame_mode == "uniform":
            interval = duration / num_frames
            cmd = [
                "ffmpeg", "-i", seg_file,
                "-vf", f"fps=1/{interval}",
                "-frames:v", str(num_frames),
                os.path.join(frames_dir, "frame_%03d.png"),
            ]
        else:
            cmd = [
                "ffmpeg", "-i", seg_file,
                "-vf", "select='gt(scene,0.3)',scale=640:-1",
                "-frames:v", str(num_frames),
                "-vsync", "vfr",
                os.path.join(frames_dir, "frame_%03d.png"),
            ]

        subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)

        frame_count = len([f for f in os.listdir(frames_dir) if f.startswith("frame_")])

        # Cleanup tmp
        if not debug:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return {
            "requested": num_frames, "saved": frame_count, "mode": frame_mode,
            "success": True, "error": None, "clamped": clamped,
        }

    except Exception as e:
        if not debug and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return {
            "requested": num_frames, "saved": 0, "mode": frame_mode,
            "success": False, "error": str(e), "clamped": clamped,
        }
