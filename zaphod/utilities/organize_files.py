#!/usr/bin/env python3
"""
Course File Organizer
Organizes course module files into structured directories.

Usage:
    python organize_files.py [--dry-run] [--verbose]
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional
import argparse


class FileOrganizer:
    """Handles organization of course files into structured directories."""

    def __init__(self, dry_run: bool = False, verbose: bool = False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.changes: List[str] = []
        self.errors: List[str] = []

    def log(self, message: str, force: bool = False):
        """Log a message if verbose mode is enabled."""
        if self.verbose or force:
            print(f"  {message}")

    def record_change(self, action: str):
        """Record a change for the summary report."""
        self.changes.append(action)
        self.log(action)

    def record_error(self, error: str):
        """Record an error for the summary report."""
        self.errors.append(error)
        print(f"  ❌ ERROR: {error}", file=sys.stderr)

    def create_directory_and_move(self, source_file: Path, 
                                   dir_suffix: str, 
                                   new_filename: str) -> Optional[Path]:
        """
        Create a directory based on filename pattern and move file into it.

        Args:
            source_file: Source file path
            dir_suffix: Suffix to strip from filename to create directory name
            new_filename: New name for the file inside the directory

        Returns:
            Path to created directory, or None if operation failed
        """
        try:
            # Create directory name by stripping the suffix
            dir_name = source_file.name.replace(dir_suffix, '')
            target_dir = source_file.parent / dir_name
            target_file = target_dir / new_filename

            # Check if source exists
            if not source_file.exists():
                self.record_error(f"Source file not found: {source_file}")
                return None

            # Check if target already exists
            if target_file.exists() and not self.dry_run:
                self.record_error(
                    f"Target already exists: {target_file}\n"
                    f"    Would overwrite existing file. Skipping."
                )
                return None

            if self.dry_run:
                self.record_change(
                    f"Would create: {target_dir}/\n"
                    f"    Would move: {source_file.name} → {target_file.name}"
                )
            else:
                # Create directory
                target_dir.mkdir(parents=True, exist_ok=True)

                # Move and rename file
                source_file.rename(target_file)

                self.record_change(
                    f"Created: {target_dir.name}/\n"
                    f"    Moved: {source_file.name} → {target_file.name}"
                )

            return target_dir

        except Exception as e:
            self.record_error(f"Failed to process {source_file}: {str(e)}")
            return None

    def move_related_file(self, source_file: Path, 
                          target_dir: Path, 
                          new_filename: Optional[str] = None):
        """
        Move a related file (rubric, starter) into a target directory.

        Args:
            source_file: Source file to move
            target_dir: Destination directory
            new_filename: Optional new filename (keeps original if None)
        """
        try:
            if not source_file.exists():
                # Not an error - related files are optional
                self.log(f"Related file not found (optional): {source_file.name}")
                return

            filename = new_filename if new_filename else source_file.name
            target_file = target_dir / filename

            if target_file.exists() and not self.dry_run:
                self.record_error(
                    f"Target already exists: {target_file}\n"
                    f"    Skipping {source_file.name}"
                )
                return

            if self.dry_run:
                self.record_change(
                    f"Would move: {source_file.name} → {target_dir.name}/{filename}"
                )
            else:
                source_file.rename(target_file)
                self.record_change(
                    f"Moved: {source_file.name} → {target_dir.name}/{filename}"
                )

        except Exception as e:
            self.record_error(
                f"Failed to move related file {source_file}: {str(e)}"
            )

    def move_bank_files(self, directory: Path):
        """
        Move .bank.md files to ../../question-banks/ directory.
        Expects the question-banks directory to already exist.

        Args:
            directory: Current working directory (must be absolute path)
        """
        print("\n🏦 Processing bank files (.bank.md)...")

        # Find all bank files
        bank_files = [f for f in directory.iterdir() if f.is_file() and f.name.endswith('.bank.md')]

        if not bank_files:
            print("  No bank files found.")
            return

        # Target directory is ../../question-banks/
        # Ensure directory is absolute before calculating parent paths
        abs_directory = directory.resolve()
        question_banks_dir = abs_directory.parent.parent / "question-banks"

        # Check if question-banks directory exists
        if not question_banks_dir.exists():
            self.record_error(
                f"Quiz banks directory does not exist: {question_banks_dir}\n"
                f"    Please create it first or check your path."
            )
            return

        if not question_banks_dir.is_dir():
            self.record_error(f"Path exists but is not a directory: {question_banks_dir}")
            return

        try:
            self.log(f"Using existing directory: {question_banks_dir}")

            # Move each bank file
            for bank_file in bank_files:
                target_file = question_banks_dir / bank_file.name

                if target_file.exists() and not self.dry_run:
                    self.record_error(
                        f"Target already exists: {target_file}\n"
                        f"    Skipping {bank_file.name}"
                    )
                    continue

                if self.dry_run:
                    self.record_change(
                        f"Would move: {bank_file.name} → question-banks/{bank_file.name}"
                    )
                else:
                    bank_file.rename(target_file)
                    self.record_change(
                        f"Moved: {bank_file.name} → question-banks/{bank_file.name}"
                    )

        except Exception as e:
            self.record_error(f"Failed to process bank files: {str(e)}")

    def organize_orphaned_files(self, directory: Path):
        """
        Handle case where Perplexity created directories but left files outside.
        Move orphaned learning files and rubrics into existing directories.

        Args:
            directory: Current working directory
        """
        print("\n🔍 Checking for orphaned files (existing directory pattern)...")

        # Get all items
        all_items = list(directory.iterdir())
        existing_dirs = [d for d in all_items if d.is_dir()]
        all_files = [f for f in all_items if f.is_file()]

        if not existing_dirs:
            print("  No existing directories found.")
            return

        # Look for orphaned learning files (XX-1-learning-*.md)
        learning_pattern = re.compile(r'^(\d+)-(\d+)-learning-.*\.md$')
        orphaned_learning = []

        for f in all_files:
            match = learning_pattern.match(f.name)
            if match:
                # Check if matching directory exists
                expected_dir = directory / f.name.replace('.md', '')
                if expected_dir.exists() and expected_dir.is_dir():
                    orphaned_learning.append((f, expected_dir))

        if orphaned_learning:
            print(f"  Found {len(orphaned_learning)} orphaned learning file(s):")
            for f, target_dir in orphaned_learning:
                print(f"      - {f.name} → {target_dir.name}/")
                self.move_related_file(f, target_dir, 'index.md')

        # Look for orphaned rubric files (XX-4-rubric.yaml or similar)
        rubric_pattern = re.compile(r'^(\d+)-(\d+)-rubric\.yaml$')
        orphaned_rubrics = []

        for f in all_files:
            match = rubric_pattern.match(f.name)
            if match:
                module_num = match.group(1)
                # Look for assignment directory with same module number
                # Pattern: XX-3-assignment-* or XX-4-assignment-*
                for d in existing_dirs:
                    if (d.name.startswith(f"{module_num}-") and 
                        'assignment' in d.name):
                        orphaned_rubrics.append((f, d))
                        break

        if orphaned_rubrics:
            print(f"  Found {len(orphaned_rubrics)} orphaned rubric file(s):")
            for f, target_dir in orphaned_rubrics:
                print(f"      - {f.name} → {target_dir.name}/")
                self.move_related_file(f, target_dir, 'rubric.yaml')

        # Look for orphaned starter files
        starter_pattern = re.compile(r'^(\d+)-starter\.(js|html|css|py|java|cpp|c|ts|jsx|tsx)$')
        orphaned_starters = []

        for f in all_files:
            match = starter_pattern.match(f.name)
            if match:
                module_num = match.group(1)
                # Look for assignment directory with same module number
                for d in existing_dirs:
                    if (d.name.startswith(f"{module_num}-") and 
                        'assignment' in d.name):
                        orphaned_starters.append((f, d))
                        break

        if orphaned_starters:
            print(f"  Found {len(orphaned_starters)} orphaned starter file(s):")
            for f, target_dir in orphaned_starters:
                print(f"      - {f.name} → {target_dir.name}/")
                self.move_related_file(f, target_dir)

        if not orphaned_learning and not orphaned_rubrics and not orphaned_starters:
            print("  No orphaned files found.")

    def organize_files(self, directory: Path = Path('.')):
        """
        Main organization function.

        Processes all files in the directory according to course file patterns.
        """
        # Resolve directory to absolute path immediately
        directory = directory.resolve()

        print(f"\n{'='*60}")
        print(f"Course File Organizer")
        print(f"{'='*60}")
        print(f"Directory: {directory}")
        print(f"Mode: {'DRY RUN (no changes will be made)' if self.dry_run else 'LIVE'}")
        print(f"{'='*60}\n")

        # Get all files in directory (only files, not directories)
        all_files = [f for f in directory.iterdir() if f.is_file()]

        # Step 0: Check for orphaned files with existing directories (new Perplexity pattern)
        self.organize_orphaned_files(directory)

        # Refresh file list after orphan processing
        all_files = [f for f in directory.iterdir() if f.is_file()]

        # Step 1: Process .page.md files and learning files
        print("\n📄 Processing page files (.page.md and learning files)...")
        page_files = [f for f in all_files if f.name.endswith('.page.md')]

        # Also catch files ending in -learning.md (edge case from Perplexity)
        learning_files = [f for f in all_files if f.name.endswith('-learning.md') and f not in page_files]
        if learning_files:
            print(f"  ⚠️  Found {len(learning_files)} learning file(s) without .page.md suffix:")
            for lf in learning_files:
                print(f"      - {lf.name}")
            page_files.extend(learning_files)

        if not page_files:
            print("  No page files found.")
        for page_file in page_files:
            self.create_directory_and_move(page_file, '.md', 'index.md')

        # Step 2: Process .quiz.md files and quiz variants
        print("\n📝 Processing quiz files (.quiz.md and variants)...")
        quiz_files = [f for f in all_files if f.name.endswith('.quiz.md')]

        # Also catch files like quiz-review.md, quiz-practice.md (edge case from Perplexity)
        # Pattern: starts with 'quiz' or contains '-quiz-' or '-quiz.md'
        quiz_variants = [
            f for f in all_files 
            if (f.name.startswith('quiz') or '-quiz-' in f.name or f.name.endswith('-quiz.md'))
            and f.name.endswith('.md')
            and '.quiz.md' not in f.name
            and f not in quiz_files
            and '.bank.md' not in f.name
            and not f.name.endswith('-learning.md')  # Don't catch learning files
        ]
        if quiz_variants:
            print(f"  ⚠️  Found {len(quiz_variants)} quiz file(s) without .quiz.md suffix:")
            for qv in quiz_variants:
                print(f"      - {qv.name}")
            quiz_files.extend(quiz_variants)

        if not quiz_files:
            print("  No quiz files found.")
        for quiz_file in quiz_files:
            self.create_directory_and_move(quiz_file, '.md', 'index.md')

        # Step 3: Process .bank.md files - move to ../../question-banks/
        self.move_bank_files(directory)

        # Step 4: Process .assignment.md files with related files
        print("\n📋 Processing assignment files (.assignment.md)...")
        assignment_files = [
            f for f in all_files 
            if '.assignment.md' in f.name and '.rubric.yaml' not in f.name
        ]

        # Also catch inconsistent naming (e.g., "02-3-assignment-functions.md")
        for f in all_files:
            if (f.name.endswith('.md') and 
                'assignment' in f.name and 
                '.assignment.md' not in f.name and
                '.rubric.yaml' not in f.name and
                '.page.md' not in f.name and
                '.quiz.md' not in f.name and
                '.bank.md' not in f.name and
                not f.name.endswith('-learning.md') and
                f not in quiz_variants):  # Don't double-process quiz variants
                print(f"  ⚠️  Found inconsistent naming: {f.name}")
                assignment_files.append(f)

        if not assignment_files:
            print("  No assignment files found.")

        for assignment_file in assignment_files:
            # Determine the base name for matching related files
            # Handle both "XX-X-assignment-name.assignment.md" and "XX-X-assignment-name.md"
            base_name = assignment_file.name

            # Create directory and move main assignment file
            if '.assignment.md' in assignment_file.name:
                target_dir = self.create_directory_and_move(
                    assignment_file, '.md', 'index.md'
                )
                # Base for finding related files
                search_base = assignment_file.name.replace('.assignment.md', '')
            else:
                # Handle inconsistent naming like "02-3-assignment-functions.md"
                target_dir = self.create_directory_and_move(
                    assignment_file, '.md', 'index.md'
                )
                search_base = assignment_file.name.replace('.md', '')

            if target_dir:
                # Find and move related rubric file
                # Try both with and without .assignment in the name
                rubric_patterns = [
                    directory / f"{search_base}.assignment.rubric.yaml",
                    directory / f"{search_base}.rubric.yaml",
                    directory / f"{search_base}-rubric.yaml"
                ]

                rubric_moved = False
                for rubric_file in rubric_patterns:
                    if rubric_file.exists():
                        self.move_related_file(rubric_file, target_dir, 'rubric.yaml')
                        rubric_moved = True
                        break

                if not rubric_moved:
                    self.log(f"No rubric found for {assignment_file.name}")

                # Find and move related starter file(s)
                # Extract module number (e.g., "01" from "01-3-assignment-...")
                match = re.match(r'^(\d+)', assignment_file.name)
                if match:
                    module_num = match.group(1)

                    # Look for starter files with common extensions
                    starter_extensions = ['.js', '.html', '.css', '.py', '.java', '.cpp', '.c', '.ts', '.jsx', '.tsx']
                    starter_found = False

                    for ext in starter_extensions:
                        starter_file = directory / f"{module_num}-starter{ext}"
                        if starter_file.exists():
                            self.move_related_file(starter_file, target_dir)
                            starter_found = True

                    if not starter_found:
                        self.log(f"No starter file found for module {module_num}")

        # Print summary
        print(f"\n{'='*60}")
        print(f"Summary")
        print(f"{'='*60}")
        print(f"Total operations: {len(self.changes)}")
        print(f"Errors: {len(self.errors)}")

        if self.errors:
            print(f"\n⚠️  Errors encountered:")
            for error in self.errors:
                print(f"  - {error}")

        if self.dry_run:
            print(f"\n💡 This was a dry run. No files were modified.")
            print(f"   Run without --dry-run to apply changes.")
        else:
            print(f"\n✅ File organization complete!")

        print(f"{'='*60}\n")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Organize course files into structured directories.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes without making them
  python organize_files.py --dry-run --verbose

  # Actually organize the files
  python organize_files.py

  # Organize with detailed output
  python organize_files.py --verbose
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying any files'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output for all operations'
    )

    parser.add_argument(
        '--directory', '-d',
        type=Path,
        default=Path('.'),
        help='Directory to organize (default: current directory)'
    )

    args = parser.parse_args()

    # Validate directory
    if not args.directory.exists():
        print(f"Error: Directory '{args.directory}' does not exist.", file=sys.stderr)
        sys.exit(1)

    if not args.directory.is_dir():
        print(f"Error: '{args.directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    # Run organizer
    organizer = FileOrganizer(dry_run=args.dry_run, verbose=args.verbose)
    try:
        organizer.organize_files(args.directory)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
