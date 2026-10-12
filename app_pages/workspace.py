# app_pages/workspace.py
"""
Workspace Page – Dual API keys, system status, session management.
Primary (Gemini) for heavy tasks + Safety Net (Groq) for quick tasks & auto-fallback.
"""
import streamlit as st
from utils.api_utils import (
    save_api_settings, save_fallback_settings, get_api_key,
    get_models, api_ready, fallback_ready, create_client,
    validate_api_key
)
from utils.auth import update_user_theme  # <-- added for theme persistence
from config import SUPPORTED_PROVIDERS
from components.ui import mini_hero, divider, toast_success, toast_error


def show():
    st.markdown('<div class="main-content">', unsafe_allow_html=True)
    mini_hero("⚙️ Workspace", "Manage your AI engine, API connections, and session data.")

    if not st.session_state.get('logged_in', False):
        st.info("🔐 Please login to access workspace settings.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ==========================================================
    # 1. PRIMARY ENGINE (Gemini — for Summary, Notes, Quiz)
    # ==========================================================
    st.markdown("### 🧠 Primary Engine")
    st.caption("Used for heavy tasks: Summary, Notes, Quiz generation")

    provider_names = list(SUPPORTED_PROVIDERS.keys())
    p_idx = provider_names.index(st.session_state.provider) if st.session_state.provider in provider_names else 0

    col1, col2 = st.columns(2)
    with col1:
        p_provider = st.selectbox(
            "Provider", provider_names, index=p_idx,
            key="ws_primary_provider"
        )
    with col2:
        p_models = get_models(p_provider)
        p_model_idx = p_models.index(st.session_state.model) if st.session_state.model in p_models else 0
        p_model = st.selectbox(
            "Model", p_models, index=p_model_idx,
            key="ws_primary_model"
        )

    p_key = st.text_input(
        f"🔑 {p_provider} API Key",
        value=get_api_key(p_provider),
        type="password",
        placeholder="Enter API key...",
        key="ws_primary_key"
    )

    if st.button("💾 Save Primary Engine", type="primary", use_container_width=True):
        if not p_key.strip():
            toast_error("Please enter an API key.")
        else:
            is_valid, err_msg = validate_api_key(p_provider, p_key)
            if is_valid:
                save_api_settings(p_provider, p_model, p_key)
                try:
                    st.session_state.client = create_client(p_provider)
                    toast_success(f"✅ Primary: {p_provider} ({p_model}) saved!")
                except Exception as e:
                    toast_error(f"Failed to create client: {e}")
            else:
                toast_error(f"❌ {err_msg}")

    divider()

    # ==========================================================
    # 2. SAFETY NET (Groq — for AI Tutor, Quiz + auto-fallback)
    # ==========================================================
    st.markdown("### ⚡ Safety Net Engine")
    st.caption("Used for AI Tutor chat + auto-switches when Primary hits rate limit")

    fb_options = ["None"] + [p for p in provider_names if p != p_provider]
    current_fb = st.session_state.get("fallback_provider", "")
    fb_idx = fb_options.index(current_fb) if current_fb in fb_options else 0

    fb_provider = st.selectbox(
        "Safety Net Provider", fb_options, index=fb_idx,
        key="ws_fallback_provider"
    )

    if fb_provider != "None":
        fb_models = get_models(fb_provider)
        fb_model_default = st.session_state.get("fallback_model", "")
        fb_model_idx = fb_models.index(fb_model_default) if fb_model_default in fb_models else 0
        fb_model = st.selectbox(
            "Safety Net Model", fb_models, index=fb_model_idx,
            key="ws_fallback_model"
        )

        fb_key = st.text_input(
            f"🔑 {fb_provider} API Key",
            value=get_api_key(fb_provider),
            type="password",
            placeholder="Enter safety net API key...",
            key="ws_fallback_key"
        )

        if st.button("💾 Save Safety Net", type="primary", use_container_width=True):
            if not fb_key.strip():
                toast_error("Please enter the safety net API key.")
            else:
                is_valid, err_msg = validate_api_key(fb_provider, fb_key)
                if is_valid:
                    st.session_state.api_keys[fb_provider] = fb_key
                    save_fallback_settings(fb_provider, fb_model)
                    toast_success(f"✅ Safety Net: {fb_provider} ({fb_model}) saved!")
                else:
                    toast_error(f"❌ {err_msg}")

        if get_api_key(fb_provider):
            st.success(f"✅ {fb_provider} key configured — auto-switch ready!")
        else:
            st.warning(f"⚠️ Add {fb_provider} key to enable auto-switch")
    else:
        st.info("No safety net — add one for seamless rate limit handling")
        if st.button("💾 Clear Safety Net", use_container_width=True):
            if current_fb in st.session_state.api_keys:
                del st.session_state.api_keys[current_fb]
            save_fallback_settings("", "")
            toast_success("Safety net cleared.")

    divider()

    # ==========================================================
    # 3. SYSTEM STATUS
    # ==========================================================
    st.markdown("### 📊 System Status")

    col_stat1, col_stat2, col_stat3 = st.columns(3)

    with col_stat1:
        if api_ready():
            st.success("✅ Primary Ready")
        else:
            st.warning("⚠️ Primary Not Set")

    with col_stat2:
        if fallback_ready():
            st.success("✅ Safety Net Ready")
        else:
            st.info("🔵 No Safety Net")

    with col_stat3:
        if 'token_usage' not in st.session_state:
            st.session_state.token_usage = {}
        total_tokens = sum(st.session_state.token_usage.values())
        st.metric("🪙 Total Tokens", f"{total_tokens:,}")

    if st.session_state.token_usage:
        with st.expander("📊 Token Usage Breakdown"):
            for prov, tokens in st.session_state.token_usage.items():
                st.markdown(f"**{prov}**: {tokens:,} tokens")

    divider()

    # ==========================================================
    # 4. APPEARANCE – now using 'theme' (unified with sidebar)
    # ==========================================================
    st.markdown("### 🎨 Appearance")
    st.caption("Customise the look and feel of Learn Sphere AI.")

    current_theme = st.session_state.get('theme', 'default')
    selected = st.radio(
        "Theme",
        ["Default", "Dark", "Light"],
        index=["default", "dark", "light"].index(current_theme),
        label_visibility="collapsed",
        horizontal=True
    )
    if selected.lower() != current_theme:
        st.session_state.theme = selected.lower()
        # Persist to database if user is logged in
        if st.session_state.get('user_id'):
            update_user_theme(st.session_state.user_id, st.session_state.theme)
        st.rerun()

    use_collage = st.checkbox(
        "🌄 Use Thumbnail Collage on Dashboard",
        value=st.session_state.get("use_collage", True),
        help="Show a blurred collage of your processed lecture thumbnails on the Dashboard"
    )
    if use_collage != st.session_state.get("use_collage", True):
        st.session_state.use_collage = use_collage
        st.rerun()

    divider()

    # ==========================================================
    # 5. SESSION MANAGEMENT
    # ==========================================================
    st.markdown("### 🧹 Session Management")
    st.caption("Clears current transcript, notes, and quiz from memory. Does not delete history.")

    if st.button("🗑️ Clear Current Session Data", use_container_width=True):
        keys_to_clear = [
            "transcript", "transcript_ready", "compressed_transcript",
            "summary", "summary_ready", "notes", "notes_ready",
            "quiz_questions", "quiz_answers", "quiz_ready", "chat_messages"
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        toast_success("Session cleared!")
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)