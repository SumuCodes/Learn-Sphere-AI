# app_pages/analyze.py
"""
Lecture Studio – Workflow‑first interface.
Import → Configure → Process.
"""

import streamlit as st
import json
import time
from utils.transcript import get_transcript, extract_video_id, get_video_title
from utils.vector_store import create_vector_store
from utils.smart_summarizer import extractive_summary, get_summary_stats
from utils.performance import log_lecture
from utils.audio_processor import download_audio, transcribe_audio
from utils.api_utils import generate_chunk_notes, CreditError, RateLimitError
from utils.text_splitter import smart_split_text
from components.loading_overlay import show_loading_overlay, clear_loading
from components.ui import mini_hero, glass_card, toast_error, toast_success
from config import DEFAULT_SUMMARY_METHOD, FREE_TIER_LIMITS
from utils.topics import load_topics, save_topics

CHUNK_SIZE_SECTIONS = 6000

def _get_user_id() -> str:
    return st.session_state.get("user_id", "")

def pre_generate_sections(transcript: str, status, progress_bar, status_text):
    chunks = smart_split_text(transcript, CHUNK_SIZE_SECTIONS)
    total_chunks = len(chunks)
    all_sections = []
    total_start_time = time.time()
    cumulative_topics = 0
    provider = st.session_state.get("provider", "unknown")
    today = time.strftime("%Y-%m-%d")
    rpd_limit = FREE_TIER_LIMITS.get(provider, {}).get("rpd", 0)

    for i, chunk in enumerate(chunks):
        chunk_start_time = time.time()
        token_usage = st.session_state.get('token_usage', {}).get(provider, 0)
        rpd_used = st.session_state.get(f"rpd_{provider}_{today}", 0)
        rpd_percent = min(100, int((rpd_used / rpd_limit) * 100)) if rpd_limit > 0 else 0
        rpd_emoji = "🟢" if rpd_percent < 70 else "🟡" if rpd_percent < 90 else "🔴"

        if i == 0:
            eta_str = "estimating..."
        else:
            elapsed = time.time() - total_start_time
            avg_time_per_chunk = elapsed / i
            remaining = total_chunks - i
            eta_seconds = avg_time_per_chunk * remaining
            eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s remaining" if eta_seconds > 60 else f"{int(eta_seconds)}s remaining"

        status.update(label=f"⏳ Chunk {i+1}/{total_chunks} (ETA: {eta_str})")
        progress_text = f"Chunk {i+1}/{total_chunks} — Topics: {cumulative_topics} | {rpd_emoji} RPD: {rpd_used}/{rpd_limit}" if rpd_limit > 0 else f"Chunk {i+1}/{total_chunks} — Topics: {cumulative_topics}"
        progress_bar.progress((i + 1) / total_chunks, text=progress_text)

        try:
            result = generate_chunk_notes(chunk)
            sections = result.get("sections", [])
            all_sections.extend(sections)
            cumulative_topics += len(sections)
            elapsed_sec = time.time() - chunk_start_time
            status_text.markdown(f"✅ Chunk {i+1} done – **+{len(sections)}** topics (Total: **{cumulative_topics}**) — ⏱️ {elapsed_sec:.1f}s")
        except (CreditError, RateLimitError) as e:
            status_text.markdown(f"❌ API error on chunk {i+1}: {e}")
            raise
        except Exception as e:
            status_text.markdown(f"⚠️ Chunk {i+1} failed: {e}")
            continue

    return all_sections, cumulative_topics

def show():
    st.markdown('<div class="main-content">', unsafe_allow_html=True)
    mini_hero("🎬 Lecture Studio", "Import, configure, and process your lecture")

    from utils.api_utils import api_ready
    if not api_ready():
        glass_card("🔑 API Key Required", "Set your AI provider API key in Workspace first.", icon="⚠️", highlight=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    user_id = _get_user_id()
    if not user_id:
        st.warning("Please login to process lectures.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ── Load existing topics if any ──
    video_id = st.session_state.get("video_id")
    if video_id and not st.session_state.get("sections_ready", False):
        topics = load_topics(video_id, user_id=user_id)
        if topics:
            st.session_state.pre_generated_sections = topics
            st.session_state.sections_ready = True

    # ── CARD 1: IMPORT ──
    st.markdown("""
    <div class="glass-card" style="padding: 1.5rem 2rem; margin-bottom: 1.5rem;">
        <h3 style="margin: 0 0 0.75rem 0; font-size: 1.1rem;">📥 Import Lecture</h3>
    </div>
    """, unsafe_allow_html=True)

    url_value = st.session_state.get("video_url", "")
    col_url, col_btn = st.columns([4, 1])
    with col_url:
        url = st.text_input(
            "YouTube URL",
            value=url_value,
            placeholder="https://www.youtube.com/watch?v=...",
            label_visibility="collapsed"
        )
    with col_btn:
        st.write("")  # vertical alignment
        st.write("")
        fetch_clicked = st.button("📥 Fetch", use_container_width=True, type="primary")

    if fetch_clicked:
        if not url:
            toast_error("Please enter a YouTube URL first.")
        else:
            loader = show_loading_overlay("🎧 Extracting transcript...")
            try:
                transcript = get_transcript(url)
                clear_loading(loader)
                if transcript:
                    toast_success(f"Transcript extracted ({len(transcript.split())} words)")
                    log_lecture(
                        video_id=st.session_state.video_id,
                        word_count=len(transcript.split()),
                        video_url=url,
                        title=st.session_state.get('video_title', 'Untitled Lecture'),
                        user_id=user_id
                    )
                    for key in ['notes_ready', 'summary_ready', 'quiz_ready', 'compressed_transcript',
                                'show_notes', 'show_summary', 'show_quiz', 'pre_generated_sections', 'sections_ready']:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
                else:
                    st.warning("⚠️ No subtitles found.")
                    st.info("Try the Whisper fallback below.")
                    if st.button("🎙️ Transcribe with AI (Whisper)"):
                        with st.spinner("Downloading audio and transcribing..."):
                            try:
                                audio_path = download_audio(url, output_dir="downloads")
                                result = transcribe_audio(audio_path, model_size="base")
                                whisper_text = result.get("text", "")
                                if whisper_text:
                                    video_id = extract_video_id(url)
                                    video_title = get_video_title(url)
                                    st.session_state.video_id = video_id
                                    st.session_state.video_url = url
                                    st.session_state.video_title = video_title
                                    st.session_state.transcript = whisper_text
                                    st.session_state.transcript_ready = True
                                    log_lecture(video_id, len(whisper_text.split()), url, video_title, user_id=user_id)
                                    toast_success(f"Whisper transcribed ({len(whisper_text.split())} words)")
                                    st.rerun()
                            except Exception as whisper_err:
                                toast_error(f"Whisper failed: {whisper_err}")
            except Exception as e:
                clear_loading(loader)
                if "No subtitles" in str(e):
                    st.warning("⚠️ No subtitles found.")
                    st.info("Try the Whisper fallback above.")
                else:
                    toast_error(f"Transcript failed: {e}")

    # ── CARD 2: CONFIGURE ──
    if st.session_state.get("transcript_ready", False):
        st.markdown("""
        <div class="glass-card" style="padding: 1.5rem 2rem; margin-bottom: 1.5rem;">
            <h3 style="margin: 0 0 0.75rem 0; font-size: 1.1rem;">⚙️ Configure Processing</h3>
        </div>
        """, unsafe_allow_html=True)

        full_transcript = st.session_state.transcript or ""
        words = full_transcript.split()
        total_words = len(words)

        # Two columns: Portion and Compression
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("**✂️ Transcript Portion**")
            portion = st.radio(
                "Select portion",
                ["Full Transcript", "Starting (first 1/3)", "Middle (middle 1/3)", "End (last 1/3)"],
                index=0,
                label_visibility="collapsed"
            )
            if portion == "Full Transcript":
                selected = full_transcript
            else:
                third = total_words // 3
                if "Starting" in portion:
                    selected = " ".join(words[:third])
                elif "Middle" in portion:
                    selected = " ".join(words[third:third * 2])
                else:
                    selected = " ".join(words[third * 2:])
            st.caption(f"📄 {len(selected.split()):,} words selected")

        with col_right:
            st.markdown("**🧠 Compression**")
            selected_words = len(selected.split())
            total_sentences = max(1, int(selected_words / 15))

            if selected_words <= 6000:
                best = 100
                label = "✅ Keep 100% for short sections"
            elif selected_words <= 24000:
                best = 70
                label = "💡 70% is the sweet spot"
            else:
                best = 50
                label = "⚠️ 50% prevents crashes & saves tokens"

            keep_percent = st.slider(
                "Detail level",
                min_value=10, max_value=100, value=best, step=5,
                label_visibility="collapsed"
            )
            st.caption(label)

            sentence_count = max(10, int(total_sentences * keep_percent / 100))
            summary_method = st.selectbox(
                "Compression engine",
                ["lsa", "lexrank"],
                format_func=lambda x: "Deep Concept (LSA)" if x == "lsa" else "Key Highlights (LexRank)",
                index=0 if DEFAULT_SUMMARY_METHOD == "lsa" else 1
            )

            with st.expander("⚙️ Advanced options"):
                auto_vector = st.checkbox("Build Vector DB (for AI Tutor)", value=True)
                generate_topics = st.checkbox("Generate structured topics", value=True, help="Speeds up Notes/Summary/Quiz")

        # ── Process button ──
        if st.button("🚀 Compress & Prepare", type="primary", use_container_width=True):
            if not selected.strip():
                toast_error("Selected portion is empty. Try a different portion.")
            else:
                loader = show_loading_overlay(f"🧠 Compressing transcript ({keep_percent}% of portion)...")
                try:
                    compressed = extractive_summary(selected, sentence_count, summary_method)
                    stats = get_summary_stats(selected, compressed)
                    st.session_state.transcript = selected
                    st.session_state.compressed_transcript = compressed
                    clear_loading(loader)
                    st.info(f"📊 {stats['original_words']:,} → {stats['compressed_words']:,} words ({stats['reduction_percent']}% reduction)")
                except Exception as e:
                    clear_loading(loader)
                    toast_error(f"Compression failed: {e}")
                    st.session_state.compressed_transcript = selected

                if auto_vector:
                    loader = show_loading_overlay("🧠 Building vector DB...")
                    try:
                        create_vector_store(selected)
                        clear_loading(loader)
                        toast_success("Vector DB built!")
                    except Exception as e:
                        clear_loading(loader)
                        toast_error(f"Vector DB failed: {e}")

                if generate_topics:
                    source_for_sections = st.session_state.get("compressed_transcript", st.session_state.transcript)
                    with st.status("Generating topics...", expanded=True) as status:
                        progress_bar = st.progress(0.0, text="Starting...")
                        status_text = st.empty()
                        try:
                            sections, total_found = pre_generate_sections(source_for_sections, status, progress_bar, status_text)
                            if sections:
                                st.session_state.pre_generated_sections = sections
                                st.session_state.sections_ready = True
                                if st.session_state.get('video_id'):
                                    save_topics(st.session_state.video_id, sections, user_id=user_id)
                                status_text.markdown(f"✅ Completed! Generated **{total_found}** topics.")
                                toast_success(f"Topics generated! ({len(sections)})")
                            else:
                                status_text.markdown("⚠️ No topics generated.")
                        except (CreditError, RateLimitError) as e:
                            status_text.markdown(f"❌ API error: {e}")
                            st.error(str(e))
                            st.markdown("### 💡 Switch to a Free Model")
                            from utils.api_utils import get_free_model_suggestions
                            for provider, model, desc in get_free_model_suggestions():
                                if st.button(f"🔄 {provider} – {model}"):
                                    st.session_state.provider = provider
                                    st.session_state.model = model
                                    st.session_state.client = None
                                    st.rerun()
                        except Exception as e:
                            status_text.markdown(f"❌ Error: {e}")
                            toast_error(f"Topic generation failed: {e}")
                        finally:
                            progress_bar.empty()
                            status_text.empty()

                st.balloons()
                st.success("✅ Lecture processed!")

    # ── CARD 3: STATUS ──
    if st.session_state.get("transcript_ready", False):
        st.markdown("""
        <div class="glass-card" style="padding: 1.5rem 2rem; margin-top: 1.5rem;">
            <h3 style="margin: 0 0 0.75rem 0; font-size: 1.1rem;">📊 Current Status</h3>
        </div>
        """, unsafe_allow_html=True)

        col_status1, col_status2 = st.columns(2)
        with col_status1:
            # ✅ Defensive check for transcript
            transcript = st.session_state.get("transcript")
            words_count = len(transcript.split()) if transcript else 0
            st.metric("📄 Words", f"{words_count:,}")

            compressed = st.session_state.get("compressed_transcript")
            if compressed:
                comp_words = len(compressed.split())
                st.metric("⚡ Compressed", f"{comp_words:,} words")

        with col_status2:
            if st.session_state.get("sections_ready", False):
                st.success(f"✅ Topics ready ({len(st.session_state.pre_generated_sections)})")
                if st.button("🗑️ Clear topics", use_container_width=True):
                    del st.session_state.pre_generated_sections
                    st.session_state.sections_ready = False
                    toast_success("Topics cleared.")
                    st.rerun()
            else:
                st.info("ℹ️ No topics generated yet.")

            if st.session_state.get("video_title"):
                st.caption(f"🎥 **{st.session_state.video_title}**")

    st.markdown('</div>', unsafe_allow_html=True)