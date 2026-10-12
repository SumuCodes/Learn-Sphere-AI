# app_pages/signup.py
"""
Sign Up Page for AI Lecture Recorder Pro.
"""

import re
import streamlit as st
from utils.auth import create_user
from components.ui import mini_hero, primary_button, toast_error, toast_success

# Simple email pattern
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def show():
    st.markdown('<div class="main-content">', unsafe_allow_html=True)

    mini_hero("📝 Create Account", "Start your Learn Sphere AI journey")   

    if st.session_state.get('logged_in', False):
        st.session_state.current_page = "Dashboard"
        st.rerun()
        return

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container():
            username = st.text_input("Username", placeholder="Choose a username", key="signup_username")
            email = st.text_input("Email", placeholder="Enter your email address", key="signup_email")
            password = st.text_input("Password", type="password", placeholder="Choose a strong password", key="signup_password")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm your password", key="signup_confirm_password")

            col_a, col_b = st.columns(2)
            with col_a:
                if primary_button("📝 Create Account", key="signup_submit_btn"):
                    if not username or not email or not password:
                        toast_error("Please fill in all fields.")
                    elif not _EMAIL_RE.match(email.strip()):
                        toast_error("Please enter a valid email address.")
                    elif password != confirm_password:
                        toast_error("Passwords do not match.")
                    elif len(password) < 6:
                        toast_error("Password must be at least 6 characters.")
                    elif len(username.strip()) < 3:
                        toast_error("Username must be at least 3 characters.")
                    else:
                        if create_user(username.strip(), email.strip(), password):
                            toast_success("Account created successfully! Please login.")
                            st.session_state.current_page = "Login"
                            st.rerun()
                        else:
                            toast_error("Username or email already exists.")

            with col_b:
                if st.button("🔐 Back to Login", use_container_width=True, key="signup_to_login_btn"):
                    st.session_state.current_page = "Login"
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
