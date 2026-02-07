from pathlib import Path
import os
import time
from typing import List

import typer

from . import (
    config,
    database,
    hasher,
    repository,
    extractor,
    embedder,
    vector_store,
)

app = typer.Typer(
    help="FileMind: A local-first file intelligence engine.",
    add_completion=False,
)

def _process_file(file_path: Path, vs: vector_store.VectorStore):
    """Processes a single file for indexing."""
    print(f"  Processing: {file_path.name}")
    
    # 1. Get file metadata
    try:
        mtime = int(file_path.stat().st_mtime)
        size = file_path.stat().st_size
    except FileNotFoundError:
        print(f"    [WARN] File not found during processing: {file_path}")
        return

    # 2. Check if file needs re-indexing
    existing_file = repository.get_file_by_path(file_path)
    if existing_file:
        file_id, db_size, db_mtime = existing_file
        if db_size == size and db_mtime == mtime:
            print("    Skipping (unchanged).")
            return
        else:
            print("    File changed, re-indexing...")
            # Deleting the old file record will cascade and delete all its chunks
            repository.delete_chunks_for_file(file_id)
            # Note: This leaves orphaned vectors in the FAISS index.
            # The plan addresses this with a 'rebuild-index' command later.
            
    # 3. Generate file hash
    file_hash = hasher.generate_file_hash(file_path)
    
    # 4. Add file to database
    file_id = repository.add_file(file_path, file_hash, size, mtime)
    
    # 5. Extract text
    text = extractor.extract_text(file_path)
    if not text:
        print("    Skipping (no text extracted).")
        return
        
    # 6. Chunk text
    chunks = list(extractor.chunk_text(text))
    if not chunks:
        print("    Skipping (no chunks generated).")
        return

    # 7. Generate embeddings for all chunks in a batch
    try:
        embeddings = embedder.generate_embeddings(chunks)
    except FileNotFoundError as e:
        typer.secho(f"ERROR: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    # 8. Add chunks and embeddings to stores
    for i, chunk_content in enumerate(chunks):
        # The chunk_id from the DB must correspond to the vector's position in FAISS
        chunk_id = repository.add_chunk(file_id, i, chunk_content)
        
        # We expect the FAISS index 'ntotal' to match the latest chunk_id
        if vs.index.ntotal != chunk_id - 1:
            typer.secho(
                f"FATAL: FAISS index out of sync. Expected ID {chunk_id - 1}, found {vs.index.ntotal}. "
                "Please run `filemind rebuild-index`.",
                fg=typer.colors.RED
            )
            raise typer.Exit(1)
            
    vs.add(embeddings)
    print(f"    Indexed {len(chunks)} chunks.")


@app.command()
def scan(
    directory: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="The directory to scan for files.",
    )
):
    """
    Scans a directory, indexing new or modified files.
    """
    typer.secho(f"Starting scan of directory: {directory}", fg=typer.colors.BLUE)
    start_time = time.time()
    
    # Ensure database is initialized
    database.initialize_database()
    
    # Load vector store
    vs = vector_store.get_vector_store()

    supported_extensions = {'.pdf', '.docx', '.txt'}
    
    files_processed = 0
    for file_path in directory.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            _process_file(file_path, vs)
            files_processed += 1

    # Persist the updated FAISS index
    vs.save()
    
    end_time = time.time()
    typer.secho(
        f"\nScan complete. Processed {files_processed} files in {end_time - start_time:.2f} seconds.",
        fg=typer.colors.GREEN,
    )

if __name__ == "__main__":
    app()
