#!/usr/bin/env python3
"""
Extract question bank IDs from Canvas HTML and generate bank-mappings.yaml

This script:
1. Parses Canvas "Manage Question Banks" page HTML
2. Extracts bank IDs and names from the HTML
3. Matches Canvas bank names to local .bank.md files
4. Generates question-banks/bank-mappings.yaml

Usage:
    # 1. Save Canvas page HTML to a file
    # Go to: Canvas > Quizzes > Manage Question Banks
    # Save page source to: banks.html

    # 2. Run this script
    python bank_scrape.py banks.html

    # 3. Review and edit the generated mappings
    cat question-banks/bank-mappings.yaml
"""

import re
import yaml
import argparse
from pathlib import Path
from datetime import datetime

def parse_html_banks(html_content):
    """
    Extract bank IDs and names from Canvas HTML.

    Returns: [(bank_id, bank_name), ...]
    """
    # Pattern matches:
    # <div class="question_bank" id="question_bank_XXXXXXXX"
    # and then: <a class="title" href="...">Title Text</a>
    pattern = r'<div class="question_bank" id="question_bank_(\d+)".*?<a class="title"[^>]*>([^<]+)</a>'
    matches = re.findall(pattern, html_content, re.DOTALL)

    return [(bank_id, title.strip()) for bank_id, title in matches]


def load_local_banks(question_banks_dir):
    """
    Load local .bank.md files and extract their names from frontmatter.

    Returns: {filename: frontmatter_name}
    e.g., {"01-variables.bank": "Session 1: JavaScript Fundamentals"}
    """
    import frontmatter

    local_banks = {}

    for bank_file in question_banks_dir.glob("*.bank.md"):
        try:
            post = frontmatter.load(bank_file)
            # Get name from frontmatter (bank_name takes priority, then name, then title)
            name = post.metadata.get('bank_name') or post.metadata.get('name') or post.metadata.get('title', '')

            # Use stem as key: "01-variables.bank.md" → "01-variables.bank"
            key = bank_file.stem
            local_banks[key] = name.strip()

        except Exception as e:
            print(f"⚠️ Couldn't parse {bank_file.name}: {e}")

    return local_banks


def match_banks(canvas_banks, local_banks):
    """
    Match Canvas banks to local files by name.

    Returns: {local_filename: canvas_id}
    """
    mappings = {}
    unmatched_canvas = []
    unmatched_local = []

    # Create reverse lookup: canvas_name → canvas_id
    canvas_lookup = {name: bank_id for bank_id, name in canvas_banks}

    # Try to match each local bank to a Canvas bank
    for local_file, local_name in local_banks.items():
        if local_name in canvas_lookup:
            # Exact match
            mappings[local_file] = int(canvas_lookup[local_name])
        else:
            # No match found
            unmatched_local.append((local_file, local_name))

    # Find Canvas banks that weren't matched
    matched_names = set(local_banks.values())
    for bank_id, canvas_name in canvas_banks:
        if canvas_name not in matched_names:
            unmatched_canvas.append((bank_id, canvas_name))

    return mappings, unmatched_local, unmatched_canvas


def save_bank_mappings(mappings, output_file):
    """Save mappings to YAML file."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Sort by key for consistency
    sorted_mappings = dict(sorted(mappings.items()))

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Question Bank ID Mappings\n")
        f.write("# Generated from Canvas HTML scrape\n")
        f.write(f"# Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("# Format: bank_filename → Canvas bank ID\n\n")
        yaml.dump(sorted_mappings, f, default_flow_style=False, sort_keys=False)

    print(f"✅ Saved {len(mappings)} mappings to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate bank-mappings.yaml from Canvas HTML',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Save Canvas page HTML, then:
  python bank_scrape.py banks.html

  # Specify output location:
  python bank_scrape.py banks.html --output ../my-course/question-banks/bank-mappings.yaml

  # Show what would be generated without writing:
  python bank_scrape.py banks.html --dry-run

Workflow:
  1. Canvas > Quizzes > Manage Question Banks
  2. Save page source to banks.html
  3. python bank_scrape.py banks.html
  4. Review: cat question-banks/bank-mappings.yaml
        """
    )
    parser.add_argument('input_file', help='Input HTML file from Canvas')
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output file path (default: question-banks/bank-mappings.yaml)'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Show what would be generated without writing file'
    )
    parser.add_argument(
        '--course-dir',
        type=Path,
        default=Path.cwd(),
        help='Course directory (default: current directory)'
    )
    args = parser.parse_args()

    # Determine paths
    course_dir = args.course_dir
    question_banks_dir = course_dir / "question-banks"

    if args.output:
        output_file = args.output
    else:
        output_file = question_banks_dir / "bank-mappings.yaml"

    # Check question-banks directory exists
    if not question_banks_dir.exists():
        print(f"❌ Question banks directory not found: {question_banks_dir}")
        print(f"   Make sure you're running this from your course directory")
        return 1

    # Read HTML
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"❌ File not found: {args.input_file}")
        return 1

    # Parse Canvas banks from HTML
    canvas_banks = parse_html_banks(html_content)
    if not canvas_banks:
        print(f"⚠️ No question banks found in HTML")
        print(f"   Make sure you saved the full page source from Canvas")
        return 1

    print(f"ℹ️ Found {len(canvas_banks)} banks in Canvas HTML")

    # Load local bank files
    try:
        import frontmatter
    except ImportError:
        print("❌ python-frontmatter not installed")
        print("   Run: pip install python-frontmatter")
        return 1

    local_banks = load_local_banks(question_banks_dir)
    if not local_banks:
        print(f"⚠️ No .bank.md files found in {question_banks_dir}")
        return 1

    print(f"ℹ️ Found {len(local_banks)} local bank files")
    print()

    # Match them up
    mappings, unmatched_local, unmatched_canvas = match_banks(canvas_banks, local_banks)

    # Show results
    if mappings:
        print(f"✅ Matched {len(mappings)} banks:")
        for filename, bank_id in sorted(mappings.items()):
            bank_name = local_banks[filename]
            print(f"  {filename}: {bank_id}  # {bank_name}")
        print()

    if unmatched_local:
        print(f"⚠️ {len(unmatched_local)} local banks not found in Canvas:")
        for filename, name in unmatched_local:
            print(f"  {filename} - {name}")
        print()

    if unmatched_canvas:
        print(f"⚠️ {len(unmatched_canvas)} Canvas banks not found locally:")
        for bank_id, name in unmatched_canvas:
            print(f"  {bank_id} - {name}")
        print()

    # Save or preview
    if mappings:
        if args.dry_run:
            print("[DRY RUN] Would write to:", output_file)
        else:
            save_bank_mappings(mappings, output_file)
            print()
            print(f"Next steps:")
            print(f"  1. Review: cat {output_file.relative_to(Path.cwd())}")
            print(f"  2. Apply IDs: python zaphod/utilities/apply_bank_ids.py")
            print(f"  3. Sync quizzes: zaphod sync")
    else:
        print("❌ No banks could be matched")
        print("   Check that bank names in frontmatter match Canvas names exactly")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
