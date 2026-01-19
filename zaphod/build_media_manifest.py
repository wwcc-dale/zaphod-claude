#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

build_media_manifest.py

Scan the course directory for large media files and generate a manifest
for use by instructors who clone the repo without the actual media files.

This script:
1. Walks the course directory looking for large media file types
2. Computes SHA256 checksum and file size for each
3. Writes _course_metadata/media_manifest.json

The manifest is a "bill of materials" only - it does not specify where to
get the files. Instructors supply the source location when running hydrate.

Run after prune step or standalone. Does not affect core Zaphod functionality.

Usage:
    python build_media_manifest.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any


COURSE_ROOT = Path.cwd()
METADATA_DIR = COURSE_ROOT / "_course_metadata"
MANIFEST_PATH = METADATA_DIR / "media_manifest.json"

# File extensions considered "large media" - excluded from Git but tracked in manifest
LARGE_MEDIA_EXTENSIONS = {
    # Video
    '.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.wmv', '.flv',
    # Audio
    '.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac', '.wma',
    # Large documents (optional - can be adjusted)
    # '.psd', '.ai', '.indd',
}

# Directories to skip when scanning
SKIP_DIRS = {
    '.git', '.venv', 'venv', '__pycache__', 'node_modules',
    '.pytest_cache', '.mypy_cache', '.egg-info',
}


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def find_large_media_files() -> List[Path]:
    """Find all large media files in the course directory."""
    media_files = []
    
    for path in COURSE_ROOT.rglob('*'):
        # Skip directories in SKIP_DIRS
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        
        if not path.is_file():
            continue
        
        if path.suffix.lower() in LARGE_MEDIA_EXTENSIONS:
            media_files.append(path)
    
    return sorted(media_files)


def build_manifest_item(file_path: Path) -> Dict[str, Any]:
    """Build a manifest entry for a single file."""
    relative_path = file_path.relative_to(COURSE_ROOT)
    stat = file_path.stat()
    
    print(f"  Processing: {relative_path}")
    checksum = compute_sha256(file_path)
    
    return {
        "relative_path": str(relative_path),
        "checksum": f"sha256:{checksum}",
        "size_bytes": stat.st_size,
    }


def build_manifest() -> Dict[str, Any]:
    """Build the complete manifest."""
    media_files = find_large_media_files()
    
    if not media_files:
        print("[manifest] No large media files found.")
        return {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "items": [],
        }
    
    print(f"[manifest] Found {len(media_files)} large media file(s):")
    
    items = []
    for file_path in media_files:
        item = build_manifest_item(file_path)
        items.append(item)
    
    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }


def write_manifest(manifest: Dict[str, Any]) -> None:
    """Write manifest to disk."""
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"[manifest] Wrote {len(manifest['items'])} item(s) to {MANIFEST_PATH}")


def main():
    parser = argparse.ArgumentParser(
        description="Build media manifest for large files excluded from Git"
    )
    parser.parse_args()
    
    print(f"[manifest] Scanning {COURSE_ROOT} for large media files...")
    print(f"[manifest] Extensions: {', '.join(sorted(LARGE_MEDIA_EXTENSIONS))}")
    
    manifest = build_manifest()
    write_manifest(manifest)
    
    # Summary
    total_size = sum(item['size_bytes'] for item in manifest['items'])
    if total_size > 0:
        size_mb = total_size / (1024 * 1024)
        print(f"[manifest] Total size: {size_mb:.1f} MB")
    
    print("[manifest] Done.")


if __name__ == "__main__":
    main()
