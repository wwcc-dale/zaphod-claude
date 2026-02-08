#!/usr/bin/env python3
"""
rubric_dedup.py (Zaphod)

Post-import deduplication of rubrics and rubric criteria rows.

Two-pass process:
  Pass 1 — Whole-rubric deduplication:
    Identical rubrics (same criteria list) across 2+ assignments are extracted
    to rubrics/<slug>.yaml and replaced with `use_rubric: slug`.

  Pass 2 — Row-level deduplication:
    Criterion rows that still appear verbatim in 2+ rubric files (including
    newly extracted shared rubrics) are extracted to rubrics/rows/<slug>.yaml
    and replaced with {{rubric_row:slug}} placeholder strings.

Integrates with:
  - sync_rubrics.py: consumes use_rubric and {{rubric_row:...}} at sync time
  - import_from_canvas.py / import_cartridge.py: called post-import

Usage (standalone):
    python -m zaphod.rubric_dedup --course-dir ./my-course
"""

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def deduplicate_rubric_rows(course_dir: Path) -> int:
    """
    Run both deduplication passes on course_dir.

    Returns:
        Total number of unique items extracted (shared rubrics + row files).
    """
    n_rubrics = _deduplicate_whole_rubrics(course_dir)
    n_rows = _deduplicate_rows(course_dir)
    return n_rubrics + n_rows


# ---------------------------------------------------------------------------
# Pass 1: whole-rubric deduplication
# ---------------------------------------------------------------------------


def _deduplicate_whole_rubrics(course_dir: Path) -> int:
    """
    Extract identical rubrics (criteria-wise) used by 2+ assignments into
    rubrics/<slug>.yaml and replace inline rubric.yaml with use_rubric: slug.

    Returns number of shared rubric files written.
    """
    rubric_files = _find_rubric_files(course_dir)
    if not rubric_files:
        return 0

    # fingerprint of full criteria list -> list of (path, full_rubric_data)
    fp_to_paths: Dict[str, List[Path]] = defaultdict(list)
    fp_to_data: Dict[str, Dict[str, Any]] = {}

    for rpath in rubric_files:
        data = _load_full_rubric(rpath)
        if data is None:
            continue
        fp = _list_fingerprint(data.get("criteria", []))
        fp_to_paths[fp].append(rpath)
        fp_to_data[fp] = data

    shared_fps = {fp for fp, paths in fp_to_paths.items() if len(paths) >= 2}
    if not shared_fps:
        return 0

    rubrics_dir = course_dir / "rubrics"
    rubrics_dir.mkdir(parents=True, exist_ok=True)
    existing_slugs: Set[str] = {p.stem for p in rubrics_dir.glob("*.yaml")}
    existing_slugs.update(p.stem for p in rubrics_dir.glob("*.yml"))

    fp_to_slug: Dict[str, str] = {}
    for fp in sorted(shared_fps):
        data = fp_to_data[fp]

        existing_slug = _find_existing_rubric(rubrics_dir, data)
        if existing_slug:
            fp_to_slug[fp] = existing_slug
            continue

        # Derive slug from title or first criterion description
        title = data.get("title", "")
        if title:
            base_slug = _make_slug(title)
        else:
            first_desc = (data.get("criteria") or [{}])[0].get("description", "")
            base_slug = _make_slug(first_desc) if first_desc else fp[:12]

        slug = _unique_slug(base_slug, existing_slugs)
        existing_slugs.add(slug)

        _write_shared_rubric(rubrics_dir, slug, data)
        fp_to_slug[fp] = slug

    # Replace assignment rubric.yaml files with use_rubric references
    for fp, paths in fp_to_paths.items():
        if fp not in fp_to_slug:
            continue
        slug = fp_to_slug[fp]
        for rpath in paths:
            rpath.write_text(
                yaml.dump({"use_rubric": slug}, default_flow_style=False),
                encoding="utf-8"
            )

    return len(fp_to_slug)


# ---------------------------------------------------------------------------
# Pass 2: row-level deduplication
# ---------------------------------------------------------------------------


def _deduplicate_rows(course_dir: Path) -> int:
    """
    Extract criterion rows appearing verbatim in 2+ rubric files into
    rubrics/rows/<slug>.yaml and replace with {{rubric_row:slug}}.

    Returns number of unique row files written.
    """
    rubric_files = _find_rubric_files(course_dir)
    # Also scan rubrics/ directory for shared rubrics (they have criteria too)
    rubric_files += list((course_dir / "rubrics").glob("*.yaml")) if (course_dir / "rubrics").exists() else []
    rubric_files = sorted(set(rubric_files))

    if not rubric_files:
        return 0

    fingerprint_to_paths: Dict[str, Set[Path]] = defaultdict(set)
    fingerprint_to_criterion: Dict[str, Dict[str, Any]] = {}

    for rpath in rubric_files:
        criteria = _load_rubric_criteria(rpath)
        if not criteria:
            continue
        for criterion in criteria:
            fp = _criterion_fingerprint(criterion)
            fingerprint_to_paths[fp].add(rpath)
            fingerprint_to_criterion[fp] = criterion

    shared_fps = {fp for fp, paths in fingerprint_to_paths.items() if len(paths) >= 2}
    if not shared_fps:
        return 0

    rows_dir = course_dir / "rubrics" / "rows"
    rows_dir.mkdir(parents=True, exist_ok=True)
    existing_slugs: Set[str] = {p.stem for p in rows_dir.glob("*.yaml")}
    existing_slugs.update(p.stem for p in rows_dir.glob("*.yml"))

    fingerprint_to_slug: Dict[str, str] = {}
    for fp in sorted(shared_fps):
        criterion = fingerprint_to_criterion[fp]

        existing_slug = _find_existing_row(rows_dir, criterion)
        if existing_slug:
            fingerprint_to_slug[fp] = existing_slug
            continue

        description = criterion.get("description", "")
        base_slug = _make_slug(description) if description else fp[:12]
        slug = _unique_slug(base_slug, existing_slugs)
        existing_slugs.add(slug)

        _write_row_file(rows_dir, slug, criterion)
        fingerprint_to_slug[fp] = slug

    affected_paths: Set[Path] = set()
    for fp in shared_fps:
        affected_paths.update(fingerprint_to_paths[fp])

    for rpath in affected_paths:
        _rewrite_rubric_file(rpath, fingerprint_to_slug)

    return len(fingerprint_to_slug)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _find_rubric_files(course_dir: Path) -> List[Path]:
    """Find all rubric.yaml / rubric.yml files under content/ (not rubrics/)."""
    files = list(course_dir.rglob("rubric.yaml"))
    files += list(course_dir.rglob("rubric.yml"))
    # Exclude files already in rubrics/ (those are shared rubrics, not inline)
    rubrics_dir = course_dir / "rubrics"
    return sorted({f for f in files if not f.is_relative_to(rubrics_dir)})


def _load_full_rubric(rubric_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load a rubric.yaml. Returns None if it's a reference (use_rubric/reference),
    unreadable, or has no inline criteria.
    """
    try:
        data = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if "use_rubric" in data or "reference" in data:
        return None
    if not data.get("criteria"):
        return None
    return data


def _load_rubric_criteria(rubric_path: Path) -> Optional[List[Dict[str, Any]]]:
    """
    Load just the inline criterion dicts from a rubric file.
    Returns None if the file should be skipped entirely.
    Filters out existing {{rubric_row:...}} placeholder strings.
    """
    try:
        data = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if "use_rubric" in data or "reference" in data:
        return None
    criteria = data.get("criteria")
    if not criteria or not isinstance(criteria, list):
        return None
    return [c for c in criteria if isinstance(c, dict)]


def _strip_strings(obj: Any) -> Any:
    """Recursively strip whitespace from all string values."""
    if isinstance(obj, str):
        return obj.strip()
    if isinstance(obj, dict):
        return {k: _strip_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip_strings(item) for item in obj]
    return obj


def _normalize(obj: Any) -> str:
    """Stable canonical JSON string (whitespace-stripped, keys sorted)."""
    return json.dumps(_strip_strings(obj), sort_keys=True)


def _list_fingerprint(criteria: List[Any]) -> str:
    """16-char SHA-256 hex of a normalized criteria list."""
    return hashlib.sha256(_normalize(criteria).encode("utf-8")).hexdigest()[:16]


def _criterion_fingerprint(criterion: Dict[str, Any]) -> str:
    """16-char SHA-256 hex of a normalized criterion dict."""
    return hashlib.sha256(_normalize(criterion).encode("utf-8")).hexdigest()[:16]


def _make_slug(text: str) -> str:
    """Derive a filesystem-safe slug from text (max 40 chars)."""
    s = text.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    s = s.strip("-")[:40].rstrip("-")
    return s or "rubric"


def _unique_slug(base_slug: str, existing_slugs: Set[str]) -> str:
    """Append _2, _3, … until the slug is unique."""
    slug = base_slug
    counter = 2
    while slug in existing_slugs:
        slug = f"{base_slug}_{counter}"
        counter += 1
    return slug


def _find_existing_rubric(rubrics_dir: Path, data: Dict[str, Any]) -> Optional[str]:
    """Return slug of an existing shared rubric with identical criteria, or None."""
    target = _normalize(data.get("criteria", []))
    for path in rubrics_dir.glob("*.yaml"):
        try:
            existing = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and _normalize(existing.get("criteria", [])) == target:
                return path.stem
        except Exception:
            continue
    return None


def _write_shared_rubric(rubrics_dir: Path, slug: str, data: Dict[str, Any]) -> None:
    """Write a full rubric dict to rubrics_dir/<slug>.yaml."""
    out = rubrics_dir / f"{slug}.yaml"
    out.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True),
                   encoding="utf-8")


def _find_existing_row(rows_dir: Path, criterion: Dict[str, Any]) -> Optional[str]:
    """Return slug of an existing row file with identical content, or None."""
    target = _normalize(criterion)
    for path in rows_dir.glob("*.yaml"):
        try:
            existing = yaml.safe_load(path.read_text(encoding="utf-8"))
            if _normalize(existing) == target:
                return path.stem
        except Exception:
            continue
    return None


def _write_row_file(rows_dir: Path, slug: str, criterion: Dict[str, Any]) -> None:
    """Write a single criterion dict to rows_dir/<slug>.yaml."""
    out = rows_dir / f"{slug}.yaml"
    out.write_text(yaml.dump(criterion, default_flow_style=False, allow_unicode=True),
                   encoding="utf-8")


def _rewrite_rubric_file(rubric_path: Path, fingerprint_to_slug: Dict[str, str]) -> bool:
    """
    Replace matching inline criterion dicts with {{rubric_row:slug}} strings.
    Returns True if any replacements were made.
    """
    try:
        data = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    criteria = data.get("criteria")
    if not criteria or not isinstance(criteria, list):
        return False

    new_criteria = []
    changed = False
    for entry in criteria:
        if isinstance(entry, dict):
            fp = _criterion_fingerprint(entry)
            if fp in fingerprint_to_slug:
                new_criteria.append(f"{{{{rubric_row:{fingerprint_to_slug[fp]}}}}}")
                changed = True
                continue
        new_criteria.append(entry)

    if not changed:
        return False

    data["criteria"] = new_criteria
    rubric_path.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8"
    )
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Deduplicate shared rubrics and rubric rows across a Zaphod course"
    )
    parser.add_argument(
        "--course-dir", "-d",
        type=Path,
        default=Path.cwd(),
        help="Course root directory (default: cwd)"
    )
    args = parser.parse_args()

    if not args.course_dir.exists():
        print(f"Error: {args.course_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    n = deduplicate_rubric_rows(args.course_dir)
    if n > 0:
        print(f"Extracted {n} shared rubric(s)/row(s)")
    else:
        print("No shared rubrics or rows found.")


if __name__ == "__main__":
    main()
