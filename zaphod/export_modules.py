#!/usr/bin/env python3
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

"""
export_modules.py — Step 5: Build module structure and write module_meta.xml.

Reads:  {content_dir}/**/meta.json   (for title, modules:, position:)
        modules/module_order.yaml    (explicit module ordering)
        EXPORT_MANIFEST_PATH         (already-exported resource identifiers)

Writes: course_settings/module_meta.xml  (Canvas-specific module extension)

Updates manifest:
  - org_items: module → children list (for imsmanifest.xml org section)
  - settings_resource_files: adds "course_settings/module_meta.xml"

Canvas requirements:
  module_meta.xml carries a <content_type> per item so Canvas creates the
  right object type on import (WikiPage, Assignment, Quizzes::Quiz, etc.).
  Without it Canvas imports everything as wiki pages.

Standalone:
    python -m zaphod.export_modules
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

import yaml

from zaphod.export_types import (
    ExportManifest,
    ExportOrgChild,
    ExportOrgItem,
    generate_content_id,
    prettify_xml,
)
from zaphod.frontmatter_to_meta import infer_module_from_path

COURSE_ROOT = Path.cwd()
METADATA_DIR = COURSE_ROOT / "_course_metadata"
EXPORTS_DIR = METADATA_DIR / "exports"
DEFAULT_MANIFEST_PATH = EXPORTS_DIR / ".export_manifest.json"
MODULES_DIR = COURSE_ROOT / "modules"

CANVAS_NS = "http://canvas.instructure.com/xsd/cccv1p0"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

# Mapping from folder extension to Canvas content_type in module_meta.xml
CANVAS_CONTENT_TYPE: Dict[str, str] = {
    "page": "WikiPage",
    "assignment": "Assignment",
    "link": "ExternalUrl",
    "file": "Attachment",
    "quiz": "Quizzes::Quiz",
}


def get_content_dir() -> Path:
    content_dir = COURSE_ROOT / "content"
    pages_dir = COURSE_ROOT / "pages"
    return content_dir if content_dir.exists() else pages_dir


def get_manifest_path() -> Path:
    env_path = os.environ.get("EXPORT_MANIFEST_PATH")
    return Path(env_path) if env_path else DEFAULT_MANIFEST_PATH


# ============================================================================
# Sorting
# ============================================================================

def _item_sort_key(folder_path: Path, meta: Dict[str, Any]) -> Tuple:
    """
    Sort key for items within a module.

    Priority (mirrors sync_modules.py):
    1. position: frontmatter key
    2. Numeric folder prefix (01-, 02-, etc.)
    3. Alphabetical by folder name
    """
    pos = meta.get("position")
    if pos is not None:
        try:
            return (0, float(pos), folder_path.name)
        except (TypeError, ValueError):
            pass

    folder_name = folder_path.name
    m = re.match(r"^(\d+)[_-]", folder_name)
    if m:
        return (1, float(m.group(1)), folder_name)

    return (2, 0.0, folder_name)


# ============================================================================
# Module order loading
# ============================================================================

def load_module_order(content_dir: Path) -> List[str]:
    """
    Load module order from module_order.yaml or infer from .module/ folders.

    Returns a list of module names in display order.
    """
    order_file = MODULES_DIR / "module_order.yaml"
    if order_file.is_file():
        try:
            data = yaml.safe_load(order_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data.get("modules", [])
            if isinstance(data, list):
                return data
        except Exception:
            pass

    # Fallback: discover from .module folder names (sorted alphabetically,
    # which preserves numeric prefix ordering 00-, 01-, etc.)
    module_order = []
    for folder in sorted(content_dir.glob("*.module")):
        raw_name = folder.name[:-7]  # strip ".module"
        if len(raw_name) >= 3 and raw_name[:2].isdigit() and raw_name[2] == "-":
            raw_name = raw_name[3:]
        module_order.append(raw_name.strip())

    return module_order


# ============================================================================
# Content + quiz scanning
# ============================================================================

def _scan_content_items(
    content_dir: Path,
) -> List[Tuple[str, str, str, Path, Dict[str, Any]]]:
    """
    Scan content dir for all non-quiz items.

    Returns list of (identifier, title, item_type, folder_path, meta) tuples.
    """
    results = []
    for ext in [".page", ".assignment", ".link", ".file"]:
        item_type = ext[1:]
        for folder in sorted(content_dir.rglob(f"*{ext}")):
            if not folder.is_dir():
                continue

            meta_path = folder / "meta.json"
            if not meta_path.is_file():
                continue

            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            title = meta.get("name") or meta.get("title") or folder.name
            identifier = generate_content_id(folder, COURSE_ROOT)
            results.append((identifier, title, item_type, folder, meta))

    return results


def _scan_quizzes(
    content_dir: Path,
) -> List[Tuple[str, str, Path, Dict[str, Any]]]:
    """
    Scan content dir for .quiz/ folders.

    Returns list of (identifier, title, folder_path, meta) tuples.
    """
    results = []
    for quiz_folder in sorted(content_dir.rglob("*.quiz")):
        if not quiz_folder.is_dir():
            continue

        meta_path = quiz_folder / "meta.json"
        if not meta_path.is_file():
            continue

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        title = meta.get("name") or meta.get("title")
        if not title:
            title = quiz_folder.stem.replace(".quiz", "").replace("-", " ").strip()

        identifier = generate_content_id(quiz_folder, COURSE_ROOT)
        results.append((identifier, title, quiz_folder, meta))

    return results


# ============================================================================
# Module structure builder
# ============================================================================

def build_module_structure(
    content_dir: Path,
) -> Tuple[List[ExportOrgItem], Dict[str, Dict]]:
    """
    Build the module structure from content items and quizzes.

    Returns:
      (org_items, id_info_map)

    id_info_map maps resource identifier → {content_type, title, published,
    url, new_tab} for use in module_meta.xml generation.
    """
    module_order = load_module_order(content_dir)

    # Create module objects in declared order (position = index in order list)
    module_map: Dict[str, ExportOrgItem] = {}
    for i, name in enumerate(module_order):
        if name not in module_map:
            module_map[name] = ExportOrgItem(
                identifier=generate_content_id(
                    COURSE_ROOT / "modules" / f"module_{i}", COURSE_ROOT
                ),
                title=name,
                position=i + 1,
            )

    # Collect all items grouped by module, with sort key
    module_entries: Dict[str, list] = defaultdict(list)
    id_info: Dict[str, Dict] = {}

    # Non-quiz content
    for identifier, title, item_type, folder, meta in _scan_content_items(content_dir):
        # Module membership: frontmatter first, then inferred from folder structure
        modules: List[str] = meta.get("modules", [])
        if not modules:
            inferred = infer_module_from_path(folder)
            if inferred:
                modules = [inferred]

        indent = int(meta.get("indent", 0))
        for module_name in modules:
            key = _item_sort_key(folder, meta)
            module_entries[module_name].append((key, identifier, title, indent))

        id_info[identifier] = {
            "content_type": CANVAS_CONTENT_TYPE.get(item_type, "WikiPage"),
            "title": title,
            "published": meta.get("published", True),
            "url": meta.get("external_url", "") if item_type == "link" else "",
            "new_tab": str(meta.get("new_tab", False)).lower(),
        }

    # Quizzes
    for identifier, title, quiz_folder, meta in _scan_quizzes(content_dir):
        module_name = infer_module_from_path(quiz_folder)
        # Also check frontmatter modules list
        fm_modules: List[str] = meta.get("modules", [])
        all_modules = fm_modules if fm_modules else ([module_name] if module_name else [])

        indent = int(meta.get("indent", 0))
        for m_name in all_modules:
            key = _item_sort_key(quiz_folder, meta)
            module_entries[m_name].append((key, identifier, title, indent))

        id_info[identifier] = {
            "content_type": "Quizzes::Quiz",
            "title": title,
            "published": meta.get("published", False),
            "url": "",
            "new_tab": "false",
        }

    # Populate modules (create new entries for modules not in module_order)
    position = len(module_order) + 1
    for module_name, entries in module_entries.items():
        if module_name not in module_map:
            module_map[module_name] = ExportOrgItem(
                identifier=generate_content_id(
                    COURSE_ROOT / "modules" / f"module_{position}", COURSE_ROOT
                ),
                title=module_name,
                position=position,
            )
            position += 1

        # Sort items within the module
        entries.sort(key=lambda e: e[0])
        for _, identifier, title, indent in entries:
            module_map[module_name].children.append(ExportOrgChild(
                identifier=f"item_{identifier}",
                identifierref=identifier,
                title=title,
                indent=indent,
            ))

    org_items = sorted(module_map.values(), key=lambda m: m.position)
    return org_items, id_info


# ============================================================================
# module_meta.xml generation
# ============================================================================

def generate_module_meta_xml(org_items: List[ExportOrgItem],
                              id_info: Dict[str, Dict]) -> str:
    """
    Generate course_settings/module_meta.xml — Canvas-specific extension.

    Each <item> must carry a <content_type> so Canvas creates the right object
    (WikiPage, Assignment, Quizzes::Quiz, etc.) on import.
    """
    root = ET.Element("modules")
    root.set("xmlns", CANVAS_NS)
    root.set("xmlns:xsi", XSI_NS)
    root.set("xsi:schemaLocation",
             f"{CANVAS_NS} https://canvas.instructure.com/xsd/cccv1p0.xsd")

    for org_item in org_items:
        mod_elem = ET.SubElement(root, "module")
        mod_elem.set("identifier", org_item.identifier)

        ET.SubElement(mod_elem, "title").text = org_item.title
        ET.SubElement(mod_elem, "workflow_state").text = "active"
        ET.SubElement(mod_elem, "position").text = str(org_item.position)
        ET.SubElement(mod_elem, "locked").text = "false"

        items_elem = ET.SubElement(mod_elem, "items")
        for item_pos, child in enumerate(org_item.children, start=1):
            info = id_info.get(child.identifierref)
            if not info:
                continue

            item_elem = ET.SubElement(items_elem, "item")
            item_elem.set("identifier", child.identifier)

            ET.SubElement(item_elem, "content_type").text = info["content_type"]
            ET.SubElement(item_elem, "workflow_state").text = (
                "active" if info["published"] else "unpublished"
            )
            ET.SubElement(item_elem, "title").text = info["title"]
            ET.SubElement(item_elem, "identifierref").text = child.identifierref
            if info["url"]:
                ET.SubElement(item_elem, "url").text = info["url"]
            ET.SubElement(item_elem, "position").text = str(item_pos)
            ET.SubElement(item_elem, "new_tab").text = info.get("new_tab", "false")
            ET.SubElement(item_elem, "indent").text = str(child.indent)
            ET.SubElement(item_elem, "link_settings_json").text = "null"

    return prettify_xml(root)


# ============================================================================
# Main step logic
# ============================================================================

def export_modules(manifest: ExportManifest) -> None:
    """Build module structure and write module_meta.xml to staging."""
    staging_dir = manifest.staging_dir
    cs_dir = staging_dir / "course_settings"
    cs_dir.mkdir(parents=True, exist_ok=True)

    content_dir = get_content_dir()
    if not content_dir.exists():
        print("[export:modules] No content directory found, skipping")
        return

    org_items, id_info = build_module_structure(content_dir)

    # Write module_meta.xml
    module_meta_xml = generate_module_meta_xml(org_items, id_info)
    (cs_dir / "module_meta.xml").write_text(module_meta_xml, encoding="utf-8")
    print(f"[export:modules] module_meta.xml — {len(org_items)} modules")

    # Append org_items to manifest (for imsmanifest.xml org section)
    for org_item in org_items:
        manifest.append_org_item(org_item)

    # Register module_meta.xml in settings resource files
    if "course_settings/module_meta.xml" not in manifest.settings_resource_files:
        manifest.settings_resource_files.append("course_settings/module_meta.xml")

    print(f"[export:modules] Done — {len(org_items)} modules exported")


def main() -> None:
    manifest_path = get_manifest_path()
    if not manifest_path.is_file():
        print(f"[export:modules] ERROR: manifest not found at {manifest_path}")
        print("[export:modules] Run 'zaphod export' first to initialise the export.")
        raise SystemExit(1)

    manifest = ExportManifest.load(manifest_path)
    export_modules(manifest)
    manifest.save(manifest_path)


if __name__ == "__main__":
    main()
