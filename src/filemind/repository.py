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

def get_file_path_by_id(file_id: int) -> Optional[str]:
    """Retrieves a file's path given its ID."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM files WHERE id = ?", (file_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

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

def search_chunks_fts(query: str, limit: int = 20) -> List[int]:
    """
    Performs a full-text search on the chunks_fts table.

    Returns:
        A list of matching chunk IDs.
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT rowid FROM chunks_fts WHERE content MATCH ? ORDER BY rank LIMIT ?",
        (query, limit),
    )
    results = [row[0] for row in cursor.fetchall()]
    conn.close()
    return results

def get_chunk_details_by_ids(chunk_ids: List[int]) -> List[Tuple[int, int, str]]:
    """
    Retrieves chunk details (id, file_id, content) for a list of chunk IDs.
    """
    if not chunk_ids:
        return []
    conn = database.get_db_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in chunk_ids)
    query = f"SELECT id, file_id, content FROM chunks WHERE id IN ({placeholders})"
    cursor.execute(query, chunk_ids)
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_chunks_ordered() -> List[Tuple[int, str]]:
    """
    Retrieves the ID and content of all chunks, ordered by ID.

    Returns:
        A list of tuples, where each tuple is (id, content).
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()
    results = cursor.fetchall()
    conn.close()
    return results

def calculate_hybrid_scores(semantic_results: Tuple, keyword_chunk_ids: List[int]) -> List[Tuple[int, dict]]:
    """
    Calculates hybrid scores for files based on semantic and keyword search results.
    """
    from collections import defaultdict

    distances, semantic_chunk_ids_flat = semantic_results
    
    file_scores = defaultdict(lambda: {"score": 0.0, "is_keyword_match": False})

    # Process semantic search results
    if semantic_chunk_ids_flat.size > 0:
        # FAISS returns 0-based indices, our DB is 1-based
        semantic_db_ids = (semantic_chunk_ids_flat + 1).tolist()
        chunk_details = get_chunk_details_by_ids(semantic_db_ids)
        
        for i, (chunk_id, file_id, _) in enumerate(chunk_details):
            score = float(distances[i])
            if score > file_scores[file_id]["score"]:
                file_scores[file_id]["score"] = score

    # Process keyword search results and apply boost
    if keyword_chunk_ids:
        chunk_details = get_chunk_details_by_ids(keyword_chunk_ids)
        for _, file_id, _ in chunk_details:
            if file_id in file_scores:
                file_scores[file_id]["is_keyword_match"] = True
                file_scores[file_id]["score"] += 0.1 # Apply boost

    # Sort files by final score
    sorted_files = sorted(file_scores.items(), key=lambda item: item[1]["score"], reverse=True)
    
    return sorted_files

