"""
vectorstore.py
--------------
Creates the pgvector table (if not exists) and inserts all chunks +
embeddings from chunks_with_embeddings.json into PostgreSQL.
"""

import os
import json
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

EMBEDDING_DIM = 768  # bge-base-en-v1.5 output size

TABLE_NAME = "dsm5_chunks"


def get_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    register_vector(conn)
    return conn


def create_table(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id SERIAL PRIMARY KEY,
                chunk_id TEXT UNIQUE NOT NULL,
                disorder_id INT NOT NULL,
                disorder_name TEXT NOT NULL,
                dsm_section TEXT NOT NULL,
                document_type TEXT NOT NULL,
                chapter TEXT NOT NULL,
                section_name TEXT NOT NULL,
                chunk_index INT NOT NULL,
                page_number INT NOT NULL,
                text TEXT NOT NULL,
                embedding vector({EMBEDDING_DIM}) NOT NULL
            );
        """)
        # Metadata filtering index
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_disorder_section
            ON {TABLE_NAME} (disorder_name, section_name);
        """)
        # Vector similarity index (HNSW)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_embedding_hnsw
            ON {TABLE_NAME} USING hnsw (embedding vector_cosine_ops);
        """)
    print(f"Table '{TABLE_NAME}' ready.")


def insert_chunks(conn, chunks_path: str):
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    rows = [
        (
            c["chunk_id"],
            c["disorder_id"],
            c["disorder_name"],
            c["dsm_section"],
            c["document_type"],
            c["chapter"],
            c["section_name"],
            c["chunk_index"],
            c["page_number"],
            c["text"],
            c["embedding"],
        )
        for c in chunks
    ]

    with conn.cursor() as cur:
        execute_values(
            cur,
            f"""
            INSERT INTO {TABLE_NAME}
            (chunk_id, disorder_id, disorder_name, dsm_section, document_type,
             chapter, section_name, chunk_index, page_number, text, embedding)
            VALUES %s
            ON CONFLICT (chunk_id) DO NOTHING
            """,
            rows,
        )
    print(f"Inserted {len(rows)} chunks (duplicates skipped).")


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent / "data"
    conn = get_connection()
    create_table(conn)
    insert_chunks(conn, str(base / "chunks_with_embeddings.json"))

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME};")
        print(f"Total rows in table: {cur.fetchone()[0]}")

    conn.close()