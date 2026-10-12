# models/video_session.py
import os
import shutil
from typing import List
import streamlit as st
from utils.vector_store import create_vector_store, delete_document, search_vector_store


class VideoSession:
    def __init__(self):
        self.sections: List[dict] = []
        self.transcript: str = ""
        self.video_url: str = ""
        self.video_id: str = ""
        self.chat_history: List[dict] = []
        self.last_api_error: str = ""

    @property
    def ready(self) -> bool:
        return bool(self.transcript and self.sections)

    @property
    def total_questions(self) -> int:
        return sum(len(section.get("questions", [])) for section in self.sections)

    def clear(self) -> None:
        """Clear session data for the current video."""
        # Clear ChromaDB document for this video
        if self.video_id:
            try:
                delete_document(self.video_id)
            except Exception:
                pass

        self.sections = []
        self.transcript = ""
        self.video_url = ""
        self.video_id = ""
        self.chat_history = []
        self.last_api_error = ""

        # Selective session state reset (preserve auth, user, page)
        video_keys = [
            "video_url", "video_id", "video_title",
            "transcript", "transcript_ready", "compressed_transcript",
            "summary", "summary_ready", "show_summary",
            "notes", "notes_ready", "show_notes",
            "quiz_questions", "quiz_answers", "quiz_user_answers",
            "quiz_score", "quiz_ready", "quiz_submitted", "show_quiz",
            "chat_messages", "chat_history",
        ]
        for key in video_keys:
            if key in st.session_state:
                del st.session_state[key]

    def create_vector_store(self, transcript: str, video_id: str) -> int:
        """Build ChromaDB vector store for the current video."""
        self.video_id = video_id
        return create_vector_store(transcript, document_id=video_id)

    def search(self, query: str) -> List[str]:
        """Search the vector store for relevant chunks."""
        if not self.video_id:
            return []
        return search_vector_store(query, document_id=self.video_id)

    def update_processed_video(self, url: str, transcript: str, sections: List[dict]) -> None:
        """Update session after processing a video."""
        self.video_url = url
        self.transcript = transcript
        self.sections = sections
        self.chat_history = [
            {
                "role": "assistant",
                "text": (
                    f"✅ Video analyzed!\n\n"
                    f"Generated **{self.total_questions} questions** from **{len(sections)} sections** of the transcript.\n\n"
                    f"⚠️ **Important:** I will answer ONLY from the video transcript. "
                    f"If a question is not covered in the video, I will say so.\n\n"
                    f"👉 Type your question below!"
                ),
            }
        ]