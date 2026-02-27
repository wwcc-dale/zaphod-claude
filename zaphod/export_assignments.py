#!/usr/bin/env python3
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

"""
export_assignments.py — Step 3: Export assignments to web_resources/{id}/.

Reads:  .assignment/meta.json   + .assignment/source.md
        .assignment/rubric.yaml  (optional; shared rubrics from rubrics/ dir)

Writes: web_resources/{id}/content.html
        web_resources/{id}/assignment_settings.xml
        web_resources/{id}/rubric.xml  (if rubric present)

Updates EXPORT_MANIFEST_PATH with one resource per assignment.

Standalone:
    python -m zaphod.export_assignments
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import markdown
import yaml

from zaphod.export_types import (
    ExportManifest,
    ExportResource,
    generate_content_id,
    prettify_xml,
    add_text_element,
)

COURSE_ROOT = Path.cwd()
METADATA_DIR = COURSE_ROOT / "_course_metadata"
EXPORTS_DIR = METADATA_DIR / "exports"
DEFAULT_MANIFEST_PATH = EXPORTS_DIR / ".export_manifest.json"
RUBRICS_DIR = COURSE_ROOT / "rubrics"

XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def get_content_dir() -> Path:
    content_dir = COURSE_ROOT / "content"
    pages_dir = COURSE_ROOT / "pages"
    return content_dir if content_dir.exists() else pages_dir


def get_manifest_path() -> Path:
    env_path = os.environ.get("EXPORT_MANIFEST_PATH")
    return Path(env_path) if env_path else DEFAULT_MANIFEST_PATH


# ============================================================================
# Rubric loading
# ============================================================================

def load_rubric(folder: Path) -> Optional[Dict[str, Any]]:
    """Load rubric from an assignment folder (inline or shared reference)."""
    for filename in ["rubric.yaml", "rubric.yml", "rubric.json"]:
        rubric_path = folder / filename
        if rubric_path.is_file():
            try:
                if filename.endswith(".json"):
                    return json.loads(rubric_path.read_text(encoding="utf-8"))
                data = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("use_rubric"):
                    return load_shared_rubric(data["use_rubric"])
                return data
            except Exception as e:
                print(f"[export:assignments:warn] Failed to load rubric {rubric_path}: {e}")
    return None


def load_shared_rubric(name: str) -> Optional[Dict[str, Any]]:
    """Load a shared rubric from rubrics/ directory."""
    for ext in [".yaml", ".yml", ".json"]:
        path = RUBRICS_DIR / f"{name}{ext}"
        if path.is_file():
            try:
                if ext == ".json":
                    return json.loads(path.read_text(encoding="utf-8"))
                return yaml.safe_load(path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[export:assignments:warn] Failed to load shared rubric {path}: {e}")
    return None


# ============================================================================
# HTML generation
# ============================================================================

def generate_content_html(title: str, source_html: str) -> str:
    """Generate content.html for an assignment folder."""
    return (
        "<html>\n"
        "<head>\n"
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>\n'
        f"<title>{html.escape(title)}</title>\n"
        "</head>\n"
        "<body>\n"
        f"{source_html}\n"
        "</body>\n"
        "</html>\n"
    )


# ============================================================================
# Assignment settings XML
# ============================================================================

def generate_assignment_settings_xml(identifier: str, title: str,
                                     meta: Dict[str, Any],
                                     has_rubric: bool) -> str:
    """
    Generate assignment_settings.xml for Common Cartridge (Canvas CE format).

    Mirrors the format Canvas produces on export. The description/body lives in
    content.html; this file carries only the settings metadata.
    """
    root = ET.Element("assignment")
    root.set("xmlns", "http://canvas.instructure.com/xsd/cccv1p0")
    root.set("xmlns:xsi", XSI_NS)
    root.set("xsi:schemaLocation",
             "http://canvas.instructure.com/xsd/cccv1p0 "
             "https://canvas.instructure.com/xsd/cccv1p0.xsd")
    root.set("identifier", identifier)

    add_text_element(root, "title", title)
    add_text_element(root, "due_at", meta.get("due_at", "") or "")
    add_text_element(root, "lock_at", meta.get("lock_at", "") or "")
    add_text_element(root, "unlock_at", meta.get("unlock_at", "") or "")
    add_text_element(root, "module_locked", "false")
    add_text_element(root, "workflow_state",
                     "published" if meta.get("published") else "unpublished")
    ET.SubElement(root, "assignment_overrides")

    exts = meta.get("allowed_extensions", "")
    if isinstance(exts, list):
        exts = ",".join(exts)
    add_text_element(root, "allowed_extensions", str(exts) if exts else "")

    add_text_element(root, "has_group_category", "false")
    add_text_element(root, "points_possible", str(meta.get("points_possible", 0)))
    add_text_element(root, "grading_type", meta.get("grading_type", "points"))
    add_text_element(root, "all_day", "false")

    sub_types = meta.get("submission_types", "online_upload")
    if isinstance(sub_types, list):
        sub_types = ",".join(sub_types)
    add_text_element(root, "submission_types", str(sub_types))

    add_text_element(root, "position", str(meta.get("position", 1)))
    add_text_element(root, "turnitin_enabled", "false")
    add_text_element(root, "vericite_enabled", "false")
    add_text_element(root, "peer_review_count", "0")
    add_text_element(root, "peer_reviews", "false")
    add_text_element(root, "automatic_peer_reviews", "false")
    add_text_element(root, "anonymous_peer_reviews", "false")
    add_text_element(root, "grade_group_students_individually", "false")
    add_text_element(root, "freeze_on_copy", "false")
    add_text_element(root, "omit_from_final_grade", "false")
    add_text_element(root, "hide_in_gradebook", "false")
    add_text_element(root, "intra_group_peer_reviews", "false")
    add_text_element(root, "only_visible_to_overrides", "false")

    if has_rubric:
        ET.SubElement(root, "rubric_identifierref").text = f"{identifier}_rubric"

    return prettify_xml(root)


# ============================================================================
# Rubric XML
# ============================================================================

def generate_rubric_xml(rubric: Dict[str, Any], assignment_id: str) -> str:
    """Generate rubric.xml for Common Cartridge (Canvas extension)."""
    root = ET.Element("rubric")
    root.set("xmlns", "http://canvas.instructure.com/xsd/rubric")
    root.set("identifier", f"{assignment_id}_rubric")

    add_text_element(root, "title", rubric.get("title", "Rubric"))
    add_text_element(root, "description", rubric.get("description", ""))
    add_text_element(root, "free_form_criterion_comments",
                     str(rubric.get("free_form_criterion_comments", False)).lower())

    criteria_elem = ET.SubElement(root, "criteria")

    for i, criterion in enumerate(rubric.get("criteria", [])):
        if isinstance(criterion, str):
            continue  # Skip shared-row template references

        crit_elem = ET.SubElement(criteria_elem, "criterion")
        crit_elem.set("id", f"criterion_{i}")

        add_text_element(crit_elem, "description", criterion.get("description", ""))
        add_text_element(crit_elem, "long_description",
                         criterion.get("long_description", ""))
        add_text_element(crit_elem, "points", str(criterion.get("points", 0)))

        # Outcome alignment: emit one <learning_outcome_foreign_guid> per vendor_guid
        # 'outcomes' list (new) or 'outcome_code' scalar (legacy)
        outcome_guids: list = list(criterion.get("outcomes") or [])
        if not outcome_guids and criterion.get("outcome_code"):
            outcome_guids = [str(criterion["outcome_code"])]
        for guid in outcome_guids:
            add_text_element(crit_elem, "learning_outcome_foreign_guid", str(guid))

        ratings_elem = ET.SubElement(crit_elem, "ratings")
        for j, rating in enumerate(criterion.get("ratings", [])):
            rating_elem = ET.SubElement(ratings_elem, "rating")
            rating_elem.set("id", f"rating_{i}_{j}")
            add_text_element(rating_elem, "description", rating.get("description", ""))
            add_text_element(rating_elem, "long_description",
                             rating.get("long_description", ""))
            add_text_element(rating_elem, "points", str(rating.get("points", 0)))

    return prettify_xml(root)


# ============================================================================
# Main step logic
# ============================================================================

def export_assignments(manifest: ExportManifest) -> None:
    """Export all assignments to web_resources/{id}/ in staging."""
    staging_dir = manifest.staging_dir
    web_dir = staging_dir / "web_resources"
    web_dir.mkdir(parents=True, exist_ok=True)

    content_dir = get_content_dir()
    if not content_dir.exists():
        print("[export:assignments] No content directory found, skipping")
        return

    count = 0
    for folder in sorted(content_dir.rglob("*.assignment")):
        if not folder.is_dir():
            continue

        meta_path = folder / "meta.json"
        if not meta_path.is_file():
            print(f"[export:assignments:warn] No meta.json in {folder.name}, skipping")
            continue

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[export:assignments:warn] Failed to load {meta_path}: {e}")
            continue

        title = meta.get("name") or meta.get("title")
        if not title:
            print(f"[export:assignments:warn] No name in {folder.name}, skipping")
            continue

        identifier = generate_content_id(folder, COURSE_ROOT)

        source_content = ""
        source_path = folder / "source.md"
        if source_path.is_file():
            source_content = source_path.read_text(encoding="utf-8")

        source_html = markdown.markdown(source_content, extensions=["extra", "codehilite"])
        rubric = load_rubric(folder)

        item_dir = web_dir / identifier
        item_dir.mkdir(parents=True, exist_ok=True)

        (item_dir / "content.html").write_text(
            generate_content_html(title, source_html), encoding="utf-8"
        )
        (item_dir / "assignment_settings.xml").write_text(
            generate_assignment_settings_xml(identifier, title, meta, rubric is not None),
            encoding="utf-8",
        )

        files: List[str] = [
            f"web_resources/{identifier}/content.html",
            f"web_resources/{identifier}/assignment_settings.xml",
        ]

        if rubric:
            (item_dir / "rubric.xml").write_text(
                generate_rubric_xml(rubric, identifier), encoding="utf-8"
            )
            files.append(f"web_resources/{identifier}/rubric.xml")

        manifest.append_resource(ExportResource(
            identifier=identifier,
            type="associatedcontent/imscc_xmlv1p1/learning-application-resource",
            href=f"web_resources/{identifier}/content.html",
            files=files,
        ))
        count += 1
        print(f"[export:assignments] {title}")

    print(f"[export:assignments] Done — {count} assignments exported")


def main() -> None:
    manifest_path = get_manifest_path()
    if not manifest_path.is_file():
        print(f"[export:assignments] ERROR: manifest not found at {manifest_path}")
        print("[export:assignments] Run 'zaphod export' first to initialise the export.")
        raise SystemExit(1)

    manifest = ExportManifest.load(manifest_path)
    export_assignments(manifest)
    manifest.save(manifest_path)


if __name__ == "__main__":
    main()
