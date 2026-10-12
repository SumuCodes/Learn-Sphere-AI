# utils/api_utils.py
"""
Utility functions for AI providers.
Ping-pong dual-engine: Primary ↔ Safety Net with smart 429 handling.
2 keys = instant switch, 1 key = wait with backoff.
"""

import time
import json
import re
import os
import tempfile
import streamlit as st
import logging

logger = logging.getLogger(__name__)

from openai import OpenAI

from config import (
    SUPPORTED_PROVIDERS,
    DEFAULT_PROVIDER,
    DEFAULT_MODEL,
    DEFAULT_FALLBACK_PROVIDER,
    DEFAULT_FALLBACK_MODEL,
    DEPRECATED_MODELS,
    FREE_TIER_LIMITS,
)


class CreditError(Exception):
    pass


class RateLimitError(Exception):
    pass


# ---------- RETRY & BACKOFF CONFIG ----------
_MAX_RETRIES = 10               # was 3
_BASE_RETRY_DELAY = 5.0         # was 2.0
_MAX_BACKOFF_WAIT = 120.0       # was 30.0

# ---------- THROTTLE (s) ----------
# Gemini free tier: 5 RPM → 1 request every 12s minimum. We use 30s for safety.
_THROTTLE_BY_PROVIDER = {
    "Google Gemini": 30.0,      # 2 RPM – well under limit
    "Groq": 22.0,
    "xAI (Grok)": 3.0,
    "OpenAI": 2.0,
    "OpenRouter": 3.0,
    "DeepSeek": 3.0,
    "Together AI": 5.0,
}
_DEFAULT_THROTTLE = 3.0

_COOLDOWN_BY_PROVIDER = {
    "Google Gemini": 60,
    "Groq": 60,
    "xAI (Grok)": 20,
    "OpenAI": 10,
    "OpenRouter": 20,
    "DeepSeek": 20,
    "Together AI": 20,
}
_DEFAULT_COOLDOWN = 20

# ---------- SIMPLE PER-PROVIDER THROTTLE (no file locking) ----------
_last_request_time = {}

def _throttle(payload_text: str = ""):
    """Enforce a minimum interval between API calls for the current provider."""
    provider = st.session_state.get("provider", "")
    if not provider:
        return

    interval = _THROTTLE_BY_PROVIDER.get(provider, _DEFAULT_THROTTLE)
    if interval <= 0:
        return

    now = time.time()
    last = _last_request_time.get(provider, 0)
    wait_time = max(0, interval - (now - last))
    if wait_time > 0:
        logger.info("Throttling %s: sleeping %.2f seconds", provider, wait_time)
        time.sleep(wait_time)

    _last_request_time[provider] = time.time()


# ---------- TOKEN ESTIMATION ----------
def get_estimated_tokens(text: str) -> int:
    if not text:
        return 0
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model("gpt-4")
        return len(encoding.encode(text))
    except (ImportError, Exception):
        word_count = len(text.split())
        return int(word_count * 1.3) + 1


# ---------- RPD TRACKING ----------
def _get_rpd_used(provider):
    today = time.strftime("%Y-%m-%d")
    return st.session_state.get(f"rpd_{provider}_{today}", 0)


def _rpd_exhausted(provider):
    limits = FREE_TIER_LIMITS.get(provider, {})
    rpd_cap = limits.get("rpd", 0)
    if not rpd_cap:
        return False
    return _get_rpd_used(provider) >= rpd_cap - 1


# ---------- SESSION MANAGEMENT ----------
def initialize_api_session():
    defaults = {
        "provider": DEFAULT_PROVIDER,
        "model": DEFAULT_MODEL,
        "api_keys": {},
        "token_usage": {},
        "fallback_provider": DEFAULT_FALLBACK_PROVIDER,
        "fallback_model": DEFAULT_FALLBACK_MODEL,
        "_using_fallback": False,
        "_original_provider": DEFAULT_PROVIDER,
        "_original_model": DEFAULT_MODEL,
        "_primary_429_time": 0.0,
        "_fallback_429_time": 0.0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "api_key" in st.session_state and st.session_state.api_key:
        provider = st.session_state.provider
        if provider not in st.session_state.api_keys:
            st.session_state.api_keys[provider] = st.session_state.api_key

    if st.session_state.model in DEPRECATED_MODELS:
        fixed = DEPRECATED_MODELS[st.session_state.model]
        st.session_state.model = fixed
        st.toast(f"🔄 Auto-fixed model → {fixed}", icon="⚠️")
    if st.session_state.fallback_model in DEPRECATED_MODELS:
        st.session_state.fallback_model = DEPRECATED_MODELS[st.session_state.fallback_model]


def save_api_settings(provider, model, api_key):
    st.session_state.provider = provider
    st.session_state.model = model
    st.session_state._original_provider = provider
    st.session_state._original_model = model
    st.session_state._using_fallback = False
    if api_key:
        if "api_keys" not in st.session_state:
            st.session_state.api_keys = {}
        st.session_state.api_keys[provider] = api_key


def save_fallback_settings(provider, model):
    st.session_state.fallback_provider = provider
    st.session_state.fallback_model = model


def get_api_key(provider=None):
    if provider is None:
        provider = st.session_state.provider
    return st.session_state.get("api_keys", {}).get(provider, "")


def get_models(provider):
    return SUPPORTED_PROVIDERS.get(provider, {}).get("models", [])


def create_client(provider=None, api_key=None):
    if provider is None:
        provider = st.session_state.provider
    if api_key is None:
        api_key = get_api_key(provider)

    api_key = str(api_key).strip()
    if not api_key:
        raise ValueError(f"No API key provided for {provider}.")

    provider_info = SUPPORTED_PROVIDERS.get(provider, {})
    base_url = provider_info.get("base_url", "https://api.openai.com/v1")

    return OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)


# ---------- API KEY VALIDATION ----------
def validate_api_key(provider: str, api_key: str) -> tuple[bool, str]:
    api_key = api_key.strip()
    if not api_key:
        return False, "API key cannot be empty."

    info = SUPPORTED_PROVIDERS.get(provider, {})
    prefix = info.get("key_prefix", "")
    if prefix and not api_key.startswith(prefix):
        return False, f"Invalid key format. {provider} keys must start with '{prefix}'."

    test_models = info.get("models", [])
    if not test_models:
        return False, f"No models configured for {provider}."

    last_error = None
    for model in test_models:
        try:
            client = create_client(provider, api_key)
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=2,
                timeout=10.0
            )
            return True, ""
        except Exception as e:
            last_error = e
            err = str(e).lower()
            # Model errors → try next
            if any(kw in err for kw in [
                "decommissioned", "not found", "404",
                "model", "invalid_model", "not support",
                "does not exist", "unavailable", "not available"
            ]):
                print(f"⚠️ Model '{model}' unavailable on {provider}: {e}. Trying next...")
                continue
            # Auth errors
            if any(kw in err for kw in ["401", "403", "authentication", "permission", "invalid", "unauthorized"]):
                return False, f"Authentication failed: Invalid API key for {provider}."
            # Credit errors
            if "402" in err or "credit" in err or "balance" in err:
                return False, f"Insufficient account balance/credits on {provider}."
            # Rate limit – key works
            if "429" in err or "quota" in err:
                return True, ""
            # Other errors – try next model
            continue

    if last_error:
        return False, f"Validation failed for all models. Last error: {str(last_error)[:120]}"
    return False, f"No suitable model found for {provider}."


# ---------- HELPERS ----------
def api_ready():
    return bool(get_api_key()) and bool(st.session_state.provider) and bool(st.session_state.model)


def current_model():
    return st.session_state.model


def current_provider():
    return st.session_state.provider


def fallback_ready():
    fb_provider = st.session_state.get("fallback_provider", "")
    fb_model = st.session_state.get("fallback_model", "")
    fb_key = get_api_key(fb_provider)
    return bool(fb_provider) and bool(fb_model) and bool(fb_key)


def _parse_retry_wait(error_str):
    match = re.search(r'try again in (\d+)ms', error_str)
    if match:
        return int(match.group(1)) / 1000.0
    match = re.search(r'try again in ([\d.]+)s', error_str)
    if match:
        return float(match.group(1))
    match = re.search(r'retry_after[:\s]+(\d+)', error_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r'wait[:\s]+(\d+)\s*(?:ms|milliseconds?)', error_str, re.IGNORECASE)
    if match:
        return int(match.group(1)) / 1000.0
    match = re.search(r'(\d+)\s*(?:seconds?|secs?)', error_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r'(\d+)\s*(?:minutes?|mins?)', error_str, re.IGNORECASE)
    if match:
        return int(match.group(1)) * 60.0
    return None


def _fix_deprecated_model():
    model = st.session_state.model
    if model in DEPRECATED_MODELS:
        fixed = DEPRECATED_MODELS[model]
        st.session_state.model = fixed
        st.toast(f"🔄 Model updated: {model} → {fixed}", icon="⚠️")
        return True
    return False


def _switch_to_fallback():
    if not fallback_ready():
        return False

    fallback_429_time = st.session_state.get("_fallback_429_time", 0)
    if fallback_429_time > 0:
        fb_provider = st.session_state.fallback_provider
        cooldown = _COOLDOWN_BY_PROVIDER.get(fb_provider, _DEFAULT_COOLDOWN)
        if time.time() - fallback_429_time < cooldown:
            return False

    st.session_state.provider = st.session_state.fallback_provider
    st.session_state.model = st.session_state.fallback_model
    st.session_state._using_fallback = True
    st.toast(
        f"⚡ Switched to {st.session_state.fallback_provider} ({st.session_state.fallback_model})",
        icon="🔄"
    )
    return True


def _switch_to_primary():
    primary = st.session_state._original_provider
    primary_model = st.session_state._original_model

    if not get_api_key(primary):
        return False

    primary_429_time = st.session_state.get("_primary_429_time", 0)
    if primary_429_time > 0:
        cooldown = _COOLDOWN_BY_PROVIDER.get(primary, _DEFAULT_COOLDOWN)
        if time.time() - primary_429_time < cooldown:
            return False

    st.session_state.provider = primary
    st.session_state.model = primary_model
    st.session_state._using_fallback = False
    st.toast(
        f"🔄 Back to {primary} ({primary_model})",
        icon="✅"
    )
    return True


# ---------- CORE GENERATE FUNCTION ----------
def generate_response(
    prompt: str,
    system_message: str = None,
    temperature: float = 0.7,
    max_tokens: int = None,
    **kwargs
) -> str:

    if not api_ready():
        raise ValueError("API key not configured in Workspace.")

    _fix_deprecated_model()

    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})

    full_payload = (system_message or "") + " " + (prompt or "")
    estimated_tokens = get_estimated_tokens(full_payload)

    def _provider_can_handle(provider_name: str) -> bool:
        limits = FREE_TIER_LIMITS.get(provider_name, {})
        tpm_limit = limits.get("tpm", 0)
        if tpm_limit == 0:
            return True
        return estimated_tokens <= tpm_limit

    primary_ok = _provider_can_handle(st.session_state.provider)
    fallback_ok = fallback_ready() and _provider_can_handle(st.session_state.fallback_provider)

    if not primary_ok and not fallback_ok:
        primary_limit = FREE_TIER_LIMITS.get(st.session_state.provider, {}).get("tpm", "N/A")
        fallback_limit = FREE_TIER_LIMITS.get(st.session_state.fallback_provider, {}).get("tpm", "N/A")
        raise ValueError(
            f"Your input exceeds the free-tier Tokens-Per-Minute (TPM) rate limit "
            f"for all configured providers.\n"
            f"Estimated tokens: {estimated_tokens}\n"
            f"TPM limits:\n"
            f"  - {st.session_state.provider}: {primary_limit}\n"
            f"  - {st.session_state.fallback_provider}: {fallback_limit}\n\n"
            f"💡 Please split your transcript into smaller chunks (e.g., 100k tokens per chunk), "
            f"wait a minute, or use a model with a higher TPM quota."
        )

    if not primary_ok and fallback_ok:
        _switch_to_fallback()
        st.toast(f"⚠️ Primary TPM too low. Using fallback ({st.session_state.fallback_provider}).", icon="🔄")

    for attempt in range(_MAX_RETRIES + 1):
        provider = st.session_state.provider

        # Preemptive RPD check
        if _rpd_exhausted(provider):
            if not st.session_state._using_fallback:
                st.toast(f"⚠️ Daily limit almost reached for {provider}. Switching to fallback...", icon="⏳")
                if _switch_to_fallback():
                    continue
            else:
                raise RateLimitError(f"Daily Request (RPD) limit reached for {provider}. Please wait until tomorrow or switch providers in settings.")

        # Throttle
        _throttle(payload_text=full_payload)

        provider = st.session_state.provider
        model = st.session_state.model

        kwargs_dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs_dict["max_tokens"] = max_tokens

        for reserved_key in ("model", "messages"):
            kwargs.pop(reserved_key, None)

        kwargs_dict.update(kwargs)

        try:
            client = create_client(provider)
            response = client.chat.completions.create(**kwargs_dict)

            if not response.choices:
                raise RuntimeError(f"Empty choices returned by {provider} ({model}).")

            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError(f"Empty content returned by {provider} ({model}). Possible content filter or refusal.")

            if hasattr(response, 'usage') and response.usage:
                tokens_used = response.usage.total_tokens
                if 'token_usage' not in st.session_state:
                    st.session_state.token_usage = {}
                st.session_state.token_usage[provider] = (
                    st.session_state.token_usage.get(provider, 0) + tokens_used
                )

            today = time.strftime("%Y-%m-%d")
            rpd_key = f"rpd_{provider}_{today}"
            st.session_state[rpd_key] = st.session_state.get(rpd_key, 0) + 1

            return content

        except Exception as e:
            error_str = str(e)

            if "402" in error_str or "credits" in error_str.lower() or "insufficient" in error_str.lower():
                raise CreditError("API credits exhausted. Add credits or switch to a free model.")

            elif "429" in error_str or "rate limit" in error_str.lower() or "resource exhausted" in error_str.lower():
                if st.session_state._using_fallback:
                    st.session_state._fallback_429_time = time.time()
                else:
                    st.session_state._primary_429_time = time.time()

                if "daily" in error_str.lower() or "quota" in error_str.lower():
                    today = time.strftime("%Y-%m-%d")
                    rpd_cap = FREE_TIER_LIMITS.get(provider, {}).get("rpd", 0)
                    if rpd_cap and rpd_cap > 0:
                        st.session_state[f"rpd_{provider}_{today}"] = rpd_cap

                switched = False

                if not st.session_state._using_fallback:
                    if fallback_ready() and _provider_can_handle(st.session_state.fallback_provider):
                        switched = _switch_to_fallback()
                    else:
                        logger.info("Payload too large for fallback; will retry primary after cooldown.")
                else:
                    if _provider_can_handle(st.session_state._original_provider):
                        switched = _switch_to_primary()

                if switched:
                    continue

                if attempt < _MAX_RETRIES:
                    server_wait = _parse_retry_wait(error_str)
                    wait = max(server_wait or 0, _BASE_RETRY_DELAY * (2 ** attempt))
                    wait = min(wait, _MAX_BACKOFF_WAIT)
                    if estimated_tokens > FREE_TIER_LIMITS.get(provider, {}).get("tpm", 0) * 0.5:
                        wait = max(wait, 60.0)
                    time.sleep(wait)
                else:
                    raise RateLimitError(f"Rate limit exhausted on {provider} after {_MAX_RETRIES} retries.")

            elif "404" in error_str or "not_found" in error_str.lower() or "not found" in error_str.lower():
                if _fix_deprecated_model():
                    continue

                hint = ""
                if st.session_state.provider == "Google Gemini":
                    hint = (
                        "\n\n💡 Ensure your Google API key was obtained from **Google AI Studio** "
                        "(aistudio.google.com), not Google Cloud Console / Vertex AI."
                    )
                raise RuntimeError(
                    f"Model '{st.session_state.model}' was not found on {st.session_state.provider}."
                    f"{hint}"
                )

            elif "response_format" in error_str or ("json" in error_str.lower() and "not support" in error_str.lower()):
                kwargs_dict.pop("response_format", None)
                try:
                    client = create_client(provider)
                    response = client.chat.completions.create(**kwargs_dict)
                    if not response.choices or not response.choices[0].message.content:
                        raise RuntimeError("Empty response after JSON fallback.")
                    return response.choices[0].message.content
                except Exception as inner_e:
                    raise RuntimeError(f"AI request failed after JSON fallback: {inner_e}")

            else:
                raise RuntimeError(f"AI request failed: {e}")

    raise RuntimeError("generate_response: unexpected exit")


# ---------- CHUNK NOTES GENERATION ----------
def generate_chunk_notes(transcript_chunk: str) -> dict:
    """Send a transcript chunk to the LLM and return structured topics."""
    word_count = len(transcript_chunk.split())
    if word_count < 500:
        excerpt_len = "1‑2"
    elif word_count < 1500:
        excerpt_len = "2‑3"
    else:
        excerpt_len = "3‑4"

    system_prompt = f"""
You are an expert academic assistant processing a chunk of a lecture transcript. The full lecture is very long (up to 15 hours), so this chunk may contain a large volume of information.

Your goal is to **distil** the chunk into a small number of **high‑level, self‑contained topics** (maximum 3) that can stand alone as revision material. Do NOT create topics for every minor point – merge related ideas.

For each topic, produce:

- `topic_title` – a short, descriptive heading (≤10 words) that clearly indicates the concept.
- `topic_key` – a snake_case identifier (e.g., "gradient_descent").
- `notes` – detailed but concise Markdown notes. Use subheadings (##), bullet points, and numbered lists. Focus on **mechanisms, cause‑effect relationships, edge cases, and comparisons** – not just definitions. Include key formulas, examples, or diagrams if they are mentioned.
- `excerpt` – a **self‑contained passage** of {excerpt_len} sentences (verbatim or lightly paraphrased) that **best represents the core idea** of this topic. This excerpt will be used later to generate **quiz questions** – so it must:

   - Explain a **concept, mechanism, or consequence** (not just a name or definition).
   - Be understandable without the surrounding context.
   - Contain enough depth to form a question that tests understanding, not recall.

**Rules for the excerpt:**
- AVOID: "X is a tool used for Y" (trivia).
- PREFER: "When X happens, Y occurs because Z, which leads to..." (mechanism).

**Continuity:** If the chunk starts with a "tail" (sentence from previous chunk), use it only for context – do NOT create topics from it.

**Output format:** Return a **valid JSON object** with key "sections" containing an array of objects, each with: topic_key, topic_title, notes, excerpt.

Example:
{{
  "sections": [
    {{
      "topic_key": "backpropagation",
      "topic_title": "Backpropagation Algorithm",
      "notes": "## Mechanism\\n- Computes gradients by chain rule...\\n## Challenges\\n- Vanishing gradients...",
      "excerpt": "During backpropagation, gradients are computed by propagating errors backward through the network. The chain rule is applied layer by layer, which can cause gradients to vanish or explode if the network is deep."
    }}
  ]
}}
"""

    for attempt in range(3):
        try:
            raw_response = generate_response(
                prompt=f"Transcript Chunk:\n\n{transcript_chunk}",
                system_message=system_prompt,
                temperature=0.3,
                max_tokens=2000
            )

            print("\n" + "="*60)
            print(f"RAW RESPONSE (first 800 chars):\n{raw_response[:800] if raw_response else 'EMPTY'}")
            print("="*60 + "\n")

            if not raw_response:
                logger.warning("generate_response returned empty/None for chunk notes.")
                return {"sections": []}

            cleaned = raw_response.replace("```json", "").replace("```", "").strip()
            print(f"CLEANED RESPONSE (first 500):\n{cleaned[:500]}")

            try:
                parsed = json.loads(cleaned)
                if "sections" in parsed:
                    sections = parsed["sections"]
                    print(f"✅ PARSED SECTIONS COUNT: {len(sections)}")
                    return parsed
                else:
                    print("❌ JSON missing 'sections' key.")
                    return {"sections": []}
            except json.JSONDecodeError as e:
                print(f"❌ JSON parse error: {e}")
                match = re.search(r'(\{.*\})', cleaned, re.DOTALL)
                if match:
                    try:
                        parsed = json.loads(match.group(1))
                        if "sections" in parsed:
                            print(f"✅ EXTRACTED SECTIONS COUNT: {len(parsed['sections'])}")
                            return parsed
                    except Exception as ex:
                        print(f"❌ Regex extraction also failed: {ex}")
                return {"sections": []}

        except (CreditError, RateLimitError) as e:
            print(f"❌ Critical error: {e}")
            raise
        except Exception as e:
            logger.error("Error generating chunk notes (attempt %d): %s", attempt + 1, e)
            time.sleep(1)
    return {"sections": []}


# ---------- FREE MODEL SUGGESTIONS (updated for high‑RPD models) ----------
def get_free_model_suggestions():
    return [
        ("Google Gemini", "gemini-3.1-flash-lite", "High RPD (500/day)"),
        ("Groq", "openai/gpt-oss-120b", "High-quality, free tier (200K TPD)"),
        ("Google Gemini", "gemini-3.5-flash", "Fast, but low RPD (20/day)"),
    ]