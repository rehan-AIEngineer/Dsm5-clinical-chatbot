# DSM-5-TR Clinical RAG Chatbot

A Retrieval-Augmented Generation (RAG) chatbot that answers clinical
questions grounded in the DSM-5-TR Disorder Compendium, with empathetic,
context-aware responses.

## Architecture

```
PDF -> Chunking -> Embeddings (local, bge-base-en-v1.5) -> PGVector (Supabase)
    -> Query Analysis -> Retrieval -> LLM Routing (Gemini -> OpenRouter -> Hugging Face)
    -> Chain-of-Thought Answer Generation
```

## Tech Stack

- **Backend:** FastAPI, LangChain, LangGraph
- **Database:** PostgreSQL + pgvector (hosted on Supabase)
- **Embeddings:** sentence-transformers (`BAAI/bge-base-en-v1.5`), local/offline
- **LLM Providers:** Gemini, OpenRouter, Hugging Face (automatic fallback routing)
- **Frontend:** React + Vite + Tailwind CSS

## Features

- 173 DSM-5-TR disorders chunked by section (Diagnostic Criteria, Prevalence, Risk Factors, etc.)
- Section III (Alternative Model for Personality Disorders) handled separately
- Multi-provider LLM routing with automatic fallback on quota/server errors
- Chat session memory with pronoun/context resolution
- Empathetic response tone for personal/emotional queries
- Zero-Shot Chain-of-Thought prompting for reasoning-grounded answers

## Project Structure

```
dsm5-rag/
├── app/
│   ├── chunker.py       # PDF -> structured chunks
│   ├── embedder.py      # local embedding generation
│   ├── vectorstore.py   # PGVector setup + insertion
│   ├── llm.py            # multi-provider routing + prompting
│   ├── graph.py           # LangGraph RAG workflow
│   └── api.py             # FastAPI endpoints
├── frontend/               # React chat interface
├── data/                   # source PDF, chunks (gitignored)
└── requirements.txt
```

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Set up `.env` with database and API credentials
3. Run ingestion: `python app/chunker.py`, then `python app/embedder.py`, then `python app/vectorstore.py`
4. Start backend: `uvicorn app.api:app --reload`
5. Start frontend: `cd frontend && npm run dev`

## Disclaimer

This tool is for informational/reference purposes only and is not a
substitute for professional medical or mental health advice.
