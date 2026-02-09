from pathlib import Path
import os
import time
from typing import List, Optional, Tuple
from collections import defaultdict
import sys
import shutil
import importlib.metadata
# import subprocess # Not directly used by CLI, but useful for more complex scenarios

import typer
import requests # Used in version_check but also directly by upgrade command for clearer error handling
from packaging.version import parse as parse_version # Used by upgrade command and version_check

# Only import lightweight modules at the top level for fast startup
from . import (
    config,
    database,
    hasher,
    repository,
    extractor,
    version_check,
)

def version_callback(value: bool):
    if value:
        try:
            version = importlib.metadata.version("filemind")
            typer.echo(f"filemind version {version}")
        except importlib.metadata.PackageNotFoundError:
            typer.echo("filemind version: (local source)")
        raise typer.Exit()

app = typer.Typer(
    help="FileMind: A local-first file intelligence engine.",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show the application's version and exit.",
    )
):
    """
    FileMind: A local-first file intelligence engine.
    Use `filemind [COMMAND] --help` for more information on a specific command.
    """
    pass

def _show_update_notification():
    """Checks for a new version and prints a notification if available."""
    try:
        new_version_info = version_check.check_for_new_version()
        if new_version_info:
            new_version, current_version = new_version_info
            typer.secho(
                f"\n[notice] A new version of FileMind is available: {current_version} -> {new_version}",
                fg=typer.colors.YELLOW,
            )
            typer.secho("         To upgrade, run 'filemind upgrade'", fg=typer.colors.YELLOW)
    except Exception:
        # Fail silently. This is a non-critical feature.
        pass

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
                    shutil.rmtree(config.MODEL_DIR) # Clean up existing model dir if incomplete
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
    _show_update_notification()

def _process_file(file_path: Path):
    """Processes a single file for indexing."""
    from . import embedder, vector_store # LAZY IMPORT
    vs = vector_store.get_vector_store()

    try:
        mtime = int(file_path.stat().st_mtime)
        size = file_path.stat().st_size
    except FileNotFoundError:
        typer.secho(f"    [WARN] Skipping (not found): {file_path}", fg=typer.colors.YELLOW)
        return

    existing_file = repository.get_file_by_path(file_path)
    if existing_file:
        file_id, db_size, db_mtime = existing_file
        if db_size == size and db_mtime == mtime:
            typer.echo(f"  Skipping (unchanged): {file_path.name}")
            return
        else:
            typer.echo(f"  Updating (changed): {file_path.name}")
            repository.delete_file_and_chunks(file_id)
            
    file_hash = hasher.generate_file_hash(file_path)
    file_id = repository.add_file(file_path, file_hash, size, mtime)
    
    text = extractor.extract_text(file_path)
    if not text:
        typer.echo(f"  Skipping (no text): {file_path.name}")
        return
        
    chunks = list(extractor.chunk_text(text))
    if not chunks:
        return

    embeddings = embedder.generate_embeddings(chunks)
    repository.add_chunks_and_vectors(file_id, chunks, embeddings, vs)
    typer.echo(f"    -> Indexed {len(chunks)} chunks.")

@app.command()
def scan(directory: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help="The directory to scan.")):
    """Scans a directory, indexing new or modified files."""
    typer.secho(f"Starting scan of directory: {directory}", fg=typer.colors.BLUE)
    start_time = time.time()
    
    database.initialize_database()
    supported_extensions = {'.pdf', '.docx', '.txt'}
    
    files_to_process = [p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in supported_extensions]
    
    with typer.progressbar(files_to_process, label="Scanning files") as progress:
        for file_path in progress:
            _process_file(file_path)
    
    from . import vector_store # LAZY IMPORT
    vector_store.get_vector_store().save()
    
    end_time = time.time()
    typer.secho(f"\nScan complete. Processed {len(files_to_process)} files in {end_time - start_time:.2f} seconds.", fg=typer.colors.GREEN)
    _show_update_notification()

@app.command()
def search(query: str = typer.Argument(...), top_k: int = typer.Option(5, "--top-k", "-k")):
    """Performs a hybrid search for files based on your query."""
    from . import embedder, vector_store # LAZY IMPORT

    typer.secho(f"Searching for: '{query}'...", fg=typer.colors.BLUE)
    database.initialize_database()
    
    vs = vector_store.get_vector_store()
    query_embedding = embedder.generate_embeddings([query])
        
    semantic_results = vs.search(query_embedding, k=top_k * 2)
    keyword_chunk_ids = repository.search_chunks_fts(query, limit=top_k * 2)

    file_scores = repository.calculate_hybrid_scores(semantic_results, keyword_chunk_ids)

    typer.secho("\n--- Search Results ---", fg=typer.colors.GREEN)
    if not file_scores:
        typer.secho("No relevant files found.", fg=typer.colors.YELLOW)
        return

    for i, (file_id, data) in enumerate(file_scores[:top_k]):
        file_path = repository.get_file_path_by_id(file_id)
        if file_path:
            score_color = typer.colors.GREEN if data['score'] > 0.5 else typer.colors.YELLOW
            typer.secho(f"\n{i+1}. Path: ", fg=typer.colors.WHITE, nl=False)
            typer.secho(file_path, fg=typer.colors.CYAN)
            typer.secho(f"   Score: ", nl=False)
            typer.secho(f"{data['score']:.2f}", fg=score_color, bold=True, nl=False)
            if data["is_keyword_match"]:
                typer.secho(" (Keyword Match)", fg=typer.colors.MAGENTA)
            else:
                typer.echo("")
    _show_update_notification()

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
    _show_update_notification()

@app.command(name="rebuild-index")
def rebuild_index():
    """
    Rebuilds the entire FAISS vector index from the database.
    This is a slow operation but is necessary to fix index inconsistencies.
    """
    typer.secho("WARNING: This will rebuild the entire search index from the database.", fg=typer.colors.YELLOW)
    typer.secho("This can be a slow process for large numbers of files.", fg=typer.colors.YELLOW)
    if not typer.confirm("Are you sure you want to proceed?", default=None):
        raise typer.Abort()

    from . import embedder, vector_store # LAZY IMPORT
    import faiss

    typer.secho("Starting index rebuild...", fg=typer.colors.BLUE)
    start_time = time.time()

    database.initialize_database()
    all_chunks = repository.get_all_chunks_ordered()

    if not all_chunks:
        typer.secho("No chunks found in the database. Nothing to rebuild.", fg=typer.colors.YELLOW)
        new_index = faiss.IndexFlatIP(vector_store.EMBEDDING_DIM)
        faiss.write_index(new_index, str(config.FAISS_INDEX_PATH))
        raise typer.Exit()

    new_index = faiss.IndexFlatIP(vector_store.EMBEDDING_DIM)
    
    batch_size = 500
    total_chunks = len(all_chunks)
    
    with typer.progressbar(range(0, total_chunks, batch_size), label="Re-embedding chunks") as progress:
        for i in progress:
            batch = all_chunks[i : i + batch_size]
            chunk_content = [c[1] for c in batch]
            
            embeddings = embedder.generate_embeddings(chunk_content)
            new_index.add(embeddings)
    
    temp_index_path = config.FAISS_INDEX_PATH.with_suffix(".tmp")
    faiss.write_index(new_index, str(temp_index_path))
    shutil.move(str(temp_index_path), str(config.FAISS_INDEX_PATH))

    end_time = time.time()
    typer.secho(f"\nIndex rebuild complete. Processed {total_chunks} chunks in {end_time - start_time:.2f} seconds.", fg=typer.colors.GREEN)
    _show_update_notification()
    
@app.command()
def upgrade():
    """Checks for and provides instructions to upgrade FileMind."""
    
    typer.secho("Checking for new versions...", fg=typer.colors.BLUE)

    try:
        current_version_str = importlib.metadata.version("filemind")
        current_version = parse_version(current_version_str)
    except importlib.metadata.PackageNotFoundError:
        typer.secho("Could not determine current version (running from source?).", fg=typer.colors.YELLOW)
        return

    try:
        new_version_info = version_check.check_for_new_version() # Reuse check_for_new_version logic
        if new_version_info:
            latest_version_str, _ = new_version_info
            latest_version = parse_version(latest_version_str)
        else:
            latest_version = current_version # Assume current if check_for_new_version fails or no newer version

        if latest_version > current_version:
            typer.secho(f"\n🎉 A new version is available: {latest_version}", fg=typer.colors.GREEN)
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                typer.secho("To upgrade this standalone application, please re-run the installation script:", fg=typer.colors.GREEN)
                typer.secho("  curl -fsSL https://raw.githubusercontent.com/Karthikeya-Akhandam/filemind/main/install.sh | sh", fg=typer.colors.BRIGHT_MAGENTA)
            else:
                typer.secho("To upgrade your pip-installed version, please run:", fg=typer.colors.GREEN)
                typer.secho(f"  pip install --upgrade filemind", fg=typer.colors.BRIGHT_MAGENTA)
        else:
            typer.secho(f"✅ You are on the latest version: {current_version}", fg=typer.colors.GREEN)

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            typer.secho("Could not check for new versions: GitHub Pages rate limit (unlikely) or network issue.", fg=typer.colors.RED)
            typer.secho("Please try again in an hour or check the repository page manually.", fg=typer.colors.YELLOW)
        else:
            typer.secho(f"Error checking for new versions: {e}", fg=typer.colors.RED)
    except requests.exceptions.RequestException as e:
        typer.secho(f"Error checking for new versions: Network error.", fg=typer.colors.RED)

@app.command()
def uninstall():
    """Removes all FileMind data, including the database, index, and models."""
    typer.secho("\nWARNING: This will permanently delete ALL FileMind data.", fg=typer.colors.RED, bold=True)
    typer.secho(f"This includes the directory: {config.APP_DIR}", fg=typer.colors.RED)
    
    if not typer.confirm("Are you sure you want to proceed?", default=None):
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
