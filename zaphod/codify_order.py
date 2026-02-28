#!/usr/bin/env python3
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

"""
codify_order.py — Stamp position and session into index.md frontmatter.

Reads each content item's folder name and current frontmatter, then writes:
  - position:  1-based rank within the item's module (same sort key as export_modules.py)
  - session:   numeric session extracted from the s{nn} folder name component

Designed to be run after `zaphod import` to lock in the derived ordering as
explicit frontmatter values that survive renaming and feed template variables.

Standalone:
    python -m zaphod.codify_order
    python -m zaphod.codify_order --dry-run --verbose
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

import frontmatter

from zaphod.frontmatter_to_meta import get_content_dir, infer_module_from_path


# ============================================================================
# Session extraction
# ============================================================================

# Matches the s{nn} component in folder names like 01-s01-variables.page
SESSION_RE = re.compile(r"(?:^|-)s(\d+)(?:-|$)", re.IGNORECASE)


def extract_session(folder_name: str) -> Optional[int]:
    """
    Extract the session number from a folder name.

    Looks for an 's{nn}' token surrounded by hyphens or at start/end.
    Examples:
      '01-s01-variables.page'  -> 1
      '03-s02-loops.assignment' -> 2
      'intro.page'              -> None
    """
    m = SESSION_RE.search(folder_name)
    return int(m.group(1)) if m else None


# ============================================================================
# Sort key (mirrors export_modules.py:_item_sort_key — replicated to avoid coupling)
# ============================================================================

def _sort_key(folder: Path, meta: dict) -> tuple:
    """
    Sort key for items within a module.

    Priority:
    1. position: frontmatter key (numeric)
    2. Numeric folder prefix (01-, 02-, etc.)
    3. Alphabetical by folder name
    """
    pos = meta.get("position")
    if pos is not None:
        try:
            return (0, float(pos), folder.name)
        except (TypeError, ValueError):
            pass

    m = re.match(r"^(\d+)[_-]", folder.name)
    if m:
        return (1, float(m.group(1)), folder.name)

    return (2, 0.0, folder.name)


# ============================================================================
# Apply helper
# ============================================================================

def _apply(
    folder: Path,
    post: frontmatter.Post,
    position: int,
    session: Optional[int],
    dry_run: bool,
    verbose: bool,
    counts: dict,
) -> None:
    """
    Write position (and session if detected) into index.md frontmatter.
    Only writes if values differ from what's already there.
    """
    changed = False
    changes = []

    current_pos = post.metadata.get("position")
    if current_pos != position:
        post["position"] = position
        changes.append(f"position: {current_pos!r} -> {position}")
        changed = True

    if session is not None:
        current_session = post.metadata.get("session")
        if current_session != session:
            post["session"] = session
            changes.append(f"session: {current_session!r} -> {session}")
            changed = True

    if changed:
        if not dry_run:
            index_path = folder / "index.md"
            index_path.write_text(frontmatter.dumps(post), encoding="utf-8")
        counts["updated"] += 1
        if verbose:
            print(f"  {'[dry-run] ' if dry_run else ''}{'[+]'} {folder.name}: {', '.join(changes)}")
    else:
        counts["skipped"] += 1
        if verbose:
            print(f"  [ ] {folder.name}: unchanged")


# ============================================================================
# Main
# ============================================================================

def codify_order(dry_run: bool = False, verbose: bool = False) -> dict:
    """
    Scan content items, derive position (within module) and session (from snn
    folder prefix), and stamp them into each index.md frontmatter.

    Returns: {"updated": int, "skipped": int, "errors": int}
    """
    content_dir = get_content_dir()
    exts = {".page", ".assignment", ".quiz"}
    counts = {"updated": 0, "skipped": 0, "errors": 0}

    # 1. Collect all content folders + load frontmatter
    items = []
    for ext in exts:
        for folder in content_dir.rglob(f"*{ext}"):
            if not folder.is_dir():
                continue
            index = folder / "index.md"
            if not index.exists():
                continue
            try:
                post = frontmatter.load(index)
            except Exception as e:
                print(f"  [!] {folder.name}: {e}")
                counts["errors"] += 1
                continue
            module = infer_module_from_path(folder)
            items.append((folder, post, module))

    if not items:
        print("No content items found.")
        return counts

    # 2. Group by module, sort within each group, assign 1-based positions
    module_groups: dict[str | None, list] = defaultdict(list)
    for folder, post, module in items:
        module_groups[module].append((folder, post))

    for module_name, group in module_groups.items():
        group.sort(key=lambda t: _sort_key(t[0], dict(t[1].metadata)))
        label = f"[module: {module_name}]" if module_name else "[no module]"
        if verbose:
            print(f"\n{label}")
        for position, (folder, post) in enumerate(group, start=1):
            session = extract_session(folder.name)
            _apply(folder, post, position, session, dry_run, verbose, counts)

    return counts


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stamp position/session into index.md frontmatter")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print each item stamped")
    args = parser.parse_args()

    result = codify_order(dry_run=args.dry_run, verbose=args.verbose)
    tag = "[dry-run] " if args.dry_run else ""
    print(f"\n{tag}Done: {result['updated']} updated, {result['skipped']} unchanged, {result['errors']} errors")
