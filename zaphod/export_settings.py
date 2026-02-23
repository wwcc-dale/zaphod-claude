#!/usr/bin/env python3
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

"""
export_settings.py — Step 6: Write Canvas CE settings files.

Reads:  EXPORT_MANIFEST_PATH (for course identifier + title)

Writes: course_settings/canvas_export.txt      (CE trigger file)
        course_settings/course_settings.xml    (CE course metadata)
        course_settings/assignment_groups.xml  (default assignment group)

Updates manifest.settings_resource_files with the three files above.

Why these files matter:
  - canvas_export.txt   — triggers Canvas CE import mode (vs generic CC)
  - course_settings.xml — required for CE importer to process pages + quizzes;
                          without it only assignments import
  - assignment_groups.xml — required for Canvas CE import

Standalone:
    python -m zaphod.export_settings
"""

from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree as ET

from zaphod.export_types import (
    ExportManifest,
    prettify_xml,
)

COURSE_ROOT = Path.cwd()
METADATA_DIR = COURSE_ROOT / "_course_metadata"
EXPORTS_DIR = METADATA_DIR / "exports"
DEFAULT_MANIFEST_PATH = EXPORTS_DIR / ".export_manifest.json"

CANVAS_NS = "http://canvas.instructure.com/xsd/cccv1p0"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def get_manifest_path() -> Path:
    env_path = os.environ.get("EXPORT_MANIFEST_PATH")
    return Path(env_path) if env_path else DEFAULT_MANIFEST_PATH


# ============================================================================
# Settings XML generators
# ============================================================================

def generate_course_settings_xml(identifier: str, title: str) -> str:
    """
    Generate course_settings/course_settings.xml.

    Canvas CE importer requires this file to recognise the package as a Canvas
    export and activate its full import path (pages, quizzes, assignments).
    Without it CE mode silently skips most content types.
    """
    root = ET.Element("course")
    root.set("identifier", identifier)
    root.set("xmlns", CANVAS_NS)
    root.set("xmlns:xsi", XSI_NS)
    root.set("xsi:schemaLocation",
             f"{CANVAS_NS} https://canvas.instructure.com/xsd/cccv1p0.xsd")

    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "course_code").text = title
    ET.SubElement(root, "start_at")
    ET.SubElement(root, "conclude_at")
    ET.SubElement(root, "is_public").text = "false"
    ET.SubElement(root, "allow_student_wiki_edits").text = "false"
    ET.SubElement(root, "lock_all_announcements").text = "false"
    ET.SubElement(root, "default_view").text = "modules"
    ET.SubElement(root, "workflow_state").text = "available"

    return prettify_xml(root)


def generate_assignment_groups_xml() -> str:
    """Generate a minimal course_settings/assignment_groups.xml."""
    root = ET.Element("assignmentGroups")
    root.set("xmlns", CANVAS_NS)
    root.set("xmlns:xsi", XSI_NS)
    root.set("xsi:schemaLocation",
             f"{CANVAS_NS} https://canvas.instructure.com/xsd/cccv1p0.xsd")

    group = ET.SubElement(root, "assignmentGroup")
    group.set("identifier", "default_assignment_group")
    ET.SubElement(group, "title").text = "Assignments"
    ET.SubElement(group, "position").text = "1"
    ET.SubElement(group, "group_weight").text = "0.0"

    return prettify_xml(root)


# ============================================================================
# Main step logic
# ============================================================================

def export_settings(manifest: ExportManifest) -> None:
    """Write Canvas CE settings files to staging and update manifest."""
    staging_dir = manifest.staging_dir
    cs_dir = staging_dir / "course_settings"
    cs_dir.mkdir(parents=True, exist_ok=True)

    # canvas_export.txt — content signals Canvas CE import mode
    (cs_dir / "canvas_export.txt").write_text(
        "Q: Why did the LMS cross the road?\nA: To get to the other course.\n",
        encoding="utf-8",
    )

    # course_settings.xml
    (cs_dir / "course_settings.xml").write_text(
        generate_course_settings_xml(manifest.identifier, manifest.title),
        encoding="utf-8",
    )

    # assignment_groups.xml
    (cs_dir / "assignment_groups.xml").write_text(
        generate_assignment_groups_xml(),
        encoding="utf-8",
    )

    # Register the three files written here (module_meta.xml added by export_modules)
    for fname in [
        "course_settings/canvas_export.txt",
        "course_settings/course_settings.xml",
        "course_settings/assignment_groups.xml",
    ]:
        if fname not in manifest.settings_resource_files:
            manifest.settings_resource_files.append(fname)

    print("[export:settings] course_settings/ CE files written")


def main() -> None:
    manifest_path = get_manifest_path()
    if not manifest_path.is_file():
        print(f"[export:settings] ERROR: manifest not found at {manifest_path}")
        print("[export:settings] Run 'zaphod export' first to initialise the export.")
        raise SystemExit(1)

    manifest = ExportManifest.load(manifest_path)
    export_settings(manifest)
    manifest.save(manifest_path)


if __name__ == "__main__":
    main()
