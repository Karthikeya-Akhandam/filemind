import sqlite3
import time
from pathlib import Path
from typing import Optional, Tuple, List

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

def delete_file_and_chunks(file_id: int):
    """
    Deletes a file record and all its associated chunks from the database.
    Because of ON DELETE CASCADE, deleting from 'files' will delete from 'chunks'.
    """
    conn = database.get_db_connection()
    conn.execute("PRAGMA foreign_keys = ON") # Ensure FKs are enabled
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

def find_duplicate_hashes() -> List[Tuple[str, int]]:
    """
    Finds file hashes that appear more than once in the database.

    Returns:
        A list of tuples, where each tuple contains (file_hash, count).
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT file_hash, COUNT(*)
        FROM files
        GROUP BY file_hash
        HAVING COUNT(*) > 1
        """
    )
    results = cursor.fetchall()
    conn.close()
    return results

def get_files_by_hash(file_hash: str) -> List[Tuple[str, int, int]]:
    """
    Retrieves all files (path, size, mtime) for a given file hash.

    Returns:
        A list of tuples, where each tuple is (file_path, file_size, last_modified_time).
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT file_path, file_size, last_modified_time FROM files WHERE file_hash = ?",
        (file_hash,),
    )
    results = cursor.fetchall()
    conn.close()
    return results