#!/usr/bin/env python3
"""
content_dedup.py (Zaphod)

Suggest-only analysis of repeated prose blocks across pages and assignments.

Scans content/**/*.page/index.md and content/**/*.assignment/index.md for
paragraph-level blocks that appear verbatim in multiple files. Reports
candidates that could become shared includes (shared/<slug>.md) without
modifying any files.

Thresholds (either condition triggers a suggestion):
  - Block is 200+ chars AND appears in 3+ files
  - Block is 400+ chars AND appears in 2+ files

Usage (standalone):
    python -m zaphod.content_dedup --course-dir ./my-course

Usage (from Python):
    from zaphod.content_dedup import suggest_shared_includes
    suggest_shared_includes(course_dir)
"""

import argparse
import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

MIN_CHARS_LOW = 200    # Minimum block length for 3+ file threshold
MIN_FILES_LOW = 3      # Minimum file count for the low-char threshold
MIN_CHARS_HIGH = 400   # Minimum block length for 2+ file threshold
MIN_FILES_HIGH = 2     # Minimum file count for the high-char threshold


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def suggest_shared_includes(course_dir: Path) -> int:
    """
    Analyse prose content for repeated blocks and print a report.

    Returns:
        Number of candidate blocks found.
    """
    candidates = _find_repeated_blocks(course_dir)
    _print_report(candidates, course_dir)
    return len(candidates)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _find_content_files(course_dir: Path) -> List[Path]:
    """Find index.md files inside .page and .assignment directories."""
    files = []
    content_dir = course_dir / "content"
    if not content_dir.exists():
        content_dir = course_dir / "pages"  # legacy fallback
    if not content_dir.exists():
        return files
    for pattern in ("**/*.page/index.md", "**/*.assignment/index.md"):
        files.extend(content_dir.glob(pattern))
    return sorted(set(files))


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter block (--- ... ---)."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def _extract_blocks(text: str) -> List[str]:
    """
    Split markdown text into paragraph blocks.

    Splits on blank lines, normalizes internal whitespace, strips leading/
    trailing whitespace per block. Skips blocks that are only headers,
    only whitespace, already {{include:...}} references, or too short to
    be meaningful (< 80 chars).
    """
    raw_blocks = re.split(r"\n\s*\n", text)
    blocks = []
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        # Skip pure headings
        if re.match(r"^#{1,6}\s", block) and "\n" not in block:
            continue
        # Skip existing includes
        if "{{include:" in block and len(block) < 80:
            continue
        # Normalise internal whitespace (collapse multiple spaces, but
        # preserve intentional line breaks within the block)
        block = "\n".join(line.rstrip() for line in block.splitlines())
        blocks.append(block)
    return blocks


def _block_fingerprint(block: str) -> str:
    """16-char SHA-256 hex of block text."""
    return hashlib.sha256(block.encode("utf-8")).hexdigest()[:16]


def _make_slug(text: str) -> str:
    """Derive a filesystem-safe slug from first ~60 chars of text."""
    # Take the first sentence or up to 60 chars
    first_line = text.splitlines()[0] if text else ""
    # Strip markdown formatting
    clean = re.sub(r"[*_`#>\[\]()]", "", first_line)
    clean = clean.strip()[:60]
    s = clean.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    s = s.strip("-")[:40].rstrip("-")
    return s or "shared-block"


def _find_repeated_blocks(
    course_dir: Path,
) -> List[Dict[str, Any]]:
    """
    Find all prose blocks meeting the repetition thresholds.

    Returns a list of dicts with keys:
        slug, text, char_count, files (sorted list of relative paths)
    """
    fp_to_block: Dict[str, str] = {}
    fp_to_files: Dict[str, Set[Path]] = defaultdict(set)

    content_files = _find_content_files(course_dir)
    for fpath in content_files:
        try:
            raw = fpath.read_text(encoding="utf-8")
        except Exception:
            continue
        body = _strip_frontmatter(raw)
        for block in _extract_blocks(body):
            fp = _block_fingerprint(block)
            fp_to_block[fp] = block
            fp_to_files[fp].add(fpath)

    candidates = []
    seen_slugs: Set[str] = set()
    for fp, files in fp_to_files.items():
        block = fp_to_block[fp]
        n_chars = len(block)
        n_files = len(files)

        qualifies = (
            (n_chars >= MIN_CHARS_LOW and n_files >= MIN_FILES_LOW)
            or (n_chars >= MIN_CHARS_HIGH and n_files >= MIN_FILES_HIGH)
        )
        if not qualifies:
            continue

        slug = _make_slug(block)
        # Ensure unique slugs in report
        base_slug = slug
        counter = 2
        while slug in seen_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1
        seen_slugs.add(slug)

        candidates.append(
            {
                "slug": slug,
                "text": block,
                "char_count": n_chars,
                "files": sorted(str(f.relative_to(course_dir)) for f in files),
            }
        )

    # Sort by (file count desc, char count desc) for most-impactful first
    candidates.sort(key=lambda c: (-len(c["files"]), -c["char_count"]))
    return candidates


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

_DIVIDER = "─" * 72
_HEADER = "━" * 72


def _print_report(candidates: List[Dict[str, Any]], course_dir: Path) -> None:
    if not candidates:
        print("No repeated prose blocks found meeting the include threshold.")
        print(
            f"(Thresholds: {MIN_CHARS_LOW}+ chars in {MIN_FILES_LOW}+ files, "
            f"or {MIN_CHARS_HIGH}+ chars in {MIN_FILES_HIGH}+ files)"
        )
        return

    print()
    print(f"Shared include candidates ({len(candidates)} found):")
    print(_HEADER)

    for c in candidates:
        slug = c["slug"]
        n_files = len(c["files"])
        n_chars = c["char_count"]
        preview = c["text"][:120].replace("\n", " ")
        if len(c["text"]) > 120:
            preview += "…"

        print()
        print(f"CANDIDATE: {slug}")
        print(f"  Appears in {n_files} file{'s' if n_files != 1 else ''} ({n_chars:,} chars)")
        for f in c["files"]:
            print(f"    - {f}")
        print(f"  Preview: \"{preview}\"")
        print(f"  To extract: shared/{slug}.md → {{{{include:{slug}}}}}")
        print(_DIVIDER)

    print()
    print("No files were modified. To act on these suggestions:")
    print("  1. Create shared/<slug>.md with the shared text")
    print("  2. Replace occurrences with {{include:<slug>}}")
    print("  3. Run: zaphod validate")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Suggest shared includes for repeated prose blocks (read-only)"
    )
    parser.add_argument(
        "--course-dir", "-d",
        type=Path,
        default=Path.cwd(),
        help="Course root directory (default: cwd)",
    )
    args = parser.parse_args()

    if not args.course_dir.exists():
        print(f"Error: {args.course_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    n = suggest_shared_includes(args.course_dir)
    if n == 0:
        sys.exit(0)


if __name__ == "__main__":
    main()
