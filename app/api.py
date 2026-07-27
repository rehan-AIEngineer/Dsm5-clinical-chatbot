"""
api.py
------
FastAPI wrapper around the existing RAG pipeline (graph.py, llm.py, etc.)
No changes to existing logic — this file only exposes it via HTTP endpoints.

Phase 1: /new-chat and /chat (in-memory session storage, no database).
"""

import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware   
from pydantic import BaseModel
from app.graph import build_graph

app = FastAPI(title="DSM-5 RAG Chatbot API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------
# In-memory chat session storage
# --------------------------------------------------------------------------
chat_sessions: dict[str, list[dict]] = {}


# --------------------------------------------------------------------------
# POST /new-chat
# --------------------------------------------------------------------------

@app.post("/new-chat")
def new_chat():
    session_id = str(uuid.uuid4())
    chat_sessions[session_id] = []
    return {"session_id": session_id}


rag_app = build_graph()


class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.post("/chat")
def chat(request: ChatRequest):
    if request.session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found. Please start a new chat.")

    history = chat_sessions[request.session_id]

    # Build a lightweight context string from prior turns
    context_prefix = ""
    if history:
         
        recent = history[-12:]   
        context_prefix = "\n".join(f"{turn['role']}: {turn['content']}" for turn in recent)
        context_prefix = f"Previous conversation:\n{context_prefix}\n\n"

    full_query = context_prefix + f"Current question: {request.message}"

    history.append({"role": "user", "content": request.message})

    result = rag_app.invoke({
        "query": full_query,
        "current_question": request.message,
        "disorders": [],
        "sections": [],
        "wants_full_detail": False,
        "chunks": [],
        "answer": None,
    })

    answer = result["answer"]
    history.append({"role": "assistant", "content": answer})

    return {"answer": answer}
