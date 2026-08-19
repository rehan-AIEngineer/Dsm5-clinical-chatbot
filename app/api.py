"""
api.py
------
FastAPI wrapper around the existing RAG pipeline (graph.py, llm.py, etc.)
"""

import uuid
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
# graph.py (heavy ML models) imported lazily to avoid OOM kill at startup
from app.chat_memory import (
    add_message,
    get_history,
    list_sessions,
    set_title_if_unset,
    session_exists,
    delete_session,
    rename_session,
)
from app.auth import verify_token

from typing import Optional, Dict, Any
from app.agent_pipeline import run_unified_pipeline
from app.grief_memory import (
    save_workbook_entry,
    get_workbook_entry_by_date,
    get_calendar_dates,
    delete_workbook_entry,
    link_workbook_entry_session,
)

logger = logging.getLogger(__name__)

# ============================================================
# App Setup
# ============================================================

app = FastAPI(title="DSM-5 RAG Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow local dev frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_rag_app = None  # Lazy-built on first request


def _get_rag_app():
    global _rag_app
    if _rag_app is None:
        from app.graph import build_graph
        _rag_app = build_graph()
    return _rag_app

FALLBACK_ANSWER = (
    "I'm having trouble processing your question right now (technical issue). "
    "Please try again shortly.\n\nIf this is urgent or safety-related, please "
    "contact a mental health professional, hospital, or crisis helpline immediately."
)


# ============================================================
# Chat & Pipeline Request Models
# ============================================================

class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1, max_length=2000)


class PipelineChatRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1, max_length=2000)
    session_context: Optional[Dict[str, Any]] = None


class GriefEntryRequest(BaseModel):
    entry_date: str = Field(..., min_length=10, max_length=10)
    entry_text: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    themes: Optional[Dict[str, Any]] = None


class GriefLinkSessionRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    entry_date: Optional[str] = None
    entry_id: Optional[int] = None


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


def _build_rag_state(query: str):
    """Added for streaming: reuse the same retrieval path without changing the old /chat endpoint."""
    from app.graph import analyze_query, retrieve
    state = {
        "query": query,
        "current_question": query,
        "disorders": [],
        "sections": [],
        "wants_full_detail": False,
        "chunks": [],
        "answer": None,
    }
    state = analyze_query(state)
    state = retrieve(state)
    return state


@app.post("/new-chat")
def new_chat(user = Depends(verify_token)):
    session_id = str(uuid.uuid4())
    add_message(
        session_id=session_id,
        role="system",
        content="Chat session started",
        user_id=user.id,
    )
    return {"session_id": session_id}


@app.post("/chat")
def chat(request: ChatRequest, user = Depends(verify_token)):
    if not session_exists(request.session_id, user_id=user.id):
        raise HTTPException(status_code=404, detail="Session not found. Please start a new chat.")

    history = get_history(request.session_id, limit=20, user_id=user.id)
    is_first_message = len(history) == 0

    context_prefix = ""
    if history:
        recent = history[-12:]
        context_prefix = "\n".join(f"{turn['role']}: {turn['content']}" for turn in recent)
        context_prefix = f"Previous conversation:\n{context_prefix}\n\n"

    full_query = context_prefix + f"Current question: {request.message}"

    add_message(request.session_id, "user", request.message, user_id=user.id)

    # Auto-name from the first message — won't ever overwrite a manual rename,
    # since set_title_if_unset only updates rows where title IS NULL.
    if is_first_message:
        trimmed = request.message.strip()
        auto_title = trimmed[:32] + "…" if len(trimmed) > 32 else trimmed
        set_title_if_unset(request.session_id, auto_title, user_id=user.id)

    try:
        result = _get_rag_app().invoke({
            "query": full_query,
            "current_question": request.message,
            "disorders": [],
            "sections": [],
            "wants_full_detail": False,
            "chunks": [],
            "answer": None,
        })
        answer = result["answer"]
    except Exception as e:
        logger.error(f"Pipeline failed for session {request.session_id}: {e}")
        answer = FALLBACK_ANSWER

    add_message(request.session_id, "assistant", answer, user_id=user.id)

    return {"answer": answer}


@app.post("/chat/stream")
def chat_stream(request: ChatRequest, user = Depends(verify_token)):
    if not session_exists(request.session_id, user_id=user.id):
        raise HTTPException(status_code=404, detail="Session not found. Please start a new chat.")

    history = get_history(request.session_id, limit=20, user_id=user.id)
    is_first_message = len(history) == 0

    context_prefix = ""
    if history:
        recent = history[-12:]
        context_prefix = "\n".join(f"{turn['role']}: {turn['content']}" for turn in recent)
        context_prefix = f"Previous conversation:\n{context_prefix}\n\n"

    full_query = context_prefix + f"Current question: {request.message}"

    add_message(request.session_id, "user", request.message, user_id=user.id)

    if is_first_message:
        trimmed = request.message.strip()
        auto_title = trimmed[:32] + "…" if len(trimmed) > 32 else trimmed
        set_title_if_unset(request.session_id, auto_title, user_id=user.id)

    state = _build_rag_state(full_query)

    def stream_answer():
        from app.llm import generate_answer_stream, generate_general_response

        if state.get("is_general"):
            answer = generate_general_response(state["current_question"])
            add_message(request.session_id, "assistant", answer, user_id=user.id)
            yield answer
            return

        answer_parts = []

        if not state["chunks"]:
            fallback = "I couldn't find relevant information in the DSM-5-TR reference for this question."
            add_message(request.session_id, "assistant", fallback, user_id=user.id)
            yield fallback
            return

        for chunk in generate_answer_stream(state["query"], state["chunks"]):
            answer_parts.append(chunk)
            yield chunk

        # Added persistence step so the streamed answer still gets stored like the old /chat flow.
        final_answer = "".join(answer_parts)
        if final_answer:
            add_message(request.session_id, "assistant", final_answer, user_id=user.id)

    return StreamingResponse(stream_answer(), media_type="text/plain; charset=utf-8")


@app.get("/chats")
def get_all_chats(user = Depends(verify_token)):
    sessions = list_sessions(user_id=user.id)
    return {"sessions": sessions}


@app.get("/chats/{session_id}")
def get_chat_by_id(session_id: str, limit: int = 50, user = Depends(verify_token)):
    if not session_exists(session_id, user_id=user.id):
        raise HTTPException(status_code=404, detail="Session not found")

    messages = get_history(session_id, limit=limit, user_id=user.id)
    return {"session_id": session_id, "messages": messages}


@app.delete("/chats/{session_id}")
def delete_chat(session_id: str, user = Depends(verify_token)):
    if not session_exists(session_id, user_id=user.id):
        raise HTTPException(status_code=404, detail="Session not found")

    delete_session(session_id, user_id=user.id)
    return {"message": "Chat deleted successfully"}


@app.put("/chats/{session_id}")
def rename_chat(session_id: str, request: RenameRequest, user = Depends(verify_token)):
    if not session_exists(session_id, user_id=user.id):
        raise HTTPException(status_code=404, detail="Session not found")

    rename_session(session_id, request.title.strip(), user_id=user.id)
    return {"message": "Chat renamed successfully", "title": request.title.strip()}


# ============================================================
# 4-Agent Unified Pipeline Endpoint
# ============================================================

@app.post("/pipeline/chat")
def pipeline_chat(request: PipelineChatRequest, user = Depends(verify_token)):
    """Runs full 4-agent pipeline with session_context and returns response + debug info."""
    if not session_exists(request.session_id, user_id=user.id):
        add_message(request.session_id, "system", "Chat session started", user_id=user.id)

    history = get_history(request.session_id, limit=20, user_id=user.id)
    is_first_message = len(history) == 0

    add_message(request.session_id, "user", request.message, user_id=user.id)

    if is_first_message:
        trimmed = request.message.strip()
        auto_title = trimmed[:32] + "…" if len(trimmed) > 32 else trimmed
        set_title_if_unset(request.session_id, auto_title, user_id=user.id)

    ctx = dict(request.session_context) if request.session_context else {}

    # Attach recent conversation history from PostgreSQL to session_context
    if history:
        recent_turns = [f"{t['role']}: {t['content']}" for t in history[-6:]]
        ctx["chat_history"] = recent_turns

    try:
        pipeline_res = run_unified_pipeline(
            user_message=request.message,
            session_context=ctx,
            user_id=user.id,
            session_id=request.session_id,
        )
        final_response = pipeline_res.get("response", FALLBACK_ANSWER)
        debug = pipeline_res.get("debug", {})
    except Exception as e:
        logger.error(f"4-Agent pipeline failed for session {request.session_id}: {e}", exc_info=True)
        final_response = FALLBACK_ANSWER
        debug = {"error": str(e)}

    add_message(request.session_id, "assistant", final_response, user_id=user.id)

    return {
        "answer": final_response,
        "debug": debug,
        "session_id": request.session_id,
    }


# ============================================================
# Grief Workbook Calendar Endpoints
# ============================================================

@app.post("/grief/entry")
def save_grief_reflection(request: GriefEntryRequest, user = Depends(verify_token)):
    """Saves or updates a Grief Workbook reflection for a specific calendar date."""
    res = save_workbook_entry(
        entry_date=request.entry_date,
        entry_text=request.entry_text,
        user_id=user.id,
        session_id=request.session_id,
        themes=request.themes,
    )
    return res


@app.get("/grief/entry")
def get_grief_reflection(date: str, session_id: Optional[str] = None, user = Depends(verify_token)):
    """Gets existing reflection for a specific date (YYYY-MM-DD)."""
    entry = get_workbook_entry_by_date(entry_date=date, user_id=user.id, session_id=session_id)
    if not entry:
        return {"entry": None}
    return {"entry": entry}


@app.get("/grief/calendar")
def get_marked_calendar_dates(session_id: Optional[str] = None, user = Depends(verify_token)):
    """Gets list of YYYY-MM-DD dates with existing workbook reflections."""
    dates = get_calendar_dates(user_id=user.id, session_id=session_id)
    return {"dates": dates}


@app.delete("/grief/entry")
def delete_grief_reflection(
    date: Optional[str] = None,
    entry_id: Optional[int] = None,
    session_id: Optional[str] = None,
    user = Depends(verify_token),
):
    """Deletes a reflection and its pgvector embedding from long-term memory."""
    success = delete_workbook_entry(
        entry_date=date,
        entry_id=entry_id,
        user_id=user.id,
        session_id=session_id,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Reflection not found or unauthorized.")
    return {"message": "Reflection deleted successfully"}


@app.post("/grief/entry/link-session")
def link_grief_reflection_session(
    request: GriefLinkSessionRequest,
    user = Depends(verify_token),
):
    """Links a workbook reflection to a chat session ID."""
    success = link_workbook_entry_session(
        session_id=request.session_id,
        entry_date=request.entry_date,
        entry_id=request.entry_id,
        user_id=user.id,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Could not link session to reflection.")
    return {"message": "Session linked successfully"}



