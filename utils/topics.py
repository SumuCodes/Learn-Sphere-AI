# utils/topics.py
"""
Content layer — owns ALL lecture content:
transcript, compressed_transcript, notes, summary, sections (topics).

Does NOT import from performance.py.
Both access performance.db independently.
"""

import json
import sqlite3
import streamlit as st
from pathlib import Path
from typing import List, Dict, Any, Optional

# ── Database ──
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "performance.db"

_CONTENT_COLUMNS = {
    "transcript",
    "compressed_transcript",
    "notes",
    "summary",
    "sections",
}


def _get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _get_user_id(user_id: Optional[str] = None) -> Optional[str]:
    """Return provided user_id or fallback to session_state."""
    if user_id is not None:
        return user_id
    return st.session_state.get("user_id", None)


def _ensure_lectures_table():
    """Create the lectures table with all content columns if it doesn't exist."""
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lectures (
                user_id TEXT NOT NULL,
                video_id TEXT NOT NULL,
                title TEXT,
                transcript TEXT,
                compressed_transcript TEXT,
                notes TEXT,
                summary TEXT,
                sections TEXT,          -- JSON array of topics
                chat_history TEXT,      -- DEPRECATED: kept for backward compat, use chat_messages table
                quiz_history TEXT,      -- DEPRECATED: kept for backward compat, use quiz_attempts table
                performance TEXT,       -- JSON for streaks, last_study_date, etc.
                PRIMARY KEY (user_id, video_id)
            )
        """)
        conn.commit()
    finally:
        conn.close()


# Run migration on import
_ensure_lectures_table()


# ═══════════════════════════════════════════════════════════════
# CORE CONTENT — save / load (with explicit user_id)
# ═══════════════════════════════════════════════════════════════

def save_lecture_content(
    video_id: str,
    content_type: str,
    content: Optional[str],
    user_id: Optional[str] = None,
) -> bool:
    """Save/overwrite a content field for a video."""
    if content_type not in _CONTENT_COLUMNS:
        raise ValueError(
            f"Invalid content_type: {content_type}. "
            f"Must be one of {_CONTENT_COLUMNS}"
        )
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return False

    conn = _get_connection()
    try:
        conn.execute(
            f"UPDATE lectures SET {content_type} = ? "
            f"WHERE video_id = ? AND user_id = ?",
            (content, video_id, user_id),
        )
        # If no row was updated, insert a new one
        if conn.total_changes == 0:
            conn.execute(
                f"INSERT INTO lectures (user_id, video_id, {content_type}) "
                f"VALUES (?, ?, ?)",
                (user_id, video_id, content),
            )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Could not save {content_type}: {e}")
        return False
    finally:
        conn.close()


def get_lecture_content(video_id: str, user_id: Optional[str] = None) -> dict:
    """Fetch all content fields for a video."""
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return {}

    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT title, transcript, compressed_transcript, "
            "notes, summary, sections "
            "FROM lectures WHERE video_id = ? AND user_id = ?",
            (video_id, user_id),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def _get_single_column(
    video_id: str,
    column: str,
    user_id: Optional[str] = None,
) -> Optional[str]:
    """Generic single-column loader."""
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return None

    conn = _get_connection()
    try:
        row = conn.execute(
            f"SELECT {column} FROM lectures "
            f"WHERE video_id = ? AND user_id = ?",
            (video_id, user_id),
        ).fetchone()
        return row[column] if row else None
    finally:
        conn.close()


def _column_exists(
    video_id: str,
    column: str,
    user_id: Optional[str] = None,
) -> bool:
    """Check if a column has data without loading it."""
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return False

    conn = _get_connection()
    try:
        row = conn.execute(
            f"SELECT 1 FROM lectures "
            f"WHERE video_id = ? AND user_id = ? AND {column} IS NOT NULL",
            (video_id, user_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# TRANSCRIPT
# ═══════════════════════════════════════════════════════════════

def save_transcript(video_id: str, transcript: str, user_id: Optional[str] = None) -> bool:
    return save_lecture_content(video_id, "transcript", transcript, user_id)


def load_transcript(video_id: str, user_id: Optional[str] = None) -> Optional[str]:
    return _get_single_column(video_id, "transcript", user_id)


def save_compressed_transcript(
    video_id: str,
    compressed: str,
    user_id: Optional[str] = None,
) -> bool:
    return save_lecture_content(video_id, "compressed_transcript", compressed, user_id)


def load_compressed_transcript(video_id: str, user_id: Optional[str] = None) -> Optional[str]:
    return _get_single_column(video_id, "compressed_transcript", user_id)


# ═══════════════════════════════════════════════════════════════
# NOTES & SUMMARY
# ═══════════════════════════════════════════════════════════════

def save_notes(video_id: str, notes: str, user_id: Optional[str] = None) -> bool:
    return save_lecture_content(video_id, "notes", notes, user_id)


def load_notes(video_id: str, user_id: Optional[str] = None) -> Optional[str]:
    return _get_single_column(video_id, "notes", user_id)


def save_summary(video_id: str, summary: str, user_id: Optional[str] = None) -> bool:
    return save_lecture_content(video_id, "summary", summary, user_id)


def load_summary(video_id: str, user_id: Optional[str] = None) -> Optional[str]:
    return _get_single_column(video_id, "summary", user_id)


# ═══════════════════════════════════════════════════════════════
# TOPICS / SECTIONS
# ═══════════════════════════════════════════════════════════════

def save_topics(
    video_id: str,
    topics: List[Dict[str, Any]],
    user_id: Optional[str] = None,
) -> bool:
    """Save structured topics to the database."""
    if not video_id:
        return False
    return save_lecture_content(video_id, "sections", json.dumps(topics), user_id)


def load_topics(video_id: str, user_id: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
    """Load structured topics from the database."""
    if not video_id:
        return None
    try:
        raw = _get_single_column(video_id, "sections", user_id)
        if raw:
            return json.loads(raw)
        return None
    except json.JSONDecodeError:
        return None
    except Exception as e:
        st.warning(f"Could not load topics: {e}")
        return None


def topics_exist(video_id: str, user_id: Optional[str] = None) -> bool:
    """Check if topics exist efficiently (no heavy JSON load)."""
    if not video_id:
        return False
    return _column_exists(video_id, "sections", user_id)


def clear_lecture_content(video_id: str, user_id: Optional[str] = None) -> bool:
    """
    SAFELY clear ALL generated content (topics, notes, summary).
    Call this before reprocessing to avoid inconsistent states.
    """
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return False

    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE lectures SET sections = NULL, notes = NULL, summary = NULL "
            "WHERE video_id = ? AND user_id = ?",
            (video_id, user_id),
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Could not clear lecture content: {e}")
        return False
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# RE-PROCESS — rewrite knowledge, keep analytics untouched
# ═══════════════════════════════════════════════════════════════

def reprocess_video(
    video_id: str,
    topics: List[Dict[str, Any]],
    notes: str,
    summary: str,
    user_id: Optional[str] = None,
) -> bool:
    """
    User processed the same video again.

    REWRITE:  topics, notes, summary        (content — owned here)
    KEEP:     quiz_history, chat, etc.      (analytics — owned by performance.py)
    """
    # First clear old content to avoid orphans
    if not clear_lecture_content(video_id, user_id):
        return False

    ok = True
    if not save_topics(video_id, topics, user_id):
        ok = False
    if not save_notes(video_id, notes, user_id):
        ok = False
    if not save_summary(video_id, summary, user_id):
        ok = False
    return ok


# ═══════════════════════════════════════════════════════════════
# SEARCH TOPICS — for AI Chat (RAG without embeddings)
# ═══════════════════════════════════════════════════════════════

def search_topics(
    query: str,
    video_id: str,
    top_k: int = 4,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Find the most relevant topics for a user's question.
    Used by AI Chat to pull the right knowledge from Topic DB.
    """
    all_topics = load_topics(video_id, user_id)
    if not all_topics:
        return []

    query_words = _tokenize(query)
    if not query_words:
        return all_topics[:top_k]

    scored = [(_score_topic(query_words, t), t) for t in all_topics]
    scored.sort(key=lambda x: x[0], reverse=True)

    relevant = [t for score, t in scored if score > 0][:top_k]
    return relevant if relevant else all_topics[:top_k]


# ═══════════════════════════════════════════════════════════════
# PRIVATE — tokenization & scoring
# ═══════════════════════════════════════════════════════════════

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be",
    "do", "does", "did", "will", "would", "could", "should",
    "can", "may", "might", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through",
    "about", "it", "its", "this", "that", "these", "those",
    "i", "me", "my", "you", "your", "we", "our", "and",
    "or", "not", "but", "if", "then", "so", "no", "yes",
    "just", "also", "very", "really", "how", "what", "why",
    "when", "where", "who", "which", "tell", "explain",
    "describe", "give", "show", "know", "mean", "please",
})


def _tokenize(text: str) -> set:
    return set(text.lower().split()) - _STOP_WORDS


# New helper
def get_topic_excerpts(video_id: str, user_id: Optional[str] = None) -> List[str]:
    """
    Return a list of excerpts from all topics for this video.
    If a topic lacks an 'excerpt' field, fall back to its 'notes'.
    """
    topics = load_topics(video_id, user_id)
    if not topics:
        return []
    return [t.get("excerpt", t.get("notes", "")) for t in topics if t.get("excerpt") or t.get("notes")]

# Updated scoring to include excerpt weight (2x)
def _score_topic(query_words: set, topic: dict) -> float:
    """Title = 5x, key = 3x, notes = 1x, excerpt = 2x."""
    title = topic.get("topic_title", "").lower()
    key = topic.get("topic_key", "").lower()
    notes = topic.get("notes", "").lower()
    excerpt = topic.get("excerpt", "").lower()

    title_words = set(title.split())
    key_words = set(key.replace("_", " ").split())
    notes_words = set(notes.split())
    excerpt_words = set(excerpt.split())

    score = 0.0
    for qw in query_words:
        if qw in title_words:
            score += 5.0
        if qw in key_words:
            score += 3.0
        if qw in notes_words:
            score += 1.0
        if qw in excerpt_words:
            score += 2.0   # excerpt is more informative than notes
    return score