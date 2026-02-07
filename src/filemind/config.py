from pathlib import Path
import os

def get_app_dir() -> Path:
    """
    Gets the application's data directory.
    On Windows, this is %LOCALAPPDATA%\FileMind.
    On macOS, this is ~/Library/Application Support/FileMind.
    On Linux, this is ~/.local/share/FileMind.
    """
    if os.name == 'nt':  # Windows
        app_dir = Path(os.getenv('LOCALAPPDATA', '')) / 'FileMind'
    elif os.uname().sysname == 'Darwin':  # macOS
        app_dir = Path.home() / 'Library' / 'Application Support' / 'FileMind'
    else:  # Linux and other UNIX-like systems
        app_dir = Path.home() / '.local' / 'share' / 'FileMind'
    
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir

APP_DIR = get_app_dir()
DB_PATH = APP_DIR / "filemind.db"
FAISS_INDEX_PATH = APP_DIR / "filemind.index"
MODEL_DIR = APP_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
