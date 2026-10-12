# components/ai_tutor_sidebar.py
import streamlit as st
from utils.api_utils import generate_response, api_ready, CreditError, RateLimitError

def show_ai_tutor_sidebar():
    """Renders the AI Tutor in a right-side column layout, with compact styling."""
    # Initialize state
    if "tutor_open" not in st.session_state:
        st.session_state.tutor_open = True  # Start open

    # 1. The Hide/Show Button (inside the tutor card when open)
    if st.session_state.tutor_open:
        # Create columns: main (2/3) and tutor (1/3)
        main_col, tutor_col = st.columns([2, 1], gap="large")

        # ── Render the Chat UI inside the right column ──
        with tutor_col:
            st.markdown('<div class="notes-tutor-column">', unsafe_allow_html=True)
            st.markdown('<div class="tutor-card">', unsafe_allow_html=True)

            # Header with Hide button on the right
            st.markdown("""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem; border-bottom:1px solid var(--border); padding-bottom:0.5rem;">
                <h4 style="margin:0; font-size:1rem; font-weight:600; color:var(--text);">🤖 AI Tutor</h4>
            </div>
            """, unsafe_allow_html=True)

            # Hide button (Streamlit)
            if st.button("✕ Hide Tutor", key="hide_tutor_btn", use_container_width=True):
                st.session_state.tutor_open = False
                st.rerun()

            if not api_ready():
                st.warning("⚠️ Set API key in Workspace.")
            elif not st.session_state.get("transcript_ready", False):
                st.info("👈 Analyze a lecture first.")
            else:
                if "panel_chat_messages" not in st.session_state:
                    st.session_state.panel_chat_messages = []

                # Chat history
                st.markdown('<div class="tutor-chat">', unsafe_allow_html=True)
                if not st.session_state.panel_chat_messages:
                    st.markdown('<div class="empty-state">💬 Ask a question about this lecture</div>', unsafe_allow_html=True)
                else:
                    for message in st.session_state.panel_chat_messages:
                        with st.chat_message(message["role"]):
                            st.markdown(message["content"])
                st.markdown('</div>', unsafe_allow_html=True)

                # Clear chat button
                if st.button("🧹 Clear", key="clear_chat_btn", use_container_width=True):
                    st.session_state.panel_chat_messages = []
                    st.rerun()

                # Chat input
                if prompt := st.chat_input("Ask your tutor...", key="right_panel_chat_input"):
                    st.session_state.panel_chat_messages.append({"role": "user", "content": prompt})
                    with st.chat_message("user"):
                        st.markdown(prompt)
                    with st.chat_message("assistant"):
                        with st.spinner("Thinking..."):
                            try:
                                context = (
                                    st.session_state.get("notes") or
                                    st.session_state.get("summary") or
                                    st.session_state.get("transcript", "")
                                )
                                context = context[:10000]
                                system_prompt = "You are an AI Tutor helping a student understand a lecture. Answer clearly and concisely."
                                full_prompt = f"Lecture Context:\n{context}\n\nStudent Question: {prompt}"
                                response = generate_response(
                                    prompt=full_prompt,
                                    system_message=system_prompt,
                                    temperature=0.4
                                )
                                st.markdown(response)
                                st.session_state.panel_chat_messages.append(
                                    {"role": "assistant", "content": response}
                                )
                            except CreditError as e:
                                st.error(str(e))
                                st.markdown("💡 **Add credits or switch to a free model in Workspace.**")
                            except RateLimitError as e:
                                st.error(str(e))
                                st.markdown("💡 **Rate limit reached. Wait a moment or switch providers in Workspace.**")
                            except Exception as e:
                                st.error(f"Error: {e}")

            st.markdown('</div></div>', unsafe_allow_html=True)  # close tutor-card and tutor-column

        return main_col

    else:
        # ── Tutor is hidden – show an "Open AI Tutor" button in the main content ──
        # We'll return a container that contains the button (styled to appear on the right)
        # using a placeholder column structure.
        container = st.container()
        with container:
            # Use columns to push the button to the right
            col1, col2, col3 = st.columns([6, 1, 1])
            with col3:
                if st.button("💬 Open AI Tutor", key="open_tutor_btn", help="Open the AI Tutor sidebar"):
                    st.session_state.tutor_open = True
                    st.rerun()
            # The rest of the main content will be rendered below this.
            # Return a dummy container that will be used by the calling page.
            # But we need to return a column-like object; we'll return the container itself.
            # The caller (notes.py) will place its content inside this container.
            # However, we need to ensure the button appears above the content.
            # We'll use a trick: return a special container that also includes the button.
            # Simpler: we can just return the main column as a placeholder.
            # Actually, the calling function expects a column to put its content in.
            # If we return a container, the caller will put its content inside it.
            # So the button will be above the caller's content.
            return container