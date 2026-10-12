# utils/smart_summarizer.py
import nltk
import streamlit as st
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.summarizers.lex_rank import LexRankSummarizer

# Safely download nltk punkt tokenizers
@st.cache_resource
def download_nltk_data():
    try:
        nltk.data.find('tokenizers/punkt')
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        nltk.download('punkt')
        nltk.download('punkt_tab')

download_nltk_data()


def extractive_summary(text: str, sentences_count: int, method: str = "lsa") -> str:
    """Extracts key sentences from text using Sumy, with a fallback for unpunctuated text."""
    if not text or len(text.split()) < 50:
        return text  # Too short to summarize

    try:
        parser = PlaintextParser.from_string(text, Tokenizer("english"))

        if method == "lexrank":
            summarizer = LexRankSummarizer()
        else:
            summarizer = LsaSummarizer()

        # Prevent requesting more sentences than exist
        actual_sentences = len(parser.document.sentences)
        if actual_sentences <= 1:
            raise ValueError("No sentence punctuation found")

        req_sentences = min(sentences_count, actual_sentences)
        summary = summarizer(parser.document, req_sentences)
        compressed = " ".join([str(sentence) for sentence in summary])

        # Fallback if sumy returns empty or fails to reduce
        if len(compressed.split()) < 10 or len(compressed) >= len(text):
            raise ValueError("Sumy failed to compress effectively.")

        return compressed

    except Exception:
        # FALLBACK: If sumy fails (e.g., no punctuation), use first N sentences
        # based on newline or period splitting, rather than random word sampling.
        # Try splitting on newlines first (common in auto-generated subtitles)
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        if len(lines) > 1:
            # Use first N lines as a rough summary
            target_lines = min(sentences_count, max(5, len(lines) // 3))
            return "\n".join(lines[:target_lines])

        # Try splitting on sentence-ending punctuation
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) > 1:
            target = min(sentences_count, len(sentences))
            return " ".join(sentences[:target])

        # Last resort: return first N*15 words
        words = text.split()
        target_word_count = sentences_count * 15
        if len(words) <= target_word_count:
            return text
        return " ".join(words[:target_word_count])


def get_summary_stats(original_text: str, compressed_text: str) -> dict:
    """Calculates compression stats."""
    orig_words = len(original_text.split())
    comp_words = len(compressed_text.split())

    if orig_words == 0:
        return {"original_words": 0, "compressed_words": 0, "reduction_percent": 0}

    reduction = ((orig_words - comp_words) / orig_words) * 100
    return {
        "original_words": orig_words,
        "compressed_words": comp_words,
        "reduction_percent": round(reduction, 1)
    }
