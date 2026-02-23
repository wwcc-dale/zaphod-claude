#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

export_cartridge.py — Orchestrator for the step-by-step CC export pipeline.

Creates an IMS Common Cartridge 1.1 package that can be imported into Canvas,
Moodle, Blackboard, Brightspace, Sakai, and other CC-compliant LMS platforms.

Pipeline steps (run in sequence):
  Step 1: frontmatter_to_meta.py  ← reads index.md, writes meta.json + source.md
          (skipped in --watch-mode or --skip-meta; sync pipeline already ran it)
  Step 2: export_pages.py         ← wiki_content/{id}.html
  Step 3: export_assignments.py   ← web_resources/{id}/
  Step 4: export_quizzes.py       ← assessments/ + non_cc_assessments/
  Step 5: export_modules.py       ← course_settings/module_meta.xml + org items
  Step 6: export_settings.py      ← course_settings/ CE files
  Step 7: export_outcomes.py      ← {name}.outcomes.csv (alongside .imscc)
  Step 8: assemble_cartridge.py   ← imsmanifest.xml + zip → .imscc

Usage:
    python export_cartridge.py [--output PATH] [--title "Course Title"]
    python export_cartridge.py --watch-mode   # skip frontmatter step (sync ran it)
    python export_cartridge.py --skip-meta    # same as watch-mode for step 1

Environment:
    EXPORT_MANIFEST_PATH    path to .export_manifest.json (set internally)
    ZAPHOD_CHANGED_FILES    (optional) for incremental exports (future)
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

from zaphod.export_types import ExportManifest
from zaphod.icons import SUCCESS

SCRIPT_DIR = Path(__file__).resolve().parent
COURSE_ROOT = Path.cwd()
METADATA_DIR = COURSE_ROOT / "_course_metadata"
EXPORTS_DIR = METADATA_DIR / "exports"
STAGING_DIR = EXPORTS_DIR / ".staging"
MANIFEST_PATH = EXPORTS_DIR / ".export_manifest.json"


# ============================================================================
# Timestamp helper
# ============================================================================

def _timestamp_filename(base: str = "export") -> str:
    """Return a timestamped filename: YYYYMMDD_HHMMSS_{base}.imscc"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{base}.imscc"


# ============================================================================
# Export initialisation
# ============================================================================

def init_export(title: str, output_path: Path) -> ExportManifest:
    """
    Create the staging directory tree and an empty manifest JSON.

    Wipes any previous staging state so every run is a clean rebuild.
    """
    # Clean rebuild — delete previous staging on each run
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)

    # Create staging subdirs expected by each step
    for subdir in [
        "wiki_content",
        "web_resources",
        "assessments",
        "non_cc_assessments",
        "course_settings",
    ]:
        (STAGING_DIR / subdir).mkdir(parents=True)

    identifier = f"cc_{hashlib.md5(title.encode()).hexdigest()[:12]}"

    manifest = ExportManifest(
        identifier=identifier,
        title=title,
        staging_dir=STAGING_DIR,
        output_path=output_path,
    )
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest.save(MANIFEST_PATH)
    return manifest


# ============================================================================
# Step runners
# ============================================================================

def _run_frontmatter_step() -> None:
    """Run frontmatter_to_meta.py as a subprocess (mirrors sync pipeline usage)."""
    script = SCRIPT_DIR / "frontmatter_to_meta.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        check=False,
    )
    if result.returncode != 0:
        print("[export] frontmatter_to_meta.py exited with errors — continuing")


def _run_export_steps() -> None:
    """
    Run export steps 2–8 by importing each module and calling its main().

    EXPORT_MANIFEST_PATH must be set in the environment before calling this
    so each step can locate the manifest without extra arguments.
    """
    from zaphod import (
        export_pages,
        export_assignments,
        export_quizzes,
        export_modules,
        export_settings,
        export_outcomes,
        assemble_cartridge,
    )

    steps = [
        ("pages",       export_pages.main),
        ("assignments", export_assignments.main),
        ("quizzes",     export_quizzes.main),
        ("modules",     export_modules.main),
        ("settings",    export_settings.main),
        ("outcomes",    export_outcomes.main),
        ("assemble",    assemble_cartridge.main),
    ]

    for name, step_fn in steps:
        print(f"\n[export] → step: {name}")
        try:
            step_fn()
        except SystemExit as exc:
            print(f"[export] Step '{name}' failed (exit {exc.code})")
            raise


# ============================================================================
# Main entry point
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Zaphod course to IMS Common Cartridge format"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file path (default: _course_metadata/exports/TIMESTAMP_export.imscc)",
    )
    parser.add_argument(
        "--title", "-t",
        help="Course title (default: from zaphod.yaml or folder name)",
    )
    parser.add_argument(
        "--watch-mode",
        action="store_true",
        help="Skip frontmatter step — sync pipeline already ran it",
    )
    parser.add_argument(
        "--skip-meta",
        action="store_true",
        help="Same as --watch-mode: skip frontmatter_to_meta.py (step 1)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="(deprecated no-op) Export is already offline by default",
    )
    args = parser.parse_args()

    skip_frontmatter = args.watch_mode or args.skip_meta

    if args.watch_mode:
        print("[export] Watch mode — frontmatter step skipped (sync already ran it)")
    if args.skip_meta:
        print("[export] --skip-meta — frontmatter step skipped")

    # Resolve course title
    title = args.title
    if not title:
        config_file = COURSE_ROOT / "zaphod.yaml"
        if config_file.is_file():
            try:
                config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
                title = config.get("title") or config.get("course_name")
            except Exception:
                pass
        if not title:
            title = COURSE_ROOT.name

    # Resolve output path
    output_path = args.output
    if not output_path:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = EXPORTS_DIR / _timestamp_filename()
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[export] Exporting course: {title}")
    print(f"[export] Output: {output_path}")

    # Step 0: initialise staging + manifest
    init_export(title, output_path)

    # Expose manifest path to all step modules via environment
    os.environ["EXPORT_MANIFEST_PATH"] = str(MANIFEST_PATH)

    # Step 1: frontmatter processing (skipped in watch/skip-meta mode)
    if not skip_frontmatter:
        print("\n[export] → step: frontmatter")
        _run_frontmatter_step()

    # Steps 2–8: export steps
    _run_export_steps()

    print(f"\n[export] {SUCCESS} {output_path}")

    if args.watch_mode:
        print("[export] Watch mode export complete")
        print("[export] Ready for next sync cycle")


if __name__ == "__main__":
    main()
