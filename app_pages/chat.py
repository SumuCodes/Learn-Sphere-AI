# app_pages/chat.py
"""
AI Tutor – Full-page ChatGPT-style interface with session history sidebar.
Now using the new normalized chat tables with explicit session_id and user_id.
"""

import streamlit as st
from datetime import datetime
from components.ui import mini_hero, glass_card
from utils.api_utils import CreditError, RateLimitError, api_ready
from utils.rag import get_answer
from utils.performance import (
    log_chat_message,
    load_chat_history,
    save_chat_message,
    get_all_sessions,
    delete_chat_session,
)


def _get_current_user_id() -> str:
    """Helper to get user_id from session_state."""
    return st.session_state.get("user_id", "")


def _get_video_id() -> str:
    """Helper to get current video_id."""
    return st.session_state.get("video_id", "")


def _generate_session_id() -> str:
    """Generate a new unique session ID (timestamp-based)."""
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def show():
    st.markdown('<div class="main-content">', unsafe_allow_html=True)

    mini_hero("👩‍🏫 AI Tutor", "Ask questions about your lecture – with persistent chat history!")

    # ── Check API key ──
    if not api_ready():
        glass_card(
            "🔑 API Key Required",
            "Please set your AI provider API key in the **Workspace** first.",
            icon="⚠️",
            highlight=True
        )
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ── Check lecture loaded ──
    if not st.session_state.get("transcript_ready", False):
        st.info("📚 No lecture loaded yet.")
        st.markdown("""
        To start chatting about a lecture:
        1. Go to **Lecture Studio**
        2. Fetch a transcript or transcribe a video
        3. Build the vector DB (auto-enabled)
        4. Return here to ask anything!
        """)
        if st.button("🎬 Go to Lecture Studio", type="primary", use_container_width=True):
            st.session_state.current_page = "Lecture Studio"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ── Get current user and video ──
    user_id = _get_current_user_id()
    video_id = _get_video_id()
    if not user_id or not video_id:
        st.error("Missing user or video information. Please re‑load the lecture.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ── Initialize chat session state ──
    # We store:
    #   - current_chat_session_id: the session_id for the currently open chat thread
    #   - chat_messages: list of messages for UI display (cached)
    if "current_chat_session_id" not in st.session_state:
        # Start with a new session
        new_session_id = _generate_session_id()
        st.session_state.current_chat_session_id = new_session_id
        st.session_state.chat_messages = []

    # If the current session ID is set, load its messages
    current_session_id = st.session_state.current_chat_session_id
    if current_session_id:
        msgs = load_chat_history(video_id, user_id=user_id, session_id=current_session_id)
        if msgs:
            # Convert to the format expected by the UI
            st.session_state.chat_messages = [
                {"role": m["role"], "content": m["content"]} for m in msgs
            ]
        else:
            # No messages for this session yet
            st.session_state.chat_messages = []

    # ── Sidebar: Chat History ──
    with st.sidebar:
        st.markdown("### 💬 Chat History")

        # New Chat button
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            new_id = _generate_session_id()
            st.session_state.current_chat_session_id = new_id
            st.session_state.chat_messages = []
            st.rerun()

        st.divider()

        # List all chat sessions for this video
        sessions = get_all_sessions(video_id, user_id=user_id)
        if not sessions:
            st.info("No past chats for this lecture.")
        else:
            for sess_id in sessions:
                # We don't have titles, so we show a short preview of the first message
                # For better UX, we could store titles, but we'll keep it simple.
                # Load the first message to use as title
                first_msgs = load_chat_history(video_id, user_id=user_id, session_id=sess_id)
                title = "Chat"
                if first_msgs:
                    first_content = first_msgs[0].get("content", "")
                    title = first_content[:30] + "..." if len(first_content) > 30 else first_content
                display_title = title[:25] + "..." if len(title) > 25 else title

                col1, col2 = st.columns([4, 1])
                with col1:
                    is_current = sess_id == current_session_id
                    if st.button(
                        display_title,
                        key=f"sess_{sess_id}",
                        use_container_width=True,
                        type="primary" if is_current else "secondary"
                    ):
                        if not is_current:
                            st.session_state.current_chat_session_id = sess_id
                            msgs = load_chat_history(video_id, user_id=user_id, session_id=sess_id)
                            st.session_state.chat_messages = [
                                {"role": m["role"], "content": m["content"]} for m in msgs
                            ]
                            st.rerun()
                with col2:
                    if st.button("🗑️", key=f"del_{sess_id}", help="Delete this chat"):
                        delete_chat_session(video_id, sess_id, user_id=user_id)
                        if sess_id == st.session_state.current_chat_session_id:
                            # Create a new session
                            new_id = _generate_session_id()
                            st.session_state.current_chat_session_id = new_id
                            st.session_state.chat_messages = []
                        st.rerun()

        st.divider()
        st.caption(f"🧠 Lecture: **{st.session_state.get('video_title', 'Unknown')}**")

    # ── Main Chat Area ──
    st.caption(f"📚 Current session: {current_session_id[:10]}...")

    chat_container = st.container(height=500, border=True)

    with chat_container:
        if not st.session_state.chat_messages:
            st.info("💬 Ask me anything about this lecture! I'll answer based on the transcript.")
        else:
            for message in st.session_state.chat_messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

    # ── Chat input ──
    if prompt := st.chat_input("Ask your tutor..."):
        # Append user message to UI
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        # Save to database
        save_chat_message(
            video_id=video_id,
            role="user",
            content=prompt,
            user_id=user_id,
            session_id=st.session_state.current_chat_session_id
        )
        # Log analytics (increment counter)
        log_chat_message(video_id, user_id=user_id)

        # Rerun to show user message immediately
        st.rerun()

    # ── Process last user message if assistant hasn't replied yet ──
    if st.session_state.chat_messages and st.session_state.chat_messages[-1]["role"] == "user":
        user_question = st.session_state.chat_messages[-1]["content"]

        with chat_container:
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        answer = get_answer(
                            user_question,
                            document_id=video_id  # we use video_id as document ID
                        )
                        st.markdown(answer)
                        st.session_state.chat_messages.append({"role": "assistant", "content": answer})
                        # Save assistant message
                        save_chat_message(
                            video_id=video_id,
                            role="assistant",
                            content=answer,
                            user_id=user_id,
                            session_id=st.session_state.current_chat_session_id
                        )
                        # Log again (could increment per message or per session – we'll keep simple)
                        log_chat_message(video_id, user_id=user_id)

                    except CreditError as e:
                        error_msg = str(e)
                        st.error(error_msg)
                        st.markdown(
                            "💡 **Add credits or switch to a free model in Workspace.**"
                        )
                        st.session_state.chat_messages.append(
                            {"role": "assistant", "content": f"⚠️ {error_msg}"}
                        )
                        save_chat_message(
                            video_id=video_id,
                            role="assistant",
                            content=f"⚠️ {error_msg}",
                            user_id=user_id,
                            session_id=st.session_state.current_chat_session_id
                        )

                    except RateLimitError as e:
                        error_msg = str(e)
                        st.error(error_msg)
                        st.markdown(
                            "💡 **Rate limit reached. Wait a moment or switch providers in Workspace.**"
                        )
                        st.session_state.chat_messages.append(
                            {"role": "assistant", "content": f"⚠️ {error_msg}"}
                        )
                        save_chat_message(
                            video_id=video_id,
                            role="assistant",
                            content=f"⚠️ {error_msg}",
                            user_id=user_id,
                            session_id=st.session_state.current_chat_session_id
                        )

                    except Exception as e:
                        error_msg = str(e)
                        st.error(f"❌ Error: {error_msg}")
                        st.session_state.chat_messages.append(
                            {"role": "assistant", "content": f"❌ I encountered an error: {error_msg}"}
                        )
                        save_chat_message(
                            video_id=video_id,
                            role="assistant",
                            content=f"❌ {error_msg}",
                            user_id=user_id,
                            session_id=st.session_state.current_chat_session_id
                        )

        # Rerun to update the UI with the assistant's response
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)