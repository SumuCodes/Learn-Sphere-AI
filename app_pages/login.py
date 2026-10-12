"""
Login Page for AI Lecture Recorder Pro.
"""

import streamlit as st
from utils.auth import authenticate_user, login_user
from components.ui import mini_hero, primary_button, toast_error, toast_success


def show():
    st.markdown('<div class="main-content">', unsafe_allow_html=True)

    mini_hero("🔐 Login", "Sign in to your Learn Sphere AI workspace")  

    # If already logged in, go to Dashboard
    if st.session_state.get('logged_in', False):
        st.session_state.current_page = "Dashboard"
        st.rerun()
        return

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container():
            username = st.text_input("Username", placeholder="Enter your username", key="login_username")
            password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")

            col_a, col_b = st.columns(2)
            with col_a:
                if primary_button("🔐 Login", key="login_submit_btn"):
                    if not username or not password:
                        toast_error("Please enter both username and password.")
                    else:
                        user = authenticate_user(username, password)
                        if user:
                            login_user(user['id'])
                            toast_success(f"Welcome back, {user['username']}! 🎉")
                            st.session_state.current_page = "Dashboard"
                            st.rerun()
                        else:
                            toast_error("Invalid username or password.")

            with col_b:
                if st.button("📝 Create Account", use_container_width=True, key="login_to_signup_btn"):
                    st.session_state.current_page = "SignUp"
                    st.rerun()

            st.divider()

    st.markdown('</div>', unsafe_allow_html=True)
