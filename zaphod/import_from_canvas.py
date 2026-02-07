#!/usr/bin/env python3
"""
import_from_canvas.py (Zaphod)

Extract a Canvas course and convert it to Zaphod's local markdown structure.

Features:
- Fetches course metadata, pages, assignments, quizzes, modules, outcomes
- Converts Canvas HTML to markdown using html2text
- Generates YAML frontmatter from Canvas metadata
- Creates proper Zaphod directory structure (content/, modules/, outcomes/, etc.)
- Converts rubrics to YAML format
- Maps module membership bidirectionally
- Handles error conditions gracefully with progress indicators

Usage:
    python -m zaphod.import_from_canvas --course-id 12345 --output-dir ./my-course
    python -m zaphod.import_from_canvas -c 12345 -o ./my-course --skip-quizzes

Requirements:
    - Canvas API credentials configured (see canvas_client.py)
    - html2text library: pip install html2text
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from canvasapi import Canvas
from canvasapi.course import Course
from canvasapi.page import Page
from canvasapi.assignment import Assignment
from canvasapi.module import Module, ModuleItem
from canvasapi.quiz import Quiz
from canvasapi.outcome import Outcome

# Import Zaphod utilities
from zaphod.canvas_client import make_canvas_api_obj
from zaphod.config_utils import ConfigurationError
from zaphod.icons import (
    fence, SUCCESS, WARNING, INFO, ERROR,
    PAGE, ASSIGNMENT, QUIZ, MODULE, OUTCOME, DOWNLOAD, FOLDER
)

# Import required HTML conversion library
import html2text


# =============================================================================
# HTML to Markdown Conversion
# =============================================================================

def html_to_markdown(html_content: str) -> str:
    """
    Convert Canvas HTML to markdown using html2text.

    Args:
        html_content: HTML string from Canvas

    Returns:
        Markdown string
    """
    if not html_content:
        return ""

    h = html2text.HTML2Text()
    h.body_width = 0  # Don't wrap lines
    h.unicode_snob = True
    h.mark_code = True
    h.wrap_links = False
    return h.handle(html_content).strip()


# =============================================================================
# Filename Sanitization
# =============================================================================

def sanitize_filename(name: str, max_length: int = 80) -> str:
    """
    Convert a Canvas name to a filesystem-safe identifier.

    Examples:
        "Week 1: Introduction" -> "week-1-introduction"
        "Assignment #2 (Due Friday!)" -> "assignment-2-due-friday"

    Args:
        name: Original Canvas name
        max_length: Maximum filename length (default 80)

    Returns:
        Sanitized filename
    """
    # Convert to lowercase
    s = name.lower()

    # Replace special characters and spaces with hyphens
    s = re.sub(r'[^\w\s-]', '', s)  # Remove non-alphanumeric (except spaces/hyphens)
    s = re.sub(r'[-\s]+', '-', s)   # Convert spaces and multiple hyphens to single hyphen
    s = s.strip('-')                 # Remove leading/trailing hyphens

    # Truncate if too long
    if len(s) > max_length:
        s = s[:max_length].rstrip('-')

    # Ensure non-empty
    if not s:
        s = "untitled"

    return s


# =============================================================================
# Canvas Data Fetchers
# =============================================================================

def fetch_course_metadata(canvas: Canvas, course_id: int) -> Dict[str, Any]:
    """
    Fetch basic course metadata from Canvas.

    Returns:
        Dict with keys: id, name, course_code, term, public_description
    """
    print(f"{INFO} Fetching course metadata...")
    course = canvas.get_course(course_id)

    metadata = {
        "id": course.id,
        "name": course.name,
        "course_code": getattr(course, "course_code", ""),
        "term": getattr(course, "term", {}).get("name", "") if hasattr(course, "term") else "",
        "public_description": getattr(course, "public_description", ""),
    }

    print(f"{SUCCESS} Course: {metadata['name']} ({metadata['course_code']})")
    return metadata


def fetch_pages(course: Course) -> List[Page]:
    """
    Fetch all pages from Canvas course.

    Returns:
        List of Canvas Page objects
    """
    print(f"{INFO} Fetching pages...")
    pages = list(course.get_pages())
    print(f"{SUCCESS} Found {len(pages)} pages")
    return pages


def fetch_assignments(course: Course) -> List[Assignment]:
    """
    Fetch all assignments from Canvas course.

    Returns:
        List of Canvas Assignment objects
    """
    print(f"{INFO} Fetching assignments...")
    assignments = list(course.get_assignments())
    print(f"{SUCCESS} Found {len(assignments)} assignments")
    return assignments


def fetch_modules(course: Course) -> List[Module]:
    """
    Fetch all modules and their items from Canvas course.

    Returns:
        List of Canvas Module objects with items
    """
    print(f"{INFO} Fetching modules...")
    modules = list(course.get_modules())

    # Fetch items for each module
    for module in modules:
        try:
            # Force load items
            _ = list(module.get_module_items())
        except Exception as e:
            print(f"{WARNING} Could not fetch items for module '{module.name}': {e}")

    print(f"{SUCCESS} Found {len(modules)} modules")
    return modules


def fetch_outcomes(course: Course) -> List[Outcome]:
    """
    Fetch learning outcomes from Canvas course (if accessible).

    Returns:
        List of Canvas Outcome objects (may be empty if not accessible)
    """
    print(f"{INFO} Fetching learning outcomes...")
    try:
        outcomes = list(course.get_outcome_groups())
        print(f"{SUCCESS} Found {len(outcomes)} outcome groups")
        return outcomes
    except Exception as e:
        print(f"{WARNING} Could not fetch outcomes (may require special permissions): {e}")
        return []


def fetch_quizzes(course: Course) -> List[Quiz]:
    """
    Fetch all quizzes from Canvas course.

    Returns:
        List of Canvas Quiz objects
    """
    print(f"{INFO} Fetching quizzes...")
    try:
        quizzes = list(course.get_quizzes())
        print(f"{SUCCESS} Found {len(quizzes)} quizzes")
        return quizzes
    except Exception as e:
        print(f"{WARNING} Could not fetch quizzes: {e}")
        return []


# =============================================================================
# Module Mapping System
# =============================================================================

def build_module_mapping(modules: List[Module]) -> Tuple[Dict[str, List[str]], Dict[int, List[str]]]:
    """
    Build bidirectional mapping of content items to modules.

    Canvas uses two types of identifiers:
    - Pages: mapped by URL (page_url)
    - Assignments/Quizzes: mapped by content ID (content_id)

    Args:
        modules: List of Canvas Module objects with items loaded

    Returns:
        Tuple of (url_to_modules, id_to_modules) dictionaries
    """
    url_to_modules: Dict[str, List[str]] = {}  # page_url -> [module_names]
    id_to_modules: Dict[int, List[str]] = {}   # content_id -> [module_names]

    for module in modules:
        module_name = module.name

        try:
            items = list(module.get_module_items())
        except Exception as e:
            print(f"{WARNING} Could not fetch items for module '{module_name}': {e}")
            continue

        for item in items:
            # Page items (mapped by URL)
            if item.type == "Page" and hasattr(item, "page_url"):
                page_url = item.page_url
                if page_url not in url_to_modules:
                    url_to_modules[page_url] = []
                url_to_modules[page_url].append(module_name)

            # Assignment/Quiz items (mapped by content_id)
            elif item.type in ("Assignment", "Quiz") and hasattr(item, "content_id"):
                content_id = item.content_id
                if content_id not in id_to_modules:
                    id_to_modules[content_id] = []
                id_to_modules[content_id].append(module_name)

    return url_to_modules, id_to_modules


# =============================================================================
# Content Creators
# =============================================================================

def create_page(
    page: Page,
    output_dir: Path,
    url_to_modules: Dict[str, List[str]]
) -> None:
    """
    Create a .page folder with index.md for a Canvas page.

    Args:
        page: Canvas Page object
        output_dir: Output directory (content/)
        url_to_modules: Mapping of page URLs to module names
    """
    # Sanitize page name for folder
    folder_name = sanitize_filename(page.title)
    page_dir = output_dir / f"{folder_name}.page"
    page_dir.mkdir(parents=True, exist_ok=True)

    # Get module membership
    modules = url_to_modules.get(page.url, [])

    # Build frontmatter
    frontmatter = {
        "type": "page",
        "name": page.title,
        "published": getattr(page, "published", True),
    }

    if modules:
        frontmatter["modules"] = modules
        # Default indent to 0 for simplicity
        frontmatter["indent"] = 0

    # Convert HTML body to markdown
    body = ""
    if hasattr(page, "body") and page.body:
        body = html_to_markdown(page.body)

    # Write index.md
    index_path = page_dir / "index.md"
    content = f"---\n{yaml.dump(frontmatter, sort_keys=False)}---\n\n{body}\n"
    index_path.write_text(content, encoding="utf-8")

    # Create meta.json for Canvas ID tracking
    meta = {
        "canvas_id": page.page_id,
        "page_url": page.url,
    }
    meta_path = page_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"{PAGE} Created: {page_dir.name}")


def create_assignment(
    assignment: Assignment,
    output_dir: Path,
    id_to_modules: Dict[int, List[str]]
) -> None:
    """
    Create a .assignment folder with index.md and optional rubric.yaml.

    Args:
        assignment: Canvas Assignment object
        output_dir: Output directory (content/)
        id_to_modules: Mapping of assignment IDs to module names
    """
    # Sanitize assignment name for folder
    folder_name = sanitize_filename(assignment.name)
    assignment_dir = output_dir / f"{folder_name}.assignment"
    assignment_dir.mkdir(parents=True, exist_ok=True)

    # Get module membership
    modules = id_to_modules.get(assignment.id, [])

    # Build frontmatter
    frontmatter = {
        "type": "assignment",
        "name": assignment.name,
        "published": getattr(assignment, "published", True),
        "points_possible": getattr(assignment, "points_possible", 0),
    }

    # Add optional fields
    if hasattr(assignment, "submission_types"):
        frontmatter["submission_types"] = assignment.submission_types

    if hasattr(assignment, "due_at") and assignment.due_at:
        frontmatter["due_at"] = assignment.due_at

    if hasattr(assignment, "grading_type"):
        frontmatter["grading_type"] = assignment.grading_type

    if modules:
        frontmatter["modules"] = modules
        frontmatter["indent"] = 0

    # Convert HTML description to markdown
    body = ""
    if hasattr(assignment, "description") and assignment.description:
        body = html_to_markdown(assignment.description)

    # Write index.md
    index_path = assignment_dir / "index.md"
    content = f"---\n{yaml.dump(frontmatter, sort_keys=False)}---\n\n{body}\n"
    index_path.write_text(content, encoding="utf-8")

    # Create meta.json for Canvas ID tracking
    meta = {
        "canvas_id": assignment.id,
    }
    meta_path = assignment_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Check for rubric
    if hasattr(assignment, "rubric") and assignment.rubric:
        create_rubric(assignment.rubric, assignment_dir)

    print(f"{ASSIGNMENT} Created: {assignment_dir.name}")


def create_quiz(
    quiz: Quiz,
    output_dir: Path,
    id_to_modules: Dict[int, List[str]]
) -> None:
    """
    Create a .quiz folder with index.md for a Canvas quiz.

    Args:
        quiz: Canvas Quiz object
        output_dir: Output directory (content/)
        id_to_modules: Mapping of quiz IDs to module names
    """
    # Sanitize quiz name for folder
    folder_name = sanitize_filename(quiz.title)
    quiz_dir = output_dir / f"{folder_name}.quiz"
    quiz_dir.mkdir(parents=True, exist_ok=True)

    # Get module membership
    modules = id_to_modules.get(quiz.id, [])

    # Build frontmatter
    frontmatter = {
        "type": "quiz",
        "name": quiz.title,
        "published": getattr(quiz, "published", True),
        "points_possible": getattr(quiz, "points_possible", 0),
    }

    # Add optional quiz-specific fields
    if hasattr(quiz, "quiz_type"):
        frontmatter["quiz_type"] = quiz.quiz_type

    if hasattr(quiz, "time_limit") and quiz.time_limit:
        frontmatter["time_limit"] = quiz.time_limit

    if hasattr(quiz, "shuffle_answers"):
        frontmatter["shuffle_answers"] = quiz.shuffle_answers

    if modules:
        frontmatter["modules"] = modules
        frontmatter["indent"] = 0

    # Convert HTML description to markdown
    body = ""
    if hasattr(quiz, "description") and quiz.description:
        body = html_to_markdown(quiz.description)

    # Write index.md
    index_path = quiz_dir / "index.md"
    content = f"---\n{yaml.dump(frontmatter, sort_keys=False)}---\n\n{body}\n"
    index_path.write_text(content, encoding="utf-8")

    # Create meta.json for Canvas ID tracking
    meta = {
        "canvas_id": quiz.id,
    }
    meta_path = quiz_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"{QUIZ} Created: {quiz_dir.name}")


def create_rubric(rubric_data: List[Dict[str, Any]], assignment_dir: Path) -> None:
    """
    Convert Canvas rubric to Zaphod YAML format.

    Args:
        rubric_data: Canvas rubric structure (list of criteria)
        assignment_dir: Assignment folder to save rubric.yaml
    """
    # Convert Canvas rubric format to Zaphod YAML format
    criteria = []

    for criterion in rubric_data:
        criterion_obj = {
            "description": criterion.get("description", ""),
            "points": criterion.get("points", 0),
            "ratings": []
        }

        # Convert ratings
        for rating in criterion.get("ratings", []):
            rating_obj = {
                "description": rating.get("description", ""),
                "points": rating.get("points", 0),
            }
            criterion_obj["ratings"].append(rating_obj)

        criteria.append(criterion_obj)

    # Write rubric.yaml
    rubric_path = assignment_dir / "rubric.yaml"
    rubric_content = {
        "criteria": criteria
    }
    rubric_path.write_text(yaml.dump(rubric_content, sort_keys=False), encoding="utf-8")
    print(f"  {SUCCESS} Created rubric.yaml")


# =============================================================================
# Configuration File Creators
# =============================================================================

def create_zaphod_yaml(output_dir: Path, course_metadata: Dict[str, Any]) -> None:
    """
    Create zaphod.yaml configuration file.

    Args:
        output_dir: Course root directory
        course_metadata: Course metadata from Canvas
    """
    config = {
        "course_id": str(course_metadata["id"]),
        "course_name": course_metadata["name"],
        "course_code": course_metadata["course_code"],
    }

    config_path = output_dir / "zaphod.yaml"
    config_path.write_text(yaml.dump(config, sort_keys=False), encoding="utf-8")
    print(f"{SUCCESS} Created zaphod.yaml")


def create_module_order_yaml(output_dir: Path, modules: List[Module]) -> None:
    """
    Create modules/module_order.yaml from Canvas module ordering.

    Args:
        output_dir: Course root directory
        modules: List of Canvas Module objects (in order)
    """
    modules_dir = output_dir / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)

    # Extract module names in order
    module_names = [m.name for m in modules]

    module_order_path = modules_dir / "module_order.yaml"
    module_order_path.write_text(yaml.dump(module_names, sort_keys=False), encoding="utf-8")
    print(f"{SUCCESS} Created modules/module_order.yaml ({len(module_names)} modules)")


def create_variables_yaml(output_dir: Path, course_metadata: Dict[str, Any]) -> None:
    """
    Create shared/variables.yaml with basic course variables.

    Args:
        output_dir: Course root directory
        course_metadata: Course metadata from Canvas
    """
    shared_dir = output_dir / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)

    variables = {
        "course_title": course_metadata["name"],
        "course_code": course_metadata["course_code"],
        "term": course_metadata["term"],
        "instructor_name": "TODO: Replace with instructor name",
        "instructor_email": "TODO: Replace with instructor email",
    }

    variables_path = shared_dir / "variables.yaml"
    variables_path.write_text(yaml.dump(variables, sort_keys=False), encoding="utf-8")
    print(f"{SUCCESS} Created shared/variables.yaml")


def create_directory_structure(output_dir: Path) -> None:
    """
    Create standard Zaphod directory structure.

    Args:
        output_dir: Course root directory
    """
    directories = [
        "content",
        "shared",
        "modules",
        "outcomes",
        "question-banks",
        "assets",
        "rubrics",
        "rubrics/rows",
        "_course_metadata",
    ]

    for dir_name in directories:
        dir_path = output_dir / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)

    print(f"{FOLDER} Created directory structure")


# =============================================================================
# Main Import Logic
# =============================================================================

def import_canvas_course(
    course_id: int,
    output_dir: Path,
    skip_quizzes: bool = False
) -> None:
    """
    Import complete Canvas course to Zaphod local structure.

    Args:
        course_id: Canvas course ID
        output_dir: Output directory for course content
        skip_quizzes: If True, skip quiz import
    """
    fence("Canvas Course Import")
        print()

    # Connect to Canvas
    print(f"{INFO} Connecting to Canvas API...")
    canvas = make_canvas_api_obj()

    # Fetch course metadata
    fence("Fetching Course Data")
    course_metadata = fetch_course_metadata(canvas, course_id)
    course = canvas.get_course(course_id)

    # Fetch all content
    pages = fetch_pages(course)
    assignments = fetch_assignments(course)
    modules = fetch_modules(course)
    outcomes = fetch_outcomes(course)

    quizzes = []
    if not skip_quizzes:
        quizzes = fetch_quizzes(course)
    else:
        print(f"{INFO} Skipping quiz import (--skip-quizzes)")

    # Build module mappings
    fence("Building Module Mappings")
    url_to_modules, id_to_modules = build_module_mapping(modules)
    print(f"{SUCCESS} Mapped {len(url_to_modules)} pages and {len(id_to_modules)} assignments/quizzes to modules")

    # Create directory structure
    fence("Creating Course Structure")
    output_dir.mkdir(parents=True, exist_ok=True)
    create_directory_structure(output_dir)

    # Create configuration files
    create_zaphod_yaml(output_dir, course_metadata)
    create_variables_yaml(output_dir, course_metadata)
    create_module_order_yaml(output_dir, modules)

    # Create content folders
    fence("Converting Content")
    content_dir = output_dir / "content"

    print(f"\n{PAGE} Creating pages...")
    for page in pages:
        try:
            create_page(page, content_dir, url_to_modules)
        except Exception as e:
            print(f"{ERROR} Failed to create page '{page.title}': {e}")

    print(f"\n{ASSIGNMENT} Creating assignments...")
    for assignment in assignments:
        try:
            create_assignment(assignment, content_dir, id_to_modules)
        except Exception as e:
            print(f"{ERROR} Failed to create assignment '{assignment.name}': {e}")

    if quizzes:
        print(f"\n{QUIZ} Creating quizzes...")
        for quiz in quizzes:
            try:
                create_quiz(quiz, content_dir, id_to_modules)
            except Exception as e:
                print(f"{ERROR} Failed to create quiz '{quiz.title}': {e}")

    # Summary
    fence("Import Complete")
    print(f"{SUCCESS} Course imported successfully!")
    print()
    print(f"Output directory: {output_dir.absolute()}")
    print()
    print("Summary:")
    print(f"  {PAGE} Pages: {len(pages)}")
    print(f"  {ASSIGNMENT} Assignments: {len(assignments)}")
    print(f"  {QUIZ} Quizzes: {len(quizzes)}")
    print(f"  {MODULE} Modules: {len(modules)}")
    print()
    print("Next steps:")
    print(f"  1. Review and edit content in {output_dir}/content/")
    print(f"  2. Update variables in {output_dir}/shared/variables.yaml")
    print(f"  3. Verify module ordering in {output_dir}/modules/module_order.yaml")
    print(f"  4. Test publishing with: python -m zaphod.canvas_publish")
    print()


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """CLI entry point for import_from_canvas."""
    parser = argparse.ArgumentParser(
        description="Import Canvas course content to Zaphod local structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import course to current directory
  python -m zaphod.import_from_canvas --course-id 12345 --output-dir ./my-course

  # Import without quizzes
  python -m zaphod.import_from_canvas -c 12345 -o ./my-course --skip-quizzes

Requirements:
  - Canvas API credentials configured (see canvas_client.py)
  - html2text library: pip install html2text
        """
    )

    parser.add_argument(
        "-c", "--course-id",
        type=int,
        required=True,
        help="Canvas course ID to import"
    )

    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        required=True,
        help="Output directory for course content"
    )

    parser.add_argument(
        "--skip-quizzes",
        action="store_true",
        help="Skip importing quizzes"
    )

    args = parser.parse_args()

    try:
        import_canvas_course(
            course_id=args.course_id,
            output_dir=args.output_dir,
            skip_quizzes=args.skip_quizzes
        )
    except ConfigurationError as e:
        print(f"{ERROR} Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"{ERROR} Import failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
