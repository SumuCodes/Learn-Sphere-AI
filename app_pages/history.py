# app_pages/history.py
import streamlit as st
import html
import datetime
from utils.performance import get_all_lectures, delete_lecture_data, update_lecture_title
from utils.topics import get_lecture_content, load_topics
from utils.transcript import get_transcript
from utils.vector_store import delete_document
from components.ui import mini_hero, glass_card, toast_success, toast_error


def load_lecture_into_session(video_id: str, target_page: str):
    """Load saved content into session and navigate."""
    user_id = st.session_state.get("user_id", None)
    content = get_lecture_content(video_id, user_id=user_id)
    if not content:
        toast_error("No data found for this lecture.")
        return

    st.session_state.video_id = video_id
    st.session_state.video_url = f"https://www.youtube.com/watch?v={video_id}"
    st.session_state.video_title = content.get('title', 'Untitled Lecture')
    st.session_state.transcript_ready = True

    st.session_state.transcript = content.get('transcript', '')
    st.session_state.compressed_transcript = content.get('compressed_transcript', '')

    saved_notes = content.get('notes', '')
    st.session_state.notes = saved_notes
    st.session_state.notes_ready = bool(saved_notes)
    st.session_state.show_notes = bool(saved_notes)

    saved_summary = content.get('summary', '')
    st.session_state.summary = saved_summary
    st.session_state.summary_ready = bool(saved_summary)
    st.session_state.show_summary = bool(saved_summary)

    topics = load_topics(video_id, user_id=user_id)
    if topics:
        st.session_state.pre_generated_sections = topics
        st.session_state.sections_ready = True
    else:
        st.session_state.sections_ready = False
        st.session_state.pre_generated_sections = []

    st.session_state.current_page = target_page
    st.rerun()


def show():
    st.markdown('<div class="main-content">', unsafe_allow_html=True)
    mini_hero("📚 Learning Library", "Your past learning sessions all in one place")

    if not st.session_state.get('logged_in', False):
        st.info("🔐 Please login to view your lecture history.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    user_id = st.session_state.get("user_id", None)
    lectures = get_all_lectures(user_id=user_id)

    if not lectures:
        glass_card("🎬 No History Yet", "Once you process a YouTube lecture, it will appear here!", icon="📁", highlight=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Deduplicate
    seen = set()
    unique = []
    for lec in lectures:
        vid = lec.get('video_id')
        if vid and vid not in seen:
            unique.append(lec)
            seen.add(vid)
    lectures = unique

    theme = st.session_state.get('theme', 'dark')

    # Filters
    col1, col2 = st.columns([1, 3])
    with col1:
        sort_filter = st.selectbox("Sort by", ["Recent", "Highest Score", "Most Revised"], label_visibility="collapsed", key="history_sort")
    with col2:
        search_query = st.text_input("🔍 Search your lectures...", placeholder="Type a title or keyword", label_visibility="collapsed")

    # Sorting
    if sort_filter == "Highest Score":
        lectures.sort(key=lambda x: x.get('highest_score') or 0, reverse=True)
    elif sort_filter == "Most Revised":
        lectures.sort(key=lambda x: x.get('word_count') or 0, reverse=True)
    else:
        lectures.sort(key=lambda x: x.get('timestamp') or '', reverse=True)

    if search_query:
        q = search_query.lower()
        lectures = [l for l in lectures if q in str(l.get('video_url', '')).lower() or q in str(l.get('video_id', '')).lower() or q in str(l.get('title', '')).lower()]

    st.write(f"Showing **{len(lectures)}** lecture(s).")
    cols = st.columns(3)

    for idx, lec in enumerate(lectures):
        video_id = lec.get('video_id')
        if not video_id:
            continue

        key_suffix = f"{idx}_{video_id}"
        url = lec.get('video_url') or f"https://www.youtube.com/watch?v={video_id}"
        words = lec.get('word_count') or 0
        date_str = lec.get('timestamp') or 'Unknown date'
        raw_title = lec.get('title') or "Untitled Lecture"
        title = html.escape(raw_title)

        try:
            dt = datetime.datetime.strptime(date_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
            formatted_date = dt.strftime('%b %d, %Y')
        except:
            formatted_date = date_str

        score = lec.get('highest_score')
        score_color = "#00C853" if score and score >= 80 else "#FF8F00" if score and score >= 50 else "#FF1744"

        progress_points = 0
        if lec.get('has_notes'): progress_points += 1
        if lec.get('has_summary'): progress_points += 1
        if score is not None: progress_points += 1
        progress_percent = int((progress_points / 3) * 100)

        thumb_url = f"https://img.youtube.com/vi/{video_id}/0.jpg"

        with cols[idx % 3]:
            is_renaming = st.session_state.get(f"renaming_{key_suffix}", False)

            # ── Card ──
            st.markdown(f"""
            <div class="history-card">
                <div class="history-card-thumbnail">
                    <img src="{thumb_url}" alt="Thumbnail" />
                </div>
                <div class="history-card-body">
                    <div class="history-card-title">{title}</div>
                    <div class="history-card-progress">
                        <div class="history-card-progress-fill" style="width:{progress_percent}%;"></div>
                    </div>
                    <div class="history-card-meta">📅 {formatted_date} • 📝 {words:,} words</div>
                    <div class="history-card-score" style="color:{score_color};">{'🏆 Highest Score: ' + str(score) + '%' if score is not None else '🏆 Not taken yet'}</div>
                </div>
                <div class="history-card-footer">
            """, unsafe_allow_html=True)

            if is_renaming:
                new_title = st.text_input("New Title", value=title, key=f"input_{key_suffix}", label_visibility="collapsed")
                rc1, rc2 = st.columns(2)
                with rc1:
                    if st.button("💾 Save", key=f"save_{key_suffix}", use_container_width=True):
                        if new_title.strip():
                            update_lecture_title(video_id, new_title.strip(), user_id=user_id)
                            del st.session_state[f"renaming_{key_suffix}"]
                            toast_success("Title updated!")
                            st.rerun()
                        else:
                            toast_error("Title cannot be empty!")
                with rc2:
                    if st.button("❌ Cancel", key=f"cancel_{key_suffix}", use_container_width=True):
                        del st.session_state[f"renaming_{key_suffix}"]
                        st.rerun()
            else:
                foot_col1, foot_col2 = st.columns([4, 1])
                with foot_col1:
                    if st.button("▶ Open", key=f"open_{key_suffix}", use_container_width=True):
                        load_lecture_into_session(video_id, "Lecture Studio")
                with foot_col2:
                    with st.popover("⋮", use_container_width=True):
                        st.markdown("#### 🔧 Actions")
                        if st.button("✏️ Rename", key=f"rename_{key_suffix}", use_container_width=True):
                            st.session_state[f"renaming_{key_suffix}"] = True
                            st.rerun()
                        if st.button("🗑️ Delete", key=f"delete_{key_suffix}", use_container_width=True):
                            delete_lecture_data(video_id, user_id=user_id)
                            delete_document(video_id)
                            toast_success("Lecture deleted!")
                            st.rerun()
                        st.divider()
                        st.markdown("#### 📚 Quick Access")
                        if st.button("📝 Notes", key=f"notes_{key_suffix}", use_container_width=True):
                            load_lecture_into_session(video_id, "Study Notes")
                        if st.button("📖 Summary", key=f"summary_{key_suffix}", use_container_width=True):
                            load_lecture_into_session(video_id, "Quick Revision")
                        if st.button("🧠 Quiz", key=f"quiz_{key_suffix}", use_container_width=True):
                            load_lecture_into_session(video_id, "Smart Quiz")

            st.markdown('</div></div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)