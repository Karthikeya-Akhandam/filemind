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

    # Asset handling logic...
    # ... (code to copy from bundled assets or source)
    
    vs = vector_store.get_vector_store()
    vs.save()
    typer.secho("Initialization complete!", fg=typer.colors.GREEN)

@app.command()
def scan(directory: Path = typer.Argument(..., help="The directory to scan.")):
    """Scans a directory, indexing new or modified files."""
    # ... (scan logic)
    typer.secho("Scan complete.", fg=typer.colors.GREEN)
    _show_update_notification()

@app.command()
def search(query: str = typer.Argument(...), top_k: int = typer.Option(5, "--top-k", "-k")):
    """Performs a hybrid search for files based on your query."""
    # ... (search logic)
    typer.secho("\n--- Search Results ---", fg=typer.colors.GREEN)
    # ... (display logic)
    _show_update_notification()

@app.command()
def upgrade():
    """Checks for and provides instructions to upgrade FileMind."""
    from . import version_check # LAZY IMPORT
    import requests

    typer.secho("Checking for new versions...", fg=typer.colors.BLUE)
    try:
        current_version_str = importlib.metadata.version("filemind")
        latest_version_str = version_check.get_latest_version_from_github()

        if not latest_version_str:
            typer.secho("Could not fetch the latest version from GitHub.", fg=typer.colors.RED)
            raise typer.Exit()

        current_version = version_check.parse_version(current_version_str)
        latest_version = version_check.parse_version(latest_version_str)

        if latest_version > current_version:
            typer.secho(f"\n🎉 A new version is available: {latest_version}", fg=typer.colors.GREEN)
            if getattr(sys, 'frozen', False):
                typer.secho("To upgrade, please re-run the installation script:", fg=typer.colors.GREEN)
                typer.secho("  curl -fsSL https://raw.githubusercontent.com/Karthikeya-Akhandam/filemind/main/install.sh | sh", fg=typer.colors.BRIGHT_MAGENTA)
            else:
                typer.secho("To upgrade your pip-installed version, please run:", fg=typer.colors.GREEN)
                typer.secho(f"  pip install --upgrade filemind", fg=typer.colors.BRIGHT_MAGENTA)
        else:
            typer.secho(f"✅ You are on the latest version: {current_version}", fg=typer.colors.GREEN)

    except importlib.metadata.PackageNotFoundError:
        typer.secho("Could not determine current version (running from source?).", fg=typer.colors.YELLOW)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            typer.secho("Could not check for new versions: GitHub API rate limit exceeded.", fg=typer.colors.RED)
            typer.secho("Please try again in an hour or check the repository page manually.", fg=typer.colors.YELLOW)
        else:
            typer.secho(f"Error checking for new versions: {e}", fg=typer.colors.RED)
    except requests.exceptions.RequestException as e:
        typer.secho(f"Error checking for new versions: Network error.", fg=typer.colors.RED)

# ... other commands like duplicates, uninstall, rebuild-index ...

if __name__ == "__main__":
    app()
