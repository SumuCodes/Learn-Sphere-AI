# components/api_key_prompt.py
import streamlit as st
from utils.api_utils import api_ready, save_api_settings, get_models
from config import SUPPORTED_PROVIDERS

@st.dialog("🔑 Set Up Your AI Provider")
def show_api_key_prompt():
    st.write("To use the AI features (Notes, Summary, Quiz, Tutor), you'll need to provide an API key.")
    st.write("You can skip this for now and set it up later in the **Workspace**.")
    
    st.markdown("---")
    
    # Provider and Model Selectors
    provider = st.selectbox("Select AI Provider", list(SUPPORTED_PROVIDERS.keys()))
    models = get_models(provider)
    default_model = models[0] if models else ""
    model = st.selectbox("Select Model", models, index=0 if models else None)
    
    # API Key Input
    api_key = st.text_input(f"Enter {provider} API Key", type="password", placeholder="sk-...")
    
    # Buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save & Continue", type="primary", use_container_width=True):
            if api_key:
                save_api_settings(provider, model, api_key)
                st.session_state.api_prompt_dismissed = True
                st.toast("API Key saved successfully!")
                st.rerun()
            else:
                st.warning("Please enter a key to save.")
                
    with col2:
        if st.button("Skip for now", use_container_width=True):
            st.session_state.api_prompt_dismissed = True
            st.rerun()