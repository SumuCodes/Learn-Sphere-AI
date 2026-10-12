# config.py
"""
Configuration file for Learn Sphere AI
"""

from pathlib import Path

# ==========================================================
# Paths
# ==========================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
VECTOR_DB_DIR = DATA_DIR / "vector_db"
TRANSCRIPT_DIR = DATA_DIR / "transcripts"

for folder in [DATA_DIR, VECTOR_DB_DIR, TRANSCRIPT_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# ==========================================================
# App Settings
# ==========================================================

APP_SETTINGS = {
    "title": "Learn Sphere AI",
    "icon": "🌐",
    "layout": "wide",
    "sidebar_state": "expanded",
}

VECTOR_SETTINGS = {
    "chunk_size": 2000,
    "chunk_overlap": 200,
    "top_k": 5,
}

QUIZ_SETTINGS = {
    "default_questions": 10,
    "min_questions": 5,
    "max_questions": 50,
    "difficulty_levels": ["Easy", "Medium", "Hard"],
    "question_types": [
        "Multiple Choice",
        "Multiple Select (MSQ)",
        "Fill in the Blanks",
        "One Word",
        "Mixed Types"
    ],
}

MAX_TRANSCRIPT_CHARS_FOR_QUIZ = 8000
MAX_NOTES_CHARS_FOR_QUIZ = 12000

DEFAULT_SUMMARY_SENTENCES = 80
DEFAULT_SUMMARY_METHOD = "lsa"

# ==========================================================
# AI Providers & Active Models (2026 – updated)
# ==========================================================

SUPPORTED_PROVIDERS = {
    "Google Gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_prefix": "AQ",           # or "AIza" – adjust as needed
        "models": [
            "gemini-3.1-flash-lite",      # 500 RPD – best for daily processing
            "gemini-3.5-flash",           # 20 RPD – fast, but low daily limit
            "gemini-3.1-pro",             # 20 RPD – powerful, but low daily limit
            "gemini-3.5-flash-lite",      # 500 RPD – similar to 3.1 Flash Lite
        ]
    },
    # Groq – updated with GPT-OSS models
    "Groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_prefix": "gsk_",
        "models": [
            "openai/gpt-oss-120b",          # Premium, free tier (200K TPD)
            "openai/gpt-oss-20b",           # Lighter, same free tier
            "llama3-8b-8192",               # reliable fallback (always active)
            "llama3-70b-8192",              # backup
        ]
    },
    "xAI (Grok)": {
        "base_url": "https://api.x.ai/v1",
        "key_prefix": "xai-",
        "models": [
            "grok-3-fast",
            "grok-3-mini",
            "grok-3",
        ]
    },
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "key_prefix": "sk-",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
        ]
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_prefix": "sk-or-v1-",
        "models": [
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "meta-llama/llama-3.1-70b-instruct",
            "meta-llama/llama-3.1-8b-instruct",
            "microsoft/phi-3.5-mini-128k-instruct",
            "deepseek/deepseek-chat",
            "google/gemini-3.5-flash",
            "x-ai/grok-3-fast",
        ]
    },
    "DeepSeek": {
        "base_url": "https://api.deepseek.com",
        "key_prefix": "sk-",
        "models": [
            "deepseek-chat",
        ]
    },
    "Together AI": {
        "base_url": "https://api.together.xyz/v1",
        "key_prefix": "",
        "models": [
            "meta-llama/Llama-3.2-3B-Instruct-Turbo",
            "mistralai/Mistral-7B-Instruct-v0.3",
        ]
    },
}

# ==========================================================
# Routing Defaults
# ==========================================================

DEFAULT_PROVIDER = "Google Gemini"
DEFAULT_MODEL = "gemini-3.1-flash-lite"       # ✅ switched to higher RPD model

DEFAULT_FALLBACK_PROVIDER = "Groq"
DEFAULT_FALLBACK_MODEL = "openai/gpt-oss-20b"   # fallback to OSS

# ==========================================================
# Deprecated Model Translation
# ==========================================================

DEPRECATED_MODELS = {
    # Gemini Legacy -> recommended high‑RPD model
    "gemini-2.0-flash": "gemini-3.1-flash-lite",
    "gemini-2.5-flash": "gemini-3.1-flash-lite",
    "gemini-2.5-pro": "gemini-3.1-pro",
    "gemini-1.5-flash": "gemini-3.1-flash-lite",
    "gemini-1.5-pro": "gemini-3.1-pro",
    "gemini-3.5-flash": "gemini-3.5-flash",        # keep
    "gemini-3.1-flash-lite": "gemini-3.1-flash-lite",

    # Groq Legacy -> OSS models
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "deepseek-r1-distill-llama-70b": "openai/gpt-oss-120b",
    "qwq-32b": "openai/gpt-oss-20b",
    "gemma-7b-it": "openai/gpt-oss-20b",
    "mixtral-8x7b-32768": "openai/gpt-oss-20b",
    "gemma2-9b-it": "openai/gpt-oss-20b",
    "llama3-8b-8192": "llama3-8b-8192",
    "llama3-70b-8192": "llama3-70b-8192",
}

# ==========================================================
# Free Quota Limits – ✅ updated for Gemini 3.1 Flash Lite
# ==========================================================

FREE_TIER_LIMITS = {
    "Google Gemini": {"rpm": 15, "rpd": 500, "tpm": 250000},   # for Flash Lite
    "Groq": {"rpm": 30, "rpd": 1000, "tpm": 8000},
    "xAI (Grok)": {"rpm": 30, "rpd": 500, "tpm": 100000},
    "OpenAI": {"rpm": 500, "rpd": 10000, "tpm": 200000},
    "OpenRouter": {"rpm": 20, "rpd": 1000, "tpm": 100000},
    "DeepSeek": {"rpm": 60, "rpd": 10000, "tpm": 100000},
    "Together AI": {"rpm": 60, "rpd": 1000, "tpm": 100000},
}