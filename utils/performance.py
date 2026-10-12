# utils/performance.py
"""
Analytics layer — owns quiz attempts, chat history, performance scores,
streaks, lecture logs, and aggregated analytics.

Does NOT import from topics.py.
Both access performance.db independently.
"""

import json
import sqlite3
import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd

# ── Database ──
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "performance.db"


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


def _get_session_id(session_id: Optional[str] = None) -> str:
    """Return provided session_id or generate one from current time."""
    if session_id is not None:
        return session_id
    ui_session = st.session_state.get("current_session_id")
    if ui_session:
        return ui_session
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_tables():
    """
    Create normalized tables for chat and quiz history.
    Also adds word_count and last_updated to lectures.
    """
    conn = _get_connection()
    try:
        # 1. Lectures table
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

        # Helper: add column only if it doesn't exist
        def add_column_if_not_exists(table, column, col_type):
            # Get existing columns
            existing = conn.execute(f"PRAGMA table_info({table})").fetchall()
            col_names = [row[1] for row in existing]
            if column not in col_names:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                except sqlite3.OperationalError as e:
                    # If it's a duplicate column error, ignore; else re-raise
                    if "duplicate column" not in str(e).lower():
                        raise

        # Add missing columns to lectures
        add_column_if_not_exists("lectures", "word_count", "INTEGER DEFAULT 0")
        add_column_if_not_exists("lectures", "last_updated", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        # 2. Chat Messages table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                video_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Add missing columns
        add_column_if_not_exists("chat_messages", "video_id", "TEXT NOT NULL DEFAULT ''")
        add_column_if_not_exists("chat_messages", "session_id", "TEXT NOT NULL DEFAULT ''")
        add_column_if_not_exists("chat_messages", "role", "TEXT NOT NULL DEFAULT ''")
        add_column_if_not_exists("chat_messages", "content", "TEXT NOT NULL DEFAULT ''")

        # 3. Quiz Attempts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                video_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                percentage REAL NOT NULL,
                answers_json TEXT,
                topics_quizzed_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Add missing columns
        add_column_if_not_exists("quiz_attempts", "video_id", "TEXT NOT NULL DEFAULT ''")
        add_column_if_not_exists("quiz_attempts", "session_id", "TEXT NOT NULL DEFAULT ''")
        add_column_if_not_exists("quiz_attempts", "score", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_not_exists("quiz_attempts", "total", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_not_exists("quiz_attempts", "percentage", "REAL NOT NULL DEFAULT 0")

        # Now create indexes (columns are guaranteed to exist)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_lookup ON chat_messages(user_id, video_id, session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_quiz_lookup ON quiz_attempts(user_id, video_id, session_id)")

        conn.commit()
    finally:
        conn.close()

# Run migration on import
_ensure_tables()


# ═══════════════════════════════════════════════════════════════
# CHAT HISTORY — Normalized Table (Append Only)
# ═══════════════════════════════════════════════════════════════

def save_chat_message(
    video_id: str,
    role: str,
    content: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> bool:
    """
    Append a chat message to this video's session history.
    Each message gets a session_id so we can restore conversations by date.
    """
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return False

    session_id = _get_session_id(session_id)

    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO chat_messages (user_id, video_id, session_id, role, content) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, video_id, session_id, role, content),
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Could not save chat message: {e}")
        return False
    finally:
        conn.close()


def load_chat_history(
    video_id: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Load chat history.
    - If session_id is provided, loads ONLY that session's chats (for restoration).
    - If session_id is None, loads ALL chats for this video (for current view).
    """
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return []

    conn = _get_connection()
    try:
        if session_id:
            rows = conn.execute(
                "SELECT role, content, created_at FROM chat_messages "
                "WHERE user_id = ? AND video_id = ? AND session_id = ? "
                "ORDER BY created_at ASC",
                (user_id, video_id, session_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT role, content, created_at FROM chat_messages "
                "WHERE user_id = ? AND video_id = ? "
                "ORDER BY created_at ASC",
                (user_id, video_id),
            ).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_all_sessions(video_id: str, user_id: Optional[str] = None) -> List[str]:
    """Return all distinct session_ids for a video (for the History page dropdown)."""
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return []

    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT session_id, MIN(created_at) as first_msg "
            "FROM chat_messages "
            "WHERE user_id = ? AND video_id = ? "
            "GROUP BY session_id "
            "ORDER BY first_msg DESC",
            (user_id, video_id),
        ).fetchall()
        return [row["session_id"] for row in rows]
    finally:
        conn.close()


def clear_chat_history(video_id: str, user_id: Optional[str] = None) -> bool:
    """DELETE all chat history for a video (use sparingly)."""
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return False

    conn = _get_connection()
    try:
        conn.execute(
            "DELETE FROM chat_messages WHERE user_id = ? AND video_id = ?",
            (user_id, video_id),
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Could not clear chat history: {e}")
        return False
    finally:
        conn.close()


def delete_chat_session(video_id: str, session_id: str, user_id: Optional[str] = None) -> bool:
    """Delete a specific chat session (all messages with that session_id)."""
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id or not session_id:
        return False

    conn = _get_connection()
    try:
        conn.execute(
            "DELETE FROM chat_messages WHERE user_id = ? AND video_id = ? AND session_id = ?",
            (user_id, video_id, session_id),
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Could not delete chat session: {e}")
        return False
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# QUIZ HISTORY — Normalized Table (APPEND ONLY, never erase)
# ═══════════════════════════════════════════════════════════════

def append_quiz_result(
    video_id: str,
    quiz_result: Dict[str, Any],
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> bool:
    """
    Add a new quiz result WITHOUT erasing previous ones.

    quiz_result = {
        "score": 6,
        "total": 10,
        "percentage": 60.0,
        "answers": [{"question": "...", "user_answer": "...", "correct": True}],
        "topics_quizzed": ["gradient descent", "backpropagation"],
    }
    """
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return False

    session_id = _get_session_id(session_id)

    score = quiz_result.get("score", 0)
    total = quiz_result.get("total", 1)
    percentage = quiz_result.get("percentage", (score / total * 100) if total > 0 else 0)
    answers_json = json.dumps(quiz_result.get("answers", []))
    topics_json = json.dumps(quiz_result.get("topics_quizzed", []))

    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO quiz_attempts
            (user_id, video_id, session_id, score, total, percentage, answers_json, topics_quizzed_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, video_id, session_id, score, total, percentage, answers_json, topics_json),
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Could not save quiz result: {e}")
        return False
    finally:
        conn.close()


def load_quiz_history(
    video_id: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Load ALL quiz results for a video (chronological).
    If session_id is provided, loads only that specific session's quiz.
    """
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return []

    conn = _get_connection()
    try:
        if session_id:
            rows = conn.execute(
                """
                SELECT score, total, percentage, answers_json, topics_quizzed_json, created_at
                FROM quiz_attempts
                WHERE user_id = ? AND video_id = ? AND session_id = ?
                ORDER BY created_at ASC
                """,
                (user_id, video_id, session_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT score, total, percentage, answers_json, topics_quizzed_json, created_at
                FROM quiz_attempts
                WHERE user_id = ? AND video_id = ?
                ORDER BY created_at ASC
                """,
                (user_id, video_id),
            ).fetchall()

        history = []
        for row in rows:
            entry = dict(row)
            entry["answers"] = json.loads(entry.pop("answers_json") or "[]")
            entry["topics_quizzed"] = json.loads(entry.pop("topics_quizzed_json") or "[]")
            history.append(entry)
        return history
    finally:
        conn.close()


def get_quiz_comparison(video_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Compare performance across all quiz attempts.
    Returns None if no attempts exist.
    """
    history = load_quiz_history(video_id, user_id)
    if not history:
        return None

    scores = [q.get("percentage", 0) for q in history]

    return {
        "total_attempts": len(scores),
        "first_score": scores[0],
        "latest_score": scores[-1],
        "best_score": max(scores),
        "improvement": scores[-1] - scores[0],
        "all_scores": scores,
        "average_score": round(sum(scores) / len(scores), 1),
    }


# ═══════════════════════════════════════════════════════════════
# STUDENT PERFORMANCE — JSON blob in 'lectures' table for streaks
# ═══════════════════════════════════════════════════════════════

def _save_performance_blob(video_id: str, data: Dict[str, Any], user_id: Optional[str] = None) -> bool:
    """Internal: save/update the performance JSON blob."""
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return False

    existing = load_performance(video_id, user_id) or {}
    merged = {**existing, **data}

    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE lectures SET performance = ? WHERE user_id = ? AND video_id = ?",
            (json.dumps(merged), user_id, video_id),
        )
        if conn.total_changes == 0:
            conn.execute(
                "INSERT INTO lectures (user_id, video_id, performance) VALUES (?, ?, ?)",
                (user_id, video_id, json.dumps(merged)),
            )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Could not save performance: {e}")
        return False
    finally:
        conn.close()


def load_performance(video_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Load student performance data for a video."""
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return None

    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT performance FROM lectures WHERE user_id = ? AND video_id = ?",
            (user_id, video_id),
        ).fetchone()
        if row and row["performance"]:
            return json.loads(row["performance"])
        return None
    except json.JSONDecodeError:
        return None
    except Exception:
        return None
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# STREAKS
# ═══════════════════════════════════════════════════════════════

def update_streak(video_id: str, user_id: Optional[str] = None) -> int:
    """
    Update study streak. Returns current streak count.
    A streak counts consecutive days the user studied this video.
    """
    perf = load_performance(video_id, user_id) or {}
    today = datetime.now().date().isoformat()

    last_study = perf.get("last_study_date")
    current_streak = perf.get("streak", 0)

    if last_study == today:
        return current_streak

    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()

    if last_study == yesterday:
        current_streak += 1
    else:
        current_streak = 1

    _save_performance_blob(video_id, {
        "last_study_date": today,
        "streak": current_streak,
    }, user_id)

    return current_streak


# ═══════════════════════════════════════════════════════════════
# LOGGING FUNCTIONS — used by UI pages
# ═══════════════════════════════════════════════════════════════

def log_lecture(
    video_id: str,
    word_count: int,
    video_url: str,
    title: str,
    user_id: Optional[str] = None,
) -> bool:
    """
    Record that a lecture was processed.
    Updates the lectures table with title, word_count, and timestamp.
    """
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return False

    conn = _get_connection()
    try:
        # Insert or update the lecture metadata
        conn.execute(
            """
            INSERT INTO lectures (user_id, video_id, title, word_count, last_updated)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, video_id) DO UPDATE SET
                title = excluded.title,
                word_count = excluded.word_count,
                last_updated = CURRENT_TIMESTAMP
            """,
            (user_id, video_id, title, word_count),
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Could not log lecture: {e}")
        return False
    finally:
        conn.close()


def log_notes(video_id: str, user_id: Optional[str] = None) -> bool:
    """Increment notes_generated counter in performance blob for this video."""
    perf = load_performance(video_id, user_id) or {}
    count = perf.get("notes_generated", 0) + 1
    return _save_performance_blob(video_id, {"notes_generated": count}, user_id)


def log_summary(video_id: str, user_id: Optional[str] = None) -> bool:
    """Increment summary_generated counter in performance blob for this video."""
    perf = load_performance(video_id, user_id) or {}
    count = perf.get("summary_generated", 0) + 1
    return _save_performance_blob(video_id, {"summary_generated": count}, user_id)


def log_chat_message(video_id: str, user_id: Optional[str] = None) -> bool:
    """Increment total_chat_messages counter in performance blob for this video."""
    perf = load_performance(video_id, user_id) or {}
    count = perf.get("total_chat_messages", 0) + 1
    return _save_performance_blob(video_id, {"total_chat_messages": count}, user_id)


# ═══════════════════════════════════════════════════════════════
# LECTURE MANAGEMENT — used by History page
# ═══════════════════════════════════════════════════════════════

def get_all_lectures(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return all lectures for the user, with highest quiz score per video.
    Used by the History page.
    """
    user_id = _get_user_id(user_id)
    if user_id is None:
        return []

    conn = _get_connection()
    try:
        # Get all lectures with highest quiz score per video
        rows = conn.execute(
            """
            SELECT
                l.video_id,
                l.title,
                l.word_count,
                l.last_updated as timestamp,
                COALESCE(
                    (SELECT MAX(percentage) FROM quiz_attempts q
                     WHERE q.user_id = l.user_id AND q.video_id = l.video_id),
                    0
                ) as highest_score,
                l.notes IS NOT NULL as has_notes,
                l.summary IS NOT NULL as has_summary
            FROM lectures l
            WHERE l.user_id = ?
            ORDER BY l.last_updated DESC
            """,
            (user_id,),
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_lecture_title(video_id: str, new_title: str, user_id: Optional[str] = None) -> bool:
    """Update the title of a lecture."""
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return False

    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE lectures SET title = ? WHERE user_id = ? AND video_id = ?",
            (new_title, user_id, video_id),
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Could not update title: {e}")
        return False
    finally:
        conn.close()


def delete_lecture_data(video_id: str, user_id: Optional[str] = None) -> bool:
    """
    Delete ALL data for a video: lectures row, chat messages, quiz attempts.
    """
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return False

    conn = _get_connection()
    try:
        # Delete from lectures
        conn.execute(
            "DELETE FROM lectures WHERE user_id = ? AND video_id = ?",
            (user_id, video_id),
        )
        # Delete from chat_messages
        conn.execute(
            "DELETE FROM chat_messages WHERE user_id = ? AND video_id = ?",
            (user_id, video_id),
        )
        # Delete from quiz_attempts
        conn.execute(
            "DELETE FROM quiz_attempts WHERE user_id = ? AND video_id = ?",
            (user_id, video_id),
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Could not delete lecture data: {e}")
        return False
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# FULL RESTORE — load everything for a video (by session)
# ═══════════════════════════════════════════════════════════════

def load_full_session(
    video_id: str,
    session_id: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Load ALL analytics for a SPECIFIC session.
    Used when restoring from history after years.
    """
    return {
        "video_id": video_id,
        "session_id": session_id,
        "chat_history": load_chat_history(video_id, user_id, session_id),
        "quiz_history": load_quiz_history(video_id, user_id, session_id),
        "performance": load_performance(video_id, user_id),
    }


def load_current_session(video_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Load the LATEST session data for the current lecture view.
    Fetches the most recent session_id from the chat_messages table.
    """
    user_id = _get_user_id(user_id)
    if user_id is None or not video_id:
        return {}

    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT session_id FROM chat_messages "
            "WHERE user_id = ? AND video_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id, video_id),
        ).fetchone()

        if not row:
            return {"video_id": video_id, "session_id": None, "chat_history": [], "quiz_history": []}

        session_id = row["session_id"]
        return load_full_session(video_id, session_id, user_id)
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# ANALYTICS DASHBOARD — used by app_pages/performance.py
# ═══════════════════════════════════════════════════════════════

def get_analytics_data(user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns comprehensive analytics for the performance dashboard.
    Includes DataFrames, summary stats, and top performers.
    """
    user_id = _get_user_id(user_id)
    if user_id is None:
        return {
            "total_lectures": 0,
            "total_quizzes": 0,
            "avg_score": 0,
            "total_words": 0,
            "lectures_today": 0,
            "lectures_df": pd.DataFrame(),
            "quiz_df": pd.DataFrame(),
            "all_lectures": pd.DataFrame(),
            "all_quizzes": pd.DataFrame(),
            "lec_4w": pd.DataFrame(),
            "quiz_4w": pd.DataFrame(),
            "top_score_video": None,
            "top_word_video": None,
            "monthly_summary": pd.DataFrame(),
        }

    conn = _get_connection()
    try:
        # 1. Lectures data
        lectures_query = """
            SELECT
                video_id,
                title,
                word_count,
                last_updated as timestamp,
                date(last_updated) as date
            FROM lectures
            WHERE user_id = ?
        """
        lectures_df = pd.read_sql_query(lectures_query, conn, params=(user_id,))

        # 2. Quiz attempts
        quiz_query = """
            SELECT
                video_id,
                score,
                total,
                percentage,
                created_at as timestamp,
                date(created_at) as date
            FROM quiz_attempts
            WHERE user_id = ?
        """
        quiz_df = pd.read_sql_query(quiz_query, conn, params=(user_id,))

        # 3. Compute stats
        total_lectures = len(lectures_df) if not lectures_df.empty else 0
        total_quizzes = len(quiz_df) if not quiz_df.empty else 0
        avg_score = quiz_df["percentage"].mean() if not quiz_df.empty else 0

        # Total words processed
        total_words = lectures_df["word_count"].sum() if not lectures_df.empty else 0

        # Lectures today
        today = datetime.now().date().isoformat()
        lectures_today = len(lectures_df[lectures_df["date"] == today]) if not lectures_df.empty else 0

        # Last 4 weeks
        four_weeks_ago = (datetime.now().date() - timedelta(days=28)).isoformat()

        lec_4w = lectures_df[lectures_df["date"] >= four_weeks_ago].copy() if not lectures_df.empty else pd.DataFrame()
        quiz_4w = quiz_df[quiz_df["date"] >= four_weeks_ago].copy() if not quiz_df.empty else pd.DataFrame()

        # Top score video
        top_score_video = None
        if not quiz_df.empty:
            top = quiz_df.loc[quiz_df["percentage"].idxmax()] if not quiz_df.empty else None
            if top is not None:
                top_score_video = {
                    "video_id": top["video_id"],
                    "title": lectures_df[lectures_df["video_id"] == top["video_id"]]["title"].iloc[0] if not lectures_df.empty else "Untitled",
                    "score": top["percentage"],
                }

        # Top word video
        top_word_video = None
        if not lectures_df.empty:
            top = lectures_df.loc[lectures_df["word_count"].idxmax()] if not lectures_df.empty else None
            if top is not None:
                top_word_video = {
                    "video_id": top["video_id"],
                    "title": top["title"],
                    "word_count": top["word_count"],
                }

        # Monthly summary (older than 4 weeks)
        monthly_summary = pd.DataFrame()
        if not lectures_df.empty:
            df = lectures_df.copy()
            df["month"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m")
            monthly_summary = (
                df[df["date"] < four_weeks_ago]
                .groupby("month")
                .agg({"video_id": "count", "word_count": "sum"})
                .reset_index()
                .rename(columns={"video_id": "Lectures Studied", "word_count": "Words Processed"})
            )
            # Ensure month column is string
            if not monthly_summary.empty:
                monthly_summary["month"] = monthly_summary["month"].astype(str)

        return {
            "total_lectures": total_lectures,
            "total_quizzes": total_quizzes,
            "avg_score": avg_score,
            "total_words": total_words,
            "lectures_today": lectures_today,
            "lectures_df": lectures_df,
            "quiz_df": quiz_df,
            "all_lectures": lectures_df,
            "all_quizzes": quiz_df,
            "lec_4w": lec_4w,
            "quiz_4w": quiz_4w,
            "top_score_video": top_score_video,
            "top_word_video": top_word_video,
            "monthly_summary": monthly_summary,
        }

    except Exception as e:
        st.error(f"Could not load analytics data: {e}")
        return {
            "total_lectures": 0,
            "total_quizzes": 0,
            "avg_score": 0,
            "total_words": 0,
            "lectures_today": 0,
            "lectures_df": pd.DataFrame(),
            "quiz_df": pd.DataFrame(),
            "all_lectures": pd.DataFrame(),
            "all_quizzes": pd.DataFrame(),
            "lec_4w": pd.DataFrame(),
            "quiz_4w": pd.DataFrame(),
            "top_score_video": None,
            "top_word_video": None,
            "monthly_summary": pd.DataFrame(),
        }
    finally:
        conn.close()