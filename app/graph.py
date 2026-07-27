"""
graph.py
--------
Orchestrates the full RAG pipeline as a LangGraph workflow:

    analyze_query -> retrieve -> generate -> END

Handles: single disorder+section, single disorder (full or specific),
disorder-to-disorder comparison, section-to-section comparison (same
disorder), and general fallback queries.
"""

import re
import difflib
from typing import TypedDict, List, Optional

from langgraph.graph import StateGraph, END

from app.vectorstore import get_connection
from app.embedder import embed_batch
from app.llm import generate_answer

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
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT disorder_name FROM dsm5_chunks;")
        names = [row[0] for row in cur.fetchall()]
    conn.close()
    return names


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
        expanded_query = expand_to_clinical_terms(state["current_question"])

        original_embedding = embed_batch([state["current_question"]])[0]
        expanded_embedding = embed_batch([expanded_query])[0]

        chunks_from_original = _fetch_by_vector(cur, original_embedding, disorder=None, top_k=30)
        chunks_from_expanded = _fetch_by_vector(cur, expanded_embedding, disorder=None, top_k=30)

        # Merge: interleave so neither source dominates, then dedupe by disorder
        merged_raw = []
        for a, b in zip(chunks_from_original, chunks_from_expanded):
            merged_raw.append(a)
            merged_raw.append(b)
        # in case one list is longer than the other
        merged_raw += chunks_from_original[len(chunks_from_expanded):]
        merged_raw += chunks_from_expanded[len(chunks_from_original):]

        seen_disorders = set()
        chunks = []
        seen_chunk_ids = set()
        for c in merged_raw:
            if c["chunk_id"] in seen_chunk_ids:
                continue
            seen_chunk_ids.add(c["chunk_id"])
            if c["disorder_name"] not in seen_disorders:
                chunks.append(c)
                seen_disorders.add(c["disorder_name"])
            if len(chunks) >= 12:
                break

    cur.close()
    conn.close()

    print(f"DEBUG - Retrieved chunks: {len(chunks)}")
    print(f"DEBUG - Retrieved disorders: {[c['disorder_name'] for c in chunks]}")
    state["chunks"] = chunks
    return state


# --------------------------------------------------------------------------
# Node 3: Generate
# --------------------------------------------------------------------------

def generate(state: RAGState) -> RAGState:
    if not state["chunks"]:
        state["answer"] = "I couldn't find relevant information in the DSM-5-TR reference for this question."
        return state

    state["answer"] = generate_answer(state["query"], state["chunks"])
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