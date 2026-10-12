# app_pages/home.py
import streamlit as st
from components.ui import inject_dynamic_background
from utils.performance import get_analytics_data
from utils.topics import get_lecture_content, load_topics
from utils.api_utils import api_ready
from components.api_key_prompt import show_api_key_prompt


def _get_user_id():
    return st.session_state.get("user_id", "")


def load_lecture_from_db(video_id: str, url: str, title: str, user_id: str):
    """Load the lecture into session and navigate to appropriate page."""
    content = get_lecture_content(video_id, user_id=user_id)
    if not content:
        st.toast("No data found for this lecture.", icon="⚠️")
        return

    st.session_state.video_id = video_id
    st.session_state.video_url = url
    st.session_state.video_title = title
    st.session_state.transcript = content.get('transcript', '')
    st.session_state.transcript_ready = bool(st.session_state.transcript)
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

    # Navigate to the most appropriate page
    if saved_notes:
        st.session_state.current_page = "Study Notes"
    elif saved_summary:
        st.session_state.current_page = "Quick Revision"
    else:
        st.session_state.current_page = "Lecture Studio"
    st.rerun()


def _calculate_progress(stats: dict, user_id: str):
    """Compute progress percentage and message for the most recent lecture."""
    df = stats.get("lectures_df")
    if df is None or df.empty:
        return 0, "No lectures yet. Start by analyzing a video!"
    latest = df.iloc[-1]
    vid = latest.get("video_id")
    if not vid:
        return 0, "No lecture data."
    content = get_lecture_content(vid, user_id=user_id)
    total = 0
    completed = 0
    # Check for notes
    if content.get("notes"):
        total += 1
        completed += 1
    else:
        total += 1
    # Check for summary
    if content.get("summary"):
        total += 1
        completed += 1
    else:
        total += 1
    # Check for quiz attempts (at least one)
    quiz_df = stats.get("quiz_df")
    if quiz_df is not None and not quiz_df.empty:
        total += 1
        if any(quiz_df["video_id"] == vid):
            completed += 1
    else:
        total += 1

    percent = int((completed / total) * 100) if total > 0 else 0
    if percent >= 100:
        msg = "🎉 Complete! Try a quiz or new lecture."
    elif percent >= 50:
        msg = "Great progress! Keep going."
    else:
        msg = "Start generating notes or summary."
    return percent, msg


def show():
    user_id = _get_user_id()
    # Get analytics data
    if st.session_state.get('logged_in', False) and user_id:
        stats = get_analytics_data(user_id=user_id)
        video_ids = stats["lectures_df"]["video_id"].tolist() if not stats["lectures_df"].empty else []
    else:
        video_ids = []
        stats = {
            "total_lectures": 0,
            "total_quizzes": 0,
            "avg_score": 0,
            "total_words": 0,
            "lectures_today": 0,
            "lectures_df": None,
            "quiz_df": None,
            "all_lectures": None,
            "all_quizzes": None,
        }

    # ── Conditional dynamic background ──
    if st.session_state.get("use_collage", True):
        inject_dynamic_background(video_ids)

    st.markdown('<div class="main-content">', unsafe_allow_html=True)

    # ── If not logged in ──
    if not st.session_state.get('logged_in', False):
        st.markdown("""
        <div class="dashboard-hero" style="text-align:center;">
            <div class="dashboard-hero-left" style="flex:1;">
                <h1>🌐 Learn Sphere AI</h1>
                <p>Your intelligent learning companion. Transform lectures into knowledge.</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔑 Go to Login", use_container_width=True, type="primary"):
                st.session_state.current_page = "Login"
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    if not user_id:
        st.warning("Please re-login to continue.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ── API Key popup ──
    if not api_ready() and not st.session_state.get('api_prompt_dismissed', False):
        show_api_key_prompt()

    username = st.session_state.get('username', 'Learner')
    today = st.session_state.get("lectures_today", 0) or stats.get("lectures_today", 0)
    total_lectures = stats.get("total_lectures", 0)

    # ── 1. HERO (using Streamlit columns for layout) ──
    # We'll use two columns: left for welcome, right for stats + button.
    hero_left, hero_right = st.columns([2, 1], gap="large")

    with hero_left:
        st.markdown(f"""
        <div>
            <h1 style="font-size: 1.75rem; font-weight: 700; margin: 0 0 0.25rem 0; color: var(--text);">
                👋 Welcome back, {username}
            </h1>
            <p style="color: var(--text-muted); font-size: 1rem; margin: 0 0 0.75rem 0;">
                Continue your learning journey or start a new lecture.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with hero_right:
        st.markdown(f"""
        <div style="display: flex; flex-direction: column; gap: 0.75rem; align-items: flex-end;">
            <div style="display: flex; gap: 0.75rem; flex-wrap: wrap; justify-content: flex-end;">
                <span class="stat-badge">📚 <strong>{total_lectures}</strong> total</span>
                <span class="stat-badge">📅 <strong>{today}</strong> today</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        # The button goes here, inside the right column, below the stats
        if st.button("🎬 Analyze New Lecture", use_container_width=True, type="primary"):
            st.session_state.current_page = "Lecture Studio"
            st.rerun()

    # ── 2. CONTINUE LEARNING ──
    lectures_df = stats.get("lectures_df")
    if lectures_df is not None and not lectures_df.empty:
        latest = lectures_df.sort_values(by="timestamp", ascending=False).iloc[0]
        video_id = latest.get("video_id")
        title = latest.get("title") or "Untitled Lecture"
        url = latest.get("video_url") or f"https://www.youtube.com/watch?v={video_id}"
        progress_pct, progress_msg = _calculate_progress(stats, user_id)

        st.markdown(f"""
        <div class="dashboard-continue">
            <div class="title">📚 Continue Learning</div>
            <div class="lecture-name">{title}</div>
            <div class="progress-wrapper">
                <div class="progress-bar">
                    <div class="fill" style="width:{progress_pct}%;"></div>
                </div>
                <div class="progress-label">{progress_pct}%</div>
            </div>
            <div class="action-row">
                <span style="color: var(--text-muted); font-size:0.9rem;">{progress_msg}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("▶ Continue where you left off", key="continue_btn", use_container_width=False):
            load_lecture_from_db(video_id, url, title, user_id)
    else:
        st.markdown("""
        <div class="dashboard-continue">
            <div class="title">📚 Continue Learning</div>
            <p style="color: var(--text-muted);">No lectures yet. Analyze your first YouTube lecture to get started.</p>
        </div>
        """, unsafe_allow_html=True)

    # ── 3. OVERVIEW STATS ──
    total_quizzes = stats.get("total_quizzes", 0)
    avg_score = stats.get("avg_score", 0)
    total_words = stats.get("total_words", 0)

    st.markdown("""
    <div class="dashboard-stats">
        <div class="stat-item">
            <div class="number">{}</div>
            <div class="label">Lectures</div>
        </div>
        <div class="stat-item">
            <div class="number">{}</div>
            <div class="label">Quizzes</div>
        </div>
        <div class="stat-item">
            <div class="number">{}</div>
            <div class="label">Avg Score</div>
        </div>
        <div class="stat-item">
            <div class="number">{}</div>
            <div class="label">Words</div>
        </div>
    </div>
    """.format(total_lectures, total_quizzes, f"{avg_score:.0f}%" if avg_score > 0 else "N/A", f"{total_words:,}"), unsafe_allow_html=True)

    # ── 4. TWO-COLUMN: Recent Activity + Quick Actions ──
    recent_lectures = []
    if lectures_df is not None and not lectures_df.empty:
        df = lectures_df.sort_values(by="timestamp", ascending=False).head(5)
        for _, row in df.iterrows():
            recent_lectures.append({
                "title": row.get("title", "Untitled"),
                "date": row.get("timestamp", "").split()[0] if isinstance(row.get("timestamp"), str) else "",
                "words": row.get("word_count", 0),
                "video_id": row.get("video_id"),
                "url": row.get("video_url") or f"https://www.youtube.com/watch?v={row.get('video_id')}"
            })

    st.markdown("""
    <div class="dashboard-grid">
        <div class="card">
            <h3>📜 Recent Activity</h3>
            <ul class="activity-list">
    """, unsafe_allow_html=True)

    if not recent_lectures:
        st.markdown('<li style="color: var(--text-muted);">No recent activity.</li>', unsafe_allow_html=True)
    else:
        for item in recent_lectures:
            date_str = item['date'] or "Just now"
            words_str = f"{item['words']:,} words" if item['words'] else ""
            st.markdown(f"""
            <li>
                <span class="activity-title">{item['title'][:40]}</span>
                <span>
                    <span class="activity-words">{words_str}</span>
                    <span class="activity-date">{date_str}</span>
                </span>
            </li>
            """, unsafe_allow_html=True)
    st.markdown('</ul></div>', unsafe_allow_html=True)

    # Quick Actions
    st.markdown("""
    <div class="card">
        <h3>⚡ Quick Actions</h3>
        <div class="quick-actions">
    """, unsafe_allow_html=True)

    # Close card and grid
    st.markdown('</div></div>', unsafe_allow_html=True)

    # Quick Actions buttons (using columns)
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🧠 Smart Quiz", use_container_width=True):
            st.session_state.current_page = "Smart Quiz"
            st.rerun()
    with col2:
        if st.button("📚 Study Notes", use_container_width=True):
            st.session_state.current_page = "Study Notes"
            st.rerun()
    with col3:
        if st.button("🤖 AI Tutor", use_container_width=True):
            st.session_state.current_page = "AI Tutor"
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)