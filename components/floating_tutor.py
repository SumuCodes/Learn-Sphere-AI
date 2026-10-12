# components/floating_tutor.py
import streamlit as st


def render_floating_tutor(page_key: str = "current_page"):
    """
    Floating AI Tutor button + modal dialog.
    Uses URL query params for click communication.
    Drag‑and‑drop position is stored per user in localStorage.
    """

    if not st.session_state.get("logged_in", False):
        return

    # ── Initialize State ───────────────────────────────────────
    if "show_quick_chat" not in st.session_state:
        st.session_state.show_quick_chat = False
    if "quick_chat_msgs" not in st.session_state:
        st.session_state.quick_chat_msgs = []

    # ── Auto‑close on page change ──────────────────────────────
    _page = st.session_state.get(page_key, "")
    if st.session_state.show_quick_chat:
        if st.session_state.get("_chat_page", _page) != _page:
            st.session_state.show_quick_chat = False
    if st.session_state.show_quick_chat:
        st.session_state._chat_page = _page

    # ── Detect click from URL query param ──────────────────────
    if st.query_params.get("open_tutor") == "1":
        st.session_state.show_quick_chat = True
        # Remove the param to avoid reopening after a rerun
        try:
            del st.query_params["open_tutor"]
        except KeyError:
            pass

    # ── Pass username to JavaScript for per‑user storage ──────
    username = st.session_state.get("username", "default")
    st.markdown(
        f"""
        <script>
            window.__username = "{username}";
        </script>
        """,
        unsafe_allow_html=True,
    )

    # ── Floating Button (HTML only) ────────────────────────────
    st.markdown("""
    <div id="ai-tutor-float">
        <div class="tutor-btn-glow"></div>
        <div class="tutor-btn-body">
            <svg viewBox="0 0 24 24" fill="white" width="26" height="26">
                <path d="M12 0L14.5 9.5L24 12L14.5 14.5L12 24L9.5 14.5L0 12L9.5 9.5Z"/>
            </svg>
        </div>
        <span class="tutor-tooltip">AI Tutor</span>
    </div>
    """, unsafe_allow_html=True)

    # ── JS: Drag + Click (with per‑user localStorage) ────────
    st.markdown("""
    <script>
    (function(){
        /* ── Per‑render: restore saved position (per user) ── */
        const el = document.getElementById('ai-tutor-float');
        if(el){
            const storageKey = 'tutor_btn_pos_' + (window.__username || 'default');
            const saved = localStorage.getItem(storageKey);
            if(saved){
                try{
                    const p = JSON.parse(saved);
                    el.style.right  = 'auto';
                    el.style.bottom = 'auto';
                    el.style.left   = p.left + 'px';
                    el.style.top    = p.top  + 'px';
                }catch(e){}
            }
        }

        /* ── One‑time: set up document‑level listeners ── */
        if(window.__tutorListenersReady) return;
        window.__tutorListenersReady = true;

        window.__tutorDrag = { on: false, moved: false, sx:0, sy:0, sl:0, st:0 };

        document.addEventListener('pointerdown', function(e){
            const el = document.getElementById('ai-tutor-float');
            if(!el || !el.contains(e.target)) return;
            const d = window.__tutorDrag;
            d.on    = true;
            d.moved = false;
            d.sx    = e.clientX;
            d.sy    = e.clientY;
            d.sl    = el.offsetLeft;
            d.st    = el.offsetTop;
        });

        document.addEventListener('pointermove', function(e){
            const d = window.__tutorDrag;
            if(!d.on) return;
            const el = document.getElementById('ai-tutor-float');
            if(!el) return;
            const dx = e.clientX - d.sx;
            const dy = e.clientY - d.sy;
            if(Math.abs(dx) > 4 || Math.abs(dy) > 4) d.moved = true;
            if(d.moved){
                el.style.right  = 'auto';
                el.style.bottom = 'auto';
                el.style.left   = (d.sl + dx) + 'px';
                el.style.top    = (d.st  + dy) + 'px';
            }
        });

        document.addEventListener('pointerup', function(e){
            const d = window.__tutorDrag;
            if(!d.on) return;
            d.on = false;

            if(d.moved){
                /* Drag ended — save position (per user) */
                const el = document.getElementById('ai-tutor-float');
                if(el){
                    const storageKey = 'tutor_btn_pos_' + (window.__username || 'default');
                    localStorage.setItem(storageKey,
                        JSON.stringify({ left: el.offsetLeft, top: el.offsetTop }));
                }
            } else {
                /* Click! — open tutor via URL query param */
                const url = new URL(window.location.href);
                url.searchParams.set('open_tutor', '1');
                window.location.href = url;   // <-- CHANGE: preserve history
            }
        });
    })();
    </script>
    """, unsafe_allow_html=True)

    # ── Dialog Definition ──────────────────────────────────────
    @st.dialog(title="✨ AI Tutor", width="small")
    def _quick_chat_popup():

        # Close button (custom)
        cols = st.columns([6, 1])
        with cols[1]:
            if st.button("✕", key="close_tutor_dialog"):
                st.session_state.show_quick_chat = False
                st.rerun()

        # Chat history (scrollable)
        with st.container(height=300, border=False):
            if not st.session_state.quick_chat_msgs:
                st.info("Ask a quick question about the app or your current lecture!")
            else:
                for msg in st.session_state.quick_chat_msgs:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

        # Chat input
        quick_prompt = st.chat_input("Ask anything...", key="quick_chat_input")

        if quick_prompt:
            st.session_state.quick_chat_msgs.append(
                {"role": "user", "content": quick_prompt}
            )
            with st.spinner("Thinking..."):
                try:
                    if (
                        st.session_state.get("transcript_ready", False)
                        and st.session_state.get("client")
                    ):
                        from utils.rag import get_answer
                        ans = get_answer(quick_prompt)
                    else:
                        ans = (
                            "I'm your Quick Helper! Analyze a lecture in "
                            "Lecture Studio first for lecture‑specific answers. "
                            "For app help, ask away!"
                        )
                    st.session_state.quick_chat_msgs.append(
                        {"role": "assistant", "content": ans}
                    )
                except Exception as e:
                    st.session_state.quick_chat_msgs.append(
                        {"role": "assistant", "content": f"⚠️ Error: {e}"}
                    )
            st.rerun()

    # ── Show dialog when flag is True ──────────────────────────
    if st.session_state.show_quick_chat:
        _quick_chat_popup()