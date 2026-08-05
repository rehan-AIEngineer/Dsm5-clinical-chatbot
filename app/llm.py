"""
llm.py
------
Handles LLM answer generation with Gemini (primary).

Simplified version: only Gemini remains.
Expansion query function stays.
"""

import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ---- Gemini credentials ----
GEMINI_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
GEMINI_MODEL = "models/gemini-flash-latest"

_gemini_key_index = 0


# --------------------------------------------------------------------------
# Error classification
# --------------------------------------------------------------------------

def _is_switchable_error(e: Exception) -> bool:
    """True if this error means 'try the next key'."""
    msg = str(e).lower()
    triggers = [
        "quota",
        "rate limit",
        "429",
        "resourceexhausted",
        "timeout",
        "timed out",
        "connection",
        "503",
        "502",
        "500",
        "unavailable",
        "server error",
    ]
    return any(t in msg for t in triggers)


# --------------------------------------------------------------------------
# Prompt building
# --------------------------------------------------------------------------

def build_cot_prompt(query: str, context_chunks: list):
    context_text = "\n\n".join(
        f"[{c['disorder_name']} — {c['section_name']}]\n{c['text']}"
        for c in context_chunks
    )

    prompt = f"""
You are an empathetic, supportive, and clinically knowledgeable AI assistant designed to help caregivers navigating mental health challenges with loved ones. You ground your diagnostic knowledge in the DSM-5-TR.

TONE & EMPATHY GUIDELINES:

1. Always lead with genuine empathy and emotional validation before diving into diagnostic criteria.
2. Avoid bulleted lists of intake questions. Ask no more than ONE or TWO gentle clarifying questions per response.
3. Use warm, accessible language. Avoid sounding like a rigid textbook or search engine.

RAG & DIAGNOSTIC GUIDELINES:

1. NEVER tell the user "the provided context does not contain" or expose your internal document limitations.
2. When discussing psychotic symptoms, always account for:
   - Timeline rules (e.g., 6 months for schizophrenia vs 1 month for brief psychosis).
   - Negative symptoms (flat affect, avolition, alogia).
   - Substance exclusion (e.g., cannabis or medication effects).
3. Always frame diagnostic criteria as possibilities for a doctor to evaluate, not a definitive diagnosis.

=========================
DSM-5-TR CONTEXT
=========================

{context_text}

=========================
USER QUESTION
=========================

{query}

=========================
FINAL ANSWER
=========================
"""

    return prompt


# --------------------------------------------------------------------------
# Provider: Gemini (with multiple keys rotation)
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

    raise RuntimeError(f"All Gemini keys failed. Last error: {last_error}")


# --------------------------------------------------------------------------
# Disclaimer Logic
# --------------------------------------------------------------------------

def _needs_disclaimer(query: str) -> bool:
    """
    Returns True if the response needs a disclaimer.
    Only for personal/assessment questions with symptoms, NOT for informational queries.
    """
    informational_keywords = [
        "what is", "define", "explain", "symptoms of", "criteria for",
        "prevalence", "difference between", "diagnostic criteria"
    ]
    
    query_lower = query.lower()
    
    for kw in informational_keywords:
        if query_lower.startswith(kw) or f" {kw}" in query_lower:
            return False
    
    symptom_keywords = [
        "sad", "depressed", "anxiety", "panic", "worried", "stress",
        "fear", "hopeless", "worthless", "sleep", "insomnia", "fatigue",
        "tired", "appetite", "hallucination", "mania", "suicidal", "self harm",
        "udaas", "ghabrahat", "fikr", "tension", "neend",
        "thakan", "bhook", "bechaini", "dil nahi lagta", "zindagi ka koi maqsad"
    ]
    
    for kw in symptom_keywords:
        if kw in query_lower:
            return True
    
    personal_keywords = ["my", "me", "i", "have", "feel", "am", "been"]
    for kw in personal_keywords:
        if kw in query_lower.split():
            return True
    
    return False


def _needs_emergency_disclaimer(query: str) -> bool:
    """
    Returns True if this is a high-risk/suicidal query.
    """
    EMERGENCY_KEYWORDS = [
        "suicide", "suicidal", "kill myself", "end my life",
        "hurt myself", "self harm", "i want to die",
        "life is not worth living", "better off without me",
        "khudkushi", "mar jana", "zindagi ka koi maqsad nahi", "khud ko nuqsan",
    ]
    query_lower = query.lower()
    return any(kw in query_lower for kw in EMERGENCY_KEYWORDS)


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------

def _strip_reasoning(text: str) -> str:
    """Removes any leaked reasoning/step markers, keeping only the final answer."""
    markers = ["Final Answer:", "Answer:", "**Final Answer:**", "**Answer:**"]
    for marker in markers:
        if marker in text:
            return text.split(marker, 1)[1].strip()
    return text.strip()


def generate_answer(query: str, context_chunks: list) -> str:
    """Generate answer using Gemini (with multi-key rotation)."""
    if not GEMINI_KEYS:
        return "Error: Gemini API key not configured. Please set GEMINI_API_KEYS in .env"
    
    if not context_chunks:
        return "I couldn't find relevant information in the DSM-5-TR reference for this question."

    prompt = build_cot_prompt(query, context_chunks)
    
    try:
        raw = _call_gemini(prompt)
        answer = _strip_reasoning(raw)
        
        # ---- Add disclaimer (only if needed and not already present) ----
        if _needs_disclaimer(query):
            disclaimer = "\n\n---\n📌 **Note:** I am an AI educational assistant based on DSM-5-TR. This information is for educational purposes only and is not a substitute for a qualified psychiatrist's or clinical psychologist's diagnosis or professional advice."
            
            if _needs_emergency_disclaimer(query):
                disclaimer = "\n\n⚠️ **Emergency Notice:** I am an AI educational assistant and not a substitute for emergency or crisis care. If you are having thoughts of harming yourself or others, please contact emergency services immediately or reach out to a crisis helpline."
            
            # ✅ Check if disclaimer already exists (prevent duplicate)
            if "I am an AI educational assistant" not in answer:
                answer += disclaimer
        
        return answer
        
    except Exception as e:
        return f"Error generating response: {str(e)}"


# --------------------------------------------------------------------------
# Query Expansion (Stays as is)
# --------------------------------------------------------------------------

def expand_to_clinical_terms(query: str) -> str:
    """
    Rewrites a casual/colloquial symptom description into clinical DSM-5
    terminology, to improve embedding similarity against clinical text.
    Uses Gemini for expansion.
    """
    prompt = f"""Rewrite the following person's description of their experience into formal clinical/psychiatric terminology (DSM-5 style terms only). Output ONLY a short comma-separated list of clinical terms — no sentences, no explanation.

Person's description: "{query}"

Clinical terms:"""

    try:
        if not GEMINI_KEYS:
            print("DEBUG - No Gemini keys configured for expansion")
            return query
        
        genai.configure(api_key=GEMINI_KEYS[_gemini_key_index])
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        expanded = response.text.strip()
        print(f"DEBUG - Expanded query (Gemini): {expanded}")
        return f"{query} ({expanded})"
        
    except Exception as e:
        print(f"DEBUG - Gemini expansion failed: {e}")
        return query