"""
graph.py
--------
Orchestrates the full RAG pipeline as a LangGraph workflow:

    analyze_query -> retrieve -> generate -> END

Handles: single disorder+section, single disorder (full or specific),
disorder-to-disorder comparison, section-to-section comparison (same
disorder), and general fallback queries.

Dependency note:
    pip install sentence-transformers
    (adds cross-encoder reranking via BAAI/bge-reranker-base)
"""

import re
import logging
import difflib
from typing import TypedDict, List, Optional

from langgraph.graph import StateGraph, END
from sentence_transformers import CrossEncoder

from app.vectorstore import get_connection
from app.embedder import embed_batch
from app.llm import generate_answer, generate_general_response

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Cross-encoder reranker (loaded once at module level)
# --------------------------------------------------------------------------

_reranker: CrossEncoder | None = None


def _get_reranker() -> CrossEncoder:
    """Lazy-load the cross-encoder so cold-start only happens on first use."""
    global _reranker
    if _reranker is None:
        logger.info("Loading cross-encoder reranker: BAAI/bge-reranker-base …")
        _reranker = CrossEncoder("BAAI/bge-reranker-base", max_length=512)
        logger.info("Reranker loaded.")
    return _reranker

# --------------------------------------------------------------------------
# Known vocab (loaded once)
# --------------------------------------------------------------------------

SECTION_KEYWORDS = {
    "Diagnostic Criteria": ["diagnostic criteria", "criteria"],
    "Diagnostic Features": ["diagnostic features", "features"],
    "Associated Features": ["associated features"],
    "Prevalence": ["prevalence", "how common", "how many people"],
    "Development and Course": ["development and course", "development", "course"],
    "Risk and Prognostic Factors": ["risk factors", "risk and prognostic", "prognostic factors"],
    "Differential Diagnosis": ["differential diagnosis", "differential"],
    "Comorbidity": ["comorbidity", "comorbid"],
    "Functional Consequences": ["functional consequences", "consequences", "impact"],
    "Overview": ["overview"],
    "Proposed Diagnostic Criteria": ["proposed diagnostic criteria", "proposed criteria"],
}

FULL_DETAIL_KEYWORDS = [
    "everything",
    "full detail",
    "complete details",
    "complete information",
    "all details",
    "tell me about",
    "give me details",
    "explain fully",
    "overview",
    "in detail",
    "detailed explanation"
]
DISORDER_ABBREVIATIONS = {
    "adhd": "Attention-Deficit/Hyperactivity Disorder",
    "asd": "Autism Spectrum Disorder",
    "ptsd": "Posttraumatic Stress Disorder",
    "ocd": "Obsessive-Compulsive Disorder",
    "mdd": "Major Depressive Disorder",
    "gad": "Generalized Anxiety Disorder",
    "bpd": "Borderline Personality Disorder",
    "ssd": "Somatic Symptom Disorder",
    "asd (autism)": "Autism Spectrum Disorder",
}

def _load_disorder_names() -> List[str]:
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT disorder_name FROM dsm5_chunks;")
            names = [row[0] for row in cur.fetchall()]
        conn.close()
        if names:
            return names
    except Exception as e:
        logger.warning("Could not load disorder names from DB at startup: %s. Using default list.", e)

    return [
        "Major Depressive Disorder",
        "Schizophrenia",
        "Bipolar I Disorder",
        "Bipolar II Disorder",
        "Generalized Anxiety Disorder",
        "Posttraumatic Stress Disorder",
        "Attention-Deficit/Hyperactivity Disorder",
        "Autism Spectrum Disorder",
        "Obsessive-Compulsive Disorder",
        "Prolonged Grief Disorder",
        "Substance-Induced Psychotic Disorder",
        "Somatic Symptom Disorder",
        "Panic Disorder",
        "Borderline Personality Disorder",
    ]


DISORDER_NAMES = _load_disorder_names()


# --------------------------------------------------------------------------
# State definition
# --------------------------------------------------------------------------

class RAGState(TypedDict):
    query: str
    current_question: str
    disorders: List[str]
    sections: List[str]
    wants_full_detail: bool
    chunks: List[dict]
    answer: Optional[str]
    is_general: bool


# --------------------------------------------------------------------------
# Node 1: Analyze query
# --------------------------------------------------------------------------

def analyze_query(state: RAGState) -> RAGState:
    full_query_lower = state["query"].lower()

    if "current question:" in full_query_lower:
        current_only = full_query_lower.split("current question:", 1)[1].strip()
    else:
        current_only = full_query_lower

    query_lower = current_only

    # Detect disorder(s) mentioned - fuzzy match against known names
    found_disorders = []
    for name in DISORDER_NAMES:
        if name.lower() in query_lower:
            found_disorders.append(name)

    # Fallback: only re-check history if current question explicitly references
    # a prior topic (pronouns) — and only pick the MOST RECENTLY mentioned disorder
    REFERENCE_CUES = ["it ", "its ", "this disorder", "that disorder",
                       "this condition", "that condition", "this one", "same disorder",
                       "what causes it", "causes it", "what about it"]
    if not found_disorders and any(cue in current_only for cue in REFERENCE_CUES):
        history_lines = full_query_lower.split("\n")
        for line in reversed(history_lines):
            for name in DISORDER_NAMES:
                if name.lower() in line:
                    found_disorders.append(name)
                    break
            if found_disorders:
                break

    if not found_disorders:
        # fallback fuzzy match (handles typos/partial names)
        close = difflib.get_close_matches(query_lower, [n.lower() for n in DISORDER_NAMES], n=2, cutoff=0.6)
        for c in close:
            match = next((n for n in DISORDER_NAMES if n.lower() == c), None)
            if match:
                found_disorders.append(match)

    # Detect section(s) mentioned
    found_sections = []
    for section_name, keywords in SECTION_KEYWORDS.items():
        if any(kw in query_lower for kw in keywords):
            found_sections.append(section_name)

    wants_full = any(kw in query_lower for kw in FULL_DETAIL_KEYWORDS)

    state["disorders"] = found_disorders[:2]
    state["sections"] = found_sections[:2]
    state["wants_full_detail"] = wants_full
    return state

# --------------------------------------------------------------------------
# Node 2: Retrieve
# --------------------------------------------------------------------------

def _fetch_by_filter(cur, disorder=None, sections=None, limit=None):
    query = "SELECT chunk_id, disorder_name, section_name, text FROM dsm5_chunks WHERE 1=1"
    params = []

    if disorder:
        query += " AND disorder_name = %s"
        params.append(disorder)
    if sections:
        query += " AND section_name = ANY(%s)"
        params.append(sections)
    if limit:
        query += " LIMIT %s"
        params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()
    return [{"chunk_id": r[0], "disorder_name": r[1], "section_name": r[2], "text": r[3]} for r in rows]


def _fetch_by_vector(cur, query_embedding, disorder=None, top_k=5):
    query = """
        SELECT chunk_id, disorder_name, section_name, text
        FROM dsm5_chunks
        WHERE 1=1
    """
    params = []
    if disorder:
        query += " AND disorder_name = %s"
        params.append(disorder)
    query += " ORDER BY embedding <=> %s::vector LIMIT %s"
    params.extend([query_embedding, top_k])

    cur.execute(query, params)
    rows = cur.fetchall()
    return [{"chunk_id": r[0], "disorder_name": r[1], "section_name": r[2], "text": r[3]} for r in rows]


def rerank_chunks(query: str, chunks: List[dict], top_k: int = 7) -> List[dict]:
    """
    Re-scores candidate chunks against the user query using a cross-encoder
    (BAAI/bge-reranker-base) and returns the top-k by relevance.

    Parameters:
        query:  The user's current question.
        chunks: De-duplicated candidate chunks from dual vector search.
        top_k:  Number of chunks to keep after reranking.

    Returns:
        List of the top-k chunks sorted by descending reranker score.
    """
    if not chunks:
        return []

    reranker = _get_reranker()

    # Build (query, passage) pairs for the cross-encoder
    pairs = [
        [query, f"{c['disorder_name']} — {c['section_name']}\n{c['text']}"]
        for c in chunks
    ]

    scores = reranker.predict(pairs)

    # Attach scores and sort descending
    scored = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)

    top_chunks = [chunk for chunk, _score in scored[:top_k]]

    logger.info(
        "Reranker: %d candidates → top %d kept  (score range %.4f … %.4f)",
        len(chunks), len(top_chunks),
        scored[0][1] if scored else 0,
        scored[-1][1] if scored else 0,
    )

    return top_chunks


def retrieve(state: RAGState) -> RAGState:
    disorders = state["disorders"]
    sections = state["sections"]
    wants_full = state["wants_full_detail"]

    conn = get_connection()
    cur = conn.cursor()
    chunks = []

    # Case: 2 disorders -> comparison, fetch each separately
    if len(disorders) == 2 and len(sections) <= 1:
        for d in disorders:
            chunks += _fetch_by_filter(cur, disorder=d, sections=sections or None)

    # Case: 1 disorder + 2 sections -> section comparison within disorder
    elif len(disorders) == 1 and len(sections) >= 2:
        chunks = _fetch_by_filter(cur, disorder=disorders[0], sections=sections)

    # Case: 1 disorder + 1 section -> exact lookup
    elif len(disorders) == 1 and len(sections) == 1:
        chunks = _fetch_by_filter(cur, disorder=disorders[0], sections=sections)

    # Case: 1 disorder, no section, wants full detail -> all sections
    elif len(disorders) == 1 and wants_full:
        chunks = _fetch_by_filter(cur, disorder=disorders[0])

    # Case: 1 disorder, no section, specific question -> vector search within disorder
    elif len(disorders) == 1:
        query_embedding = embed_batch([state["current_question"]])[0]
        chunks = _fetch_by_vector(cur, query_embedding, disorder=disorders[0], top_k=5)

    # Case: no disorder detected -> pure vector search, whole table
    else:
        from app.llm import expand_to_clinical_terms

        # ✅ Classify query first
        result = expand_to_clinical_terms(state["current_question"])

        # ✅ If general query — skip DSM retrieval
        if result["type"] == "general":
            print(f"DEBUG - General query detected, skipping DSM retrieval: {state['current_question']}")
            state["chunks"] = []
            state["is_general"] = True
            return state

        # ✅ Clinical query — use expanded query
        expanded_query = result["query"]

        original_embedding = embed_batch([state["current_question"]])[0]
        expanded_embedding = embed_batch([expanded_query])[0]

        chunks_from_original = _fetch_by_vector(cur, original_embedding, disorder=None, top_k=30)
        chunks_from_expanded = _fetch_by_vector(cur, expanded_embedding, disorder=None, top_k=30)

        # Merge: interleave so neither source dominates, then dedupe by chunk_id
        merged_raw = []
        for a, b in zip(chunks_from_original, chunks_from_expanded):
            merged_raw.append(a)
            merged_raw.append(b)
        # in case one list is longer than the other
        merged_raw += chunks_from_original[len(chunks_from_expanded):]
        merged_raw += chunks_from_expanded[len(chunks_from_original):]

        # Dedupe by chunk_id only — allow multiple sections of the same
        # disorder (e.g. Diagnostic Criteria + Differential Diagnosis)
        deduped = []
        seen_chunk_ids = set()
        for c in merged_raw:
            if c["chunk_id"] in seen_chunk_ids:
                continue
            seen_chunk_ids.add(c["chunk_id"])
            deduped.append(c)

        # Cross-encoder reranking: score every candidate against the
        # user's question and keep only the most relevant chunks.
        chunks = rerank_chunks(state["current_question"], deduped, top_k=7)

    cur.close()
    conn.close()

    print(f"DEBUG - Retrieved chunks: {len(chunks)}")
    print(f"DEBUG - Retrieved disorders: {[c['disorder_name'] for c in chunks]}")
    state["chunks"] = chunks
    state["is_general"] = False
    return state

# --------------------------------------------------------------------------
# Node 3: Generate
# --------------------------------------------------------------------------

def generate(state: RAGState) -> RAGState:
    if state["is_general"]:
        state["answer"] = generate_general_response(
            state["current_question"]
        )
        return state

    if not state["chunks"]:
        state["answer"] = (
            "I couldn't find relevant information in the DSM-5-TR "
            "reference for this question."
        )
        return state

    state["answer"] = generate_answer(
        state["query"],
        state["chunks"]
    )

    return state


# --------------------------------------------------------------------------
# Build the graph
# --------------------------------------------------------------------------

def build_graph():
    workflow = StateGraph(RAGState)

    workflow.add_node("analyze_query", analyze_query)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("generate", generate)

    workflow.set_entry_point("analyze_query")
    workflow.add_edge("analyze_query", "retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)

    return workflow.compile()


# --------------------------------------------------------------------------
# CLI test
# --------------------------------------------------------------------------

if __name__ == "__main__":
    app = build_graph()

    print("DSM-5 RAG Chatbot")
    print("Type 'exit', 'quit', or 'bye' to stop.\n")

    while True:
        test_query = input("Ask a question: ").strip()

        # Exit condition
        if test_query.lower() in ["exit", "quit", "bye"]:
            print("\nGoodbye!")
            break

        result = app.invoke({
            "query": test_query,
            "disorders": [],
            "sections": [],
            "wants_full_detail": False,
            "chunks": [],
            "answer": None,
        })

        print("\n--- ANSWER ---")
        print(result["answer"])
        print("-" * 60)