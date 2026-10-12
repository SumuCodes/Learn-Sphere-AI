# app_pages/notes.py
"""
Study Notes – Workspace layout with topic sidebar and detailed notes.
"""

import streamlit as st
import time
import re
import hashlib
import json
import os
from collections import defaultdict
from components.ui import mini_hero, primary_button, toast_error, toast_success, glass_card
from utils.api_utils import (
    generate_chunk_notes,
    CreditError,
    RateLimitError,
    get_free_model_suggestions
)
from utils.performance import log_notes
from utils.topics import save_lecture_content
from utils.text_splitter import smart_split_text
from components.ai_tutor_sidebar import show_ai_tutor_sidebar
from config import DATA_DIR

CHUNK_SIZE = 30000
CHECKPOINT_DIR = str(DATA_DIR / ".checkpoints")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)


def _get_user_id() -> str:
    return st.session_state.get("user_id", "")


def _get_video_id() -> str:
    return st.session_state.get("video_id", "")


def show():
    # ── Get the main column (AI Tutor is rendered on the right) ──
    main_col = show_ai_tutor_sidebar()

    with main_col:
        st.markdown('<div class="main-content green-headings">', unsafe_allow_html=True)
        mini_hero("📓 Study Notes", "Structured, exam-friendly notes from the lecture transcript")

        # ── Check lecture ──
        if not st.session_state.get("transcript_ready", False):
            glass_card("🎬 No Lecture", "Analyze a YouTube lecture first.", icon="📺", highlight=True)
            st.markdown('</div>', unsafe_allow_html=True)
            return

        user_id = _get_user_id()
        video_id = _get_video_id()
        if not user_id or not video_id:
            st.error("Missing user or video information. Please re‑load the lecture.")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        has_topics = (
            st.session_state.get("sections_ready", False)
            and bool(st.session_state.get("pre_generated_sections", []))
        )

        # ── If no topics and no notes, show generation options ──
        if not has_topics and not st.session_state.get("notes_ready", False):
            st.info("💡 No pre‑generated topics found. You can generate notes from the full transcript or go to Lecture Studio to generate topics first.")
            col_gen1, col_gen2 = st.columns(2)
            with col_gen1:
                if st.button("📄 Generate Notes from Transcript", use_container_width=True, type="primary"):
                    st.session_state._generate_from_transcript = True
                    st.rerun()
            with col_gen2:
                if st.button("🎬 Go to Lecture Studio", use_container_width=True):
                    st.session_state.current_page = "Lecture Studio"
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            return

        # ── Generate notes if not ready ──
        if not st.session_state.get("notes_ready", False):
            if has_topics:
                # Fast path: build notes from pre‑generated topics
                with st.status("Building notes from topics...", expanded=True) as status:
                    try:
                        sections = st.session_state.pre_generated_sections
                        grouped = defaultdict(lambda: {"title": "", "notes": []})
                        for sec in sections:
                            key = sec.get("topic_key", "misc")
                            title = sec.get("topic_title", key.replace("_", " ").title())
                            notes = sec.get("notes", "")
                            if not grouped[key]["title"]:
                                grouped[key]["title"] = title
                            if notes:
                                grouped[key]["notes"].append(notes)

                        final = ""
                        for key, data in grouped.items():
                            title = data["title"] or key.replace("_", " ").title()
                            final += f"## {title}\n\n"
                            for block in data["notes"]:
                                final += f"{block}\n\n"
                            final += "\n---\n\n"

                        if not final:
                            final = "No structured notes could be generated from the pre‑generated topics."

                        st.session_state.notes = final
                        st.session_state.notes_ready = True
                        st.session_state.show_notes = True
                        if video_id:
                            save_lecture_content(video_id, 'notes', final, user_id=user_id)
                        log_notes(video_id, user_id=user_id)
                        status.update(label="✅ Notes ready!", state="complete")
                        toast_success("Notes loaded instantly from pre‑generated topics!")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        status.update(label="❌ Error", state="error")
                        toast_error(f"Failed to build notes from topics: {e}")

            else:
                # Slow path: generate from full transcript
                source_transcript = st.session_state.get("compressed_transcript") or st.session_state.transcript
                if not source_transcript:
                    st.warning("No transcript found.")
                    st.markdown('</div>', unsafe_allow_html=True)
                    return

                if primary_button("✨ Generate AI Notes from Transcript"):
                    with st.status("Generating notes...", expanded=True) as status:
                        try:
                            words = len(source_transcript.split())
                            chunks = smart_split_text(source_transcript, CHUNK_SIZE)
                            total = len(chunks)
                            status.write(f"📄 {total} chunks (~{words:,} words)")

                            t_hash = hashlib.md5(source_transcript.encode('utf-8')).hexdigest()
                            grouped = defaultdict(lambda: {"title": "", "notes": []})
                            progress_bar = st.progress(0, text="Starting...")

                            for i, chunk in enumerate(chunks):
                                progress_bar.progress((i + 1) / total, text=f"Chunk {i+1}/{total}")
                                status.update(label=f"Chunk {i+1}/{total}...")
                                cp_file = os.path.join(CHECKPOINT_DIR, f"{t_hash}_chunk_{i}.json")

                                if os.path.exists(cp_file):
                                    with open(cp_file, 'r') as f:
                                        sections = json.load(f)
                                    status.write(f"✅ Loaded chunk {i+1} from checkpoint")
                                else:
                                    status.write(f"📝 Sending chunk {i+1} to AI...")
                                    try:
                                        result = generate_chunk_notes(chunk)
                                        sections = result.get("sections", [])
                                        with open(cp_file, 'w') as f:
                                            json.dump(sections, f)
                                        status.write(f"✅ Chunk {i+1} done")
                                    except (CreditError, RateLimitError) as e:
                                        status.write(f"❌ Critical error on chunk {i+1}: {e}")
                                        progress_bar.empty()
                                        raise
                                    except Exception as e:
                                        status.write(f"❌ Chunk {i+1} failed: {e}")
                                        sections = []

                                for sec in sections:
                                    key = sec.get("topic_key", "misc")
                                    title = sec.get("topic_title", key.replace("_", " ").title())
                                    notes = sec.get("notes", "")
                                    if not grouped[key]["title"]:
                                        grouped[key]["title"] = title
                                    if notes:
                                        grouped[key]["notes"].append(notes)

                            progress_bar.empty()

                            final = ""
                            for key, data in grouped.items():
                                title = data["title"] or key.replace("_", " ").title()
                                final += f"## {title}\n\n"
                                for block in data["notes"]:
                                    final += f"{block}\n\n"
                                final += "\n---\n\n"

                            if not final:
                                final = "No structured notes could be generated."

                            st.session_state.notes = final
                            st.session_state.notes_ready = True
                            st.session_state.show_notes = True
                            if video_id:
                                save_lecture_content(video_id, 'notes', final, user_id=user_id)
                                save_lecture_content(video_id, 'transcript', source_transcript, user_id=user_id)
                            log_notes(video_id, user_id=user_id)

                            status.update(label="✅ Notes generated!", state="complete")
                            toast_success("Study notes generated successfully!")
                            time.sleep(1)
                            st.rerun()

                        except (CreditError, RateLimitError) as e:
                            status.update(label="❌ API error", state="error")
                            st.error(str(e))
                            st.markdown("### 💡 Switch to a Free Model")
                            suggestions = get_free_model_suggestions()
                            for provider, model, _ in suggestions:
                                if st.button(f"🔄 {provider} – {model}"):
                                    st.session_state.provider = provider
                                    st.session_state.model = model
                                    st.session_state.client = None
                                    st.rerun()
                        except Exception as e:
                            status.update(label="❌ Error", state="error")
                            toast_error(f"Failed to generate notes: {e}")

            # If notes just became ready, rerun to show them in the workspace layout
            if st.session_state.get("notes_ready", False):
                st.rerun()

        # ── Display notes in workspace layout ──
        if st.session_state.get("notes_ready", False) and st.session_state.get("show_notes", False):
            notes_content = st.session_state.notes

            # Extract headings for TOC and sidebar
            headings = re.findall(r'^##\s+(.*)$', notes_content, re.MULTILINE)
            if not headings:
                headings = ["Notes"]

            # ── Workspace: left sidebar + main content ──
            col_left, col_right = st.columns([1, 4], gap="large")

            with col_left:
                st.markdown('<div class="notes-topic-sidebar">', unsafe_allow_html=True)
                st.markdown('<div class="sidebar-label">📑 Topics</div>', unsafe_allow_html=True)

                # ── Search inside sidebar ──
                st.markdown('<div class="search-box">', unsafe_allow_html=True)
                search_term = st.text_input(
                    "Search topics",
                    placeholder="Filter topics...",
                    key="topic_search",
                    label_visibility="collapsed"
                )
                st.markdown('</div>', unsafe_allow_html=True)

                # ── Filter headings based on search ──
                filtered_indices = []
                for i, h in enumerate(headings):
                    if search_term:
                        if search_term.lower() in h.lower():
                            filtered_indices.append(i)
                    else:
                        filtered_indices.append(i)

                # ── Render topic items (unique keys via original index) ──
                if "_active_topic_idx" not in st.session_state:
                    st.session_state._active_topic_idx = 0

                for display_idx, orig_idx in enumerate(filtered_indices):
                    heading = headings[orig_idx]
                    is_active = (orig_idx == st.session_state._active_topic_idx)

                    if st.button(
                        f"{display_idx+1:02d} {heading}",
                        key=f"topic_{orig_idx}",               # guaranteed unique
                        use_container_width=True,
                        type="primary" if is_active else "secondary"
                    ):
                        st.session_state._active_topic_idx = orig_idx
                        anchor = re.sub(r'[^\w\s-]', '', heading).strip().lower().replace(' ', '-')
                        st.markdown(f'<script>document.getElementById("{anchor}").scrollIntoView();</script>', unsafe_allow_html=True)
                        st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)

            with col_right:
                st.markdown('<div class="notes-content">', unsafe_allow_html=True)

                # ── Header ──
                st.markdown(
                    """
                    <div class="notes-header">
                        <h2>📓 Lecture Notes</h2>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # ── Table of Contents (compact) ──
                if len(headings) > 1:
                    with st.expander("📑 Table of Contents", expanded=False):
                        for h in headings:
                            anchor = re.sub(r'[^\w\s-]', '', h).strip().lower().replace(' ', '-')
                            st.markdown(f"- [{h}](#{anchor})")

                # ── Notes body with search highlighting ──
                if search_term:
                    highlighted = re.sub(
                        f"({re.escape(search_term)})",
                        r'<mark style="background:#FFD600;color:#000;padding:1px 3px;border-radius:3px;">\1</mark>',
                        notes_content,
                        flags=re.IGNORECASE
                    )
                    st.markdown(f'<div class="notes-body">{highlighted}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="notes-body">{notes_content}</div>', unsafe_allow_html=True)

                # ── Download buttons ──
                st.markdown('<div class="download-row">', unsafe_allow_html=True)
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    st.download_button(
                        "📥 Download Markdown",
                        data=notes_content,
                        file_name="lecture_notes.md",
                        mime="text/markdown",
                        use_container_width=True
                    )
                with col_dl2:
                    st.download_button(
                        "📄 Download Text",
                        data=notes_content,
                        file_name="lecture_notes.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('</div>', unsafe_allow_html=True)  # end notes-content

        st.markdown('</div>', unsafe_allow_html=True)  # end main-content