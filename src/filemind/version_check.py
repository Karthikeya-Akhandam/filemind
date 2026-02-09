import time
import json
from typing import Optional, Tuple
import importlib.metadata

import requests
from packaging.version import parse as parse_version

from . import config

CACHE_FILE = config.APP_DIR / "version_cache.json"
CACHE_EXPIRY_SECONDS = 24 * 60 * 60  # 24 hours
VERSION_URL = "https://karthikeya-akhandam.github.io/filemind/version.txt"

def get_cached_version() -> Optional[str]:
    """Reads the latest version from the cache if it's not expired."""
    if not CACHE_FILE.exists():
        return None
    
    try:
        if time.time() - CACHE_FILE.stat().st_mtime > CACHE_EXPIRY_SECONDS:
            return None
        with open(CACHE_FILE, 'r') as f:
            return json.load(f).get('latest_version')
    except (json.JSONDecodeError, FileNotFoundError, KeyError):
        return None

def set_cached_version(latest_version: str):
    """Writes the latest version to the cache file."""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump({'latest_version': latest_version}, f)
    except IOError:
        pass # Fail silently if cache can't be written

def get_latest_version_from_url() -> Optional[str]:
    """Fetches the latest version string from the hosted version.txt file."""
    try:
        response = requests.get(VERSION_URL, timeout=5)
        response.raise_for_status()
        latest_version_str = response.text.strip()
        set_cached_version(latest_version_str)
        return latest_version_str
    except requests.RequestException:
        return None

def check_for_new_version() -> Optional[Tuple[str, str]]:
    """
    Checks for a new version of FileMind.

    Returns:
        A tuple of (new_version, current_version) if an update is available, else None.
    """
    try:
        current_version_str = importlib.metadata.version("filemind")
        current_version = parse_version(current_version_str)
    except importlib.metadata.PackageNotFoundError:
        return None

    latest_version_str = get_cached_version()
    if not latest_version_str:
        latest_version_str = get_latest_version_from_url()

    if not latest_version_str:
        return None

    latest_version = parse_version(latest_version_str)

    if latest_version > current_version:
        return (latest_version_str, current_version_str)
    
    return None