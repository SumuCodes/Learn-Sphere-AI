# utils/session.py
"""
Session state initialization for AI Lecture Recorder Pro.
All Streamlit session keys are defined in one place to avoid KeyError issues.
Dual-engine: Primary (Gemini) + Safety Net (Groq).
"""

import streamlit as st

from config import (
    DEFAULT_PROVIDER,
    DEFAULT_MODEL,
    DEFAULT_FALLBACK_PROVIDER,
    DEFAULT_FALLBACK_MODEL,
)
from utils.api_utils import initialize_api_session


def init_session():
    """Initialize all session state variables."""

    defaults = {
        # ======================================================
        # Video / Transcript
        # ======================================================
        "video_url": "",
        "video_id": "",
        "video_title": "",           # <-- ADDED: title of the YouTube video
        "current_video_id": "",
        "transcript": "",
        "transcript_ready": False,

        # ======================================================
        # AI Generated Content
        # ======================================================
        "summary": "",
        "summary_ready": False,

        "notes": "",
        "notes_ready": False,

        # ======================================================
        # Quiz State
        # ======================================================
        "quiz_questions": [],
        "quiz_answers": [],
        "quiz_user_answers": [],
        "quiz_score": 0,
        "quiz_ready": False,
        "quiz_submitted": False,

        # ======================================================
        # Chat State
        # ======================================================
        "chat_messages": [],
        "chat_history": [],
        "chat_ready": False,

        # ======================================================
        # Performance / Analytics
        # ======================================================
        "performance_ready": False,

        # ======================================================
        # Navigation
        # ======================================================
        "current_page": "Dashboard",

        # ======================================================
        # User Authentication
        # ======================================================
        "user_id": None,
        "username": "",
        "logged_in": False,
        "theme": "dark",
    }

    # Create missing keys
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Delegate API-related session init to api_utils (single source of truth)
    initialize_api_session()