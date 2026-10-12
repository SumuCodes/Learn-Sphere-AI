# components/sidebar.py
"""
Minimal, Premium Sidebar for AI Lecture Recorder Pro.
"""
import streamlit as st
from utils.auth import logout_user  # <-- removed update_user_theme

def render_sidebar():
    with st.sidebar:
        # ==========================================================
        # 1. APP IDENTITY & USER
        # ==========================================================
        st.markdown("### 🌐 Learn Sphere AI")   
        st.caption("Your intelligent learning companion. Transform lectures into knowledge")
        st.divider()

        if st.session_state.get('logged_in', False):
            st.markdown(f"👤 **{st.session_state.get('username', 'User')}**")
            
            current_plain = st.session_state.get("current_page", "Dashboard")
            
            # Helper function for nav buttons
            def nav_button(label, page_key):
                if st.button(label, key=f"nav_{page_key}", use_container_width=True, 
                             type="primary" if current_plain == page_key else "secondary"):
                    st.session_state.current_page = page_key
                    st.rerun()

            # ==========================================================
            # 2. DASHBOARD
            # ==========================================================
            nav_button("🏠 Dashboard", "Dashboard")
            st.markdown("")  # Spacer

            # ==========================================================
            # 3. LEARN
            # ==========================================================
            st.markdown("#### 📚 Learn")
            nav_button("🎬 Lecture Studio", "Lecture Studio")
            nav_button("📖 History", "History")
            nav_button("📝 Study Notes", "Study Notes")
            nav_button("⚡ Quick Revision", "Quick Revision")
            st.markdown("")

            # ==========================================================
            # 4. PRACTICE
            # ==========================================================
            st.markdown("#### 🧠 Practice")
            nav_button("🥇 Smart Quiz", "Smart Quiz")
            nav_button("👩‍🏫 AI Tutor", "AI Tutor")
            st.markdown("")

            # ==========================================================
            # 5. PROGRESS
            # ==========================================================
            st.markdown("#### 📈 Progress")
            nav_button("📊 Learning Analytics", "Learning Analytics")
            st.markdown("")

            # ==========================================================
            # 6. WORKSPACE
            # ==========================================================
            st.markdown("#### ⚙️ Workspace")
            nav_button("🧠 AI Engine & Settings", "Workspace")
            
            # ==========================================================
            # 7. BOTTOM UTILITY (Logout only – theme moved to Workspace)
            # ==========================================================
            st.divider()
            # Single column for logout
            if st.button("🚪 Logout", use_container_width=True):
                logout_user()
                st.rerun()

        else:
            # ==========================================================
            # LOGGED OUT VIEW
            # ==========================================================
            st.markdown("#### Welcome!")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔐 Login", use_container_width=True):
                    st.session_state.current_page = "Login"
                    st.rerun()
            with col2:
                if st.button("📝 Sign Up", use_container_width=True):
                    st.session_state.current_page = "SignUp"
                    st.rerun()