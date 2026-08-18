"""
db_tables.py
------------
Database table creation script for Supabase/PostgreSQL.
Run this once to set up all tables.

Tables:
- user_profiles: User profile data (name, avatar, etc.)
- chat_history: Chat messages (current)
- user_sessions: Chat sessions (future)
- session_messages: Messages within sessions (future)
"""

from app.vectorstore import get_connection


# ============================================================
# 1. USER_PROFILES TABLE
# ============================================================

def create_user_profiles_table():
    """Create user_profiles table for user data."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
                email TEXT NOT NULL,
                full_name TEXT,
                avatar_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);
        """)
        cur.execute("ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;")
        
        # Policies
        cur.execute("""
            DROP POLICY IF EXISTS "Users can view own profile" ON user_profiles;
            CREATE POLICY "Users can view own profile" ON user_profiles
                FOR SELECT USING (auth.uid() = user_id);
        """)
        cur.execute("""
            DROP POLICY IF EXISTS "Users can insert own profile" ON user_profiles;
            CREATE POLICY "Users can insert own profile" ON user_profiles
                FOR INSERT WITH CHECK (auth.uid() = user_id);
        """)
        cur.execute("""
            DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;
            CREATE POLICY "Users can update own profile" ON user_profiles
                FOR UPDATE USING (auth.uid() = user_id);
        """)
        
        conn.commit()
    conn.close()
    print("✅ user_profiles table created successfully!")


# ============================================================
# 2. TRIGGER: AUTO-CREATE PROFILE ON SIGNUP
# ============================================================

def create_profile_trigger():
    """Create trigger to auto-create profile when user signs up."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE OR REPLACE FUNCTION public.handle_new_user()
            RETURNS TRIGGER AS $$
            BEGIN
                INSERT INTO public.user_profiles (user_id, email, full_name)
                VALUES (
                    NEW.id,
                    NEW.email,
                    COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1))
                );
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql SECURITY DEFINER;
        """)
        
        cur.execute("""
            DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
            CREATE TRIGGER on_auth_user_created
                AFTER INSERT ON auth.users
                FOR EACH ROW
                EXECUTE FUNCTION public.handle_new_user();
        """)
        
        conn.commit()
    conn.close()
    print("✅ Profile trigger created successfully!")


# ============================================================
# 3. CHAT HISTORY — ADD user_id COLUMN
# ============================================================

def add_user_id_to_chat_history():
    """Add user_id column to chat_history if not exists."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS user_id UUID DEFAULT NULL;
        """)
        cur.execute("""
            ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS title TEXT DEFAULT NULL;
        """)
        conn.commit()
    conn.close()
    print("✅ chat_history columns added (user_id, title)!")


# ============================================================
# 4. CHAT HISTORY RLS
# ============================================================

def setup_chat_history_rls():
    """Ensure RLS is enabled on chat_history table."""
    conn = get_connection()
    with conn.cursor() as cur:
        # Add columns first
        cur.execute("""
            ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS user_id UUID DEFAULT NULL;
        """)
        cur.execute("""
            ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS title TEXT DEFAULT NULL;
        """)
        
        cur.execute("ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;")
        
        # Drop existing policies
        cur.execute('DROP POLICY IF EXISTS "Users can view their own chats" ON chat_history;')
        cur.execute('DROP POLICY IF EXISTS "Users can insert their own chats" ON chat_history;')
        cur.execute('DROP POLICY IF EXISTS "Users can update their own chats" ON chat_history;')
        cur.execute('DROP POLICY IF EXISTS "Users can delete their own chats" ON chat_history;')
        
        # Create new policies
        cur.execute("""
            CREATE POLICY "Users can view their own chats" ON chat_history
                FOR SELECT
                USING (auth.uid() = user_id OR user_id IS NULL);
        """)
        cur.execute("""
            CREATE POLICY "Users can insert their own chats" ON chat_history
                FOR INSERT
                WITH CHECK (auth.uid() = user_id OR user_id IS NULL);
        """)
        cur.execute("""
            CREATE POLICY "Users can update their own chats" ON chat_history
                FOR UPDATE
                USING (auth.uid() = user_id);
        """)
        cur.execute("""
            CREATE POLICY "Users can delete their own chats" ON chat_history
                FOR DELETE
                USING (auth.uid() = user_id);
        """)
        
        conn.commit()
    conn.close()
    print("✅ chat_history RLS configured!")


# ============================================================
# 5. USER_SESSIONS (Future)
# ============================================================

def create_user_sessions_table():
    """Create user_sessions table for future use."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
                title TEXT DEFAULT 'New chat',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
        """)
        cur.execute("ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;")
        
        cur.execute("""
            DROP POLICY IF EXISTS "Users can view own sessions" ON user_sessions;
            CREATE POLICY "Users can view own sessions" ON user_sessions
                FOR SELECT USING (auth.uid() = user_id);
        """)
        cur.execute("""
            DROP POLICY IF EXISTS "Users can insert own sessions" ON user_sessions;
            CREATE POLICY "Users can insert own sessions" ON user_sessions
                FOR INSERT WITH CHECK (auth.uid() = user_id);
        """)
        cur.execute("""
            DROP POLICY IF EXISTS "Users can update own sessions" ON user_sessions;
            CREATE POLICY "Users can update own sessions" ON user_sessions
                FOR UPDATE USING (auth.uid() = user_id);
        """)
        cur.execute("""
            DROP POLICY IF EXISTS "Users can delete own sessions" ON user_sessions;
            CREATE POLICY "Users can delete own sessions" ON user_sessions
                FOR DELETE USING (auth.uid() = user_id);
        """)
        
        conn.commit()
    conn.close()
    print("✅ user_sessions table created!")


# ============================================================
# 6. SESSION_MESSAGES (Future)
# ============================================================

def create_session_messages_table():
    """Create session_messages table for future use."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS session_messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id UUID NOT NULL REFERENCES user_sessions(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_messages_session_id ON session_messages(session_id);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_messages_created_at ON session_messages(created_at);
        """)
        cur.execute("ALTER TABLE session_messages ENABLE ROW LEVEL SECURITY;")
        
        cur.execute("""
            DROP POLICY IF EXISTS "Users can view messages" ON session_messages;
            CREATE POLICY "Users can view messages" ON session_messages
                FOR SELECT
                USING (EXISTS (
                    SELECT 1 FROM user_sessions 
                    WHERE user_sessions.id = session_id AND user_sessions.user_id = auth.uid()
                ));
        """)
        cur.execute("""
            DROP POLICY IF EXISTS "Users can insert messages" ON session_messages;
            CREATE POLICY "Users can insert messages" ON session_messages
                FOR INSERT
                WITH CHECK (EXISTS (
                    SELECT 1 FROM user_sessions 
                    WHERE user_sessions.id = session_id AND user_sessions.user_id = auth.uid()
                ));
        """)
        cur.execute("""
            DROP POLICY IF EXISTS "Users can update messages" ON session_messages;
            CREATE POLICY "Users can update messages" ON session_messages
                FOR UPDATE
                USING (EXISTS (
                    SELECT 1 FROM user_sessions 
                    WHERE user_sessions.id = session_id AND user_sessions.user_id = auth.uid()
                ));
        """)
        cur.execute("""
            DROP POLICY IF EXISTS "Users can delete messages" ON session_messages;
            CREATE POLICY "Users can delete messages" ON session_messages
                FOR DELETE
                USING (EXISTS (
                    SELECT 1 FROM user_sessions 
                    WHERE user_sessions.id = session_id AND user_sessions.user_id = auth.uid()
                ));
        """)
        
        conn.commit()
    conn.close()
    print("✅ session_messages table created!")


def create_grief_workbook_table():
    """Create grief_workbook_entries table for Grief Workbook Calendar & longitudinal memory with pgvector."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grief_workbook_entries (
                id SERIAL PRIMARY KEY,
                user_id UUID DEFAULT NULL,
                session_id TEXT DEFAULT NULL,
                entry_date DATE NOT NULL,
                entry_text TEXT NOT NULL,
                themes JSONB DEFAULT '{}'::jsonb,
                embedding vector(768) DEFAULT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_grief_workbook_user_id ON grief_workbook_entries(user_id);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_grief_workbook_entry_date ON grief_workbook_entries(entry_date);
        """)
        conn.commit()
    conn.close()
    print("✅ grief_workbook_entries table created successfully!")


# ============================================================
# RUN ALL TABLES
# ============================================================

def create_all_tables():
    """Create all tables and setup triggers."""
    print("🔄 Creating tables...")
    
    try:
        # 1. User profiles
        create_user_profiles_table()
        
        # 2. Profile trigger
        create_profile_trigger()
        
        # 3. Chat history columns
        add_user_id_to_chat_history()
        
        # 4. Chat history RLS
        setup_chat_history_rls()
        
        # 5. Grief workbook table with pgvector
        create_grief_workbook_table()
        
        # 6. Future tables (uncomment when ready)
        # create_user_sessions_table()
        # create_session_messages_table()
        
        print("\n✅ All tables created successfully!")
    except Exception as e:
        print(f"❌ Error: {e}")


def drop_all_tables():
    """Drop all tables (use with caution!)."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS session_messages CASCADE;")
        cur.execute("DROP TABLE IF EXISTS user_sessions CASCADE;")
        cur.execute("DROP TABLE IF EXISTS chat_history CASCADE;")
        cur.execute("DROP TABLE IF EXISTS user_profiles CASCADE;")
        conn.commit()
    conn.close()
    print("✅ All tables dropped!")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        drop_all_tables()
    else:
        create_all_tables()