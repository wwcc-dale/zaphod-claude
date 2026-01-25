#!/usr/bin/env python3
"""
canvas_client.py - Shared Canvas API client helper

Replaces markdown2canvas's make_canvas_api_obj() with a Zaphod-native implementation.

SECURITY: Uses safe credential parsing instead of exec().
"""

import os
import re
import stat
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Tuple

# Lazy import - only load canvasapi when actually needed
if TYPE_CHECKING:
    from canvasapi import Canvas


def _parse_credentials_safe(cred_file: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse credentials file safely without exec().
    
    SECURITY: This replaces the dangerous exec() pattern that could
    execute arbitrary code if the credentials file was compromised.
    """
    content = cred_file.read_text(encoding="utf-8")
    
    api_key = None
    api_url = None
    
    # Match API_KEY = "value" or API_KEY = 'value' or API_KEY = value
    for pattern in [r'API_KEY\s*=\s*["\']([^"\']+)["\']', r'API_KEY\s*=\s*(\S+)']:
        match = re.search(pattern, content)
        if match:
            api_key = match.group(1).strip().strip('"\'')
            break
    
    for pattern in [r'API_URL\s*=\s*["\']([^"\']+)["\']', r'API_URL\s*=\s*(\S+)']:
        match = re.search(pattern, content)
        if match:
            api_url = match.group(1).strip().strip('"\'')
            break
    
    return api_key, api_url


def _check_file_permissions(cred_file: Path) -> None:
    """Warn if credential file has insecure permissions."""
    try:
        mode = os.stat(cred_file).st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            print(f"[canvas:SECURITY] Credentials file has insecure permissions: {cred_file}")
            print(f"[canvas:SECURITY] Other users may be able to read your API key.")
            print(f"[canvas:SECURITY] Fix with: chmod 600 {cred_file}")
    except OSError:
        pass  # Can't check permissions (e.g., Windows)


def get_canvas_credentials() -> Tuple[str, str]:
    """
    Read Canvas API credentials safely.
    
    Checks (in order):
    1. CANVAS_API_KEY and CANVAS_API_URL environment variables
    2. CANVAS_CREDENTIAL_FILE (or default ~/.canvas/credentials.txt)
    
    Returns:
        (api_url, api_key) tuple
        
    Raises:
        SystemExit: If credentials not found or missing required values
    """
    # Priority 1: Environment variables
    env_key = os.environ.get("CANVAS_API_KEY")
    env_url = os.environ.get("CANVAS_API_URL")
    if env_key and env_url:
        return env_url.rstrip("/"), env_key
    
    # Priority 2: Credential file
    cred_path = os.environ.get("CANVAS_CREDENTIAL_FILE")
    if not cred_path:
        # Default location
        cred_path = str(Path.home() / ".canvas" / "credentials.txt")
    
    cred_file = Path(cred_path)
    if not cred_file.is_file():
        raise SystemExit(
            f"Canvas credentials file not found: {cred_file}\n\n"
            f"Option 1 - Environment variables:\n"
            f"  export CANVAS_API_KEY='your_token'\n"
            f"  export CANVAS_API_URL='https://canvas.yourinstitution.edu'\n\n"
            f"Option 2 - Create credentials file:\n"
            f"  mkdir -p ~/.canvas\n"
            f"  nano ~/.canvas/credentials.txt\n"
            f"  chmod 600 ~/.canvas/credentials.txt\n\n"
            f"Contents:\n"
            f'  API_KEY = "your_canvas_token"\n'
            f'  API_URL = "https://canvas.yourinstitution.edu"'
        )
    
    # SECURITY: Parse credentials safely without exec()
    api_key, api_url = _parse_credentials_safe(cred_file)
    
    if not api_key or not api_url:
        raise SystemExit(
            f"Credentials file must define API_KEY and API_URL: {cred_file}"
        )
    
    # Check file permissions
    _check_file_permissions(cred_file)
    
    # Normalize URL (remove trailing slash)
    api_url = api_url.rstrip("/")
    
    return api_url, api_key


def make_canvas_api_obj() -> "Canvas":
    """
    Create and return a Canvas API client.
    
    Drop-in replacement for markdown2canvas.setup_functions.make_canvas_api_obj()
    
    Returns:
        canvasapi.Canvas instance
    """
    from canvasapi import Canvas  # Lazy import
    api_url, api_key = get_canvas_credentials()
    return Canvas(api_url, api_key)


def get_canvas_base_url() -> str:
    """
    Get the base Canvas URL (without /api/v1).
    
    Useful for constructing URLs like media_attachments_iframe.
    
    Returns:
        Base URL string (e.g., "https://canvas.institution.edu")
    """
    api_url, _ = get_canvas_credentials()
    return api_url
