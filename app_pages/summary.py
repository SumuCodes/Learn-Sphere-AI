# app_pages/summary.py
"""
AI-generated lecture summary – now with Master Summary (from topics) and Full Transcript modes.
"""

import streamlit as st
import time
import re
from components.ui import (
    mini_hero, primary_button, divider, toast_error, toast_success, glass_card,
)
from utils.api_utils import generate_response, CreditError, RateLimitError, get_free_model_suggestions
from utils.performance import log_summary
from utils.topics import save_lecture_content
from utils.text_splitter import smart_split_text
from components.ai_tutor_sidebar import show_ai_tutor_sidebar

# Try to import the topic extractor from notes.py
try:
    from app_pages.notes import generate_chunk_topics
except ImportError:
    # Fallback: define a stub that raises an error (should not happen)
    def generate_chunk_topics(chunk):
        raise RuntimeError("generate_chunk_topics not available; please ensure notes.py is present.")

CHUNK_SIZE_TRANSCRIPT = 15000


def _get_user_id() -> str:
    return st.session_state.get("user_id", "")


def _get_video_id() -> str:
    return st.session_state.get("video_id", "")


def extract_sections_from_notes(notes_md: str):
    """Parse markdown notes (## headings) into (heading, content) list."""
    sections = []
    lines = notes_md.split('\n')
    current_heading = None
    current_content = []
    for line in lines:
        if line.strip().startswith('## '):
            if current_heading is not None:
                sections.append((current_heading, '\n'.join(current_content).strip()))
            current_heading = line.strip()[3:].strip()
            current_content = []
        else:
            if current_heading is not None:
                current_content.append(line)
    if current_heading is not None:
        sections.append((current_heading, '\n'.join(current_content).strip()))
    return sections


def summarize_from_headings(sections):
    """
    Create a master summary from a list of (heading, content) pairs.
    Uses only headings + first sentence to minimise token usage.
    """
    if not sections:
        return ""

    heading_summaries = []
    for heading, content in sections:
        first_line = ""
        if content:
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            first_line = lines[0] if lines else ""
        if len(first_line) > 100:
            first_line = first_line[:100] + "..."
        heading_summaries.append(f"- **{heading}**: {first_line}")

    compact = "\n".join(heading_summaries)

    # Approximate token check (could be replaced with tiktoken for precision)
    if len(compact) < 20000:  # ~5k tokens
        prompt = f"""
        The following are topics from a lecture, each with a brief description.
        Create a cohesive summary that groups related topics under broad headings (use Markdown H2 '##').
        The summary should be concise but cover all main topics. Remove repetition.

        Topics:
        {compact}
        """
        return generate_response(
            prompt,
            system_message="You are an expert summarisation assistant.",
            temperature=0.3,
            max_tokens=1200
        )

    groups = [heading_summaries[i:i+30] for i in range(0, len(heading_summaries), 30)]
    group_summaries = []
    for idx, group in enumerate(groups):
        group_text = "\n".join(group)
        prompt = f"Summarise the key themes from these topics (Part {idx+1} of {len(groups)}):\n\n{group_text}"
        summary = generate_response(
            prompt,
            system_message="Provide a concise summary of these topics.",
            temperature=0.3,
            max_tokens=600
        )
        group_summaries.append(summary)

    combined = "\n\n---\n\n".join(group_summaries)
    final_prompt = f"Combine the following summaries into one master summary. Group related ideas under broad headings (use ##).\n\nSummaries:\n{combined}"
    return generate_response(
        final_prompt,
        system_message="Create a final, flowing master summary.",
        temperature=0.3,
        max_tokens=1500
    )


def show():
    # Right sidebar (AI Tutor) – returns the left column
    main_col = show_ai_tutor_sidebar()

    with main_col:
        st.markdown('<div class="main-content">', unsafe_allow_html=True)
        mini_hero("📖 Quick Revision", "A concise revision sheet from the lecture")

        # Wrap content in green-headings for coloured headings and links
        st.markdown('<div class="green-headings">', unsafe_allow_html=True)

        if not st.session_state.get("transcript_ready", False):
            glass_card("🎬 No Lecture Available", "Analyze a YouTube lecture first.", icon="📺", highlight=True)
            st.markdown('</div></div>', unsafe_allow_html=True)  # close green-headings and main-content
            return

        user_id = _get_user_id()
        video_id = _get_video_id()
        if not user_id or not video_id:
            st.error("Missing user or video information. Please re‑load the lecture.")
            st.markdown('</div></div>', unsafe_allow_html=True)
            return

        has_topics = st.session_state.get("sections_ready", False) and st.session_state.get("pre_generated_sections", [])
        notes_available = st.session_state.get("notes_ready", False) and st.session_state.get("notes", "").strip()

        if not st.session_state.get("summary_ready", False):
            st.markdown("### 📝 Choose Input Source")

            # --- SOURCE SELECTION (simplified to 2 options based on priority) ---
            if has_topics:
                # Topics exist → show Topics vs Full Transcript
                mode = st.radio(
                    "Select summary source:",
                    [
                        "📚 Master Summary from Topics (Recommended – fastest)",
                        "📄 Full Transcript (Slower)"
                    ],
                    horizontal=True,
                    label_visibility="collapsed"
                )
                use_topics = "Master Summary" in mode
                use_notes = False
            elif notes_available:
                # No topics, but notes exist → show Notes vs Full Transcript
                mode = st.radio(
                    "Select summary source:",
                    [
                        "📘 Notes Summary from your Notes (Recommended – faster)",
                        "📄 Full Transcript (Slower)"
                    ],
                    horizontal=True,
                    label_visibility="collapsed"
                )
                use_topics = False
                use_notes = "Notes Summary" in mode
            else:
                # Neither topics nor notes → force Full Transcript with info
                st.info("💡 Generate study notes or topics first for a faster summary.")
                use_topics = False
                use_notes = False
                st.markdown("📄 **Using Full Transcript** (no notes or topics found)")

            if primary_button("✨ Generate AI Summary"):
                progress_bar = st.progress(0.0, text="Preparing to generate summary...")
                status_text = st.empty()

                try:
                    summary = None

                    # ======================================================
                    # MODE 1: Master Summary (from pre‑generated topics)
                    # ======================================================
                    if use_topics and has_topics:
                        status_text.markdown("🧠 Extracting topics from pre‑generated sections...")
                        sections = st.session_state.pre_generated_sections
                        # Convert to (heading, content) – heading = topic_title, content = notes
                        topic_sections = []
                        for sec in sections:
                            heading = sec.get("topic_title", sec.get("topic_key", "Untitled"))
                            content = sec.get("notes", "")
                            topic_sections.append((heading, content))
                        progress_bar.progress(0.3, text=f"Found {len(topic_sections)} topics")

                        if topic_sections:
                            status_text.markdown("🧠 Generating master summary from topics...")
                            summary = summarize_from_headings(topic_sections)
                            progress_bar.progress(0.9, text="Finalising...")
                        else:
                            raise RuntimeError("No topics found in pre‑generated sections.")

                    # ======================================================
                    # MODE 2: Notes Summary (from existing notes)
                    # ======================================================
                    elif use_notes and notes_available:
                        status_text.markdown("🧠 Extracting topics from your notes...")
                        sections = extract_sections_from_notes(st.session_state.notes)
                        progress_bar.progress(0.3, text=f"Found {len(sections)} topics")

                        if sections:
                            status_text.markdown("🧠 Generating summary from headings...")
                            summary = summarize_from_headings(sections)
                            progress_bar.progress(0.9, text="Finalising...")
                        else:
                            raise RuntimeError("Could not parse any topics from notes.")

                    # ======================================================
                    # MODE 3: Full Transcript (Map‑Reduce with Topic Extraction)
                    # ======================================================
                    else:
                        # Use raw transcript (no compressed version)
                        source_transcript = st.session_state.transcript
                        words = len(source_transcript.split())
                        chunks = smart_split_text(source_transcript, CHUNK_SIZE_TRANSCRIPT)
                        total_chunks = len(chunks)

                        if total_chunks == 1:
                            # Single chunk: directly extract topics and summarise
                            status_text.markdown("🧠 Extracting topics from transcript...")
                            topics_md = generate_chunk_topics(source_transcript)
                            sections = extract_sections_from_notes(topics_md)
                            if sections:
                                summary = summarize_from_headings(sections)
                            else:
                                raise RuntimeError("No topics extracted from transcript.")
                        else:
                            status_text.info(f"📄 {total_chunks} chunks → {total_chunks} topic extraction calls (~{words:,} words)")
                            all_topics_md = []
                            start_time = time.time()

                            for i, chunk in enumerate(chunks):
                                progress_percent = (i / total_chunks)
                                progress_bar.progress(progress_percent, text=f"Processing chunk {i+1} of {total_chunks}...")
                                if i > 0:
                                    elapsed = time.time() - start_time
                                    est_total = elapsed / i * total_chunks
                                    remaining = est_total - elapsed
                                    time_str = f"~{int(remaining/60)}m {int(remaining%60)}s left" if remaining > 60 else f"~{int(remaining)}s left"
                                    status_text.markdown(f"📝 Extracting topics from chunk **{i+1} of {total_chunks}**... (⏳ {time_str})")
                                else:
                                    status_text.markdown(f"📝 Extracting topics from chunk **{i+1} of {total_chunks}**...")

                                try:
                                    topics_md = generate_chunk_topics(chunk)
                                    all_topics_md.append(topics_md)
                                except (CreditError, RateLimitError) as e:
                                    progress_bar.empty()
                                    status_text.markdown(f"❌ Critical error on chunk {i+1}: {e}")
                                    raise
                                except Exception as e:
                                    status_text.markdown(f"⚠️ Chunk {i+1} failed: {e}")
                                    all_topics_md.append("")

                            all_topics_md = [t for t in all_topics_md if t.strip()]
                            if not all_topics_md:
                                raise RuntimeError("No valid topic extractions from any chunk.")

                            # Combine all topic markdowns
                            combined_md = "\n\n---\n\n".join(all_topics_md)
                            sections = extract_sections_from_notes(combined_md)
                            if not sections:
                                raise RuntimeError("Could not extract any topics from combined markdown.")
                            progress_bar.progress(0.9, text="Finalising summary...")
                            status_text.markdown("🔗 Consolidating topics into final summary...")
                            summary = summarize_from_headings(sections)

                    if summary:
                        st.session_state.summary = summary
                        st.session_state.summary_ready = True
                        st.session_state.show_summary = True

                        # Save to DB using topics.py
                        if video_id:
                            save_lecture_content(video_id, 'summary', summary, user_id=user_id)

                        # Log analytics
                        log_summary(video_id, user_id=user_id)

                        progress_bar.progress(1.0, text="Completed!")
                        status_text.empty()
                        toast_success("Summary generated successfully!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        raise RuntimeError("No summary was generated.")

                except (CreditError, RateLimitError) as e:
                    progress_bar.empty()
                    status_text.empty()
                    st.error(str(e))
                    st.markdown("### 💡 Switch to a Free Model")
                    suggestions = get_free_model_suggestions()
                    cols = st.columns(min(len(suggestions), 3))
                    for idx, (provider, model, desc) in enumerate(suggestions):
                        with cols[idx % len(cols)]:
                            if st.button(f"🔄 {provider}\n{model}", key=f"summary_switch_{provider}_{model}"):
                                st.session_state.provider = provider
                                st.session_state.model = model
                                st.session_state.client = None
                                st.rerun()
                except Exception as e:
                    progress_bar.empty()
                    status_text.empty()
                    toast_error(f"Failed to generate summary: {e}")

        else:
            # ---- SHOW EXISTING SUMMARY ----
            if not st.session_state.get("show_summary", False):
                if primary_button("👁️ View Generated Summary"):
                    st.session_state.show_summary = True
                    st.rerun()
            else:
                divider()
                st.markdown("### 📄 Lecture Summary")
                search_term = st.text_input("🔍 Search in summary...", placeholder="Type a keyword to highlight it")
                summary_content = st.session_state.summary

                if search_term:
                    matches = len(re.findall(search_term, summary_content, flags=re.IGNORECASE))
                    st.caption(f"Found **{matches}** match(es) for '{search_term}'.")
                    highlighted = re.sub(
                        f"({re.escape(search_term)})",
                        r'<mark style="background-color: #FFD600; color: #000000; padding: 1px 3px; border-radius: 3px;">\1</mark>',
                        summary_content,
                        flags=re.IGNORECASE
                    )
                    st.markdown(highlighted, unsafe_allow_html=True)
                else:
                    st.markdown(summary_content)

                divider()
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(label="📥 Download Markdown", data=st.session_state.summary, file_name="lecture_summary.md", mime="text/markdown", use_container_width=True)
                with col2:
                    st.download_button(label="📄 Download Text", data=st.session_state.summary, file_name="lecture_summary.txt", mime="text/plain", use_container_width=True)

        # Close green-headings and main-content divs
        st.markdown('</div></div>', unsafe_allow_html=True)