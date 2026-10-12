"""
Navigation: maps sidebar page names to app page modules.
Uses plain keys (no emojis) to avoid Unicode mismatch problems.
"""

import importlib
import streamlit as st


# ==========================================================
# PAGE MAPPING – Plain keys, no emojis
# ==========================================================
# To change a page's display name, edit the key here.
# The value is the module name under app_pages/.
PAGES = {
    "Dashboard": "app_pages.home",
    "Lecture Studio": "app_pages.analyze",
    "History": "app_pages.history",
    "Quick Revision": "app_pages.summary",
    "Study Notes": "app_pages.notes",          # <-- Already "Study Notes" (not "AI Notes")
    "Smart Quiz": "app_pages.quiz",
    "AI Tutor": "app_pages.chat",
    "Learning Analytics": "app_pages.performance",
    "Workspace": "app_pages.workspace",
    "Login": "app_pages.login",
    "SignUp": "app_pages.signup",
}

# Cache loaded modules to avoid repeated import overhead
_module_cache = {}


def navigate_to_page():
    """Load and display the current page."""

    page = st.session_state.get("current_page", "Dashboard")

    if page not in PAGES:
        print(f"⚠️ Page '{page}' not found. Redirecting to Dashboard.")
        page = "Dashboard"
        st.session_state.current_page = page   # Ensures the session state is updated

    module_name = PAGES[page]

    try:
        # Use cached module if already loaded
        if module_name not in _module_cache:
            _module_cache[module_name] = importlib.import_module(module_name)

        module = _module_cache[module_name]
        if hasattr(module, "show"):
            module.show()
        else:
            st.error(f"Page '{page}' does not have a show() function.")
    except ImportError as e:
        st.error(f"Could not load page '{page}': {e}")