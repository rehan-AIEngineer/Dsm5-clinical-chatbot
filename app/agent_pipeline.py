"""
app/agent_pipeline.py
----------------------
Orchestrates the 4-agent pipeline:

    Agent 1 (Guardrail) -> [early exit if CRISIS/OFF_TOPIC]
    -> Agent 2 (Clinical/Grief Reasoning)
    -> Agent 3 (Empathy Synthesizer)
    -> Agent 4 (Safety & Compliance Auditor)
    -> Final response
"""

import time
import logging

from app.agents import (
    run_agent_1_guardrail,
    run_agent_2_clinical,
    run_agent_3_empathy,
    run_agent_4_audit,
)
from app.grief_memory import retrieve_relevant_grief_memory

logger = logging.getLogger(__name__)

# Crisis resources (TC-01 Standard)
CRISIS_MESSAGE = (
    "I am deeply concerned about what you are going through, and your safety is the absolute highest priority.\n\n"
    "Please reach out for immediate help right now:\n"
    "• 988 Suicide & Crisis Lifeline: Call or text 988 (Available 24/7, Free & Confidential)\n"
    "• Umang Mental Health Helpline: 0311-7786264\n"
    "• Emergency Rescue Services: 1122 / 911\n"
    "• National Youth Helpline: 0800-69457\n\n"
    "Please do not stay alone with this pain. Reach out to a loved one, trusted person, or go to the nearest emergency room immediately."
)
PK_CRISIS_MESSAGE = CRISIS_MESSAGE

OFF_TOPIC_MESSAGE = (
    "I'm here to support mental health, caregiving, and grief-related questions. "
    "I'm not able to help with that, but I'm glad to talk if something's on your mind."
)


def run_unified_pipeline(user_message: str, session_context: dict, user_id: str = None, session_id: str = None) -> dict:
    """
    Runs the full 4-agent pipeline for a single user turn, measuring execution latency.

    Parameters:
        user_message (str): The user's message or workbook entry.
        session_context (dict): Full session context (feature_mode, user_role, clinical_data/grief_data, etc.)
        user_id (str): Optional authenticated user UUID for longitudinal memory lookup.
        session_id (str): Optional active chat session ID.

    Returns:
        dict: {
            "response": str,
            "debug": {
                "agent1": {...},
                "agent2": {...} | None,
                "agent3_draft": str | None,
                "agent4_final": str | None,
                "metrics": {
                    "agent1_time_ms": int,
                    "agent2_time_ms": int,
                    "agent3_time_ms": int,
                    "agent4_time_ms": int,
                    "total_time_ms": int,
                }
            }
        }
    """
    start_total = time.time()
    debug = {
        "agent1": None,
        "agent2": None,
        "agent3_draft": None,
        "agent4_final": None,
        "metrics": {
            "agent1_time_ms": 0,
            "agent2_time_ms": 0,
            "agent3_time_ms": 0,
            "agent4_time_ms": 0,
            "total_time_ms": 0,
        },
    }

    session_context = dict(session_context) if isinstance(session_context, dict) else {}

    # --- Agent 1: Intent & Safety Guardrail ---
    t0 = time.time()
    a1 = run_agent_1_guardrail(user_message, session_context)
    debug["metrics"]["agent1_time_ms"] = int((time.time() - t0) * 1000)
    debug["agent1"] = a1

    if a1["category"] == "OFF_TOPIC":
        debug["metrics"]["total_time_ms"] = int((time.time() - start_total) * 1000)
        return {"response": OFF_TOPIC_MESSAGE, "debug": debug}

    if a1["category"] == "CRISIS":
        logger.warning("CRISIS category triggered. reasoning=%s", a1.get("reasoning"))
        debug["metrics"]["total_time_ms"] = int((time.time() - start_total) * 1000)
        return {"response": PK_CRISIS_MESSAGE, "debug": debug}

    if a1.get("passive_risk_flag"):
        logger.warning("passive_risk_flag set on category=%s — monitor this session.", a1["category"])

    derived_feature_mode = (
        "grief_workbook" if a1["category"] == "GRIEF_WORKBOOK" else "clinical_support"
    )
    if session_context.get("feature_mode") != derived_feature_mode:
        session_context["feature_mode"] = derived_feature_mode

    # --- Longitudinal Memory Retrieval (PostgreSQL + pgvector) ---
    if derived_feature_mode == "grief_workbook":
        past_memories = retrieve_relevant_grief_memory(
            query_text=user_message,
            user_id=user_id,
            session_id=session_id,
            top_k=3,
        )
        if past_memories:
            grief_data = session_context.get("grief_data", {}) or {}
            grief_data["past_reflections"] = past_memories
            session_context["grief_data"] = grief_data

    # --- Agent 2: Clinical/Grief Reasoning ---
    t0 = time.time()
    a2 = run_agent_2_clinical(user_message, session_context)
    debug["metrics"]["agent2_time_ms"] = int((time.time() - t0) * 1000)
    debug["agent2"] = a2

    # --- Agent 3: Empathy Synthesizer ---
    t0 = time.time()
    a3_draft = run_agent_3_empathy(user_message, session_context, a2)
    debug["metrics"]["agent3_time_ms"] = int((time.time() - t0) * 1000)
    debug["agent3_draft"] = a3_draft

    # --- Agent 4: Safety & Compliance Auditor ---
    t0 = time.time()
    final = run_agent_4_audit(a3_draft)
    debug["metrics"]["agent4_time_ms"] = int((time.time() - t0) * 1000)
    debug["agent4_final"] = final

    debug["metrics"]["total_time_ms"] = int((time.time() - start_total) * 1000)
    return {"response": final, "debug": debug}