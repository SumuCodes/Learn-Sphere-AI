# app_pages/quiz.py
"""
Smart Quiz – Premium exam‑prep experience with visual feedback and AI explanations.
"""

import streamlit as st
import time
import logging
import html
from config import QUIZ_SETTINGS
from utils.api_utils import CreditError, RateLimitError, get_free_model_suggestions
from utils.quiz_generator import (
    generate_quiz,
    check_answer,
    generate_ai_feedback,
    get_full_correct_display,
    clean_source_for_quiz,
    generate_session_id,
    estimate_source_quality
)
from utils.performance import append_quiz_result
from components.ui import (
    mini_hero, primary_button, divider, toast_error, toast_success,
    quiz_progress, difficulty_badge, mini_divider, glass_card
)

logger = logging.getLogger(__name__)

# ── Helpers ──

def _get_user_id() -> str:
    return st.session_state.get("user_id", "")

def _get_video_id() -> str:
    return st.session_state.get("video_id", "")

def _check_unanswered(user_answers, questions):
    unanswered = []
    for i, (ans, q) in enumerate(zip(user_answers, questions), start=1):
        q_type = q.get("type", "MCQ")
        if q_type == "MSQ":
            if not ans or len(ans) == 0:
                unanswered.append(i)
        else:
            if ans is None or (isinstance(ans, str) and not ans.strip()):
                unanswered.append(i)
    return unanswered

def _get_best_source():
    if st.session_state.get("sections_ready", False) and st.session_state.get("pre_generated_sections", []):
        return "topics"
    if st.session_state.get("notes_ready", False) and st.session_state.get("notes", "").strip():
        return "notes"
    return "transcript"

def _build_source_text(source_type):
    if source_type == "topics":
        sections = st.session_state.pre_generated_sections
        topic_texts = []
        for sec in sections:
            title = sec.get("topic_title", sec.get("topic_key", "Untitled"))
            notes = sec.get("notes", "")
            topic_texts.append(f"## {title}\n{notes}")
        return "\n\n---\n\n".join(topic_texts)
    elif source_type == "notes":
        return st.session_state.notes
    else:
        return st.session_state.transcript

def _type_icon(q_type: str) -> str:
    return {"MCQ": "🔘", "MSQ": "☑️", "OneWord": "✏️"}.get(q_type, "❓")

def _type_label(q_type: str) -> str:
    return {"MCQ": "Multiple Choice", "MSQ": "Multiple Select", "OneWord": "One Word"}.get(q_type, q_type)

def _render_question(i, q, user_answer, is_submitted):
    """
    Render a single question card with answer options and feedback if submitted.
    Returns the user's answer (if not submitted, returns None).
    """
    q_type = q.get("type", "MCQ")
    difficulty = q.get("difficulty", "")
    options = q.get("options", [])
    question_text = q.get("question", "")

    # Determine if answer is correct (only if submitted)
    is_correct = None
    if is_submitted:
        is_correct = check_answer(user_answer, q.get("correct", []), q_type)

    # Build card
    st.markdown(f"""
    <div class="quiz-question">
        <div class="q-header">
            <span class="q-number">Q{i+1}</span>
            <span class="q-type">{_type_icon(q_type)} {_type_label(q_type)}</span>
            {difficulty_badge(difficulty) if difficulty else ''}
        </div>
        <div class="q-text">{question_text}</div>
    """, unsafe_allow_html=True)

    # Render answer input based on type
    if q_type == "MCQ":
        selected = st.radio(
            "Select your answer",
            options,
            key=f"quiz_q_{i}",
            label_visibility="collapsed",
            index=None
        )
        user_answer = selected

    elif q_type == "MSQ":
        selected = st.multiselect(
            "Select all correct answers",
            options,
            key=f"quiz_q_{i}",
            label_visibility="collapsed",
            placeholder="Choose one or more..."
        )
        user_answer = selected

    elif q_type == "OneWord":
        selected = st.text_input(
            "Type your answer",
            key=f"quiz_q_{i}",
            label_visibility="collapsed",
            placeholder="Your answer..."
        )
        user_answer = selected

    # If submitted, show feedback
    if is_submitted:
        correct_display = get_full_correct_display(q.get("correct", []), options, q_type)
        if is_correct:
            st.markdown(f'<div class="q-feedback correct">✅ Correct!</div>', unsafe_allow_html=True)
        else:
            if q_type == "MCQ" or q_type == "MSQ":
                st.markdown(f'<div class="q-feedback incorrect">❌ Incorrect. The correct answer is: <strong>{correct_display}</strong></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="q-feedback incorrect">❌ Incorrect. We expected: <strong>{correct_display}</strong></div>', unsafe_allow_html=True)

        # Show explanation if available
        explanation = q.get("explanation", "").strip()
        if explanation:
            st.markdown(f'<div class="q-feedback explanation"><strong>📖 Explanation:</strong> {explanation}</div>', unsafe_allow_html=True)

        # Show hint if available (even after submission, it's fine)
        if q.get("hint"):
            st.markdown(f'<div class="q-hint">💡 Hint: {q["hint"]}</div>', unsafe_allow_html=True)

    else:
        # Show hint before submission if enabled
        if st.session_state.get("quiz_include_hints", True) and q.get("hint"):
            with st.expander("💡 Need a hint?"):
                st.write(q["hint"])

    st.markdown('</div>', unsafe_allow_html=True)  # close .quiz-question

    return user_answer

# ── Main Page ──

def show():
    st.markdown('<div class="main-content">', unsafe_allow_html=True)
    mini_hero("🥇 Smart Quiz", "Test your knowledge with conceptual questions")

    if not st.session_state.get("transcript_ready", False):
        glass_card("🎬 No Lecture", "Analyze a YouTube lecture first.", icon="📺", highlight=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    if st.session_state.get("quiz_ready", False) and st.session_state.get("show_quiz", False):
        if "quiz_start_time" not in st.session_state:
            st.session_state.quiz_start_time = time.time()

    user_id = _get_user_id()
    video_id = _get_video_id()
    if not user_id or not video_id:
        st.error("Missing user or video info. Please re‑load the lecture.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Routing
    if not st.session_state.get("quiz_ready", False):
        _show_generation_form(user_id, video_id)
    elif not st.session_state.get("show_quiz", False) and not st.session_state.get("quiz_submitted", False):
        if primary_button("👁️ View Generated Quiz"):
            st.session_state.show_quiz = True
            st.rerun()
    elif not st.session_state.get("quiz_submitted", False):
        _show_quiz_display(user_id, video_id)
    else:
        _show_quiz_results()

    st.markdown('</div>', unsafe_allow_html=True)

# ── Generation Form ──

def _show_generation_form(user_id, video_id):
    st.markdown("### ⚙️ Quiz Settings")

    source_type = _get_best_source()
    source_label = {
        "topics": "📚 Study Notes",
        "notes": "📘 Notes",
        "transcript": "📄 Transcript"
    }[source_type]
    st.caption(f"Source: **{source_label}** (auto-selected)")

    # Source quality warning
    raw_text = _build_source_text(source_type)
    quality = estimate_source_quality(raw_text)
    if quality["duplicate_pct"] > 30 and source_type == "transcript":
        st.warning(
            f"⚠️ Transcript quality is low ({quality['duplicate_pct']}% duplicate content). "
            f"Quiz questions may be repetitive. Go to **Study Notes** first for better results."
        )
    elif quality["score"] < 40:
        st.info(
            f"💡 Source quality score: {quality['score']}/100. "
            f"For exam-level questions, use the **Study Notes** or **Topics** tab before generating a quiz."
        )

    col1, col2 = st.columns(2)
    with col1:
        num_questions = st.number_input(
            "Number of Questions",
            min_value=QUIZ_SETTINGS["min_questions"],
            max_value=QUIZ_SETTINGS["max_questions"],
            value=QUIZ_SETTINGS["default_questions"],
            step=1
        )
        question_types = st.selectbox(
            "Question Type",
            ["Mixed", "MCQ", "MSQ", "OneWord"],
            index=0,
            help="MCQ = 1 correct answer. MSQ = 2-3 correct answers. OneWord = short text answer."
        )
    with col2:
        difficulty = st.selectbox("Difficulty", ["Mixed", "Easy", "Medium", "Hard"], index=0)
        include_hints = st.checkbox("💡 Include Hints", value=True)
        include_explanations = st.checkbox("📖 Include AI Explanations", value=True, help="Shows why the correct answer is right after you submit.")

    include_feedback = st.checkbox("📝 Get detailed AI feedback after quiz", value=False)

    if primary_button("✨ Generate AI Quiz"):
        progress_bar = st.progress(0.0, text="Preparing...")
        status_text = st.empty()

        try:
            source_text = _build_source_text(source_type)
            if not source_text or not source_text.strip():
                progress_bar.empty()
                status_text.empty()
                toast_error("No source content available.")
                return

            source_text = clean_source_for_quiz(source_text)

            status_text.markdown("Generating questions...")
            questions = generate_quiz(
                source_text=source_text,
                num_questions=num_questions,
                difficulty=difficulty,
                question_types=question_types,
                include_hints=include_hints,
                include_explanations=include_explanations,
                progress_bar=progress_bar,
                status_text=status_text,
                provider=st.session_state.get("provider", "unknown")
            )

            if questions:
                if len(questions) < num_questions:
                    st.warning(f"⚠️ Only generated {len(questions)} out of {num_questions} requested questions. The source text may be too short or repetitive for your settings.")

                st.session_state.quiz_questions = questions
                st.session_state.quiz_user_answers = []
                st.session_state.quiz_score = 0
                st.session_state.quiz_submitted = False
                st.session_state.quiz_ready = True
                st.session_state.show_quiz = True
                st.session_state.quiz_include_hints = include_hints
                st.session_state.quiz_include_explanations = include_explanations
                st.session_state.quiz_include_feedback = include_feedback
                st.session_state.quiz_session_id = generate_session_id()
                st.session_state.pop("quiz_start_time", None)
                st.session_state.pop("quiz_time_taken", None)

                progress_bar.progress(1.0, text="Done!")
                status_text.empty()
                toast_success(f"Quiz generated! ({len(questions)} questions)")
                logger.info(f"Quiz generated: {len(questions)} questions, session={st.session_state.quiz_session_id}")
                time.sleep(0.5)
                st.rerun()
            else:
                progress_bar.empty()
                status_text.empty()
                toast_error("No valid questions generated. Please try again.")

        except (CreditError, RateLimitError) as e:
            progress_bar.empty()
            status_text.empty()
            st.error(str(e))
            st.markdown("### 💡 Switch to a Free Model")
            suggestions = get_free_model_suggestions()
            cols = st.columns(min(len(suggestions), 3))
            for idx, (provider, model, desc) in enumerate(suggestions):
                with cols[idx % len(cols)]:
                    if st.button(f"🔄 {provider} – {model}", key=f"switch_{idx}"):
                        st.session_state.provider = provider
                        st.session_state.model = model
                        st.session_state.client = None
                        st.rerun()
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            toast_error(f"Error: {e}")
            logger.error(f"Quiz generation error: {e}")

# ── Quiz Display ──

def _show_quiz_display(user_id, video_id):
    include_hints = st.session_state.get("quiz_include_hints", True)
    total_questions = len(st.session_state.quiz_questions)

    # Header with progress
    st.markdown(f"""
    <div class="quiz-header">
        <span class="quiz-title">📋 Quiz ({total_questions} Questions)</span>
    </div>
    """, unsafe_allow_html=True)

    # Progress bar
    current_q = 0  # not used for progress bar, but we can show overall progress
    # We'll just show a static progress bar representing completion (0% before submission)
    quiz_progress(0, total_questions)  # or we could show a "Question X of Y" indicator if we want, but we'll keep it simple

    user_answers = []
    for i, q in enumerate(st.session_state.quiz_questions):
        ans = _render_question(i, q, None, False)
        user_answers.append(ans)

    # Submit button
    if primary_button("✅ Submit Quiz"):
        unanswered = _check_unanswered(user_answers, st.session_state.quiz_questions)
        if unanswered:
            toast_error(f"Please answer all questions. Unanswered: {', '.join(map(str, unanswered))}")
            return

        correct = 0
        for i, q in enumerate(st.session_state.quiz_questions):
            q_type = q.get("type", "MCQ")
            if check_answer(user_answers[i], q.get("correct", []), q_type):
                correct += 1

        score_percent = int(correct / total_questions * 100)
        st.session_state.quiz_score = score_percent
        st.session_state.quiz_submitted = True
        st.session_state.quiz_user_answers = user_answers
        st.session_state.quiz_correct_count = correct

        if 'quiz_start_time' in st.session_state:
            st.session_state.quiz_time_taken = time.time() - st.session_state.quiz_start_time
        else:
            st.session_state.quiz_time_taken = 0

        quiz_session_id = st.session_state.get("quiz_session_id", generate_session_id())
        try:
            quiz_result = {
                "score": correct,
                "total": total_questions,
                "percentage": score_percent,
                "answers": [
                    {
                        "question": q["question"],
                        "user_answer": user_answers[i],
                        "correct_answer": q.get("correct", []),
                        "is_correct": check_answer(user_answers[i], q.get("correct", []), q.get("type", "MCQ")),
                    }
                    for i, q in enumerate(st.session_state.quiz_questions)
                ],
                "topics_quizzed": list({q.get("topic", q.get("difficulty", "")) for q in st.session_state.quiz_questions}),
            }
            append_quiz_result(
                video_id=video_id,
                quiz_result=quiz_result,
                user_id=user_id,
                session_id=quiz_session_id
            )
            logger.info(f"Quiz submitted: {correct}/{total_questions}, session={quiz_session_id}")
        except Exception as e:
            logger.error(f"Save error: {e}")
            st.warning("Quiz result could not be saved, but your score is displayed below.")

        if score_percent >= 80:
            st.balloons()

        toast_success(f"Score: {score_percent}%")
        st.rerun()

# ── Results ──

def _show_quiz_results():
    score = st.session_state.quiz_score
    total_q = len(st.session_state.quiz_questions)
    correct_count = st.session_state.get("quiz_correct_count", 0)
    include_hints = st.session_state.get("quiz_include_hints", True)
    include_explanations = st.session_state.get("quiz_include_explanations", True)
    include_feedback = st.session_state.get("quiz_include_feedback", False)

    time_taken = st.session_state.get('quiz_time_taken', 0)
    mins, secs = divmod(int(time_taken), 60)

    color = "#00C853" if score >= 80 else "#FF8F00" if score >= 60 else "#FF1744"

    st.markdown(f"""
    <div class="quiz-score-display" style="border-color:{color}44;">
        <div class="quiz-score-number" style="color:{color};">{score}%</div>
        <div class="quiz-score-sub" style="color:{color};">{correct_count} / {total_q} Correct</div>
        <div class="quiz-score-time">⏱️ Time taken: {mins}m {secs}s</div>
    </div>
    """, unsafe_allow_html=True)

    if include_feedback:
        try:
            with st.spinner("Generating feedback..."):
                feedback = generate_ai_feedback(score, correct_count, total_q)
            st.info(feedback)
        except Exception as e:
            logger.error(f"Feedback error: {e}")
            st.info(f"Score: {correct_count}/{total_q}. Review your answers below.")
    else:
        st.info(f"Score: {correct_count}/{total_q}. Review your answers below.")

    divider()
    st.markdown("### 📖 Review Your Answers")

    for i, q in enumerate(st.session_state.quiz_questions):
        user_ans = st.session_state.quiz_user_answers[i]
        correct_ans = q.get("correct", [])
        q_type = q.get("type", "MCQ")
        options = q.get("options", [])
        is_correct = check_answer(user_ans, correct_ans, q_type)

        correct_display = get_full_correct_display(correct_ans, options, q_type)

        if q_type == "MSQ":
            user_display = " | ".join(user_ans) if user_ans else "No answer"
        else:
            user_display = user_ans if user_ans else "No answer"

        safe_display = html.escape(str(user_display))

        with st.expander(f"Q{i+1}. {q['question']} {'✅' if is_correct else '❌'}"):
            st.caption(f"{_type_icon(q_type)} {_type_label(q_type)}")
            if is_correct:
                st.markdown(f"✅ **Your answer:** <span class='correct'>{safe_display}</span><br><br>**Correct answer:** <span class='correct'>{correct_display}</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"❌ **Your answer:** <span class='incorrect'>{safe_display}</span><br><br>**Correct answer:** <span class='correct'>{correct_display}</span>", unsafe_allow_html=True)

            if include_hints and q.get("hint"):
                st.markdown(f"**💡 Hint:** {q['hint']}")

            if include_explanations:
                explanation = q.get("explanation", "").strip()
                if explanation:
                    st.markdown("---")
                    st.markdown(f"**📖 Explanation:** {explanation}")
                else:
                    st.markdown("---")
                    st.caption("No explanation available for this question.")
        mini_divider()

    if primary_button("🔄 Retake Quiz"):
        keys = ['quiz_ready', 'quiz_submitted', 'show_quiz', 'quiz_questions',
                'quiz_user_answers', 'quiz_score', 'quiz_start_time', 'quiz_time_taken',
                'quiz_correct_count', 'quiz_session_id', 'quiz_include_feedback',
                'quiz_include_explanations']
        for k in keys:
            st.session_state.pop(k, None)
        logger.info("Quiz retaken")
        st.rerun()