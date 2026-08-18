"""
chat_memory.py
---------------
Persistent chat-history storage in Postgres (Supabase), replacing the
in-memory dictionary. Uses the same connection as vectorstore.py.
"""

from app.vectorstore import get_connection

TABLE_NAME = "chat_history"


def create_chat_table():
    """Create chat_history table with all columns."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                user_id UUID DEFAULT NULL,
                title TEXT DEFAULT NULL
            );
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_session_id
            ON {TABLE_NAME} (session_id);
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_user_id
            ON {TABLE_NAME} (user_id);
        """)
    conn.commit()
    conn.close()
    print(f"Table '{TABLE_NAME}' ready.")


def create_session(session_id: str, user_id: str = None):
    """Marks a new session as started (no messages yet)."""
    add_message(session_id, "system", "Chat session started", user_id)


def add_message(session_id: str, role: str, content: str, user_id: str = None):
    """Add a message to chat history with optional user_id."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {TABLE_NAME} (session_id, role, content, user_id)
            VALUES (%s, %s, %s, %s)
            """,
            (session_id, role, content, user_id),
        )
    conn.commit()
    conn.close()


def set_title_if_unset(session_id: str, title: str, user_id: str = None):
    """Auto-names a session from its first message — but only if no title
    exists yet, so it never clobbers a title the user set via rename."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {TABLE_NAME}
            SET title = %s
            WHERE session_id = %s AND user_id = %s AND title IS NULL
            """,
            (title, session_id, user_id),
        )
    conn.commit()
    conn.close()


def get_history(session_id: str, limit: int = 12, user_id: str = None):
    """Returns the last `limit` messages for a session, oldest first."""
    conn = get_connection()
    with conn.cursor() as cur:
        if user_id:
            cur.execute(
                f"""
                SELECT role, content FROM {TABLE_NAME}
                WHERE session_id = %s AND user_id = %s AND role != 'system'
                ORDER BY id DESC
                LIMIT %s
                """,
                (session_id, user_id, limit),
            )
        else:
            cur.execute(
                f"""
                SELECT role, content FROM {TABLE_NAME}
                WHERE session_id = %s AND role != 'system'
                ORDER BY id DESC
                LIMIT %s
                """,
                (session_id, limit),
            )
        rows = cur.fetchall()
    conn.close()
    rows.reverse()  # oldest first
    return [{"role": r[0], "content": r[1]} for r in rows]


def session_exists(session_id: str, user_id: str = None) -> bool:
    """Cheap existence/ownership check — doesn't care whether it has any
    non-system messages yet (unlike get_history, which filters system out)."""
    conn = get_connection()
    with conn.cursor() as cur:
        if user_id:
            cur.execute(
                f"SELECT 1 FROM {TABLE_NAME} WHERE session_id = %s AND user_id = %s LIMIT 1",
                (session_id, user_id),
            )
        else:
            cur.execute(
                f"SELECT 1 FROM {TABLE_NAME} WHERE session_id = %s LIMIT 1",
                (session_id,),
            )
        row = cur.fetchone()
    conn.close()
    return row is not None


def list_sessions(user_id: str = None):
    conn = get_connection()
    with conn.cursor() as cur:
        if user_id:
            cur.execute(f"""
                WITH session_times AS (
                    SELECT session_id, MIN(created_at) AS created_at
                    FROM {TABLE_NAME}
                    WHERE user_id = %s
                    GROUP BY session_id
                ), session_titles AS (
                    SELECT DISTINCT ON (session_id)
                        session_id,
                        title
                    FROM {TABLE_NAME}
                    WHERE user_id = %s AND title IS NOT NULL
                    ORDER BY session_id, created_at DESC
                )
                SELECT
                    t.session_id,
                    COALESCE(ti.title, 'New chat') AS title,
                    t.created_at
                FROM session_times t
                LEFT JOIN session_titles ti ON ti.session_id = t.session_id
                ORDER BY t.created_at DESC
            """, (user_id, user_id))
        else:
            cur.execute(f"""
                WITH session_times AS (
                    SELECT session_id, MIN(created_at) AS created_at
                    FROM {TABLE_NAME}
                    GROUP BY session_id
                ), session_titles AS (
                    SELECT DISTINCT ON (session_id)
                        session_id,
                        title
                    FROM {TABLE_NAME}
                    WHERE title IS NOT NULL
                    ORDER BY session_id, created_at DESC
                )
                SELECT
                    t.session_id,
                    COALESCE(ti.title, 'New chat') AS title,
                    t.created_at
                FROM session_times t
                LEFT JOIN session_titles ti ON ti.session_id = t.session_id
                ORDER BY t.created_at DESC
            """)
        rows = cur.fetchall()
    conn.close()
    return [{
        "session_id": r[0],
        "title": r[1][:40] + "…" if len(r[1]) > 40 else r[1],
        "created_at": str(r[2])
    } for r in rows]


def delete_session(session_id: str, user_id: str = None):
    """Delete a session and all its messages."""
    conn = get_connection()
    with conn.cursor() as cur:
        if user_id:
            cur.execute(
                f"DELETE FROM {TABLE_NAME} WHERE session_id = %s AND user_id = %s",
                (session_id, user_id),
            )
        else:
            cur.execute(
                f"DELETE FROM {TABLE_NAME} WHERE session_id = %s",
                (session_id,),
            )
        conn.commit()
    conn.close()


def rename_session(session_id: str, title: str, user_id: str = None):
    """Explicit rename — always overwrites, unlike set_title_if_unset."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE {TABLE_NAME} SET title = %s WHERE session_id = %s AND user_id = %s",
            (title, session_id, user_id),
        )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    create_chat_table()