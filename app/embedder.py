"""
embedder.py
-----------
Reads chunks.json (output of chunker.py) and generates embeddings for each
chunk's text using a local sentence-transformers model (BAAI/bge-base-en-v1.5).

No API keys, no quota limits, no network calls — runs fully offline.
"""

import os
import json
from pathlib import Path

from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
BATCH_SIZE = 50

_model = SentenceTransformer(EMBEDDING_MODEL)


def embed_batch(texts: list):
    """Embeds a batch of texts locally, returns list of embedding vectors."""
    embeddings = _model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_chunks(chunks_path: str, output_path: str):
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    done_ids = set()
    chunks_out = []
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            chunks_out = json.load(f)
        done_ids = {c["chunk_id"] for c in chunks_out}

    remaining = [c for c in chunks if c["chunk_id"] not in done_ids]
    print(f"Already embedded: {len(done_ids)} | Remaining: {len(remaining)}")

    for i in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[i:i + BATCH_SIZE]
        texts = [c["text"] for c in batch]

        embeddings = embed_batch(texts)
        for chunk, emb in zip(batch, embeddings):
            chunk["embedding"] = emb
            chunks_out.append(chunk)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(chunks_out, f, ensure_ascii=False)
        print(f"  {len(chunks_out)}/{len(chunks)} done (checkpoint saved)")

    print(f"Saved embedded chunks to {output_path}")


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent / "data"
    embed_chunks(str(base / "chunks.json"), str(base / "chunks_with_embeddings.json"))