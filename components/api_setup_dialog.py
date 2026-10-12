# components/api_setup_dialog.py
"""
Skippable API Setup Dialog — appears after login if no API keys configured.
User can add keys or skip (still access History, Performance without API).
"""

import streamlit as st
from utils.api_utils import (
    save_api_settings, save_fallback_settings, get_api_key,
    get_models, api_ready, create_client
)
from config import (
    SUPPORTED_PROVIDERS,
    DEFAULT_PROVIDER, DEFAULT_MODEL,
    DEFAULT_FALLBACK_PROVIDER, DEFAULT_FALLBACK_MODEL,
)


def show_api_setup_dialog():
    """
    Show the API setup dialog if:
      1. User is logged in
      2. No API keys are configured yet
      3. User hasn't permanently dismissed it
    """
    if not st.session_state.get('logged_in', False):
        return

    # Check if any API keys exist
    has_keys = bool(st.session_state.get("api_keys", {}))

    # Check if user permanently dismissed the dialog
    dismissed = st.session_state.get("_api_setup_dismissed", False)

    # Show dialog only if no keys and not dismissed
    if not has_keys and not dismissed:
        _render_setup_dialog()


@st.dialog(title="🚀 Welcome to Learn Sphere AI! Set up your AI Engine", width="large")   
def _render_setup_dialog():

    st.markdown("""
    To use AI features (Summary, Notes, Quiz, AI Tutor), you need an API key.
    
    **Don't worry — it's free and takes 30 seconds!** You can also skip this 
    and add keys later from **⚙️ Workspace**.
    """)

    # ── Quick links to get free keys ──
    with st.expander("🔑 Where to get FREE API keys?", expanded=True):
        col_link1, col_link2 = st.columns(2)
        with col_link1:
            st.markdown("""
            **🧠 Google Gemini** *(Recommended)*
            - 👉 [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
            - 🎁 **1M TPM free** — best for everything!
            """)
        with col_link2:
            st.markdown("""
            **⚡ Groq** *(Safety Net)*
            - 👉 [console.groq.com](https://console.groq.com)
            - 🎁 **1M tokens/day** free — perfect backup
            """)

    st.divider()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PRIMARY ENGINE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    st.markdown("#### 🧠 Primary Engine")
    st.caption("For heavy tasks: Summary, Notes, Quiz generation")

    provider_names = list(SUPPORTED_PROVIDERS.keys())
    p_idx = provider_names.index(DEFAULT_PROVIDER) if DEFAULT_PROVIDER in provider_names else 0

    col1, col2 = st.columns(2)
    with col1:
        p_provider = st.selectbox(
            "Provider", provider_names, index=p_idx,
            key="setup_primary_provider"
        )
    with col2:
        p_models = get_models(p_provider)
        p_model_idx = p_models.index(DEFAULT_MODEL) if DEFAULT_MODEL in p_models else 0
        p_model = st.selectbox(
            "Model", p_models, index=p_model_idx,
            key="setup_primary_model"
        )

    p_key = st.text_input(
        f"🔑 {p_provider} API Key",
        value=get_api_key(p_provider),
        type="password",
        placeholder="Paste your API key here...",
        key="setup_primary_key"
    )

    st.divider()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SAFETY NET (Optional)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    st.markdown("#### ⚡ Safety Net *(optional)*")
    st.caption("Auto-switches when Primary hits rate limit — prevents interruptions")

    fb_options = ["None"] + [p for p in provider_names if p != p_provider]
    fb_idx = fb_options.index(DEFAULT_FALLBACK_PROVIDER) if DEFAULT_FALLBACK_PROVIDER in fb_options else 0

    fb_provider = st.selectbox(
        "Safety Net Provider", fb_options, index=fb_idx,
        key="setup_fallback_provider"
    )

    fb_model = ""
    if fb_provider != "None":
        fb_models = get_models(fb_provider)
        fb_model_idx = fb_models.index(DEFAULT_FALLBACK_MODEL) if DEFAULT_FALLBACK_MODEL in fb_models else 0
        fb_model = st.selectbox(
            "Safety Net Model", fb_models, index=fb_model_idx,
            key="setup_fallback_model"
        )

        fb_key = st.text_input(
            f"🔑 {fb_provider} API Key",
            value=get_api_key(fb_provider),
            type="password",
            placeholder="Paste your safety net API key...",
            key="setup_fallback_key"
        )

    st.divider()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ACTION BUTTONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    col_save, col_skip = st.columns([2, 1])

    with col_save:
        save_label = "✅ Save & Start Learning" if p_key.strip() else "✅ Save & Start Learning"
        if st.button(save_label, type="primary", use_container_width=True, key="setup_save"):
            # Save primary
            if p_key.strip():
                save_api_settings(p_provider, p_model, p_key)
                try:
                    st.session_state.client = create_client(p_provider)
                except Exception:
                    pass

            # Save safety net
            if fb_provider != "None" and fb_model:
                if fb_key.strip():
                    st.session_state.api_keys[fb_provider] = fb_key
                save_fallback_settings(fb_provider, fb_model)

            st.session_state._api_setup_dismissed = True
            st.rerun()

    with col_skip:
        if st.button("⏭️ Skip for now", use_container_width=True, key="setup_skip"):
            st.session_state._api_setup_dismissed = True
            st.rerun()

    # ── Helpful note ──
    if not p_key.strip():
        st.info(
            "💡 You can skip this and still access **History** and "
            "**Performance Insights** without an API key. "
            "Add keys anytime from ⚙️ Workspace."
        )