#!/usr/bin/env python3
"""
Extract outcome IDs from Canvas HTML and generate outcome-mappings.yaml

This script:
1. Parses Canvas "Outcomes" page HTML
2. Extracts outcome IDs and titles from the HTML
3. Matches Canvas outcome titles to local outcomes.yaml entries
4. Generates outcomes/outcome-mappings.yaml

Usage:
    # 1. Save Canvas page HTML to a file
    # Go to: Canvas > Outcomes
    # Save page source to: outcomes.html

    # 2. Run this script
    python outcome_scrape.py outcomes.html

    # 3. Review and edit the generated mappings
    cat outcomes/outcome-mappings.yaml
"""

import re
import yaml
import argparse
from pathlib import Path
from datetime import datetime

def parse_html_outcomes(html_content):
    """
    Extract outcome IDs and titles from Canvas HTML.

    Canvas outcomes may be in various formats. Common patterns:
    - data-outcome-id="XXXXX" with data-testid="outcome-management-item-title"
    - outcome_XXXXX in IDs with title elements
    - JSON data embedded in script tags

    Returns: [(outcome_id, outcome_title), ...]
    """
    outcomes = []

    # Pattern 1: data-outcome-id attribute with title
    # <div data-outcome-id="12345"...>
    #   <h4 data-testid="outcome-management-item-title">Title</h4>
    pattern1 = r'data-outcome-id="(\d+)"[^>]*>.*?data-testid="outcome-management-item-title">([^<]+)</h4>'
    matches1 = re.findall(pattern1, html_content, re.DOTALL)
    outcomes.extend([(outcome_id, title.strip()) for outcome_id, title in matches1])

    # Pattern 2: outcome_XXXXX in element IDs
    # <div id="outcome_12345"...>
    #   <h4 class="title">Title</h4>
    pattern2 = r'id="outcome_(\d+)"[^>]*>.*?<h4[^>]*class="title"[^>]*>([^<]+)</h4>'
    matches2 = re.findall(pattern2, html_content, re.DOTALL)
    outcomes.extend([(outcome_id, title.strip()) for outcome_id, title in matches2])

    # Pattern 3: JSON data in script tags (Canvas often embeds data this way)
    # Look for "id":12345,"title":"..."
    pattern3 = r'"id"\s*:\s*(\d+)\s*,\s*"title"\s*:\s*"([^"]+)"'
    matches3 = re.findall(pattern3, html_content)
    outcomes.extend([(outcome_id, title.strip()) for outcome_id, title in matches3])

    # Remove duplicates (same ID), keeping first occurrence
    seen_ids = set()
    unique_outcomes = []
    for outcome_id, title in outcomes:
        if outcome_id not in seen_ids:
            seen_ids.add(outcome_id)
            unique_outcomes.append((outcome_id, title))

    return unique_outcomes


def load_local_outcomes(outcomes_dir):
    """
    Load local outcomes.yaml and extract outcome codes/titles.

    Returns: {code: title}
    e.g., {"CLO1": "Analyze and improve design via UX process"}
    """
    outcomes_file = outcomes_dir / "outcomes.yaml"
    if not outcomes_file.exists():
        return {}

    try:
        with open(outcomes_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        local_outcomes = {}

        # Handle different possible structures
        if isinstance(data, dict):
            # Structure 1: {outcomes: [{code: ..., title: ...}, ...]}
            if 'outcomes' in data:
                for outcome in data['outcomes']:
                    code = outcome.get('code')
                    title = outcome.get('title', '')
                    if code:
                        local_outcomes[code] = title.strip()
            # Structure 2: {CLO1: {title: ...}, CLO2: {title: ...}}
            else:
                for code, details in data.items():
                    if isinstance(details, dict):
                        title = details.get('title', '')
                        local_outcomes[code] = title.strip()
        # Structure 3: [{code: ..., title: ...}, ...]
        elif isinstance(data, list):
            for outcome in data:
                code = outcome.get('code')
                title = outcome.get('title', '')
                if code:
                    local_outcomes[code] = title.strip()

        return local_outcomes

    except Exception as e:
        print(f"⚠️ Couldn't parse outcomes.yaml: {e}")
        return {}


def match_outcomes(canvas_outcomes, local_outcomes):
    """
    Match Canvas outcomes to local codes by title.

    Returns: {local_code: canvas_id}, unmatched_local, unmatched_canvas
    """
    mappings = {}
    unmatched_canvas = []
    unmatched_local = []

    # Create reverse lookup: canvas_title → canvas_id
    canvas_lookup = {title: outcome_id for outcome_id, title in canvas_outcomes}

    # Try to match each local outcome to a Canvas outcome
    for local_code, local_title in local_outcomes.items():
        # Try exact match
        if local_title in canvas_lookup:
            mappings[local_code] = int(canvas_lookup[local_title])
        else:
            # Try case-insensitive match
            matched = False
            for canvas_title, canvas_id in canvas_lookup.items():
                if canvas_title.lower() == local_title.lower():
                    mappings[local_code] = int(canvas_id)
                    matched = True
                    break

            if not matched:
                unmatched_local.append((local_code, local_title))

    # Find Canvas outcomes that weren't matched
    matched_titles = set(local_outcomes.values())
    for outcome_id, canvas_title in canvas_outcomes:
        if canvas_title not in matched_titles:
            # Check case-insensitive
            if not any(canvas_title.lower() == t.lower() for t in matched_titles):
                unmatched_canvas.append((outcome_id, canvas_title))

    return mappings, unmatched_local, unmatched_canvas


def save_outcome_mappings(mappings, output_file):
    """Save mappings to YAML file."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Sort by key for consistency
    sorted_mappings = dict(sorted(mappings.items()))

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Outcome ID Mappings\n")
        f.write("# Generated from Canvas HTML scrape\n")
        f.write(f"# Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("# Format: outcome_code → Canvas outcome ID\n\n")
        yaml.dump(sorted_mappings, f, default_flow_style=False, sort_keys=False)

    print(f"✅ Saved {len(mappings)} mappings to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate outcome-mappings.yaml from Canvas HTML',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Save Canvas page HTML, then:
  python outcome_scrape.py outcomes.html

  # Specify output location:
  python outcome_scrape.py outcomes.html --output ../my-course/outcomes/outcome-mappings.yaml

  # Show what would be generated without writing:
  python outcome_scrape.py outcomes.html --dry-run

Workflow:
  1. Canvas > Outcomes
  2. Save page source to outcomes.html
  3. python outcome_scrape.py outcomes.html
  4. Review: cat outcomes/outcome-mappings.yaml
        """
    )
    parser.add_argument('input_file', help='Input HTML file from Canvas')
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output file path (default: outcomes/outcome-mappings.yaml)'
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
    outcomes_dir = course_dir / "outcomes"

    if args.output:
        output_file = args.output
    else:
        output_file = outcomes_dir / "outcome-mappings.yaml"

    # Check outcomes directory exists
    if not outcomes_dir.exists():
        print(f"❌ Outcomes directory not found: {outcomes_dir}")
        print(f"   Make sure you're running this from your course directory")
        return 1

    # Read HTML
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"❌ File not found: {args.input_file}")
        return 1

    # Parse Canvas outcomes from HTML
    canvas_outcomes = parse_html_outcomes(html_content)
    if not canvas_outcomes:
        print(f"⚠️ No outcomes found in HTML")
        print(f"   Make sure you saved the full page source from Canvas")
        print(f"   If outcomes are there, the HTML structure may have changed.")
        print(f"   Check the regex patterns in parse_html_outcomes()")
        return 1

    print(f"ℹ️ Found {len(canvas_outcomes)} outcomes in Canvas HTML")

    # Load local outcomes
    local_outcomes = load_local_outcomes(outcomes_dir)
    if not local_outcomes:
        print(f"⚠️ No outcomes found in {outcomes_dir}/outcomes.yaml")
        return 1

    print(f"ℹ️ Found {len(local_outcomes)} local outcomes")
    print()

    # Match them up
    mappings, unmatched_local, unmatched_canvas = match_outcomes(canvas_outcomes, local_outcomes)

    # Show results
    if mappings:
        print(f"✅ Matched {len(mappings)} outcomes:")
        for code, outcome_id in sorted(mappings.items()):
            outcome_title = local_outcomes[code]
            print(f"  {code}: {outcome_id}  # {outcome_title}")
        print()

    if unmatched_local:
        print(f"⚠️ {len(unmatched_local)} local outcomes not found in Canvas:")
        for code, title in unmatched_local:
            print(f"  {code} - {title}")
        print()

    if unmatched_canvas:
        print(f"⚠️ {len(unmatched_canvas)} Canvas outcomes not found locally:")
        for outcome_id, title in unmatched_canvas:
            print(f"  {outcome_id} - {title}")
        print()

    # Save or preview
    if mappings:
        if args.dry_run:
            print("[DRY RUN] Would write to:", output_file)
        else:
            save_outcome_mappings(mappings, output_file)
            print()
            print(f"Next steps:")
            print(f"  1. Review: cat {output_file.relative_to(Path.cwd())}")
            print(f"  2. Use mappings in your sync scripts")
    else:
        print("❌ No outcomes could be matched")
        print("   Check that outcome titles in outcomes.yaml match Canvas titles")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
