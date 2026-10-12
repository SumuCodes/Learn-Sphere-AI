# utils/rag.py
"""
RAG — reads content from topics.py, logs analytics to performance.py.
No circular risk: rag.py imports both, they don't import each other.
"""

import streamlit as st
from utils.vector_store import search_vector_store
from utils.api_utils import generate_response, CreditError
from utils.topics import search_topics, topics_exist
from utils.performance import log_chat_message


def _get_video_id() -> str:
    return st.session_state.get("video_id", "")


def _get_user_id() -> str:
    return st.session_state.get("user_id", "")


def get_answer(query: str, document_id: str = "current_video") -> str:
    if not st.session_state.transcript_ready:
        return "No transcript loaded. Please analyze a video first."

    username = st.session_state.get("username", "there")
    video_id = st.session_state.get("video_id", "current_video")
    video_title = st.session_state.get("video_title", "the lecture")
    user_id = _get_user_id()

    # ── Build context from Topic DB ──
    if topics_exist(video_id):
        relevant_topics = search_topics(query, video_id, top_k=4)
        topic_context = _format_topics(relevant_topics)

        chunks = search_vector_store(query, document_id)
        chunk_context = "\n\n".join(chunks) if chunks else ""

        context_block = f"""━━━ TOPIC DATABASE (primary) ━━━
{topic_context}

━━━ TRANSCRIPT EXCERPTS (extra detail) ━━━
{chunk_context if chunk_context else "Not needed."}"""
        source = "topic_db"
    else:
        chunks = search_vector_store(query, document_id)
        context_block = "\n\n".join(chunks) if chunks else "No context found."
        source = "raw_chunks"

    # ── Adaptive prompt ──
    system_prompt = _build_system_prompt(username, video_title, source)

    user_prompt = f"""{context_block}

━━━ STUDENT'S QUESTION ━━━
{query}

Remember: ADAPT the knowledge — reword, adjust examples, match depth — 
to what THIS student needs."""

    try:
        answer = generate_response(
            user_prompt, system_message=system_prompt, temperature=0.6
        )
        # ✅ FIXED: Pass video_id and user_id to log_chat_message
        log_chat_message(video_id, user_id=user_id)
        return answer
    except CreditError:
        raise
    except Exception as e:
        return f"Sorry {username}, I ran into an error: {e}"


def _build_system_prompt(username, video_title, source):
    base = (
        f"You are a friendly, encouraging human tutor chatting with {username}. "
        f"Lecture: \"{video_title}\". "
        f"Be conversational, use emojis occasionally, always supportive. "
        f"Greet by name if they say hi. Answer ANY question."
    )
    if source == "topic_db":
        adaptation = (
            "\n\nYou have STRUCTURED KNOWLEDGE from the Topic Database. "
            "ADAPT it to the student:\n"
            "• 'simply'/'basics' → simple language, analogies, no jargon\n"
            "• 'in depth'/'detailed' → thorough, all nuances\n"
            "• 'example'/'show me' → fresh concrete example\n"
            "• 'math'/'formula' → include notation\n"
            "• 'compare'/'vs' → pull MULTIPLE topics, contrast\n"
            "• 'why'/'intuition' → explain the WHY\n"
            "• REWORD in your own voice — never copy-paste notes\n"
            "• ADJUST EXAMPLES to student's level\n"
            "• Going beyond lecture? Say 'Going beyond the lecture...'"
        )
    else:
        adaptation = "\n\nUse transcript excerpts. Reword in your own voice."
    return base + adaptation


def _format_topics(topics):
    if not topics:
        return "No relevant topics found."
    parts = []
    for i, t in enumerate(topics, 1):
        title = t.get("topic_title", "Untitled")
        key = t.get("topic_key", "")
        notes = t.get("notes", "No notes.")
        header = f"Topic {i}: {title}"
        if key:
            header += f"  [{key}]"
        parts.append(f"{header}\n{notes}")
    return "\n\n".join(parts)