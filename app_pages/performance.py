# app_pages/performance.py
"""
Learning Analytics – Student Report Card.
Premium SaaS-style visualizations with custom Plotly themes and glassmorphism.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from utils.performance import get_analytics_data
from components.ui import mini_hero, glass_card, divider, stat_card


def _get_user_id() -> str:
    return st.session_state.get("user_id", "")


def show():
    st.markdown('<div class="main-content">', unsafe_allow_html=True)
    mini_hero("📈 Learning Analytics", "Track your learning journey and achievements")

    if not st.session_state.get('logged_in', False):
        st.info("🔐 Please login to view your report card.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    user_id = _get_user_id()
    if not user_id:
        st.warning("User ID not found. Please log in again.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ── Get analytics data ──
    data = get_analytics_data(user_id=user_id)

    # Check if any data exists
    if not data or (data.get('all_lectures') is not None and data['all_lectures'].empty and
                    data.get('all_quizzes') is not None and data['all_quizzes'].empty):
        glass_card("📭 No Data Yet", "Start processing lectures and taking quizzes to see your report card!", icon="📊", highlight=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    lec_4w = data.get('lec_4w', pd.DataFrame())
    quiz_4w = data.get('quiz_4w', pd.DataFrame())
    all_lectures = data.get('all_lectures', pd.DataFrame())
    all_quizzes = data.get('all_quizzes', pd.DataFrame())

    theme = st.session_state.get('theme', 'dark')
    plotly_text_color = "#A0A0A0" if theme == 'dark' else "#555"
    plotly_grid_color = "rgba(255,255,255,0.05)" if theme == 'dark' else "rgba(0,0,0,0.05)"

    # ── 1. Current Month Metrics ──
    st.markdown("### 📅 Current Month (Last 4 Weeks)")

    all_dates = []
    if not lec_4w.empty:
        all_dates.extend(lec_4w['date'].tolist())
    if not quiz_4w.empty:
        all_dates.extend(quiz_4w['date'].tolist())
    active_days = len(set(all_dates))
    videos_studied = len(lec_4w)
    avg_score = int(quiz_4w['score'].mean()) if not quiz_4w.empty else 0
    words_processed = lec_4w['word_count'].sum() if not lec_4w.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        stat_card(f"{active_days}/28", "Active Days", "📅")
    with col2:
        stat_card(f"{videos_studied}", "Videos Studied", "🎬")
    with col3:
        stat_card(f"{avg_score}%", "Avg Quiz Score", "🏆")
    with col4:
        stat_card(f"{words_processed:,}", "Words Processed", "📝")

    divider()

    # ── 2. Interactive Performance Trends ──
    st.markdown("### 📊 Performance Trends")
    time_range = st.radio("Select Time Range", ["Last 4 Weeks", "This Year"], horizontal=True, label_visibility="collapsed")

    if time_range == "Last 4 Weeks":
        plot_lec = lec_4w.copy()
        plot_quiz = quiz_4w.copy()
    else:
        start_of_year = datetime(datetime.now().year, 1, 1).date()
        plot_lec = all_lectures[all_lectures['date'] >= start_of_year].copy() if not all_lectures.empty else pd.DataFrame()
        plot_quiz = all_quizzes[all_quizzes['date'] >= start_of_year].copy() if not all_quizzes.empty else pd.DataFrame()

    if not plot_lec.empty:
        plot_lec['count'] = 1
        lec_by_day = plot_lec.groupby('date')['count'].sum().reset_index()
        lec_by_day['date'] = pd.to_datetime(lec_by_day['date'])
    else:
        lec_by_day = pd.DataFrame(columns=['date', 'count'])

    if not plot_quiz.empty:
        quiz_by_day = plot_quiz.groupby('date')['score'].mean().reset_index()
        quiz_by_day['date'] = pd.to_datetime(quiz_by_day['date'])
    else:
        quiz_by_day = pd.DataFrame(columns=['date', 'score'])

    def apply_custom_layout(fig):
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color=plotly_text_color, family="Inter, sans-serif", size=12),
            margin=dict(l=10, r=10, t=10, b=10),
            height=280,
            xaxis=dict(showgrid=False, linecolor=plotly_grid_color),
            yaxis=dict(showgrid=True, gridcolor=plotly_grid_color, linecolor=plotly_grid_color, zeroline=False),
            hoverlabel=dict(
                bgcolor="rgba(15,15,20,0.9)" if theme == 'dark' else "rgba(255,255,255,0.9)",
                font_size=12,
                font_color="#fff" if theme == 'dark' else "#333"
            )
        )
        return fig

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown('<div class="performance-card"><h4>🎬 Lecture Activity</h4>', unsafe_allow_html=True)
        if not lec_by_day.empty:
            fig_lec = px.bar(
                lec_by_day,
                x='date',
                y='count',
                labels={'date': '', 'count': 'Lectures'},
                color_discrete_sequence=['#7C3AED'],
                template='plotly_dark' if theme == 'dark' else 'plotly_white'
            )
            fig_lec.update_traces(marker_line_width=0, width=0.5 * 24 * 60 * 60 * 1000)
            fig_lec = apply_custom_layout(fig_lec)
            st.plotly_chart(fig_lec, use_container_width=True)
        else:
            st.info("No lecture data for this period.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_chart2:
        st.markdown('<div class="performance-card"><h4>🧠 Quiz Score Trend</h4>', unsafe_allow_html=True)
        if not quiz_by_day.empty:
            fig_quiz = px.line(
                quiz_by_day,
                x='date',
                y='score',
                labels={'date': '', 'score': 'Score (%)'},
                color_discrete_sequence=['#A78BFA'],
                line_shape='spline',
                template='plotly_dark' if theme == 'dark' else 'plotly_white'
            )
            fig_quiz.update_traces(mode='lines+markers', line_width=3, marker_size=8)
            fig_quiz.update_layout(yaxis_range=[0, 100])
            fig_quiz = apply_custom_layout(fig_quiz)
            st.plotly_chart(fig_quiz, use_container_width=True)
        else:
            st.info("No quiz data for this period.")
        st.markdown('</div>', unsafe_allow_html=True)

    divider()

    # ── 3. Hall of Fame ──
    st.markdown("### 🏅 Hall of Fame")
    top_score = data.get('top_score_video')
    top_words = data.get('top_word_video')

    col_hof1, col_hof2 = st.columns(2)

    with col_hof1:
        if top_score:
            title = top_score.get('title') or "Untitled Lecture"
            st.markdown(f"""
            <div class="hall-of-fame-item score">
                <div class="icon">🥇</div>
                <div class="label">Highest Scoring Video</div>
                <div class="title">{title}</div>
                <div class="value">{top_score['score']}%</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            glass_card("Take a quiz to see your highest scoring video!", "", icon="🥇")

    with col_hof2:
        if top_words:
            title = top_words.get('title') or "Untitled Lecture"
            st.markdown(f"""
            <div class="hall-of-fame-item words">
                <div class="icon">📚</div>
                <div class="label">Most Studied Video</div>
                <div class="title">{title}</div>
                <div class="value">{top_words['word_count']:,} Words</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            glass_card("Process a lecture to see your most studied video!", "", icon="📚")

    divider()

    # ── 4. Monthly History ──
    st.markdown("### 📚 Monthly History Archive")
    monthly_summary = data.get('monthly_summary', pd.DataFrame())

    if not monthly_summary.empty:
        monthly_summary['month'] = monthly_summary['month'].apply(lambda m: datetime.strptime(m, "%Y-%m").strftime("%B %Y"))
        monthly_summary.columns = ['Month', 'Lectures Studied', 'Words Processed']
        st.markdown('<div class="performance-card">', unsafe_allow_html=True)
        st.dataframe(
            monthly_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Lectures Studied": st.column_config.ProgressColumn(
                    "Lectures Studied",
                    help="Number of lectures processed that month",
                    format="%d",
                    min_value=0,
                    max_value=int(monthly_summary['Lectures Studied'].max()) + 1
                )
            }
        )
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Records older than 4 weeks will appear here as a monthly summary. Keep studying to build your history!")

    st.markdown('</div>', unsafe_allow_html=True)