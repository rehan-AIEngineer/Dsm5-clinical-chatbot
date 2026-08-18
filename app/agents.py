"""
app/agents.py
-------------
Unified Multi-Agent Pipeline for Mental Health, Caregiving, & Grief Support.

Agent 1: Intent & Safety Guardrail Classifier.
Agent 2: DSM-5-TR Clinical & Grief Reasoning Engine.
"""

import json
import time
import logging
from typing import Dict, Any
import google.generativeai as genai

from app.llm import GEMINI_KEYS, GEMINI_MODEL, _is_switchable_error

logger = logging.getLogger(__name__)

PRIMARY_MODEL_FLASH = "models/gemini-3.5-flash-lite"
PRIMARY_MODEL_PRO = "models/gemini-3.5-flash"
FALLBACK_MODEL = "models/gemini-3.5-flash-lite"

_gemini_key_index = 0


# --------------------------------------------------------------------------
# Shared Helpers
# --------------------------------------------------------------------------

def _call_gemini_json(prompt: str, model: str = PRIMARY_MODEL_FLASH, json_mode: bool = True) -> str:
    """
    Calls Gemini API with key rotation and model fallback, optionally requesting JSON format.
    """
    global _gemini_key_index

    if not GEMINI_KEYS:
        raise RuntimeError("Gemini API keys are not configured in GEMINI_KEYS.")

    models_to_try = [model]
    for m in [PRIMARY_MODEL_FLASH, "gemini-1.5-flash", PRIMARY_MODEL_PRO, FALLBACK_MODEL]:
        if m and m not in models_to_try:
            models_to_try.append(m)

    last_exception = None

    for model_name in models_to_try:
        for _ in range(len(GEMINI_KEYS)):
            current_key = GEMINI_KEYS[_gemini_key_index]
            try:
                genai.configure(api_key=current_key)
                generation_config = {"response_mime_type": "application/json"} if json_mode else {}
                gmodel = genai.GenerativeModel(
                    model_name,
                    generation_config=generation_config
                )
                response = gmodel.generate_content(prompt)
                if response and response.text:
                    return response.text
                raise ValueError("Empty response text returned from Gemini.")
            except Exception as e:
                last_exception = e
                if _is_switchable_error(e):
                    logger.warning(
                        "Gemini model %s key index %d failed with error (%s). Rotating key...",
                        model_name,
                        _gemini_key_index,
                        str(e)[:120]
                    )
                    _gemini_key_index = (_gemini_key_index + 1) % len(GEMINI_KEYS)
                    time.sleep(0.5)
                    continue
                break

    raise RuntimeError(f"All Gemini models and keys failed. Last error: {last_exception}")


def _parse_json_response(raw_text: str) -> dict:
    """
    Parses a raw Gemini response string into a Python dict.

    Strips markdown code fences (```json ... ```) if present,
    then runs json.loads().

    Parameters:
        raw_text (str): Raw response text from Gemini (may include markdown fences).

    Returns:
        dict: Parsed JSON data.

    Raises:
        json.JSONDecodeError: If the cleaned text is not valid JSON.
        ValueError: If the parsed result is not a dict.
    """
    cleaned = raw_text.strip()

    # Strip markdown code fences if present
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    data = json.loads(cleaned)

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object (dict), got {type(data).__name__}")

    return data


# --------------------------------------------------------------------------
# Agent 1: Intent & Safety Guardrail
# --------------------------------------------------------------------------

def run_agent_1_guardrail(user_message: str, session_context: dict) -> dict:
    """
    Agent 1: Intent & Safety Guardrail Classifier.

    Classifies the user message into exactly one category:
    CLINICAL_QUERY, GRIEF_WORKBOOK, CRISIS, or OFF_TOPIC.

    Parameters:
        user_message (str): The message or workbook entry provided by the user.
        session_context (dict): Session context dictionary containing feature_mode,
                                user_role, diagnosis_status, clinical_data, grief_data, etc.

    Returns:
        dict: A dictionary containing:
              - 'category': 'CLINICAL_QUERY' | 'GRIEF_WORKBOOK' | 'CRISIS' | 'OFF_TOPIC'
              - 'passive_risk_flag': bool
              - 'reasoning': str
              In case of failure or malformed JSON, returns a fail-safe CRISIS dict:
              {"category": "CRISIS", "passive_risk_flag": True, "reasoning": "classification_failed_fail_safe"}
    """
    valid_categories = {"CLINICAL_QUERY", "GRIEF_WORKBOOK", "CRISIS", "OFF_TOPIC"}

    context_json = json.dumps(session_context)

    prompt = f"""You are an Intent and Safety Classifier for a Mental Health and Grief Support System.

Categorize the user's input into EXACTLY ONE category:
1. CLINICAL_QUERY: Mental health concerns, symptoms, psychiatric coping, or caregiving.
2. GRIEF_WORKBOOK: Reflections on loss, bereavement, memories, or workbook discussions.
   NOTE: Deep sadness/yearning for the deceased is GRIEF, not CRISIS, unless active
   self-harm or a specific plan is stated. However, if the message expresses passive
   death wishes (e.g. wanting to "join" the deceased, "not waking up"), set
   "passive_risk_flag": true even while keeping the category as GRIEF_WORKBOOK.
3. CRISIS: Active suicide threats, explicit self-harm plans, intent to harm others, or
   immediate physical emergency.
4. OFF_TOPIC: Coding requests, math, software dev, trivia, recipes, or unrelated tasks.

Context: {context_json}
User input: {user_message}

Output strictly JSON with this schema:
{{"category": "CLINICAL_QUERY" | "GRIEF_WORKBOOK" | "CRISIS" | "OFF_TOPIC",
 "passive_risk_flag": true | false,
 "reasoning": "..."}}"""

    try:
        raw_response = _call_gemini_json(prompt, model=PRIMARY_MODEL_FLASH)

        data = _parse_json_response(raw_response)

        category = data.get("category")
        if category not in valid_categories:
            raise ValueError(f"Invalid or missing category in response: '{category}'")

        passive_risk_flag = bool(data.get("passive_risk_flag", False))
        reasoning = str(data.get("reasoning", ""))

        return {
            "category": category,
            "passive_risk_flag": passive_risk_flag,
            "reasoning": reasoning,
        }

    except Exception as e:
        logger.error("Agent 1 classification failed: %s", str(e), exc_info=True)
        return {
            "category": "CRISIS",
            "passive_risk_flag": True,
            "reasoning": "classification_failed_fail_safe",
        }


# --------------------------------------------------------------------------
# Agent 2: DSM-5-TR Clinical & Grief Reasoning Engine
# --------------------------------------------------------------------------

# Schema keys expected per feature_mode
_CLINICAL_REQUIRED_KEYS = {"matched_criteria", "timeline_assessment", "ruleouts", "clinical_key_points"}
_GRIEF_REQUIRED_KEYS = {"primary_emotions", "pgd_criteria_status", "recommended_response_angle"}

# Fail-safe dicts per feature_mode
_CLINICAL_FAILSAFE = {
    "matched_criteria": [],
    "timeline_assessment": "unavailable",
    "ruleouts": [],
    "clinical_key_points": ["assessment_failed_fail_safe"],
}

_GRIEF_FAILSAFE = {
    "primary_emotions": [],
    "pgd_criteria_status": "unavailable",
    "recommended_response_angle": "assessment_failed_fail_safe",
}


def _retrieve_dsm5_context(query_text: str, top_k: int = 8) -> list:
    """
    Retrieves relevant DSM-5-TR chunks via graph.py's query analysis & retrieval pipeline.

    Parameters:
        query_text (str): Text to analyze and retrieve against dsm5_chunks.
        top_k (int): Ignored/optional as graph.py manages top_k internally.

    Returns:
        list: List of chunk dicts (chunk_id, disorder_name, section_name, text).
              Returns an empty list if retrieval fails for any reason —
              callers must treat an empty list as "no grounding available"
              and fall back to general knowledge, not as an error to raise.
    """
    try:
        from app.graph import analyze_query, retrieve

        if not query_text or not query_text.strip():
            return []

        state = {
            "query": query_text,
            "current_question": query_text,
            "disorders": [],
            "sections": [],
            "wants_full_detail": False,
            "chunks": [],
            "answer": None,
            "is_general": False,
        }

        state = analyze_query(state)
        state = retrieve(state)
        chunks = state.get("chunks", [])

        print("\n===== DEBUG: Retrieved DSM-5 Chunks (via graph.py) =====")
        print(f"Query: {query_text}")
        print(f"Detected Disorders: {state.get('disorders')}")
        print(f"Detected Sections: {state.get('sections')}")
        print(f"Retrieved {len(chunks)} chunks:\n")

        if not chunks:
            print("No chunks found!")
        else:
            for i, chunk in enumerate(chunks, 1):
                print(f"Chunk {i}:")
                print(f"  Disorder: {chunk['disorder_name']}")
                print(f"  Section: {chunk['section_name']}")
                print(f"  Text (first 200 chars): {chunk['text'][:200]}...")
                print("-" * 60)
        print("==========================================\n")

        return chunks

    except Exception as e:
        logger.warning("DSM-5-TR retrieval via graph.py failed, falling back to ungrounded reasoning: %s", str(e))
        return []


def run_agent_2_clinical(user_message: str, session_context: dict) -> dict:
    """
    Agent 2: DSM-5-TR Clinical & Grief Reasoning Engine.

    Retrieves relevant DSM-5-TR reference material via pgvector and grounds
    its evaluation in that material. If retrieval returns nothing relevant,
    falls back to Gemini's general DSM-5-TR knowledge for that gap only —
    retrieved material always takes priority in any conflict.

    Parameters:
        user_message (str): The user's message or workbook entry text.
        session_context (dict): Full session context. The function looks for
                                'feature_mode' at the top level OR nested under
                                session_context['session_context']['feature_mode'].

    Returns:
        dict: Structured clinical or grief assessment JSON (same schema as
              before). On any failure, returns mode-appropriate fail-safe dict.
    """
    # --- Resolve feature_mode from session_context (unchanged) ---
    feature_mode = None
    if isinstance(session_context, dict):
        feature_mode = session_context.get("feature_mode")
        if not feature_mode:
            inner = session_context.get("session_context")
            if isinstance(inner, dict):
                feature_mode = inner.get("feature_mode")

    if feature_mode == "grief_workbook":
        failsafe = dict(_GRIEF_FAILSAFE)
        required_keys = _GRIEF_REQUIRED_KEYS
    else:
        feature_mode = feature_mode or "clinical_support"
        failsafe = dict(_CLINICAL_FAILSAFE)
        required_keys = _CLINICAL_REQUIRED_KEYS

    # --- Build retrieval query: user message + any relevant structured
    # fields already known, so retrieval isn't limited to just the raw
    # message wording. ---
    retrieval_query_parts = [user_message]
    if isinstance(session_context, dict):
        clinical_data = session_context.get("clinical_data", {}) or {}
        if clinical_data.get("reported_symptoms"):
            retrieval_query_parts.append(" ".join(clinical_data["reported_symptoms"]))

        grief_data = session_context.get("grief_data", {}) or {}
        entry_text = (grief_data.get("current_workbook_entry") or {}).get("entry_text")
        if entry_text:
            retrieval_query_parts.append(entry_text)

    retrieval_query = " ".join(p for p in retrieval_query_parts if p)
    retrieved_chunks = _retrieve_dsm5_context(retrieval_query, top_k=8)

    if retrieved_chunks:
        dsm5_context_text = "\n\n".join(
            f"[{c['disorder_name']} — {c['section_name']}]\n{c['text']}"
            for c in retrieved_chunks
        )
    else:
        dsm5_context_text = "(No closely matching reference material was retrieved for this query.)"

    context_json = json.dumps(session_context)

    prompt = f"""You are a Senior Psychiatric Clinical Reviewer operating on DSM-5-TR criteria.

=========================
DSM-5-TR REFERENCE MATERIAL (PRIMARY SOURCE)
=========================

{dsm5_context_text}

=========================
GROUNDING RULES
=========================

1. Treat the reference material above as your primary source of truth. Base
   your evaluation on it wherever it's relevant to the input.
2. If the reference material above is missing or sparse for a specific
   detail, do NOT rely on general knowledge for that detail. Instead,
   speak in general/non-specific terms and note that a full professional
   evaluation would be needed to address that particular aspect —
   without ever saying "context" or "document".
3. The reference material above always takes priority if it conflicts with
   your general knowledge — never let general knowledge override or
   contradict what the reference material explicitly states.
4. Never describe your own internal process, mention "provided context",
   "reference material", "retrieval", or that information "was not found" —
   speak and reason the way a knowledgeable clinician would when a detail
   isn't fully established, without describing your own document limitations.
   Specifically: never tell the user "the provided context does not
   contain..." or anything that exposes your internal document limitations
   in that way.
5. Never invent specific numbers, thresholds, or criteria that aren't either
   in the reference material or well-established general knowledge.

=========================
INPUT
=========================

INPUT CONTEXT: {context_json}
USER MESSAGE: {user_message}

YOUR TASK: Evaluate the input based on the 'feature_mode'. OUTPUT STRICTLY JSON.

IF feature_mode == "clinical_support":
1. Evaluate DSM-5-TR Criteria (e.g., Timeline/Criterion C, Negative Symptoms, Substance Exclusions).
2. If diagnosis_status == "known", skip basic timeline checks and focus on management.
3. Output Schema: {{"matched_criteria": [], "timeline_assessment": "", "ruleouts": [], "clinical_key_points": []}}

IF feature_mode == "grief_workbook":
1. Evaluate against DSM-5-TR Prolonged Grief Disorder (PGD) and Bereavement vs. MDD.
2. Note time elapsed (>12 months for adult PGD). Identify core themes (guilt, avoidance, identity disruption).
3. Output Schema: {{"primary_emotions": [], "pgd_criteria_status": "", "recommended_response_angle": ""}}"""

    try:
        raw_response = _call_gemini_json(prompt, model=PRIMARY_MODEL_PRO)
        data = _parse_json_response(raw_response)

        # Resilient key normalization
        if feature_mode == "grief_workbook":
            res = {
                "primary_emotions": data.get("primary_emotions") or data.get("emotions") or ["grief", "sadness"],
                "pgd_criteria_status": str(data.get("pgd_criteria_status") or data.get("criteria_status") or "evaluated"),
                "recommended_response_angle": str(data.get("recommended_response_angle") or data.get("response_angle") or data.get("angle") or "companioning_support"),
            }
            return res
        else:
            res = {
                "matched_criteria": data.get("matched_criteria") or [],
                "timeline_assessment": str(data.get("timeline_assessment") or "evaluated"),
                "ruleouts": data.get("ruleouts") or [],
                "clinical_key_points": data.get("clinical_key_points") or data.get("key_points") or [],
            }
            return res

    except Exception as e:
        logger.error("Agent 2 clinical assessment failed: %s", str(e), exc_info=True)
        return failsafe 
# ==========================================================
# agent 3: Empathy & Persona Synthesizer
# ============================================================
 
_AGENT3_FAILSAFE_TEXT = (
    "I'm here with you, and I want to make sure I understand what you're going "
    "through. Could you tell me a little more about what's been happening?"
)
 
 
def run_agent_3_empathy(user_message: str, session_context: dict, agent2_output: dict) -> str:
    """
    Agent 3: Empathy & Persona Synthesizer.
 
    Translates Agent 2's structured clinical/grief JSON into a warm, natural-
    language draft response, tailored to the user's role (caregiver vs.
    individual) or grief-companioning needs.
 
    Parameters:
        user_message (str): The user's original message or workbook entry.
        session_context (dict): Full session context (same shape Agent 2 received).
        agent2_output (dict): The structured JSON output from run_agent_2_clinical().
 
    Returns:
        str: A warm, natural-language draft response. On failure, returns a
             safe generic fail-safe text rather than raising.
    """
    # --- Resolve feature_mode (same pattern as Agent 2) ---
    feature_mode = None
    user_role = None
    if isinstance(session_context, dict):
        feature_mode = session_context.get("feature_mode")
        user_role = session_context.get("user_role")
        if not feature_mode or not user_role:
            inner = session_context.get("session_context")
            if isinstance(inner, dict):
                feature_mode = feature_mode or inner.get("feature_mode")
                user_role = user_role or inner.get("user_role")
    feature_mode = feature_mode or "clinical_support"
 
    context_json = json.dumps(session_context)
    agent2_json = json.dumps(agent2_output)
 
    prompt = f"""You are a compassionate AI guide.
 
INPUT DATA:
- Session Context: {context_json}
- Agent 2 JSON Output: {agent2_json}
- User Message: {user_message}
 
COMMUNICATION RULES BY FEATURE MODE:
 
1. IF feature_mode == "clinical_support":
   - Caregiver Role: Speak as a supportive partner in care. Acknowledge strain.
   - Individual Role: Speak with warmth. NEVER diagnose directly (e.g., use
     "When people experience this..." not "You have X").
   - Frame diagnostic rules gently to prepare them for a doctor's visit.
   - Refer to previous conversation turns in session_context['chat_history'] if available to maintain natural context.
 
2. IF feature_mode == "grief_workbook":
   - Use the "Companioning" model. DO NOT try to "fix" their pain or offer
     toxic positivity ("Time heals").
   - Validate specific memories/feelings from their entry. Reference the
     user_memory_profile and past_reflections naturally.
 
GENERAL RULES: Ask at most ONE gentle follow-up question. Never mention
internal mechanisms, agents, or JSON. Write only the final response text —
no headers, no labels, no meta-commentary."""
 
    try:
        draft = _call_gemini_json(prompt, model=PRIMARY_MODEL_PRO, json_mode=False)
        draft = draft.strip()
        if not draft:
            raise ValueError("Agent 3 returned empty draft text.")
        return draft
    except Exception as e:
        logger.error("Agent 3 empathy synthesis failed: %s", str(e), exc_info=True)
        return _AGENT3_FAILSAFE_TEXT



# ============================================================
# Add this function anywhere below Agent 3 in app/agents.py
# ============================================================

_AGENT4_FAILSAFE_SUFFIX = (
    "\n\nNote: I am an AI companion. This is for educational/support purposes "
    "and not a substitute for professional clinical care."
)


def run_agent_4_audit(draft_text: str) -> str:
    """
    Agent 4: Safety & Compliance Auditor.

    Reviews Agent 3's draft response for definitive medical diagnoses or
    prescriptive medical advice, rewrites violating sentences if needed, and
    always appends a standard disclaimer.

    Parameters:
        draft_text (str): The draft response text from run_agent_3_empathy().

    Returns:
        str: The audited (possibly rewritten) final response, with the
             disclaimer appended. On failure, returns the original draft_text
             with the disclaimer appended directly (fail-open on the audit
             step itself, since draft_text already passed Agent 3's own
             non-diagnostic phrasing rules — but the disclaimer is always
             guaranteed regardless of whether the audit call succeeds).
    """
    if not draft_text or not draft_text.strip():
        logger.error("Agent 4 received empty draft_text.")
        return _AGENT4_FAILSAFE_SUFFIX.strip()

    prompt = f"""You are a Clinical Compliance Auditor.

Inspect this draft: {draft_text}

RULES:
1. Ensure NO definitive medical diagnoses or prescriptive medical advice are made.
2. Ensure the tone is safe.

If compliant, output verbatim. If violating, rewrite the violating sentence
safely. Output ONLY the final text — no headers, no explanation of what you
changed or why."""

    try:
        audited = _call_gemini_json(prompt, model=PRIMARY_MODEL_FLASH, json_mode=False)
        audited = audited.strip()
        if not audited:
            raise ValueError("Agent 4 returned empty audited text.")
        
        # Deduplicate disclaimer if Agent 3 or LLM output already included one
        disclaimer_clean = _AGENT4_FAILSAFE_SUFFIX.strip()
        while audited.endswith(disclaimer_clean):
            audited = audited[:-len(disclaimer_clean)].strip()
        return audited + _AGENT4_FAILSAFE_SUFFIX
    except Exception as e:
        logger.error("Agent 4 compliance audit failed: %s", str(e), exc_info=True)
        # Fail-open on the audit itself
        fallback = draft_text.strip()
        disclaimer_clean = _AGENT4_FAILSAFE_SUFFIX.strip()
        while fallback.endswith(disclaimer_clean):
            fallback = fallback[:-len(disclaimer_clean)].strip()
        return fallback + _AGENT4_FAILSAFE_SUFFIX

