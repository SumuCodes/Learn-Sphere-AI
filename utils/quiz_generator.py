"""
Quiz Generation Utility – MCQ, MSQ, and OneWord.
Domain-agnostic. Ultra-strict prompt + structural validators.
"""

import json
import re
import random
import logging
from typing import List, Dict, Any, Optional, Union, Set

from utils.api_utils import generate_response, CreditError, RateLimitError
from utils.text_splitter import smart_split_text

logger = logging.getLogger(__name__)

# ── Constants ──
CHUNK_SIZE = 8000
API_TIMEOUT = 60
MIN_WORDS_PER_QUESTION = 150
BUFFER_MULTIPLIER = 1.5

# ── Filler cleaning ──
_FILLER_PATTERNS = [
    r"(?i)(the\s+)?video\s+has\s+(come\s+to\s+an\s+end|ended|concluded)[.,;]?\s*",
    r"(?i)thanks\s+for\s+watching[.,;]?\s*",
    r"(?i)subscribe\s+to\s+the\s+channel[.,;]?\s*",
    r"(?i)like\s+and\s+share[.,;]?\s*",
]

# ── Helpers ──

def clean_source_for_quiz(text: str) -> str:
    """Clean transcript filler and collapse near-duplicate paragraphs."""
    if not text:
        return text
    for pat in _FILLER_PATTERNS:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)
    text = re.sub(r'\n\s*\n', '\n\n', text)

    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    seen_hashes = set()
    unique_paragraphs = []
    for para in paragraphs:
        norm = re.sub(r'[^\w\s]', '', para.lower())
        norm = re.sub(r'\s+', ' ', norm).strip()
        h = hash(norm)
        if h in seen_hashes:
            continue
        if any(norm in existing and len(norm) < len(existing) - 20 for existing in seen_hashes):
            continue
        seen_hashes.add(norm)
        unique_paragraphs.append(para)

    return '\n\n'.join(unique_paragraphs)


def estimate_source_quality(text: str) -> dict:
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    total = len(paragraphs)
    if total == 0:
        return {"score": 0, "duplicate_pct": 100, "paragraphs": 0}
    norms = []
    for p in paragraphs:
        norm = re.sub(r'[^\w\s]', '', p.lower())
        norm = re.sub(r'\s+', ' ', norm).strip()
        norms.append(norm)
    unique = set(norms)
    duplicate_pct = int((1 - len(unique) / total) * 100)
    score = max(0, 100 - duplicate_pct * 2)
    return {"score": score, "duplicate_pct": duplicate_pct, "paragraphs": total}


def generate_session_id() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def extract_json(raw_response: str) -> Optional[Union[dict, list]]:
    cleaned = raw_response.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except:
        pass
    for match in re.finditer(r'(\{.*\}|\[.*\])', cleaned, re.DOTALL):
        try:
            return json.loads(match.group(0))
        except:
            continue
    return None

# ── Answer Checking ──

def _extract_letter(val: Any) -> Optional[str]:
    val_str = str(val).strip().upper()
    match = re.match(r'^([A-D])\s*[:\.\)]\s*', val_str)
    if match:
        return match.group(1)
    if len(val_str) == 1 and val_str in "ABCD":
        return val_str
    return None


def _extract_text(val: Any) -> str:
    val_str = str(val).strip()
    match = re.match(r'^[A-Da-d]\s*[:\.\)]\s*(.+)', val_str)
    if match:
        return match.group(1).strip()
    return val_str


def check_answer(user_ans: Any, correct_ans: List[str], q_type: str = "MCQ") -> bool:
    if not user_ans or not correct_ans:
        return False

    if q_type == "MCQ":
        user_str = user_ans[0] if isinstance(user_ans, list) else str(user_ans)
        user_text = _extract_text(user_str)
        correct_text = _extract_text(correct_ans[0])
        return user_text.lower() == correct_text.lower()

    elif q_type == "MSQ":
        if not isinstance(user_ans, list):
            return False
        user_set = set()
        for ans in user_ans:
            letter = _extract_letter(ans)
            if letter:
                user_set.add(letter)
            else:
                user_set.add(str(ans).strip().lower())

        correct_set = set()
        for ans in correct_ans:
            letter = _extract_letter(ans)
            if letter:
                correct_set.add(letter)
            else:
                correct_set.add(str(ans).strip().lower())

        return user_set == correct_set

    elif q_type == "OneWord":
        user_str = str(user_ans).strip().lower()
        correct_strs = [str(ans).strip().lower() for ans in correct_ans]
        return user_str in correct_strs

    return False


def get_full_correct_display(correct_ans: List[str], options: List[str], q_type: str = "MCQ") -> str:
    if not correct_ans:
        return "N/A"

    if q_type == "OneWord":
        return ", ".join(correct_ans)

    if q_type == "MSQ":
        displays = []
        for ans in correct_ans:
            letter = _extract_letter(ans)
            if letter:
                for opt in options:
                    if opt.strip().upper().startswith(letter + ":"):
                        displays.append(opt.strip())
                        break
                else:
                    displays.append(ans)
            else:
                displays.append(ans)
        return " | ".join(displays) if displays else "N/A"

    # MCQ
    if len(correct_ans) > 0 and len(correct_ans[0]) > 2 and ":" not in correct_ans[0]:
        return ", ".join(correct_ans)

    letter = _extract_letter(correct_ans[0])
    if letter:
        for opt in options:
            if opt.strip().upper().startswith(letter + ":"):
                return opt.strip()
    return correct_ans[0]

# ── TRIVIA DETECTOR ──

def _is_trivia(q: dict) -> bool:
    """Returns True if the question is trivia (name recall, definition regurgitation)."""
    question = q.get("question", "").lower()
    hint = q.get("hint", "").lower()
    correct = str(q.get("correct", [""])[0]).lower()

    # ── Structural trivia patterns (domain-agnostic) ──
    trivia_patterns = [
        # Direct name requests
        r"which (function|method|command|tool|operator|keyword) (is|does|can|should|would)",
        r"what (function|method|command|tool|operator|keyword) (is|does|can|should|would)",
        r"how (do you|would you|can you) (use|call|run|write|define|create|install)\b",
        r"what is the (primary |main |) (use|purpose|function|role) of",
        r"what does \w+ (stand for|mean|do)\?",
        r"which of the following (is|are) used to",
        r"_____?__ is the (primary |main |) (tool|function|method|command)",
        # Self-contradicting stems
        r"to make predictions.*use the _____",
        r"to train.*use the _____ method.*predict",
    ]
    for pat in trivia_patterns:
        if re.search(pat, question):
            return True

    # ── Hint gives away the answer ──
    if correct and len(correct) > 3:
        correct_clean = re.sub(r'[^\w]', '', correct)
        hint_clean = re.sub(r'[^\w]', '', hint)
        if correct_clean in hint_clean:
            return True

    # ── Self-contradiction: predict vs fit ──
    if "predict" in question and "fit" in correct and "predict" not in correct:
        return True
    if "fit" in question and "predict" in correct and "fit" not in correct:
        return True

    return False

# ── Validators ──

def _has_plausible_distractors(options: List[str]) -> bool:
    if len(options) != 4:
        return False
    for opt in options:
        if not opt or not opt.strip():
            return False
    if len(set(opt.strip().lower() for opt in options)) < 4:
        return False
    return True


def _is_quality_stem(question_text: str, q_type: str) -> bool:
    text = question_text.strip()
    if len(text) < 25:
        return False
    lower = text.lower()
    if lower in {"oneword", "one word", "one word or short phrase", "mcq", "msq", "multiple choice", "multiple select"}:
        return False
    if q_type == "OneWord" and text.count(" ") < 5:
        return False
    if re.match(r'^[A-Z][a-zA-Z\s]+\.$', text) and text.count(" ") < 4:
        return False
    return True


def _is_difficulty_appropriate(q: dict) -> bool:
    text = q.get("question", "").lower()
    difficulty = q.get("difficulty", "Easy")
    if difficulty == "Easy":
        return True

    trivial_patterns = [
        r"what is the (primary |main |)(use|purpose|function|role) of",
        r"how (do you|would you|can you|to) (convert|define|create|install|run|use|write)",
        r"what type of (error|exception|loop|operator|variable)",
        r"which of the following (commands|functions|methods|tools) (is|are) used to",
        r"what is the difference between \w+ and \w+\?",
        r"how many (types|kinds|ways|steps)",
        r"what does \w+ (stand for|mean|do)\?",
    ]
    for pat in trivial_patterns:
        if re.search(pat, text):
            return False
    return True


def _is_structurally_valid(q: dict, seen_set: set) -> bool:
    q_type = q.get("type", "MCQ")
    question_text = q.get("question", "").strip()
    if not question_text:
        return False

    # Trivia check
    if _is_trivia(q):
        logger.warning(f"Blocked trivia: {question_text[:60]}...")
        return False

    if not _is_quality_stem(question_text, q_type):
        return False

    if not _is_difficulty_appropriate(q):
        return False

    fp = question_text.strip().lower()
    if fp in seen_set:
        return False
    seen_set.add(fp)

    correct = q.get("correct", [])
    if not isinstance(correct, list) or len(correct) == 0:
        return False

    if q_type == "MCQ":
        opts = q.get("options", [])
        if len(opts) != 4 or len(correct) != 1:
            return False
        if not _has_plausible_distractors(opts):
            return False
        if re.search(r'(all of the above|none of the above)', correct[0], re.I):
            return False
        return True

    elif q_type == "MSQ":
        opts = q.get("options", [])
        if len(opts) != 4:
            return False
        if len(correct) < 2 or len(correct) > 4:
            return False
        if not _has_plausible_distractors(opts):
            return False
        correct_letters = set()
        for ans in correct:
            letter = _extract_letter(ans)
            if letter:
                correct_letters.add(letter)
        if len(correct_letters) < 2:
            return False
        return True

    elif q_type == "OneWord":
        opts = q.get("options", [])
        if opts and len(opts) > 0:
            return False
        if len(correct) < 1 or len(correct) > 3:
            return False
        if "_____" not in question_text and "____" not in question_text:
            return False
        for ans in correct:
            if len(str(ans).split()) > 3:
                return False
        return True

    return False

# ── Post-filtering ──

def _enforce_distribution(
    questions: List[Dict[str, Any]],
    num_questions: int,
    difficulty: str,
    question_types: str,
) -> List[Dict[str, Any]]:
    if difficulty != "Mixed":
        questions = [q for q in questions if q.get("difficulty") == difficulty]
    if question_types != "Mixed":
        questions = [q for q in questions if q.get("type") == question_types]

    if difficulty != "Mixed" and question_types != "Mixed":
        random.shuffle(questions)
        return questions[:num_questions]

    def _distribute(total: int, keys: List[str]) -> Dict[str, int]:
        base, rem = divmod(total, len(keys))
        return {k: base + (1 if i < rem else 0) for i, k in enumerate(keys)}

    selected: List[Dict[str, Any]] = []
    used_ids: Set[int] = set()

    if difficulty == "Mixed" and question_types == "Mixed":
        diff_targets = _distribute(num_questions, ["Easy", "Medium", "Hard"])
        for d in ["Easy", "Medium", "Hard"]:
            d_pool = [q for q in questions if q.get("difficulty") == d and id(q) not in used_ids]
            type_targets = _distribute(diff_targets[d], ["MCQ", "MSQ", "OneWord"])
            for t in ["MCQ", "MSQ", "OneWord"]:
                picks = [q for q in d_pool if q.get("type") == t and id(q) not in used_ids][:type_targets[t]]
                selected.extend(picks)
                used_ids.update(id(q) for q in picks)

    elif difficulty == "Mixed":
        targets = _distribute(num_questions, ["Easy", "Medium", "Hard"])
        for d in ["Easy", "Medium", "Hard"]:
            picks = [q for q in questions if q.get("difficulty") == d and id(q) not in used_ids][:targets[d]]
            selected.extend(picks)
            used_ids.update(id(q) for q in picks)

    else:
        targets = _distribute(num_questions, ["MCQ", "MSQ", "OneWord"])
        for t in ["MCQ", "MSQ", "OneWord"]:
            picks = [q for q in questions if q.get("type") == t and id(q) not in used_ids][:targets[t]]
            selected.extend(picks)
            used_ids.update(id(q) for q in picks)

    remaining = [q for q in questions if id(q) not in used_ids]
    random.shuffle(remaining)
    while len(selected) < num_questions and remaining:
        selected.append(remaining.pop())

    random.shuffle(selected)
    return selected[:num_questions]

# ── Prompt Builder ──

def _build_type_instructions(question_types: str) -> str:
    lines = []
    if question_types == "Mixed":
        lines.append("Generate a balanced mix of MCQ, MSQ, and OneWord questions.")
    else:
        lines.append(f"Generate ONLY {question_types} questions.")

    lines.append("""
**MCQ Rules:** Exactly 4 options (A-D). Exactly 1 correct answer.
**MSQ Rules:** Exactly 4 options (A-D). Exactly 2 or 3 correct answers.
**OneWord MANDATORY FORMAT:** The question MUST be a complete sentence with a blank (_____) that represents a MECHANISM or CONSEQUENCE.
    - BAD: "______ is the primary tool for executing commands."
    - BAD: "One word or short phrase: Weight Conversion"
    - GOOD: "When a child class overrides a method but still needs to invoke the parent's original implementation, the ______ mechanism traverses the inheritance chain to access it."
    - GOOD: "If a user enters '25' via input() and the code attempts arithmetic without conversion, Python raises a ______ because the operands are incompatible types."
""")
    return "\n".join(lines)


def _build_difficulty_rubric() -> str:
    return """
## 📊 Difficulty Calibration (Bloom's Taxonomy)

**EASY (Remember / Understand):**
- Single-step causal relationship or direct comparison.
- Example: "Why does Python raise a TypeError when concatenating string and int?"

**MEDIUM (Apply / Analyze):**
- Multi-step reasoning or applying a concept to a new scenario.
- Example: "If you modify a list while iterating, what is the most likely outcome?"

**HARD (Evaluate / Synthesize):**
- Counterfactuals, edge cases, or system-wide implications.
- Example: "If Django's migration system didn't auto-detect changes, what would be the most severe consequence?"
"""


def _build_quality_rules(include_hints: bool) -> str:
    hint_rule = "Include a 'hint' field that guides reasoning, never the answer." if include_hints else "Do NOT include a 'hint' field."
    return f"""
## 🚨 ZERO-TOLERANCE RULES (Breaking any = instant rejection)

1. **NO FUNCTION/COMMAND NAMES IN QUESTIONS**  
   - FORBIDDEN: "Which function...", "What command...", "How do you use X..."  
   - FORBIDDEN: Any question where knowing the name of a function/command is sufficient.  
   - REQUIRED: Frame every question around BEHAVIOR, CONSEQUENCE, or MECHANISM.

2. **NO DEFINITION REGURGITATION**  
   - FORBIDDEN: "What is the primary use of...", "What is the purpose of..."  
   - FORBIDDEN: "______ is the tool for..." (OneWord must test a MECHANISM, not a label)

3. **HINTS MUST NOT CONTAIN THE ANSWER**  
   - BAD: "Consider the role of manage.py" → gives away the answer.
   - GOOD: "Consider what happens to the database schema when model changes are not registered."

4. **EXPLANATIONS MUST EXPLAIN THE CONCEPT, NOT REPEAT THE ANSWER**  
   - BAD: "The correct answer is super() because super() accesses parent methods." (Circular)
   - GOOD: "Inheritance creates a lookup chain for methods. When a child overrides a method, the original parent implementation becomes inaccessible unless explicitly invoked through a mechanism that traverses this chain."

5. **NO SELF-CONTRADICTING STEMS**  
   - FORBIDDEN: "To make predictions using a decision tree, we can use the ______ method, which trains the model..." (predict ≠ fit)
   - Check: The blank must logically complete the sentence without contradiction.

6. **DIFFICULTY ENFORCEMENT** – Trivia is always EASY. If the question tests reasoning beyond recall, label accordingly.

7. **{hint_rule}**

## 📚 EXAMPLES

GOOD (Easy, conceptual): "What happens to a while loop when the condition becomes false?"
BAD (Trivia – rejected): "Which function is used to convert string to int?"
"""


def _build_output_format(include_hints: bool, include_explanations: bool) -> str:
    hint_field = '"hint": string (guides reasoning, not answer),' if include_hints else ''
    explanation_field = '"explanation": string (2-3 sentences, explains concept, not circular),' if include_explanations else ''
    return f"""
## 📤 Output Format
Return a valid JSON object with key "questions" containing an array.
Each object MUST have:
- "question": string (MUST be a complete sentence; for MCQ/MSQ start with Why/How/What happens/Compare; for OneWord contain a blank _____)
- "options": list of EXACTLY 4 strings for MCQ/MSQ; EMPTY list [] for OneWord
- "correct": list of strings (1 for MCQ, 2-3 for MSQ, 1-3 for OneWord)
- "type": "MCQ" | "MSQ" | "OneWord"
- "difficulty": "Easy" | "Medium" | "Hard"
{hint_field}
{explanation_field}
"""

# ── MAIN GENERATOR ──

def generate_quiz(
    source_text: str,
    num_questions: int,
    difficulty: str,
    question_types: str,
    include_hints: bool,
    include_explanations: bool = True,
    progress_bar=None,
    status_text=None,
    *,
    provider: str = "unknown",
) -> List[Dict[str, Any]]:
    if num_questions <= 0:
        raise ValueError("num_questions must be > 0")
    if not source_text or not source_text.strip():
        raise ValueError("source_text cannot be empty")
    if difficulty not in {"Easy", "Medium", "Hard", "Mixed"}:
        raise ValueError(f"Invalid difficulty: {difficulty}")
    if question_types not in {"MCQ", "MSQ", "OneWord", "Mixed"}:
        raise ValueError(f"Invalid question_types: {question_types}")

    source_text = clean_source_for_quiz(source_text)
    chunks = smart_split_text(source_text, CHUNK_SIZE)
    total_chunks = len(chunks)
    if total_chunks == 0:
        raise ValueError("No chunks extracted.")

    if status_text:
        status_text.info(f"Processing {total_chunks} chunks.")

    buffered_num = int(num_questions * BUFFER_MULTIPLIER)
    base_q = buffered_num // total_chunks
    extra = buffered_num % total_chunks
    questions_per_chunk = [base_q + (1 if i < extra else 0) for i in range(total_chunks)]

    for i, chunk in enumerate(chunks):
        max_q = max(1, len(chunk.split()) // MIN_WORDS_PER_QUESTION)
        if questions_per_chunk[i] > max_q:
            questions_per_chunk[i] = max_q

    surplus = buffered_num - sum(questions_per_chunk)
    if surplus > 0:
        sorted_idx = sorted(range(total_chunks), key=lambda idx: len(chunks[idx].split()), reverse=True)
        for idx in sorted_idx:
            if surplus <= 0:
                break
            max_q = max(1, len(chunks[idx].split()) // MIN_WORDS_PER_QUESTION)
            if questions_per_chunk[idx] < max_q:
                add = min(surplus, max_q - questions_per_chunk[idx])
                questions_per_chunk[idx] += add
                surplus -= add

    seen_questions = set()
    all_questions = []

    type_instructions = _build_type_instructions(question_types)
    difficulty_rubric = _build_difficulty_rubric()
    quality_rules = _build_quality_rules(include_hints)
    output_format = _build_output_format(include_hints, include_explanations)

    for i, chunk in enumerate(chunks):
        q_count = questions_per_chunk[i]
        if q_count == 0:
            continue

        if progress_bar:
            progress_bar.progress((i / total_chunks) * 0.95, text=f"Chunk {i+1}/{total_chunks}")
        if status_text:
            status_text.markdown(f"📝 Reading Chunk {i+1}/{total_chunks}")

        prompt = f"""
You are a senior examination board assessor. Your task is to create **conceptual, high-stakes questions** that test **deep understanding**.

## 🧠 Task
Analyze the lecture chunk and generate exactly {q_count} questions.

{type_instructions}
{difficulty_rubric}
{quality_rules}
{output_format}

---
**LECTURE CHUNK:**
{chunk}
---
"""

        try:
            extra_kwargs = {"timeout": API_TIMEOUT}
            if provider in {"OpenAI", "Google Gemini"}:
                extra_kwargs["response_format"] = {"type": "json_object"}

            response = generate_response(
                prompt,
                system_message="""You are a senior examination board assessor.
VIOLATION POLICY: Any question that asks about a function name, command name, syntax, or basic definition will be REJECTED and DISCARDED. You will receive NO CREDIT for trivia questions.
You MUST create questions that test MECHANISMS, CAUSE-EFFECT, and EDGE CASES — never memorization.
If the lecture only contains definitions, you MUST invent a scenario that requires reasoning about the concept.
Example of FORBIDDEN output: "Which function is used for X?" → INSTANT REJECTION.
Example of REQUIRED output: "If X were removed from a system already using Y, which failure would occur first?"
""",
                temperature=0.75,
                max_tokens=min(4000, max(1500, q_count * 350)),
                **extra_kwargs
            )

            parsed = extract_json(response)
            if not parsed:
                if status_text:
                    status_text.warning(f"Chunk {i+1}: JSON parse failed.")
                continue

            questions_arr = parsed.get("questions") or parsed.get("quiz") if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else None)

            if not questions_arr:
                if status_text:
                    status_text.warning(f"Chunk {i+1}: No questions array.")
                continue

            valid_count = 0
            for q in questions_arr:
                if not isinstance(q, dict):
                    continue

                q["type"] = q.get("type", "MCQ")
                if q["type"] not in {"MCQ", "MSQ", "OneWord"}:
                    q["type"] = "MCQ"

                if "correct" not in q or not isinstance(q["correct"], list):
                    q["correct"] = []
                if "options" not in q or not isinstance(q["options"], list):
                    q["options"] = []

                if _is_structurally_valid(q, seen_questions):
                    all_questions.append(q)
                    valid_count += 1

            if status_text:
                status_text.markdown(f"✅ Chunk {i+1} contributed {valid_count} questions")

        except (CreditError, RateLimitError) as e:
            if progress_bar:
                progress_bar.empty()
            if status_text:
                status_text.error(f"API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Chunk {i+1} error: {e}")
            if status_text:
                status_text.warning(f"Chunk {i+1} failed: {e}")
            continue

    if not include_hints:
        for q in all_questions:
            q.pop("hint", None)

    if not include_explanations:
        for q in all_questions:
            q.pop("explanation", None)

    selected = _enforce_distribution(all_questions, num_questions, difficulty, question_types)

    if include_explanations:
        selected = _backfill_explanations(selected, provider)

    if status_text:
        status_text.info(f"🎯 Generated {len(selected)} final questions.")

    logger.info("Generated %d questions (types=%s, difficulty=%s).", len(selected), question_types, difficulty)
    return selected


# ── Backfill Explanations ──

def _backfill_explanations(questions: List[Dict[str, Any]], provider: str) -> List[Dict[str, Any]]:
    missing = [q for q in questions if not q.get("explanation", "").strip()]
    if not missing:
        return questions

    batch_items = []
    for idx, q in enumerate(missing):
        q_type = q.get("type", "MCQ")
        correct = get_full_correct_display(q.get("correct", []), q.get("options", []), q_type)
        opts = "\n".join(q.get("options", [])) if q_type != "OneWord" else "N/A"
        batch_items.append(f"""
[{idx}]
Question: {q['question']}
Type: {q_type}
Options: {opts}
Correct: {correct}
""")

    separator = "\n---\n"
    prompt = f"""You are an expert tutor writing explanations for an exam-prep platform.

For each question below, write a 2-3 sentence explanation that:
1. States the core concept being tested.
2. Explains why the CORRECT answer is correct.
3. Explains why the MOST TEMPTING distractor is incorrect.

Return ONLY a JSON array. Each element: {{"explanation": "..."}}

{separator.join(batch_items)}
"""

    try:
        extra = {"timeout": API_TIMEOUT}
        response = generate_response(
            prompt,
            system_message="You write clear, educational explanations for quiz questions.",
            temperature=0.5,
            max_tokens=2000,
            **extra
        )

        parsed = extract_json(response)
        explanations = []
        if isinstance(parsed, list):
            explanations = parsed
        elif isinstance(parsed, dict):
            explanations = parsed.get("explanations", []) or list(parsed.values())

        for i, q in enumerate(missing):
            if i < len(explanations):
                exp = explanations[i]
                if isinstance(exp, dict):
                    q["explanation"] = exp.get("explanation", "")
                elif isinstance(exp, str):
                    q["explanation"] = exp

    except Exception as e:
        logger.warning(f"Explanation backfill failed: {e}")

    return questions


def generate_ai_feedback(score_percent: int, correct_count: int, total: int) -> str:
    prompt = f"A student scored {score_percent}% ({correct_count}/{total} correct) on a quiz. Give brief, encouraging feedback."
    try:
        return generate_response(
            prompt,
            system_message="You are a supportive tutor.",
            temperature=0.7,
            max_tokens=100,
            timeout=API_TIMEOUT
        )
    except Exception:
        return "Great effort! Review the explanations to solidify your understanding."