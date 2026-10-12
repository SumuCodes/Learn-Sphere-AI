
"""
Content layer — owns lecture content:
transcript, compressed_transcript, notes, summary, sections (topics).

Uses SQLite at data/performance.db.
The data directory and database table are created automatically.
"""

import json
import sqlite3
import streamlit as st
from pathlib import Path
from typing import List, Dict, Any, Optional


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "performance.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)

_CONTENT_COLUMNS = {
    "transcript",
    "compressed_transcript",
    "notes",
    "summary",
    "sections",
}

_READABLE_COLUMNS = {
    "title",
    "transcript",
    "compressed_transcript",
    "notes",
    "summary",
    "sections",
}


def _get_connection():
    """Open a SQLite connection and ensure the database directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _get_user_id(user_id: Optional[str] = None) -> Optional[str]:
    """Return the supplied user ID or the logged-in session user ID."""
    if user_id is not None:
        return str(user_id) if str(user_id).strip() else None

    value = st.session_state.get("user_id")
    return str(value) if value is not None and str(value).strip() else None


def _ensure_lectures_table():
    """Create the lecture content table if it does not exist."""
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
                sections TEXT,
                chat_history TEXT,
                quiz_history TEXT,
                performance TEXT,
                PRIMARY KEY (user_id, video_id)
            )
        """)
        conn.commit()
    finally:
        conn.close()


# Initialize the database on module import.
_ensure_lectures_table()


# ============================================================
# CORE SAVE / LOAD FUNCTIONS
# ============================================================

def save_lecture_content(
    video_id: str,
    content_type: str,
    content: Optional[str],
    user_id: Optional[str] = None,
) -> bool:
    """Save or update one lecture content field."""

    if content_type not in _CONTENT_COLUMNS:
        raise ValueError(f"Invalid content type: {content_type}")

    user_id = _get_user_id(user_id)

    if not video_id or user_id is None:
        return False

    conn = _get_connection()

    try:
        cursor = conn.execute(
            f"""
            UPDATE lectures
            SET {content_type} = ?
            WHERE user_id = ? AND video_id = ?
            """,
            (content, user_id, video_id),
        )

        # rowcount refers to this UPDATE, not earlier SQL operations.
        if cursor.rowcount == 0:
            conn.execute(
                f"""
                INSERT INTO lectures
                    (user_id, video_id, {content_type})
                VALUES (?, ?, ?)
                """,
                (user_id, video_id, content),
            )

        conn.commit()
        return True

    except sqlite3.Error as exc:
        conn.rollback()
        st.error(f"Could not save {content_type}: {exc}")
        return False

    finally:
        conn.close()


def get_lecture_content(
    video_id: str,
    user_id: Optional[str] = None,
) -> dict:
    """Fetch all lecture content fields."""
    user_id = _get_user_id(user_id)

    if not video_id or user_id is None:
        return {}

    conn = _get_connection()

    try:
        row = conn.execute(
            """
            SELECT title, transcript, compressed_transcript,
                   notes, summary, sections
            FROM lectures
            WHERE user_id = ? AND video_id = ?
            """,
            (user_id, video_id),
        ).fetchone()

        return dict(row) if row else {}

    finally:
        conn.close()


def _get_single_column(
    video_id: str,
    column: str,
    user_id: Optional[str] = None,
) -> Optional[str]:
    """Load one approved content column."""
    if column not in _READABLE_COLUMNS:
        raise ValueError(f"Invalid content column: {column}")

    user_id = _get_user_id(user_id)

    if not video_id or user_id is None:
        return None

    conn = _get_connection()

    try:
        row = conn.execute(
            f"""
            SELECT {column}
            FROM lectures
            WHERE user_id = ? AND video_id = ?
            """,
            (user_id, video_id),
        ).fetchone()

        return row[column] if row else None

    finally:
        conn.close()


def _column_exists(
    video_id: str,
    column: str,
    user_id: Optional[str] = None,
) -> bool:
    """Check whether a lecture content column is not NULL."""
    if column not in _READABLE_COLUMNS:
        raise ValueError(f"Invalid content column: {column}")

    user_id = _get_user_id(user_id)

    if not video_id or user_id is None:
        return False

    conn = _get_connection()

    try:
        row = conn.execute(
            f"""
            SELECT 1
            FROM lectures
            WHERE user_id = ? AND video_id = ?
              AND {column} IS NOT NULL
            LIMIT 1
            """,
            (user_id, video_id),
        ).fetchone()

        return row is not None

    finally:
        conn.close()


# ============================================================
# TRANSCRIPT
# ============================================================

def save_transcript(
    video_id: str,
    transcript: str,
    user_id: Optional[str] = None,
) -> bool:
    return save_lecture_content(
        video_id, "transcript", transcript, user_id
    )


def load_transcript(
    video_id: str,
    user_id: Optional[str] = None,
) -> Optional[str]:
    return _get_single_column(video_id, "transcript", user_id)


def save_compressed_transcript(
    video_id: str,
    compressed: str,
    user_id: Optional[str] = None,
) -> bool:
    return save_lecture_content(
        video_id, "compressed_transcript", compressed, user_id
    )


def load_compressed_transcript(
    video_id: str,
    user_id: Optional[str] = None,
) -> Optional[str]:
    return _get_single_column(
        video_id, "compressed_transcript", user_id
    )


# ============================================================
# NOTES AND SUMMARY
# ============================================================

def save_notes(
    video_id: str,
    notes: str,
    user_id: Optional[str] = None,
) -> bool:
    return save_lecture_content(video_id, "notes", notes, user_id)


def load_notes(
    video_id: str,
    user_id: Optional[str] = None,
) -> Optional[str]:
    return _get_single_column(video_id, "notes", user_id)


def save_summary(
    video_id: str,
    summary: str,
    user_id: Optional[str] = None,
) -> bool:
    return save_lecture_content(video_id, "summary", summary, user_id)


def load_summary(
    video_id: str,
    user_id: Optional[str] = None,
) -> Optional[str]:
    return _get_single_column(video_id, "summary", user_id)


# ============================================================
# TOPICS / SECTIONS
# ============================================================

def save_topics(
    video_id: str,
    topics: List[Dict[str, Any]],
    user_id: Optional[str] = None,
) -> bool:
    """Save generated topics as JSON in the sections column."""
    if not video_id or not isinstance(topics, list):
        return False

    try:
        topics_json = json.dumps(
            topics,
            ensure_ascii=False,
        )
    except (TypeError, ValueError) as exc:
        st.error(f"Could not serialize generated topics: {exc}")
        return False

    return save_lecture_content(
        video_id,
        "sections",
        topics_json,
        user_id,
    )


def load_topics(
    video_id: str,
    user_id: Optional[str] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Load saved topics from SQLite."""
    if not video_id:
        return None

    try:
        raw = _get_single_column(
            video_id, "sections", user_id
        )

        if not raw:
            return None

        topics = json.loads(raw)

        if isinstance(topics, list):
            return topics

        st.warning("Saved topics have an unexpected format.")
        return None

    except json.JSONDecodeError:
        st.warning("Saved topics are not valid JSON.")
        return None

    except (sqlite3.Error, OSError) as exc:
        st.warning(f"Could not load topics: {exc}")
        return None


def topics_exist(
    video_id: str,
    user_id: Optional[str] = None,
) -> bool:
    """Return True when the sections field is not NULL."""
    if not video_id:
        return False

    return _column_exists(video_id, "sections", user_id)


def clear_lecture_content(
    video_id: str,
    user_id: Optional[str] = None,
) -> bool:
    """Clear generated topics, notes and summary for one lecture."""
    user_id = _get_user_id(user_id)

    if not video_id or user_id is None:
        return False

    conn = _get_connection()

    try:
        conn.execute(
            """
            UPDATE lectures
            SET sections = NULL, notes = NULL, summary = NULL
            WHERE user_id = ? AND video_id = ?
            """,
            (user_id, video_id),
        )

        conn.commit()
        return True

    except sqlite3.Error as exc:
        conn.rollback()
        st.error(f"Could not clear lecture content: {exc}")
        return False

    finally:
        conn.close()


# ============================================================
# REPROCESS LECTURE
# ============================================================

def reprocess_video(
    video_id: str,
    topics: List[Dict[str, Any]],
    notes: str,
    summary: str,
    user_id: Optional[str] = None,
) -> bool:
    """Replace a lecture's generated topics, notes and summary."""
    user_id = _get_user_id(user_id)

    if not video_id or user_id is None:
        return False

    conn = _get_connection()

    try:
        # Use one transaction so existing content is not partially cleared.
        conn.execute(
            """
            INSERT OR IGNORE INTO lectures (user_id, video_id)
            VALUES (?, ?)
            """,
            (user_id, video_id),
        )

        conn.execute(
            """
            UPDATE lectures
            SET sections = ?, notes = ?, summary = ?
            WHERE user_id = ? AND video_id = ?
            """,
            (
                json.dumps(topics, ensure_ascii=False),
                notes,
                summary,
                user_id,
                video_id,
            ),
        )

        conn.commit()
        return True

    except (sqlite3.Error, TypeError, ValueError) as exc:
        conn.rollback()
        st.error(f"Could not reprocess lecture: {exc}")
        return False

    finally:
        conn.close()


# ============================================================
# TOPIC SEARCH FOR AI CHAT
# ============================================================

def search_topics(
    query: str,
    video_id: str,
    top_k: int = 4,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Find relevant saved topics using simple word matching."""
    all_topics = load_topics(video_id, user_id)

    if not all_topics:
        return []

    query_words = _tokenize(query)

    if not query_words:
        return all_topics[:top_k]

    scored = [
        (_score_topic(query_words, topic), topic)
        for topic in all_topics
        if isinstance(topic, dict)
    ]

    scored.sort(key=lambda item: item[0], reverse=True)

    relevant = [
        topic for score, topic in scored if score > 0
    ][:top_k]

    return relevant if relevant else all_topics[:top_k]


# ============================================================
# TOPIC EXCERPTS
# ============================================================

def get_topic_excerpts(
    video_id: str,
    user_id: Optional[str] = None,
) -> List[str]:
    """Return available excerpts or notes from saved topics."""
    topics = load_topics(video_id, user_id)

    if not topics:
        return []

    excerpts = []

    for topic in topics:
        if not isinstance(topic, dict):
            continue

        excerpt = topic.get("excerpt") or topic.get("notes")

        if isinstance(excerpt, str) and excerpt.strip():
            excerpts.append(excerpt)

    return excerpts


# ============================================================
# PRIVATE TOKENIZATION AND SCORING
# ============================================================

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


def _score_topic(
    query_words: set,
    topic: dict,
) -> float:
    """Score title (5x), key (3x), excerpt (2x), notes (1x)."""
    title = str(topic.get("topic_title") or "").lower()
    key = str(topic.get("topic_key") or "").lower()
    notes = str(topic.get("notes") or "").lower()
    excerpt = str(topic.get("excerpt") or "").lower()

    title_words = set(title.split())
    key_words = set(key.replace("_", " ").split())
    notes_words = set(notes.split())
    excerpt_words = set(excerpt.split())

    score = 0.0

    for word in query_words:
        if word in title_words:
            score += 5.0
        if word in key_words:
            score += 3.0
        if word in notes_words:
            score += 1.0
        if word in excerpt_words:
            score += 2.0

    return score
