import sqlite3
import time
from pathlib import Path
from typing import Optional, Tuple

from . import database

def add_file(file_path: Path, file_hash: str, file_size: int, mtime: int) -> int:
    """
    Adds a file record to the database.

    Returns:
        The ID of the newly inserted file.
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()
    indexed_at = int(time.time())
    cursor.execute(
        """
        INSERT INTO files (file_path, file_hash, file_size, last_modified_time, indexed_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (str(file_path), file_hash, file_size, mtime, indexed_at),
    )
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

def get_file_by_path(file_path: Path) -> Optional[Tuple[int, int, int]]:
    """
    Retrieves a file's ID, size, and last modified time from the database.

    Returns:
        A tuple of (id, file_size, last_modified_time) or None if not found.
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, file_size, last_modified_time FROM files WHERE file_path = ?",
        (str(file_path),),
    )
    result = cursor.fetchone()
    conn.close()
    return result

def delete_chunks_for_file(file_id: int):
    """Deletes all chunks associated with a specific file_id."""
    conn = database.get_db_connection()
    # Enable foreign key support to ensure ON DELETE CASCADE works
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()

def add_chunk(file_id: int, chunk_index: int, content: str) -> int:
    """

    Adds a text chunk to the database. The triggers will automatically update the FTS table.

    Returns:
        The ID of the newly inserted chunk.
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chunks (file_id, chunk_index, content) VALUES (?, ?, ?)",
        (file_id, chunk_index, content),
    )
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id
