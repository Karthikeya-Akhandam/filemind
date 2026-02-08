from pathlib import Path
import os
import time
from typing import List
from collections import defaultdict
import sys
import shutil

import typer

# Only import lightweight modules at the top level for fast startup
from . import (
    config,
    database,
    hasher,
    repository,
    extractor,
)

app = typer.Typer(
    help="FileMind: A local-first file intelligence engine.",
    add_completion=False,
)

@app.command()
def init():
    """
    Initializes FileMind: sets up directories and prepares model assets.
    """
    # LAZY IMPORT: only needed for init
    from . import vector_store

    typer.secho("Initializing FileMind...", fg=typer.colors.BLUE)
    
    # 1. Ensure application directory exists
    config.APP_DIR.mkdir(parents=True, exist_ok=True)
    config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    typer.secho(f"Application data directory set up at: {config.APP_DIR}", fg=typer.colors.GREEN)

    # 2. Initialize database
    database.initialize_database()
    typer.secho(f"Database initialized at: {config.DB_PATH}", fg=typer.colors.GREEN)

    # 3. Handle model assets
    onnx_model_path = config.MODEL_DIR / "model.onnx"
    tokenizer_json_path = config.MODEL_DIR / "tokenizer.json"

    if onnx_model_path.exists() and tokenizer_json_path.exists():
        typer.secho("Model assets already exist. Skipping preparation.", fg=typer.colors.GREEN)
    else:
        typer.secho("Preparing model assets...", fg=typer.colors.BLUE)
        
        # Check if running as a PyInstaller bundled app
        source_path = None
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # In a bundled app, assets are in a temporary folder (_MEIPASS)
            source_path = Path(sys._MEIPASS) / "models"
            typer.echo("Running in bundled mode. Locating assets...")
        else:
            # In dev mode, assets are in the repo's 'assets/models' directory
            source_path = Path(__file__).parent.parent.parent / "assets" / "models"
            typer.echo("Running in development mode. Locating assets...")

        if source_path and source_path.exists():
            try:
                # Ensure a clean copy
                if config.MODEL_DIR.exists():
                    shutil.rmtree(config.MODEL_DIR)
                shutil.copytree(source_path, config.MODEL_DIR)
                typer.secho(f"Copied model assets to {config.MODEL_DIR}", fg=typer.colors.GREEN)
            except Exception as e:
                typer.secho(f"ERROR: Failed to copy model assets from {source_path}: {e}", fg=typer.colors.RED)
                raise typer.Exit(1)
        else:
            typer.secho(f"ERROR: Model assets not found at the source location ({source_path}).", fg=typer.colors.RED)
            typer.secho("If running from source, ensure the 'assets/models' directory is populated.", fg=typer.colors.YELLOW)
            raise typer.Exit(1)

    # 4. Initialize FAISS index file
    vs = vector_store.get_vector_store()
    vs.save()
    typer.secho(f"FAISS index initialized at: {config.FAISS_INDEX_PATH}", fg=typer.colors.GREEN)
    
    typer.secho("\nFileMind initialization complete! You can now run 'filemind scan <directory>'", fg=typer.colors.GREEN)


def _process_file(file_path: Path):
    """Processes a single file for indexing. Lazily imports heavy modules."""
    # LAZY IMPORT of heavy modules
    from . import embedder, vector_store
    vs = vector_store.get_vector_store()

    typer.echo(f"  Processing: {file_path.name}")
    
    try:
        mtime = int(file_path.stat().st_mtime)
        size = file_path.stat().st_size
    except FileNotFoundError:
        typer.secho(f"    [WARN] File not found: {file_path}", fg=typer.colors.YELLOW)
        return

    existing_file = repository.get_file_by_path(file_path)
    if existing_file:
        file_id, db_size, db_mtime = existing_file
        if db_size == size and db_mtime == mtime:
            typer.echo("    Skipping (unchanged).")
            return
        else:
            typer.echo("    File changed, re-indexing...")
            repository.delete_file_and_chunks(file_id)
            # Note: This requires a `rebuild-index` command to clean up FAISS
            
    file_hash = hasher.generate_file_hash(file_path)
    file_id = repository.add_file(file_path, file_hash, size, mtime)
    
    text = extractor.extract_text(file_path)
    if not text:
        return
        
    chunks = list(extractor.chunk_text(text))
    if not chunks:
        return

    try:
        embeddings = embedder.generate_embeddings(chunks)
    except FileNotFoundError:
        typer.secho("ERROR: Model files not found. Please run 'filemind init'.", fg=typer.colors.RED)
        raise typer.Exit(1)

    # 8. Add chunks to the database
    for i, chunk_content in enumerate(chunks):
        repository.add_chunk(file_id, i, chunk_content)

    # 9. Add all embeddings to the vector store in a single batch
    vs.add(embeddings)
    typer.echo(f"    Indexed {len(chunks)} chunks.")


@app.command()
def scan(directory: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help="The directory to scan for files.")):
    """Scans a directory, indexing new or modified files."""
    typer.secho(f"Starting scan of directory: {directory}", fg=typer.colors.BLUE)
    start_time = time.time()
    
    database.initialize_database()
    supported_extensions = {'.pdf', '.docx', '.txt'}
    
    files_processed = 0
    for file_path in directory.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            _process_file(file_path)
            files_processed += 1
    
    # LAZY IMPORT
    from . import vector_store
    vector_store.get_vector_store().save()
    
    end_time = time.time()
    typer.secho(f"\nScan complete. Processed {files_processed} files in {end_time - start_time:.2f} seconds.", fg=typer.colors.GREEN)

@app.command()
def duplicates():
    """Finds and lists files that are exact duplicates based on their content hash."""
    typer.secho("Searching for duplicate files...", fg=typer.colors.BLUE)
    database.initialize_database()
    duplicate_hashes = repository.find_duplicate_hashes()

    if not duplicate_hashes:
        typer.secho("No exact duplicate files found.", fg=typer.colors.GREEN)
        return

    for file_hash, count in duplicate_hashes:
        typer.secho(f"\nHash: {file_hash} (found {count} times)", fg=typer.colors.YELLOW)
        for file_info in repository.get_files_by_hash(file_hash):
            typer.echo(f"  - {file_info[0]}")
    
    typer.secho("\nDuplicate search complete.", fg=typer.colors.GREEN)

@app.command(help="Performs a hybrid search. Use 'filemind search --help' for options.")
def search(query: str = typer.Argument(..., help="The text to search for."), top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to return.")):
    """Performs a hybrid search for files based on your query."""
    # LAZY IMPORT of heavy modules
    from . import embedder, vector_store

    typer.secho(f"Searching for: '{query}'...", fg=typer.colors.BLUE)
    database.initialize_database()
    
    try:
        vs = vector_store.get_vector_store()
        query_embedding = embedder.generate_embeddings([query])
    except FileNotFoundError:
        typer.secho("ERROR: Model not found. Please run 'filemind init'.", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    distances, semantic_chunk_ids = vs.search(query_embedding, k=top_k * 2)
    keyword_chunk_ids = repository.search_chunks_fts(query, limit=top_k * 2)

    file_results = defaultdict(lambda: {"max_score": 0.0, "keyword_hit": False})
    
    if semantic_chunk_ids.size > 0:
        semantic_chunk_ids_list = (semantic_chunk_ids[0] + 1).tolist()
        chunk_details = repository.get_chunk_details_by_ids(semantic_chunk_ids_list)
        for i, (chunk_id, file_id, content) in enumerate(chunk_details):
            score = float(distances[0][i])
            if score > file_results[file_id]["max_score"]:
                file_results[file_id]["max_score"] = score

    if keyword_chunk_ids:
        chunk_details = repository.get_chunk_details_by_ids(keyword_chunk_ids)
        for chunk_id, file_id, content in chunk_details:
            file_results[file_id]["keyword_hit"] = True

    for file_id in file_results:
        if file_results[file_id]["keyword_hit"]:
            file_results[file_id]["max_score"] += 0.1

    sorted_files = sorted(file_results.items(), key=lambda item: item[1]["max_score"], reverse=True)

    typer.secho("\n--- Search Results ---", fg=typer.colors.GREEN)
    if not sorted_files:
        typer.secho("No relevant files found.", fg=typer.colors.YELLOW)
        return

    for i, (file_id, data) in enumerate(sorted_files[:top_k]):
        file_path = repository.get_file_path_by_id(file_id)
        if file_path:
            score_color = typer.colors.GREEN if data['max_score'] > 0.5 else typer.colors.YELLOW
            typer.secho(f"\n{i+1}. Path: ", fg=typer.colors.WHITE, nl=False)
            typer.secho(file_path, fg=typer.colors.CYAN)
            typer.secho(f"   Score: ", nl=False)
            typer.secho(f"{data['max_score']:.2f}", fg=score_color, bold=True, nl=False)
            if data["keyword_hit"]:
                typer.secho(" (Keyword Match)", fg=typer.colors.MAGENTA)
            else:
                typer.echo("")

@app.command()
def uninstall():
    """Removes all FileMind data, including the database, index, and models."""
    typer.secho("\nWARNING: This will permanently delete ALL FileMind data.", fg=typer.colors.RED, bold=True)
    typer.secho(f"This includes the directory: {config.APP_DIR}", fg=typer.colors.RED)
    
    if not typer.confirm("Are you sure you want to proceed?"):
        typer.secho("Uninstallation cancelled.", fg=typer.colors.YELLOW)
        raise typer.Exit()
        
    try:
        if config.APP_DIR.exists():
            shutil.rmtree(config.APP_DIR)
            typer.secho(f"Successfully removed: {config.APP_DIR}", fg=typer.colors.GREEN)
        else:
            typer.secho("FileMind data directory not found. Nothing to remove.", fg=typer.colors.YELLOW)
    except Exception as e:
        typer.secho(f"ERROR: Failed to remove directory: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    typer.secho("\nFileMind uninstallation complete.", fg=typer.colors.GREEN)

if __name__ == "__main__":
    app()
