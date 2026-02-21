#!/usr/bin/env python3
"""
Apply bank IDs from bank-mappings.yaml to quiz frontmatter files.

This utility reads the bank ID mappings generated during bank sync and
applies them to quiz question_groups, adding the bank_id field that
Canvas needs to link quizzes to question banks.

Usage:
    python apply_bank_ids.py                 # Apply to all quizzes
    python apply_bank_ids.py --quiz 01.quiz  # Apply to specific quiz
    python apply_bank_ids.py --dry-run       # Preview changes

Workflow:
    1. Run: zaphod sync --banks
       → Generates question-banks/bank-mappings.yaml

    2. Run: python zaphod/utilities/apply_bank_ids.py
       → Updates quiz frontmatter with bank_id fields

    3. Run: zaphod sync --quizzes
       → Syncs quizzes to Canvas with proper bank references
"""

import argparse
import yaml
import frontmatter
from pathlib import Path

COURSE_ROOT = Path.cwd()
CONTENT_DIR = COURSE_ROOT / "content"
PAGES_DIR = COURSE_ROOT / "pages"
QUESTION_BANKS_DIR = COURSE_ROOT / "question-banks"
BANK_MAPPINGS_FILE = QUESTION_BANKS_DIR / "bank-mappings.yaml"


def get_content_dir():
    """Get content directory (content/ or pages/)."""
    if CONTENT_DIR.exists():
        return CONTENT_DIR
    return PAGES_DIR


def load_bank_mappings():
    """Load bank ID mappings from YAML."""
    if not BANK_MAPPINGS_FILE.exists():
        print(f"❌ Bank mappings file not found: {BANK_MAPPINGS_FILE}")
        print(f"")
        print(f"To generate mappings:")
        print(f"  1. Run: zaphod sync --banks")
        print(f"  2. This will create {BANK_MAPPINGS_FILE.relative_to(COURSE_ROOT)}")
        return None

    try:
        with open(BANK_MAPPINGS_FILE, 'r', encoding='utf-8') as f:
            mappings = yaml.safe_load(f) or {}

        # Handle nested format
        if 'banks' in mappings:
            return {k: v['id'] if isinstance(v, dict) else v
                    for k, v in mappings['banks'].items()}

        return mappings
    except Exception as e:
        print(f"❌ Failed to load bank mappings: {e}")
        return None


def load_bank_names():
    """
    Load bank frontmatter names for reverse lookup.

    Returns: {canvas_name: (filename, bank_id)}
    e.g., {"Session 1: JavaScript Fundamentals": ("01-variables.bank", 12345)}
    """
    if not QUESTION_BANKS_DIR.exists():
        return {}

    bank_names = {}

    for bank_file in QUESTION_BANKS_DIR.glob("*.bank.md"):
        try:
            post = frontmatter.load(bank_file)
            # Get name from frontmatter (bank_name takes priority, then name, then title)
            name = post.metadata.get('bank_name') or post.metadata.get('name') or post.metadata.get('title', '')
            if name:
                filename = bank_file.stem  # "01-variables.bank.md" → "01-variables.bank"
                bank_names[name.strip()] = filename
        except Exception:
            pass

    return bank_names


def lookup_bank_id(bank_ref: str, mappings: dict, bank_names: dict) -> tuple:
    """
    Look up bank_id by filename OR Canvas name.

    Args:
        bank_ref: Reference from quiz (could be filename or Canvas name)
        mappings: filename → bank_id mapping
        bank_names: Canvas name → filename mapping

    Returns: (bank_id, match_type) or (None, None)
        match_type: "filename" | "filename.bank" | "canvas_name"
    """
    # Try 1: Exact filename match
    if bank_ref in mappings:
        return mappings[bank_ref], "filename"

    # Try 2: Add .bank extension
    if not bank_ref.endswith('.bank'):
        bank_with_ext = f"{bank_ref}.bank"
        if bank_with_ext in mappings:
            return mappings[bank_with_ext], "filename.bank"

    # Try 3: Match by Canvas name
    if bank_ref in bank_names:
        filename = bank_names[bank_ref]
        if filename in mappings:
            return mappings[filename], "canvas_name"

    return None, None


def apply_bank_ids_to_quiz(quiz_path: Path, mappings: dict, bank_names: dict, dry_run: bool = False):
    """
    Apply bank IDs to a single quiz's question_groups.

    Supports matching by:
    - Exact filename: "chapter1.bank"
    - Filename without extension: "chapter1"
    - Canvas bank name: "Session 1: JavaScript Fundamentals"

    Returns: (updated: bool, changes: list)
    """
    index_md = quiz_path / "index.md"
    if not index_md.exists():
        return False, [f"⚠️ No index.md found"]

    # Load frontmatter
    try:
        post = frontmatter.load(index_md)
    except Exception as e:
        return False, [f"❌ Failed to parse frontmatter: {e}"]

    question_groups = post.metadata.get('question_groups', [])

    if not question_groups:
        return False, [f"No question_groups in frontmatter"]

    changes = []
    updated = False

    for i, group in enumerate(question_groups):
        bank_ref = group.get('bank')
        if not bank_ref:
            continue

        # Already has a real bank_id (integer)? Skip it.
        # String values like PLACEHOLDER_REPLACE_AFTER_SYNC are treated as "not set".
        if 'bank_id' in group and isinstance(group['bank_id'], int):
            existing_id = group['bank_id']
            changes.append(f"  Group {i+1}: {bank_ref} → bank_id: {existing_id} (already set)")
            continue

        # Look up bank_id (supports filename OR Canvas name)
        bank_id, match_type = lookup_bank_id(bank_ref, mappings, bank_names)

        if bank_id:
            group['bank_id'] = bank_id
            match_info = f"matched by {match_type}" if match_type == "canvas_name" else ""
            changes.append(f"  Group {i+1}: {bank_ref} → bank_id: {bank_id} {match_info}".strip())
            updated = True
        else:
            changes.append(f"  Group {i+1}: {bank_ref} → ⚠️ ID not found (tried filename and Canvas name)")

    if updated and not dry_run:
        # Save updated frontmatter
        try:
            with open(index_md, 'w', encoding='utf-8') as f:
                f.write(frontmatter.dumps(post))
        except Exception as e:
            return False, [f"❌ Failed to write file: {e}"]

    return updated, changes


def main():
    parser = argparse.ArgumentParser(
        description="Apply bank IDs from mappings to quiz frontmatter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python apply_bank_ids.py                    # Apply to all quizzes
  python apply_bank_ids.py --quiz 01.quiz     # Apply to one quiz
  python apply_bank_ids.py --dry-run          # Preview changes

Workflow:
  1. zaphod sync --banks                      # Generate mappings
  2. python zaphod/utilities/apply_bank_ids.py # Apply IDs
  3. zaphod sync --quizzes                    # Sync to Canvas
        """
    )
    parser.add_argument(
        '--quiz', '-q',
        type=Path,
        help="Apply to specific quiz folder (e.g., 01-quiz.quiz)"
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help="Show what would change without modifying files"
    )
    args = parser.parse_args()

    # Load mappings
    mappings = load_bank_mappings()
    if mappings is None:
        return

    print(f"ℹ️ Loaded {len(mappings)} bank ID mapping(s)")
    for bank_name, bank_id in sorted(mappings.items()):
        print(f"  {bank_name} → {bank_id}")
    print()

    # Load bank names for reverse lookup (Canvas name → filename)
    bank_names = load_bank_names()
    if bank_names:
        print(f"ℹ️ Loaded {len(bank_names)} bank name(s) for matching")
        print()

    # Get content directory
    content_dir = get_content_dir()
    if not content_dir.exists():
        print(f"❌ Content directory not found: {content_dir}")
        return

    # Get quiz folders
    if args.quiz:
        # Handle both relative and absolute paths
        if args.quiz.is_absolute():
            quiz_path = args.quiz
        else:
            quiz_path = content_dir / args.quiz

        quiz_folders = [quiz_path] if quiz_path.exists() else []
        if not quiz_folders:
            print(f"❌ Quiz folder not found: {quiz_path}")
            return
    else:
        quiz_folders = sorted(content_dir.rglob("*.quiz"))

    if not quiz_folders:
        print(f"No quiz folders found in {content_dir}")
        return

    print(f"Processing {len(quiz_folders)} quiz folder(s)...")
    if args.dry_run:
        print("DRY RUN - no files will be modified")
    print()

    updated_count = 0
    skipped_count = 0

    for quiz_path in quiz_folders:
        updated, changes = apply_bank_ids_to_quiz(quiz_path, mappings, bank_names, args.dry_run)

        if changes:
            icon = '✅' if updated else '⏭️'
            print(f"{icon} {quiz_path.name}")
            for change in changes:
                print(change)
            print()

            if updated:
                updated_count += 1
            else:
                skipped_count += 1
        else:
            skipped_count += 1

    # Summary
    mode = "[DRY RUN] " if args.dry_run else ""
    print(f"{mode}✅ Updated: {updated_count}, ⏭️ Skipped: {skipped_count}")


if __name__ == "__main__":
    main()
