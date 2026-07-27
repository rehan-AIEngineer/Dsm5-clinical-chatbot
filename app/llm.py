"""
llm.py
------
Handles LLM answer generation with provider routing:
    Gemini (primary) -> OpenRouter (fallback 1) -> Hugging Face (fallback 2)

Switches to the next provider when the current one fails due to:
    - quota/rate-limit exhausted
    - server down / timeout / connection error

Applies a Zero-Shot Chain-of-Thought prompt template before sending to
whichever provider ends up handling the request.
"""

import os
import requests
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ---- Provider credentials ----
GEMINI_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
HF_KEY = os.getenv("HF_API_KEY", "")

GEMINI_MODEL = "models/gemini-flash-latest"
OPENROUTER_MODEL = "openrouter/auto"
HF_MODEL = "meta-llama/Llama-3.3-70B-Instruct"

_gemini_key_index = 0


# --------------------------------------------------------------------------
# Error classification
# --------------------------------------------------------------------------

def _is_switchable_error(e: Exception) -> bool:
    """True if this error means 'try the next provider/key'."""
    msg = str(e).lower()
    triggers = [
        "quota", "rate limit", "429", "resourceexhausted",
        "timeout", "timed out", "connection", "503", "502", "500",
        "unavailable", "server error", "404", "not found",
    ]
    return any(t in msg for t in triggers)


# --------------------------------------------------------------------------
# Zero-Shot Chain-of-Thought prompt builder
# --------------------------------------------------------------------------

def build_cot_prompt(query: str, context_chunks: list) -> str:
    context_text = "\n\n".join(
        f"[{c['disorder_name']} — {c['section_name']}]\n{c['text']}"
        for c in context_chunks
    )

    prompt = f"""You are a compassionate clinical reference assistant. You answer strictly from the DSM-5-TR context provided below, but you also communicate with warmth and empathy — especially when the question reflects personal worry (e.g., about oneself, a friend, or a family member).
Context:
{context_text}

Question: {query}

Think through this step by step internally (do not show this thinking in your response):
1. Check if the question reflects personal worry or concern (about the person themselves, a friend, or a family member).
2. Identify which part(s) of the context are relevant to the question.
3. Reason about what the context actually says about that.
4. If the question compares two disorders/sections, reason about each separately first, then compare.

Do NOT show your reasoning, step numbers, or any "Step 1/Step 2" text in your response. Output ONLY the final answer directly, with no preamble like "Based on the context" or "Here is my reasoning."

If the question reflected personal worry (step 1), begin your final answer with one brief, warm, non-clinical sentence acknowledging that concern, then give the clinical information. If appropriate, gently suggest consulting a mental health professional for personal situations.

Final Answer:"""
    return prompt


# --------------------------------------------------------------------------
# Provider 1: Gemini
# --------------------------------------------------------------------------

def _call_gemini(prompt: str) -> str:
    global _gemini_key_index
    if not GEMINI_KEYS:
        raise RuntimeError("Gemini quota exhausted: no API keys configured")
    last_error = None
    for _ in range(len(GEMINI_KEYS)):
        try:
            genai.configure(api_key=GEMINI_KEYS[_gemini_key_index])
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            last_error = e
            if _is_switchable_error(e):
                print(f"Gemini key {_gemini_key_index} failed, rotating...")
                _gemini_key_index = (_gemini_key_index + 1) % len(GEMINI_KEYS)
                continue
            raise

    raise RuntimeError(f"All Gemini keys failed: {last_error}")


# --------------------------------------------------------------------------
# Provider 2: OpenRouter
# --------------------------------------------------------------------------

def _call_openrouter(prompt: str) -> str:
    if not OPENROUTER_KEY:
        raise RuntimeError("OpenRouter quota exhausted: no API key configured")

    resp = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
        json={
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter error {resp.status_code}: {resp.text}")
    return resp.json()["choices"][0]["message"]["content"]


# --------------------------------------------------------------------------
# Provider 3: Hugging Face
# --------------------------------------------------------------------------

def _call_huggingface(prompt: str) -> str:
    if not HF_KEY:
        raise RuntimeError("Hugging Face quota exhausted: no API key configured")

    resp = requests.post(
        url="https://router.huggingface.co/v1/chat/completions",
        headers={"Authorization": f"Bearer {HF_KEY}"},
        json={
            "model": HF_MODEL,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Hugging Face error {resp.status_code}: {resp.text}")
    return resp.json()["choices"][0]["message"]["content"]

# --------------------------------------------------------------------------
# Public entry point: routing across all 3 providers
# --------------------------------------------------------------------------
def _strip_reasoning(text: str) -> str:
    """Removes any leaked reasoning/step markers, keeping only the final answer."""
    markers = ["Final Answer:", "Answer:", "**Final Answer:**", "**Answer:**"]
    for marker in markers:
        if marker in text:
            return text.split(marker, 1)[1].strip()
    return text.strip()


def generate_answer(query: str, context_chunks: list) -> str:
    prompt = build_cot_prompt(query, context_chunks)

    providers = [
        ("Gemini", _call_gemini),
        ("OpenRouter", _call_openrouter),
        ("Hugging Face", _call_huggingface),
    ]

    last_error = None
    for name, fn in providers:
        try:
            raw = fn(prompt)
            return _strip_reasoning(raw)
        except Exception as e:
            last_error = e
            if _is_switchable_error(e):
                print(f"{name} failed ({e}), switching to next provider...")
                continue
            raise

    raise RuntimeError(f"All providers failed. Last error: {last_error}")



def expand_to_clinical_terms(query: str) -> str:
    """
    Rewrites a casual/colloquial symptom description into clinical DSM-5
    terminology, to improve embedding similarity against clinical text.
    Tries Gemini first, falls back to OpenRouter, then to the original
    query if both fail.
    """
    prompt = f"""Rewrite the following person's description of their experience into formal clinical/psychiatric terminology (DSM-5 style terms only). Output ONLY a short comma-separated list of clinical terms — no sentences, no explanation.

Person's description: "{query}"

Clinical terms:"""

    # Try Gemini first
    try:
        if not GEMINI_KEYS:
            raise RuntimeError("no Gemini keys configured")
        genai.configure(api_key=GEMINI_KEYS[_gemini_key_index])
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        expanded = response.text.strip()
        print(f"DEBUG - Expanded query (Gemini): {expanded}")
        return f"{query} ({expanded})"
    except Exception as e:
        print(f"DEBUG - Gemini expansion failed: {e}")

    # Fallback: OpenRouter
    try:
        expanded = _call_openrouter(prompt)
        print(f"DEBUG - Expanded query (OpenRouter): {expanded}")
        return f"{query} ({expanded})"
    except Exception as e:
        print(f"DEBUG - OpenRouter expansion failed: {e}")

    # Both failed — use original query unmodified
    return query