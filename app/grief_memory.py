"""
app/grief_memory.py
-------------------
Longitudinal Grief Memory & Calendar Service stored in PostgreSQL with pgvector.
Connects calendar reflections to vector embeddings for longitudinal context retrieval.
"""

import json
import logging
from typing import List, Dict, Optional
from app.vectorstore import get_connection
from app.embedder import embed_batch

logger = logging.getLogger(__name__)
TABLE_NAME = "grief_workbook_entries"


def save_workbook_entry(
    entry_date: str,
    entry_text: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    themes: Optional[dict] = None,
) -> dict:
    """
    Saves or updates a Grief Workbook reflection for a given date in Postgres,
    generating vector embeddings for longitudinal memory retrieval.
    """
    if not entry_text or not entry_text.strip():
        raise ValueError("Entry text cannot be empty.")

    embedding_list = embed_batch([entry_text.strip()])[0]
    themes_json = json.dumps(themes or {})

    conn = get_connection()
    with conn.cursor() as cur:
        if user_id:
            cur.execute(
                f"""
                SELECT id FROM {TABLE_NAME}
                WHERE user_id = %s AND entry_date = %s
                """,
                (user_id, entry_date),
            )
        else:
            cur.execute(
                f"""
                SELECT id FROM {TABLE_NAME}
                WHERE (session_id = %s OR session_id IS NULL) AND entry_date = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                (session_id, entry_date),
            )
        existing = cur.fetchone()

        if existing:
            entry_id = existing[0]
            cur.execute(
                f"""
                UPDATE {TABLE_NAME}
                SET entry_text = %s, themes = %s, embedding = %s::vector, updated_at = NOW()
                WHERE id = %s
                """,
                (entry_text.strip(), themes_json, embedding_list, entry_id),
            )
        else:
            cur.execute(
                f"""
                INSERT INTO {TABLE_NAME} (user_id, session_id, entry_date, entry_text, themes, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::vector)
                RETURNING id
                """,
                (user_id, session_id, entry_date, entry_text.strip(), themes_json, embedding_list),
            )
            entry_id = cur.fetchone()[0]

    conn.commit()
    conn.close()

    logger.info("Saved Grief Workbook entry ID %d for date %s", entry_id, entry_date)
    return {
        "id": entry_id,
        "entry_date": entry_date,
        "entry_text": entry_text.strip(),
        "status": "saved",
    }


def get_workbook_entry_by_date(entry_date: str, user_id: Optional[str] = None, session_id: Optional[str] = None) -> Optional[dict]:
    """Retrieves a single workbook reflection for a specific calendar date."""
    conn = get_connection()
    with conn.cursor() as cur:
        if user_id:
            cur.execute(
                f"""
                SELECT id, entry_date, entry_text, themes, created_at, session_id
                FROM {TABLE_NAME}
                WHERE user_id = %s AND entry_date = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                (user_id, entry_date),
            )
        else:
            cur.execute(
                f"""
                SELECT id, entry_date, entry_text, themes, created_at, session_id
                FROM {TABLE_NAME}
                WHERE (session_id = %s OR session_id IS NULL) AND entry_date = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                (session_id, entry_date),
            )
        row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "entry_date": str(row[1]),
        "entry_text": row[2],
        "themes": row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}"),
        "created_at": str(row[4]),
        "session_id": str(row[5]) if row[5] else None,
    }


def link_workbook_entry_session(
    session_id: str,
    entry_date: Optional[str] = None,
    entry_id: Optional[int] = None,
    user_id: Optional[str] = None,
) -> bool:
    """Links an existing workbook reflection to a chat session ID."""
    conn = get_connection()
    with conn.cursor() as cur:
        if entry_id:
            if user_id:
                cur.execute(
                    f"UPDATE {TABLE_NAME} SET session_id = %s, updated_at = NOW() WHERE id = %s AND user_id = %s RETURNING id;",
                    (session_id, entry_id, user_id),
                )
            else:
                cur.execute(
                    f"UPDATE {TABLE_NAME} SET session_id = %s, updated_at = NOW() WHERE id = %s RETURNING id;",
                    (session_id, entry_id),
                )
        elif entry_date:
            if user_id:
                cur.execute(
                    f"UPDATE {TABLE_NAME} SET session_id = %s, updated_at = NOW() WHERE entry_date = %s AND user_id = %s RETURNING id;",
                    (session_id, entry_date, user_id),
                )
            else:
                cur.execute(
                    f"UPDATE {TABLE_NAME} SET session_id = %s, updated_at = NOW() WHERE entry_date = %s RETURNING id;",
                    (session_id, entry_date),
                )
        row = cur.fetchone()
    conn.commit()
    conn.close()
    return row is not None


def delete_workbook_entry(
    entry_date: Optional[str] = None,
    entry_id: Optional[int] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> bool:
    """
    Deletes a workbook reflection and its pgvector embedding permanently.
    Ensures it will never appear in future semantic grief retrieval.
    """
    conn = get_connection()
    with conn.cursor() as cur:
        if entry_id:
            if user_id:
                cur.execute(
                    f"DELETE FROM {TABLE_NAME} WHERE id = %s AND user_id = %s RETURNING id;",
                    (entry_id, user_id),
                )
            else:
                cur.execute(
                    f"DELETE FROM {TABLE_NAME} WHERE id = %s RETURNING id;",
                    (entry_id,),
                )
        elif entry_date:
            if user_id:
                cur.execute(
                    f"DELETE FROM {TABLE_NAME} WHERE entry_date = %s AND user_id = %s RETURNING id;",
                    (entry_date, user_id),
                )
            else:
                cur.execute(
                    f"DELETE FROM {TABLE_NAME} WHERE entry_date = %s AND (session_id = %s OR session_id IS NULL) RETURNING id;",
                    (entry_date, session_id),
                )
        else:
            conn.close()
            return False

        row = cur.fetchone()
    conn.commit()
    conn.close()
    return row is not None


def get_calendar_dates(user_id: Optional[str] = None, session_id: Optional[str] = None) -> List[str]:
    """Returns a list of YYYY-MM-DD date strings that have existing workbook reflections."""
    conn = get_connection()
    with conn.cursor() as cur:
        if user_id:
            cur.execute(
                f"SELECT DISTINCT entry_date FROM {TABLE_NAME} WHERE user_id = %s ORDER BY entry_date DESC",
                (user_id,),
            )
        else:
            cur.execute(
                f"SELECT DISTINCT entry_date FROM {TABLE_NAME} WHERE session_id = %s OR session_id IS NULL ORDER BY entry_date DESC",
                (session_id,),
            )
        rows = cur.fetchall()
    conn.close()
    return [str(r[0]) for r in rows]


def retrieve_relevant_grief_memory(
    query_text: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    top_k: int = 3,
) -> List[dict]:
    """
    Performs pgvector cosine similarity search over past Grief Workbook entries
    to load relevant longitudinal memory into the current session context.
    """
    if not query_text or not query_text.strip():
        return []

    try:
        query_embedding = embed_batch([query_text.strip()])[0]
        conn = get_connection()
        with conn.cursor() as cur:
            if user_id:
                cur.execute(
                    f"""
                    SELECT id, entry_date, entry_text
                    FROM {TABLE_NAME}
                    WHERE user_id = %s AND embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (user_id, query_embedding, top_k),
                )
            else:
                cur.execute(
                    f"""
                    SELECT id, entry_date, entry_text
                    FROM {TABLE_NAME}
                    WHERE (session_id = %s OR session_id IS NULL) AND embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (session_id, query_embedding, top_k),
                )
            rows = cur.fetchall()
        conn.close()

        return [
            {
                "entry_date": str(r[1]),
                "entry_text": r[2],
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("Longitudinal grief memory retrieval failed: %s", str(e))
        return []
