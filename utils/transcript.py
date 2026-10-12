# utils/transcript.py
"""
Transcript Utilities – using yt-dlp for reliable subtitle extraction.
Now includes video title fetching for the AI Tutor.
"""

import json
import os
import re
import subprocess
import tempfile
import logging
import streamlit as st

# Set up logger
logger = logging.getLogger(__name__)


def extract_video_id(url: str):
    """Extract YouTube video ID from URL."""
    if not url:
        return None
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:[?&]|$)",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
        r"(?:youtube\.com\/embed\/)([0-9A-Za-z_-]{11})",
        r"(?:youtube\.com\/shorts\/)([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def clean_transcript(text: str) -> str:
    """Clean transcript text."""
    if not text:
        return ""
    text = re.sub(r"WEBVTT", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Kind:.*", "", text)
    text = re.sub(r"Language:.*", "", text)
    text = re.sub(r"\d{2}:\d{2}:\d{2}\.\d+\s-->\s\d{2}:\d{2}:\d{2}\.\d+", "", text)
    text = re.sub(r"^\d+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def read_subtitle_file(filepath: str) -> str:
    """Read subtitle file (JSON, VTT, SRT)."""
    if filepath.endswith(".json"):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        text = []
        for event in data.get("events", []):
            for seg in event.get("segs", []):
                value = seg.get("utf8", "").strip()
                if value:
                    text.append(value)
        return " ".join(text)
    else:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()


def get_transcript_ytdlp(url: str, language: str = "en") -> str:
    """Download transcript using yt-dlp."""
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        raise RuntimeError("yt-dlp is not installed. Please run: pip install yt-dlp")

    with tempfile.TemporaryDirectory() as tmp:
        commands = [
            ["yt-dlp", "--skip-download", "--write-subs", "--sub-lang", language,
             "--sub-format", "json", "--no-warnings", "-o", os.path.join(tmp, "%(id)s.%(ext)s"), url],
            ["yt-dlp", "--skip-download", "--write-auto-subs", "--sub-lang", language,
             "--sub-format", "json", "--no-warnings", "-o", os.path.join(tmp, "%(id)s.%(ext)s"), url],
            ["yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs",
             "--sub-lang", language, "--sub-format", "best", "--no-warnings",
             "-o", os.path.join(tmp, "%(id)s.%(ext)s"), url],
        ]

        for command in commands:
            subprocess.run(command, capture_output=True, text=True)
            files = os.listdir(tmp)
            subtitle_files = [f for f in files if f.endswith((".json", ".vtt", ".srt"))]
            if subtitle_files:
                path = os.path.join(tmp, subtitle_files[0])
                transcript = read_subtitle_file(path)
                transcript = clean_transcript(transcript)
                if transcript.strip():
                    return transcript

        raise RuntimeError("No subtitles available for this video.")


def get_video_title(url: str) -> str:
    """Fetch the title of the YouTube video using yt-dlp."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--skip-download", "--print", "title", url],
            capture_output=True, text=True, check=False  # Don't raise on non-zero exit
        )
        title = result.stdout.strip()
        if title:
            return title
        else:
            # Log warning if title is empty
            logger.warning(f"No title found for URL: {url}")
            return "Untitled Lecture"
    except Exception as e:
        # Log the full error
        logger.error(f"Error fetching video title for {url}: {e}")
        return "Untitled Lecture"


def get_transcript(url: str) -> str | None:
    """
    Main entry point: extract transcript and return it.
    Side effects (session state updates) are separated for clarity.
    """
    try:
        video_id = extract_video_id(url)
        if not video_id:
            st.error("❌ Invalid YouTube URL.")
            return None

        transcript = get_transcript_ytdlp(url)
        if not transcript:
            st.error("❌ Transcript is empty.")
            return None

        # Store in session state
        st.session_state.video_title = get_video_title(url)
        st.session_state.video_url = url
        st.session_state.video_id = video_id
        st.session_state.transcript = transcript
        st.session_state.transcript_ready = True

        return transcript

    except Exception as e:
        # Log the error for debugging
        logger.error(f"Error in get_transcript for {url}: {e}")
        st.error(f"❌ {e}")
        return None