from pathlib import Path
import os
import time
from typing import List
from collections import defaultdict

import typer
import numpy as np

# For init command
try:
    # These imports are expected to fail if 'filemind[init]' is not installed
    from sentence_transformers import SentenceTransformer
    from optimum.onnxruntime import ORTModelForFeatureExtraction
    from transformers import AutoTokenizer, AutoConfig
    import shutil
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


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

MODEL_NAME = "BAAI/bge-small-en-v1.5"

@app.command()
def init():
    """
    Initializes FileMind: sets up directories, downloads and converts the model,
    and initializes the database.
    """
    typer.secho("Initializing FileMind...", fg=typer.colors.BLUE)
    
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        typer.secho(
            "ERROR: 'sentence-transformers', 'optimum', and 'transformers' are required for initialization. "
            "Please install them: pip install 'filemind[init]'",
            fg=typer.colors.RED
        )
        raise typer.Exit(1)

    # 1. Ensure application directory exists
    config.APP_DIR.mkdir(parents=True, exist_ok=True)
    config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    typer.secho(f"Application directory created at: {config.APP_DIR}", fg=typer.colors.GREEN)

    # 2. Initialize database
    database.initialize_database()
    typer.secho(f"Database initialized at: {config.DB_PATH}", fg=typer.colors.GREEN)

    # 3. Download and convert model
    typer.secho(f"Downloading and converting model '{MODEL_NAME}' to ONNX...", fg=typer.colors.BLUE)
    
    # Check if ONNX model and tokenizer already exist
    onnx_model_path = config.MODEL_DIR / "model.onnx"
    tokenizer_json_path = config.MODEL_DIR / "tokenizer.json"
    
    if onnx_model_path.exists() and tokenizer_json_path.exists():
        typer.secho("ONNX model and tokenizer already exist. Skipping download and conversion.", fg=typer.colors.GREEN)
    else:
        # Download the model and tokenizer using SentenceTransformer and AutoTokenizer
        try:
            # SentenceTransformer downloads the model to a cache directory
            model_cache_dir = config.MODEL_DIR / "hf_cache"
            model_cache_dir.mkdir(exist_ok=True)
            
            sbert_model = SentenceTransformer(MODEL_NAME, cache_folder=str(model_cache_dir))
            
            # Save the Hugging Face model and tokenizer to a temporary directory for optimum export
            temp_hf_model_path = config.MODEL_DIR / "temp_hf_model_for_export"
            temp_hf_model_path.mkdir(exist_ok=True)
            sbert_model.save(str(temp_hf_model_path)) # Saves PyTorch model and tokenizer
            
            # Load tokenizer from the downloaded path
            tokenizer = AutoTokenizer.from_pretrained(str(temp_hf_model_path))
            
            # Create a dummy config for optimum to export
            # AutoConfig.from_pretrained works with the same path as AutoTokenizer.
            AutoConfig.from_pretrained(str(temp_hf_model_path)).save_pretrained(str(temp_hf_model_path))

            typer.secho("Exporting model to ONNX and quantizing...", fg=typer.colors.YELLOW)
            onnx_model = ORTModelForFeatureExtraction.from_pretrained(
                str(temp_hf_model_path),
                export=True,
                opset=13, # Common opset version
                feature="sentence-embedding"
            )
            # Save the ONNX model to the final location
            onnx_model.save_pretrained(str(config.MODEL_DIR), file_name="model.onnx")
            
            # Save tokenizer directly to final MODEL_DIR
            tokenizer.save_pretrained(str(config.MODEL_DIR))

            typer.secho(f"Model converted and saved to {config.MODEL_DIR}", fg=typer.colors.GREEN)

            # Clean up temporary model files
            if model_cache_dir.exists():
                shutil.rmtree(model_cache_dir)
            if temp_hf_model_path.exists():
                shutil.rmtree(temp_hf_model_path)

        except Exception as e:
            typer.secho(f"ERROR: Failed to download or convert model: {e}", fg=typer.colors.RED)
            typer.secho("Please ensure you have an internet connection for initial setup.", fg=typer.colors.RED)
            raise typer.Exit(1)

    # 4. Initialize FAISS index file (if it doesn't exist)
    vs = vector_store.get_vector_store() # This will create an empty index if not present
    vs.save() # Persist the empty index
    typer.secho(f"FAISS index initialized at: {config.FAISS_INDEX_PATH}", fg=typer.colors.GREEN)
    
    typer.secho("FileMind initialization complete! You can now run 'filemind scan <directory>'", fg=typer.colors.GREEN)


def _process_file(file_path: Path, vs: vector_store.VectorStore):
    """Processes a single file for indexing."""
    typer.echo(f"  Processing: {file_path.name}")
    
    # 1. Get file metadata
    try:
        mtime = int(file_path.stat().st_mtime)
        size = file_path.stat().st_size
    except FileNotFoundError:
        typer.secho(f"    [WARN] File not found during processing: {file_path}", fg=typer.colors.YELLOW)
        return

    # 2. Check if file needs re-indexing
    existing_file = repository.get_file_by_path(file_path)
    if existing_file:
        file_id, db_size, db_mtime = existing_file
        if db_size == size and db_mtime == mtime:
            typer.echo("    Skipping (unchanged).")
            return
        else:
            typer.echo("    File changed, re-indexing...")
            # Deleting the old file record will cascade and delete all its chunks
            repository.delete_file_and_chunks(file_id)
            # Note: This leaves orphaned vectors in the FAISS index.
            # The plan addresses this with a 'rebuild-index' command later.
            
    # 3. Generate file hash
    file_hash = hasher.generate_file_hash(file_path)
    
    # 4. Add file to database
    file_id = repository.add_file(file_path, file_hash, size, mtime)
    
    # 5. Extract text
    text = extractor.extract_text(file_path)
    if not text:
        typer.echo("    Skipping (no text extracted).")
        return
        
    # 6. Chunk text
    chunks = list(extractor.chunk_text(text))
    if not chunks:
        typer.echo("    Skipping (no chunks generated).")
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
        # This check is crucial for maintaining FAISS-SQLite consistency.
        # It handles scenarios where FAISS might not have been persisted correctly or was rebuilt.
        # If the check fails, we cannot simply 'add' to FAISS without potentially corrupting it.
        # The ultimate solution is `rebuild-index`.
        if vs.index.ntotal != chunk_id - 1:
            typer.secho(
                f"FATAL: FAISS index out of sync. Expected index size {chunk_id - 1}, found {vs.index.ntotal}. "
                "This can happen after re-indexing files or if the index was not saved correctly. "
                "The current implementation does not support arbitrary deletions from FAISS. "
                "To resolve, please run `filemind rebuild-index` (once implemented). "
                "Skipping FAISS addition for this file to prevent corruption.",
                fg=typer.colors.RED
            )
            # Do not add to FAISS if out of sync, relying on rebuild-index to fix this.
            # This is a temporary measure until rebuild-index is available.
            return
            
    vs.add(embeddings)
    typer.echo(f"    Indexed {len(chunks)} chunks.")


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

@app.command()
def duplicates():
    """
    Finds and lists files that are exact duplicates based on their content hash.
    """
    typer.secho("Searching for duplicate files...", fg=typer.colors.BLUE)
    database.initialize_database()

    duplicate_hashes = repository.find_duplicate_hashes()

    if not duplicate_hashes:
        typer.secho("No exact duplicate files found.", fg=typer.colors.GREEN)
        return

    for file_hash, count in duplicate_hashes:
        typer.secho(f"\nHash: {file_hash} (found {count} times)", fg=typer.colors.YELLOW)
        duplicate_files = repository.get_files_by_hash(file_hash)
        for file_path, file_size, mtime in duplicate_files:
            typer.echo(f"  - {file_path} (Size: {file_size} bytes, Modified: {time.ctime(mtime)})")
    
    typer.secho("\nDuplicate search complete.", fg=typer.colors.GREEN)


@app.command()
def search(
    query: str = typer.Argument(..., help="The text to search for."),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to return."),
):
    """
    Performs a hybrid search for files based on your query.
    """
    typer.secho(f"Searching for: '{query}'...", fg=typer.colors.BLUE)
    database.initialize_database()
    
    # Load stores
    try:
        vs = vector_store.get_vector_store()
        query_embedding = embedder.generate_embeddings([query])
    except FileNotFoundError as e:
        typer.secho(f"ERROR: {e}", fg=typer.colors.RED)
        typer.secho("Please run 'filemind init' first.", fg=typer.colors.YELLOW)
        raise typer.Exit(1)
        
    # 1. Semantic Search
    distances, semantic_chunk_ids = vs.search(query_embedding, k=top_k * 2) # Fetch more to allow for merging
    
    # 2. Keyword Search
    keyword_chunk_ids = repository.search_chunks_fts(query, limit=top_k * 2)

    # 3. Merge and Rank Results
    # Using defaultdict to store results for each file
    file_results = defaultdict(lambda: {"max_score": 0.0, "keyword_hit": False, "best_chunk_id": -1})
    
    # Process semantic results
    if semantic_chunk_ids.size > 0:
        # FAISS returns 1-based IDs if we use its ID map, but here the index is the chunk_id
        # We must add 1 to our chunk IDs when inserting to match this behavior if we used add_with_ids
        # Since we use add(), the index is 0-based and corresponds to chunk_id - 1
        semantic_chunk_ids_list = (semantic_chunk_ids[0] + 1).tolist()
        
        chunk_details = repository.get_chunk_details_by_ids(semantic_chunk_ids_list)
        for i, (chunk_id, file_id, content) in enumerate(chunk_details):
            score = float(distances[0][i])
            if score > file_results[file_id]["max_score"]:
                file_results[file_id]["max_score"] = score
                file_results[file_id]["best_chunk_id"] = chunk_id

    # Process keyword results
    if keyword_chunk_ids:
        chunk_details = repository.get_chunk_details_by_ids(keyword_chunk_ids)
        for chunk_id, file_id, content in chunk_details:
            file_results[file_id]["keyword_hit"] = True
            # If a file was only found by keyword, it has no score, so assign a default
            if file_results[file_id]["max_score"] == 0.0:
                file_results[file_id]["best_chunk_id"] = chunk_id

    # Boost score for keyword hits
    for file_id in file_results:
        if file_results[file_id]["keyword_hit"]:
            file_results[file_id]["max_score"] += 0.1 # Simple boost

    # Sort results by score
    sorted_files = sorted(file_results.items(), key=lambda item: item[1]["max_score"], reverse=True)

    # 4. Display Results
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
    """
    Removes all FileMind data, including the database, FAISS index, and cached models.
    This action is irreversible.
    """
    typer.secho("\nWARNING: This command will permanently delete ALL FileMind data,", fg=typer.colors.RED, bold=True)
    typer.secho(f"including your database, FAISS index, and cached models located at: {config.APP_DIR}", fg=typer.colors.RED)
    
    confirm = typer.confirm("Are you sure you want to proceed?")
    
    if not confirm:
        typer.secho("Uninstallation cancelled.", fg=typer.colors.YELLOW)
        raise typer.Exit()
        
    try:
        if config.APP_DIR.exists():
            shutil.rmtree(config.APP_DIR)
            typer.secho(f"Successfully removed FileMind data directory: {config.APP_DIR}", fg=typer.colors.GREEN)
        else:
            typer.secho(f"FileMind data directory not found at {config.APP_DIR}. Nothing to remove.", fg=typer.colors.YELLOW)
    except Exception as e:
        typer.secho(f"ERROR: Failed to remove FileMind data: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    typer.secho("FileMind uninstallation complete. You may also want to uninstall the Python package:", fg=typer.colors.GREEN)
    typer.secho("  pip uninstall filemind", fg=typer.colors.BRIGHT_MAGENTA)

