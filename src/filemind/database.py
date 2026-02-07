import sqlite3
from . import config

def get_db_connection() -> sqlite3.Connection:
    """Establishes a connection to the SQLite database."""
    return sqlite3.connect(config.DB_PATH)

def initialize_database():
    """
    Initializes the database by creating the necessary tables if they don't exist.
    This function is idempotent.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create 'files' table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY,
        file_path TEXT NOT NULL UNIQUE,
        file_hash TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        last_modified_time INTEGER NOT NULL,
        indexed_at INTEGER NOT NULL
    );
    """)

    # Create 'chunks' table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY,
        file_id INTEGER NOT NULL,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
    );
    """)

    # Create 'chunks_fts' virtual table for full-text search
    # It links to the 'chunks' table.
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
        content,
        content='chunks',
        content_rowid='id'
    );
    """)
    
    # Create a trigger to keep the FTS table synchronized with the chunks table
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS chunks_after_insert
    AFTER INSERT ON chunks
    BEGIN
        INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
    END;
    """)
    
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS chunks_after_delete
    AFTER DELETE ON chunks
    BEGIN
        INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES ('delete', old.id, old.content);
    END;
    """)

    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS chunks_after_update
    AFTER UPDATE ON chunks
    BEGIN
        INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES ('delete', old.id, old.content);
        INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
    END;
    """)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    print("Initializing database...")
    initialize_database()
    print(f"Database created/verified at: {config.DB_PATH}")
