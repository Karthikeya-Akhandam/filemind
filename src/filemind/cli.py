from pathlib import Path
import os
import time
from typing import List, Optional
from collections import defaultdict
import sys
import shutil
import importlib.metadata

import typer

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
        new_version, current_version = version_check.check_for_new_version()
        if new_version:
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
    """Initializes FileMind: sets up directories and prepares model assets."""
    from . import vector_store # LAZY IMPORT

    typer.secho("Initializing FileMind...", fg=typer.colors.BLUE)
    config.APP_DIR.mkdir(parents=True, exist_ok=True)
    config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    database.initialize_database()
    typer.secho(f"Application data directory set up at: {config.APP_DIR}", fg=typer.colors.GREEN)

    source_path = None
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        source_path = Path(sys._MEIPASS) / "models"
    else:
        source_path = Path(__file__).parent.parent.parent / "assets" / "models"

    if source_path and source_path.exists():
        if not all((config.MODEL_DIR / f).exists() for f in os.listdir(source_path)):
            typer.secho("Copying model assets...", fg=typer.colors.BLUE)
            shutil.copytree(source_path, config.MODEL_DIR, dirs_exist_ok=True)
            typer.secho("Model assets copied.", fg=typer.colors.GREEN)
    
    vs = vector_store.get_vector_store()
    if not config.FAISS_INDEX_PATH.exists():
        vs.save()
    typer.secho("Initialization complete!", fg=typer.colors.GREEN)

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
        
    semantic_chunk_ids = vs.search(query_embedding, k=top_k * 2)
    keyword_chunk_ids = repository.search_chunks_fts(query, limit=top_k * 2)

    typer.echo(f"[Debug] Semantic matches found: {len(semantic_chunk_ids)}")
    typer.echo(f"[Debug] Keyword matches found: {len(keyword_chunk_ids)}")

    file_scores = repository.calculate_hybrid_scores(semantic_chunk_ids, keyword_chunk_ids)

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
    # ... (code for duplicates)
    _show_update_notification()

@app.command(name="rebuild-index")
def rebuild_index():
    """Rebuilds the FAISS index from the database."""
    # ... (code for rebuild-index)
    _show_update_notification()
    
@app.command()
def upgrade():
    """Checks for and provides instructions to upgrade FileMind."""
    # ... (code for upgrade)

@app.command()
def uninstall():
    """Removes all FileMind data."""
    # ... (code for uninstall)

if __name__ == "__main__":
    app()