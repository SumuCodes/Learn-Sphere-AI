# app.py
import streamlit as st
import os
import logging

# ── Set page config FIRST ──
from config import APP_SETTINGS

st.set_page_config(
    page_title=APP_SETTINGS["title"],
    page_icon=APP_SETTINGS["icon"],
    layout=APP_SETTINGS["layout"],
    initial_sidebar_state=APP_SETTINGS["sidebar_state"],
)

# ── Now safe to import the rest ──
from utils.session import init_session
from utils.auth import init_db
from components.sidebar import render_sidebar
from components.floating_tutor import render_floating_tutor
from utils.navigation import navigate_to_page

logger = logging.getLogger(__name__)

# ── Initialize DB (once) ──
if 'db_initialized' not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

# ── Initialize Session ──
init_session()

# ── Load CSS (cached) ──
@st.cache_data
def load_css():
    css = ""
    for file in ["base.css", "components.css", "pages.css"]:  # ⚠️ Confirm filenames
        path = os.path.join("styles", file)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                css += f.read() + "\n"
    return css

css = load_css()
if css:
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# ── Theme Variables ──
theme = st.session_state.get('theme', 'default')

if theme == 'light':
    st.markdown("""
    <style>
    :root {
        --bg: #F8F9FC !important;
        --surface: #FFFFFF !important;
        --surface-elevated: #F1F3F9 !important;
        --surface-glass: rgba(255, 255, 255, 0.6) !important;
        --border: rgba(0, 0, 0, 0.10) !important;
        --border-hover: rgba(124, 58, 237, 0.3) !important;
        --text: #1A1A1A !important;
        --text-muted: #5A5A66 !important;
        --text-light: #333333 !important;
        --primary-text: #6D28D9 !important;
        --shadow: 0 8px 24px rgba(0, 0, 0, 0.06) !important;
        --shadow-hover: 0 16px 40px rgba(0, 0, 0, 0.10), 0 0 20px rgba(124, 58, 237, 0.04) !important;
        --glass-bg: rgba(255, 255, 255, 0.6) !important;
        --glass-border: rgba(0, 0, 0, 0.08) !important;
    }

    /* FIX: Force all sidebar text to be dark in light mode */
    section[data-testid="stSidebar"] {
        color: #1A1A1A !important;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] h4,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] .stMarkdown * {
        color: #1A1A1A !important;
    }

    /* Keep the ACTIVE sidebar item purple so it stands out */
    section[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"],
    section[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] * {
        color: #6D28D9 !important;
    }

    /* Streamlit buttons keep white text on their purple background */
    section[data-testid="stSidebar"] .stButton > button,
    section[data-testid="stSidebar"] .stButton > button * {
        color: #FFFFFF !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ── Sidebar & Router ──
render_sidebar()

try:
    navigate_to_page()
except Exception as e:
    logger.exception("Navigation failed")
    st.error("Something went wrong loading this page.")
    with st.expander("Technical details"):
        st.exception(e)

# ── Floating AI Tutor ──
try:
    render_floating_tutor()
except Exception as e:
    logger.exception("Floating tutor failed")
    st.caption("AI Tutor is currently unavailable.")