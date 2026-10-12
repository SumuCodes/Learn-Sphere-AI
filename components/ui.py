import streamlit as st

# ==========================================================
# Dynamic Background
# ==========================================================

def inject_dynamic_background(video_ids: list):
    """
    Injects CSS for dynamic background:
    - 0 videos: gradient
    - 1–3 videos: grid using repeated thumbnails (collage effect)
    - 4+ videos: grid from unique thumbnails (up to 8)
    All tiles use background-size: cover to preserve aspect ratio.
    """
    # FIXED: Default now matches app.py ('default' instead of 'dark')
    theme = st.session_state.get('theme', 'default')
    unique_ids = list(dict.fromkeys(video_ids))
    recent_ids = unique_ids[-8:]  # max 8

    # ── Shared CSS: makes ALL Streamlit container layers transparent ──
    # This is the critical piece that stops the white background from showing.
    transparent_layers = """
        .stApp,
        [data-testid="stAppViewContainer"],
        section.main,
        .main {
            background: transparent !important;
        }
        [data-testid="stHeader"] {
            background: transparent !important;
        }
    """

    if not recent_ids:
        # Gradient background for 0 videos
        if theme == 'light':
            # LIGHT gradient
            css = f"""
            <style>
            .stApp,
            [data-testid="stAppViewContainer"],
            section.main,
            .main {{
                background: radial-gradient(circle at 50% -20%, #F3E5F5 0%, #E1BEE7 60%, #FFFFFF 100%) !important;
            }}
            [data-testid="stHeader"] {{
                background: transparent !important;
            }}
            .stApp::before {{
                content: "";
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background-image: radial-gradient(circle at 80% 50%, rgba(156, 39, 176, 0.05) 1px, transparent 1px);
                background-size: 20px 20px;
                z-index: 0;
                pointer-events: none;
            }}
            header, .main-content, section[data-testid="stSidebar"] {{
                z-index: 9999 !important;
                position: relative !important;
            }}
            </style>
            """
        else:
            # DEFAULT / DARK gradient
            css = f"""
            <style>
            .stApp,
            [data-testid="stAppViewContainer"],
            section.main,
            .main {{
                background: radial-gradient(circle at 50% -20%, #4A148C 0%, #1A0420 60%, #050505 100%) !important;
            }}
            [data-testid="stHeader"] {{
                background: transparent !important;
            }}
            .stApp::before {{
                content: "";
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background-image: radial-gradient(circle at 80% 50%, rgba(123, 31, 162, 0.15) 1px, transparent 1px);
                background-size: 20px 20px;
                z-index: 0;
                pointer-events: none;
            }}
            header, .main-content, section[data-testid="stSidebar"] {{
                z-index: 9999 !important;
                position: relative !important;
            }}
            </style>
            """
        st.markdown(css, unsafe_allow_html=True)
        return

    # ── Build thumbnail URLs ──
    urls = [f"https://img.youtube.com/vi/{vid}/hqdefault.jpg" for vid in recent_ids]

    # FIXED: Default theme now falls into the dark overlay branch
    overlay = "rgba(255, 255, 255, 0.75)" if theme == 'light' else "rgba(10, 10, 20, 0.75)"

    # ── Determine grid layout and tile sizes ──
    if len(urls) == 1:
        # Repeat the single thumbnail 4 times (2x2 grid)
        bg_images = ", ".join([f"url('{urls[0]}')"] * 4)
        positions = ["0% 0%", "100% 0%", "0% 100%", "100% 100%"]
        bg_positions = ", ".join(positions)
        tile_sizes = ", ".join(["cover"] * 4)
    elif len(urls) == 2:
        # Repeat each thumbnail twice (2x2 grid)
        bg_images = ", ".join([
            f"url('{urls[0]}')",
            f"url('{urls[1]}')",
            f"url('{urls[0]}')",
            f"url('{urls[1]}')"
        ])
        positions = ["0% 0%", "100% 0%", "0% 100%", "100% 100%"]
        bg_positions = ", ".join(positions)
        tile_sizes = ", ".join(["cover"] * 4)
    elif len(urls) == 3:
        # Place 3 images in a 2x2 grid, repeat the first to fill the 4th slot
        bg_images = ", ".join([
            f"url('{urls[0]}')",
            f"url('{urls[1]}')",
            f"url('{urls[2]}')",
            f"url('{urls[0]}')"
        ])
        positions = ["0% 0%", "100% 0%", "0% 100%", "100% 100%"]
        bg_positions = ", ".join(positions)
        tile_sizes = ", ".join(["cover"] * 4)
    else:
        # 4–8 images: unique grid
        bg_images = ", ".join([f"url('{u}')" for u in urls])
        if len(urls) <= 4:
            # 2x2 grid
            positions = ["0% 0%", "100% 0%", "0% 100%", "100% 100%"]
            tile_sizes = ", ".join(["cover"] * 4)
        else:
            # 4x2 grid (up to 8 images)
            positions = [
                "0% 0%", "33.33% 0%", "66.66% 0%", "100% 0%",
                "0% 33.33%", "33.33% 33.33%", "66.66% 33.33%", "100% 33.33%"
            ]
            tile_sizes = ", ".join(["cover"] * 8)
        bg_positions = ", ".join([positions[i] for i in range(len(urls))])

    # Build background-size: one "cover" for the gradient, and "cover" for each tile
    bg_size = f"cover, {tile_sizes}"

    # FIXED:
    #   - Added stAppViewContainer + section.main + .main for transparency
    #   - Added [data-testid="stHeader"] transparency
    #   - Changed #custom-bg z-index from 0 to -1
    #   - Removed fragile .st-emotion-cache-1g4en9s selector
    css = f"""
    <style>
    /* Make ALL Streamlit container layers transparent so #custom-bg shows through */
    .stApp,
    [data-testid="stAppViewContainer"],
    section.main,
    .main {{
        background: transparent !important;
    }}

    /* Top header defaults to white — make it transparent too */
    [data-testid="stHeader"] {{
        background: transparent !important;
    }}

    #custom-bg {{
        position: fixed;
        top: -5vh;
        left: -5vw;
        width: 110vw;
        height: 110vh;
        background-image: 
            linear-gradient({overlay}, {overlay}),
            {bg_images};
        background-size: {bg_size};
        background-repeat: no-repeat;
        background-position: center, {bg_positions};
        filter: blur(15px) brightness(0.8);
        transform: scale(1.1);
        z-index: -1;   /* Sits behind everything */
        pointer-events: none;
    }}

    header, .main-content, section[data-testid="stSidebar"] {{
        z-index: 9999 !important;
        position: relative !important;
    }}
    </style>
    <div id="custom-bg"></div>
    """
    st.markdown(css, unsafe_allow_html=True)


# ==========================================================
# Hero / Banners
# ==========================================================

def hero_banner(title, subtitle, icon="🎓"):
    """Large hero banner with premium gradient."""
    st.markdown(f"""
    <div class="hero-banner">
        <div class="icon">{icon}</div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def mini_hero(title: str, subtitle: str = ""):
    """Smaller hero for sub-pages."""
    st.markdown(f"""
    <div class="mini-hero">
        <h2>{title}</h2>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


# ==========================================================
# Cards
# ==========================================================

def glass_card(title: str, content: str = "", icon: str = None, highlight: bool = False):
    """Glassmorphism card with hover effect."""
    icon_html = f'<span class="icon">{icon}</span>' if icon else ""
    highlight_class = " highlight" if highlight else ""
    st.markdown(f"""
    <div class="glass-card{highlight_class}">
        <div class="card-header">
            {icon_html}
            <h3 class="card-title">{title}</h3>
        </div>
        <div class="card-content">{content}</div>
    </div>
    """, unsafe_allow_html=True)


def stat_card(value: str, label: str, icon: str = None, delta: str = None):
    """Metric/stat card with large number."""
    icon_html = f'<div class="stat-icon">{icon}</div>' if icon else ""
    delta_html = f'<div class="stat-delta">{delta}</div>' if delta else ""
    st.markdown(f"""
    <div class="stat-card">
        {icon_html}
        <div class="stat-number">{value}</div>
        <div class="stat-label">{label}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def info_card(title: str, content: str, icon: str = "ℹ️"):
    """Info card with icon."""
    st.markdown(f"""
    <div class="info-card">
        <span class="icon">{icon}</span>
        <div>
            <div class="title">{title}</div>
            <div class="content">{content}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ==========================================================
# Buttons
# ==========================================================

def primary_button(label: str, key: str = None, use_container_width: bool = True):
    """Purple gradient button (styled via CSS)."""
    return st.button(label, key=key, type="primary", use_container_width=use_container_width)


# ==========================================================
# Quiz / Progress
# ==========================================================

def quiz_progress(current: int, total: int):
    """Progress bar for quiz."""
    percentage = int((current / total) * 100) if total > 0 else 0
    st.markdown(f"""
    <div class="quiz-progress-wrapper">
        <div class="quiz-progress-labels">
            <span>Question {current} of {total}</span>
            <span>{percentage}%</span>
        </div>
        <div class="quiz-progress-bar">
            <div class="quiz-progress-fill" style="width: {percentage}%;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ==========================================================
# Divider
# ==========================================================

def divider():
    """Custom purple gradient divider."""
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)


def mini_divider():
    """Smaller divider for inside sections."""
    st.markdown('<div class="mini-divider"></div>', unsafe_allow_html=True)


# ==========================================================
# Toast / Alert
# ==========================================================

def toast_success(message: str):
    st.markdown(f'<div class="toast-success">✅ {message}</div>', unsafe_allow_html=True)


def toast_error(message: str):
    st.markdown(f'<div class="toast-error">❌ {message}</div>', unsafe_allow_html=True)


def toast_info(message: str):
    st.markdown(f'<div class="toast-info">ℹ️ {message}</div>', unsafe_allow_html=True)


# ==========================================================
# Badge / Tags
# ==========================================================

def difficulty_badge(level: str):
    """Difficulty badge for quiz questions."""
    level_map = {
        "Easy": "easy",
        "Medium": "medium",
        "Hard": "hard",
        "Mixed": "mixed"
    }
    badge_class = level_map.get(level, "mixed")
    st.markdown(f'<span class="badge-{badge_class}">{level}</span>', unsafe_allow_html=True)


# ==========================================================
# Friendly Error Helper
# ==========================================================

def friendly_error(e: Exception = None, custom_msg: str = None):
    """Replaces scary API JSON errors with a clean, user-friendly message."""
    if custom_msg:
        st.error(custom_msg)
        return
    err_str = str(e).lower()
    if "rate_limit" in err_str or "429" in err_str or "413" in err_str or "too large" in err_str:
        st.error(
            "⚠️ **Lecture Too Large for Free Tier**\n\n"
            "The AI provider's free tier limit was reached. To fix this:\n"
            "- Use **Smart Mode** if available.\n"
            "- Go back to **Lecture Studio** and lower the compression slider.\n"
            "- Or switch to a different AI Provider in the sidebar."
        )
    else:
        short_msg = str(e).split('\n')[0]
        st.error(f"⚠️ An AI error occurred: {short_msg}")