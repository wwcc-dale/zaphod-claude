#!/usr/bin/env python3
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

"""
codify_order.py — Stamp position, session, modules, and course_order from folder names.

Reads each content item's folder name and current frontmatter, then writes:
  - position:     1-based rank within the item's module (same sort key as export_modules.py)
  - session:      numeric session extracted from the s{nn} folder name component
  - modules:      inferred from the nearest .module ancestor directory (if not already set)

Also writes to shared/variables.yaml:
  - course_order: numeric prefix extracted from the course root directory name

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
import yaml

from zaphod.frontmatter_to_meta import get_content_dir, infer_module_from_path

COURSE_ROOT = Path.cwd()


# ============================================================================
# Course-level extraction
# ============================================================================

# Matches a leading numeric prefix in directory names like '07-javascript-cards'
COURSE_PREFIX_RE = re.compile(r"^(\d+)[_-]")


def extract_course_order(course_root: Path) -> Optional[int]:
    """
    Extract the numeric sort prefix from a course directory name.

    Examples:
      '07-javascript-cards' -> 7
      '01-intro-to-python'  -> 1
      'my-course'           -> None
    """
    m = COURSE_PREFIX_RE.match(course_root.name)
    return int(m.group(1)) if m else None


def stamp_course_variables(course_order: int, dry_run: bool, verbose: bool) -> bool:
    """
    Write course_order into shared/variables.yaml, merging with existing content.
    Creates shared/ and variables.yaml if they don't exist.
    Returns True if the file was changed.
    """
    shared_dir = COURSE_ROOT / "shared"
    vars_path = shared_dir / "variables.yaml"

    existing: dict = {}
    if vars_path.exists():
        try:
            data = yaml.safe_load(vars_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                existing = data
        except Exception as e:
            print(f"  [!] shared/variables.yaml: {e}")
            return False

    if existing.get("course_order") == course_order:
        if verbose:
            print(f"  [ ] shared/variables.yaml: course_order unchanged ({course_order})")
        return False

    old_val = existing.get("course_order")
    existing["course_order"] = course_order

    tag = "[dry-run] " if dry_run else ""
    if not dry_run:
        shared_dir.mkdir(exist_ok=True)
        vars_path.write_text(
            yaml.dump(existing, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    if verbose:
        print(f"  {tag}[+] shared/variables.yaml: course_order: {old_val!r} -> {course_order}")
    return True


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
    module: Optional[str],
    dry_run: bool,
    verbose: bool,
    counts: dict,
) -> None:
    """
    Write position, session (if detected), and modules (if not already set)
    into index.md frontmatter. Only writes if values differ from what's there.
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

    if module is not None:
        current_modules = post.metadata.get("modules")
        if not current_modules:
            post["modules"] = [module]
            changes.append(f"modules: {current_modules!r} -> [{module!r}]")
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
    Scan content items and stamp derived values into frontmatter / shared variables:

      index.md frontmatter:
        position:  1-based rank within the item's module
        session:   from the s{nn} folder prefix (if present)
        modules:   from the nearest .module ancestor dir (if not already set)

      shared/variables.yaml:
        course_order: numeric prefix from the course root directory name (if present)

    Returns: {"updated": int, "skipped": int, "errors": int}
    """
    content_dir = get_content_dir()
    exts = {".page", ".assignment", ".quiz"}
    counts = {"updated": 0, "skipped": 0, "errors": 0}

    # -- course_order in shared/variables.yaml --------------------------------
    course_order = extract_course_order(COURSE_ROOT)
    if course_order is not None:
        if verbose:
            print(f"[course: {COURSE_ROOT.name}]")
        stamp_course_variables(course_order, dry_run, verbose)

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
        label = f"\n[module: {module_name}]" if module_name else "\n[no module]"
        if verbose:
            print(label)
        for position, (folder, post) in enumerate(group, start=1):
            session = extract_session(folder.name)
            _apply(folder, post, position, session, module_name, dry_run, verbose, counts)

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
