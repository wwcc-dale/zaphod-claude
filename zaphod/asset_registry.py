#!/usr/bin/env python3
"""
asset_registry.py - Zaphod Asset Registry

Tracks mappings between local asset files and Canvas file IDs/URLs.

This eliminates the need to mutate source.md files with Canvas URLs,
enabling clean round-trip import/export and version control.

Registry Format:
{
  "version": "1.0",
  "assets": {
    "content-hash-abc123": {
      "local_paths": ["assets/images/photo.jpg", "../../assets/images/photo.jpg"],
      "canvas_file_id": 456,
      "canvas_url": "https://canvas.../files/456/download?download_frd=1",
      "content_hash": "abc123def456...",
      "uploaded_at": "2026-02-05T12:34:56Z",
      "file_size": 12345,
      "filename": "photo.jpg"
    }
  },
  "path_lookup": {
    "assets/images/photo.jpg": "content-hash-abc123",
    "../../assets/images/photo.jpg": "content-hash-abc123"
  }
}

Usage:
    from zaphod.asset_registry import AssetRegistry

    # Load registry
    registry = AssetRegistry(course_root)

    # Track an upload
    registry.track_upload(
        local_path="assets/images/photo.jpg",
        canvas_file_id=456,
        canvas_url="https://canvas.../files/456/download"
    )

    # Query for Canvas URL
    canvas_url = registry.get_canvas_url("assets/images/photo.jpg")
    canvas_url = registry.get_canvas_url("../../assets/images/photo.jpg")  # Also works

    # Save registry
    registry.save()
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from zaphod.icons import SUCCESS, WARNING


class AssetRegistry:
    """
    Manager for asset registry.

    Tracks mappings between local asset files and Canvas uploads.
    Uses content-hash deduplication to handle:
    - Same file referenced from different locations
    - Updated files with same name
    """

    def __init__(self, course_root: Path):
        """
        Initialize asset registry.

        Args:
            course_root: Course root directory
        """
        self.course_root = Path(course_root)
        self.registry_path = self.course_root / "_course_metadata" / "asset_registry.json"

        # Registry structure
        self.version = "1.0"
        self.assets: Dict[str, Dict[str, Any]] = {}  # hash -> asset_data
        self.path_lookup: Dict[str, str] = {}  # local_path -> hash

        # Load existing registry
        self._load()

    def _load(self):
        """Load registry from disk."""
        if not self.registry_path.exists():
            return

        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
            self.version = data.get("version", "1.0")
            self.assets = data.get("assets", {})
            self.path_lookup = data.get("path_lookup", {})
        except Exception as e:
            print(f"[registry:warn] {WARNING} Failed to load registry: {e}")
            print(f"[registry:warn] Starting with empty registry")

    def save(self):
        """Save registry to disk."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": self.version,
            "assets": self.assets,
            "path_lookup": self.path_lookup,
        }

        try:
            self.registry_path.write_text(
                json.dumps(data, indent=2, sort_keys=True),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"[registry:err] Failed to save registry: {e}")

    def _compute_hash(self, file_path: Path) -> str:
        """
        Compute content hash for a file.

        Args:
            file_path: Path to file

        Returns:
            12-character hex hash
        """
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        return hashlib.md5(file_path.read_bytes()).hexdigest()[:12]

    def _normalize_path(self, local_path: str) -> str:
        """
        Normalize a local path for consistent lookups.

        Args:
            local_path: Local path (may be relative, contain ../, etc.)

        Returns:
            Normalized path string
        """
        # Convert to Path, normalize, convert back
        return str(Path(local_path).as_posix())

    def track_upload(
        self,
        local_path: str | Path,
        canvas_file_id: int,
        canvas_url: str,
        file_size: Optional[int] = None,
    ):
        """
        Track an asset upload in the registry.

        Args:
            local_path: Local file path (absolute or relative to course root)
            canvas_file_id: Canvas file ID
            canvas_url: Canvas file URL
            file_size: Optional file size in bytes
        """
        local_path = Path(local_path)

        # Resolve to absolute path if relative
        if not local_path.is_absolute():
            local_path = self.course_root / local_path

        # Compute content hash
        content_hash = self._compute_hash(local_path)
        hash_key = f"content-hash-{content_hash}"

        # Get file info
        filename = local_path.name
        if file_size is None and local_path.is_file():
            file_size = local_path.stat().st_size

        # Normalize the path for storage
        try:
            rel_path = local_path.relative_to(self.course_root)
            normalized_path = str(rel_path.as_posix())
        except ValueError:
            # Path is outside course root - use absolute path
            normalized_path = str(local_path.as_posix())

        # Create or update asset entry
        if hash_key not in self.assets:
            self.assets[hash_key] = {
                "local_paths": [],
                "canvas_file_id": canvas_file_id,
                "canvas_url": canvas_url,
                "content_hash": content_hash,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "file_size": file_size,
                "filename": filename,
            }
        else:
            # Update existing entry
            self.assets[hash_key]["canvas_file_id"] = canvas_file_id
            self.assets[hash_key]["canvas_url"] = canvas_url
            self.assets[hash_key]["uploaded_at"] = datetime.now(timezone.utc).isoformat()

        # Add this path to the asset's known paths
        if normalized_path not in self.assets[hash_key]["local_paths"]:
            self.assets[hash_key]["local_paths"].append(normalized_path)

        # Update path lookup
        self.path_lookup[normalized_path] = hash_key

        # Also add common relative path variations for convenience
        # This allows queries like "../assets/photo.jpg" or "assets/photo.jpg"
        try:
            # From content folder perspective (../../assets/...)
            rel_from_content = Path("../../assets") / local_path.relative_to(self.course_root / "assets")
            rel_from_content_str = str(rel_from_content.as_posix())
            if rel_from_content_str not in self.path_lookup:
                self.path_lookup[rel_from_content_str] = hash_key
                if rel_from_content_str not in self.assets[hash_key]["local_paths"]:
                    self.assets[hash_key]["local_paths"].append(rel_from_content_str)
        except (ValueError, Exception):
            pass

    def get_canvas_url(self, local_path: str | Path) -> Optional[str]:
        """
        Get Canvas URL for a local asset path.

        Args:
            local_path: Local file path (absolute or relative)

        Returns:
            Canvas URL if found, None otherwise
        """
        # Try exact match first
        normalized = self._normalize_path(str(local_path))
        hash_key = self.path_lookup.get(normalized)

        if hash_key:
            return self.assets[hash_key].get("canvas_url")

        # Try resolving as absolute path
        path_obj = Path(local_path)
        if not path_obj.is_absolute():
            path_obj = self.course_root / path_obj

        # Try looking up by content hash if file exists
        if path_obj.is_file():
            try:
                content_hash = self._compute_hash(path_obj)
                hash_key = f"content-hash-{content_hash}"
                if hash_key in self.assets:
                    return self.assets[hash_key].get("canvas_url")
            except Exception:
                pass

        # Try matching by filename only (last resort)
        filename = Path(local_path).name
        for asset_data in self.assets.values():
            if asset_data.get("filename") == filename:
                return asset_data.get("canvas_url")

        return None

    def get_canvas_file_id(self, local_path: str | Path) -> Optional[int]:
        """
        Get Canvas file ID for a local asset path.

        Args:
            local_path: Local file path (absolute or relative)

        Returns:
            Canvas file ID if found, None otherwise
        """
        normalized = self._normalize_path(str(local_path))
        hash_key = self.path_lookup.get(normalized)

        if hash_key:
            return self.assets[hash_key].get("canvas_file_id")

        # Try by content hash
        path_obj = Path(local_path)
        if not path_obj.is_absolute():
            path_obj = self.course_root / path_obj

        if path_obj.is_file():
            try:
                content_hash = self._compute_hash(path_obj)
                hash_key = f"content-hash-{content_hash}"
                if hash_key in self.assets:
                    return self.assets[hash_key].get("canvas_file_id")
            except Exception:
                pass

        return None

    def is_tracked(self, local_path: str | Path) -> bool:
        """
        Check if a local asset is tracked in the registry.

        Args:
            local_path: Local file path

        Returns:
            True if tracked, False otherwise
        """
        return self.get_canvas_url(local_path) is not None

    def get_all_assets(self) -> List[Dict[str, Any]]:
        """
        Get all tracked assets.

        Returns:
            List of asset data dictionaries
        """
        return list(self.assets.values())

    def get_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dictionary with stats
        """
        total_size = sum(
            asset.get("file_size", 0)
            for asset in self.assets.values()
        )

        return {
            "total_assets": len(self.assets),
            "total_paths": len(self.path_lookup),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
        }

    def prune_missing(self) -> int:
        """
        Remove entries for files that no longer exist locally.

        Returns:
            Number of entries removed
        """
        to_remove = []

        for hash_key, asset_data in self.assets.items():
            # Check if any of the local paths still exist
            any_exist = False
            for path_str in asset_data.get("local_paths", []):
                path = self.course_root / path_str
                if path.is_file():
                    any_exist = True
                    break

            if not any_exist:
                to_remove.append(hash_key)

        # Remove entries
        for hash_key in to_remove:
            # Remove from assets
            asset_data = self.assets.pop(hash_key)

            # Remove from path_lookup
            for path_str in asset_data.get("local_paths", []):
                self.path_lookup.pop(path_str, None)

        if to_remove:
            print(f"[registry] Pruned {len(to_remove)} missing asset(s)")
            self.save()

        return len(to_remove)

    def print_stats(self):
        """Print registry statistics."""
        stats = self.get_stats()
        print(f"[registry] {SUCCESS} Asset Registry")
        print(f"[registry]   Assets tracked: {stats['total_assets']}")
        print(f"[registry]   Path references: {stats['total_paths']}")
        print(f"[registry]   Total size: {stats['total_size_mb']:.2f} MB")
