#!/usr/bin/env python3
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

"""
export_types.py

Shared dataclasses, manifest JSON I/O, and XML/ID utility functions for the
step-by-step export pipeline.

Every export step imports from here:
  - ExportManifest   — accumulated state for one run (staging dir + resource list)
  - ExportResource   — one <resource> in imsmanifest.xml
  - ExportOrgItem    — one module in the <organization> section
  - ExportOrgChild   — one leaf item within a module
  - generate_id()             — random CC resource identifier
  - generate_content_id()     — deterministic ID from folder path
  - prettify_xml()            — pretty-print an ElementTree element
  - add_text_element()        — convenience helper
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree as ET
from defusedxml import minidom  # SECURITY: Hardened against XXE attacks


# ============================================================================
# ID Utilities
# ============================================================================

def generate_id(prefix: str = "i") -> str:
    """Generate a random unique identifier for CC resources."""
    return f"{prefix}{uuid.uuid4().hex[:16]}"


def generate_content_id(path: Path, course_root: Path) -> str:
    """
    Generate a deterministic ID based on a path relative to the course root.

    Works for both folder paths (pages, assignments, quizzes) and file paths
    (legacy quiz.txt). Stable across export runs for the same content.
    """
    hash_input = str(path.relative_to(course_root))
    return f"i{hashlib.md5(hash_input.encode()).hexdigest()[:16]}"


# ============================================================================
# XML Utilities
# ============================================================================

def prettify_xml(elem: ET.Element) -> str:
    """
    Return a pretty-printed XML string for the given ElementTree element.

    SECURITY: Uses defusedxml.minidom instead of xml.dom.minidom to protect
    against XXE (XML External Entity) attacks. While the XML being parsed is
    internally generated (from ET.tostring), this provides defence-in-depth.
    """
    rough_string = ET.tostring(elem, encoding="unicode")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def add_text_element(parent: ET.Element, tag: str, text: str, **attribs) -> ET.Element:
    """Add a child element with text content to *parent*."""
    elem = ET.SubElement(parent, tag, **attribs)
    elem.text = text
    return elem


# ============================================================================
# Manifest Dataclasses
# ============================================================================

@dataclass
class ExportResource:
    """Represents one <resource> entry in the CC imsmanifest.xml."""

    identifier: str
    type: str                    # e.g. "webcontent", "imsqti_xmlv1p2/..."
    href: Optional[str]          # manifest href attribute (None for QTI resources)
    files: List[str]             # relative paths within staging dir
    dependency: Optional[str] = None  # identifierref of a companion resource

    def to_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "type": self.type,
            "href": self.href,
            "files": self.files,
            "dependency": self.dependency,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ExportResource:
        return cls(
            identifier=d["identifier"],
            type=d["type"],
            href=d.get("href"),
            files=d.get("files", []),
            dependency=d.get("dependency"),
        )


@dataclass
class ExportOrgChild:
    """A leaf item within a module in the CC <organization> section."""

    identifier: str      # "item_{identifierref}"
    identifierref: str   # points to an ExportResource.identifier
    title: str

    def to_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "identifierref": self.identifierref,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ExportOrgChild:
        return cls(
            identifier=d["identifier"],
            identifierref=d["identifierref"],
            title=d["title"],
        )


@dataclass
class ExportOrgItem:
    """A module-level item in the CC <organization> section."""

    identifier: str      # module identifier
    title: str
    position: int        # 1-based display position
    children: List[ExportOrgChild] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "title": self.title,
            "position": self.position,
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, d: dict) -> ExportOrgItem:
        return cls(
            identifier=d["identifier"],
            title=d["title"],
            position=d["position"],
            children=[ExportOrgChild.from_dict(c) for c in d.get("children", [])],
        )


@dataclass
class ExportManifest:
    """
    Accumulated state for one export run.

    Each pipeline step:
      1. Loads this from .export_manifest.json
      2. Writes its output files to staging_dir
      3. Appends resource / org_item entries
      4. Saves the manifest back

    The final assemble_cartridge step reads the fully-populated manifest to
    build imsmanifest.xml and zip the cartridge.
    """

    identifier: str              # e.g. "cc_abc123def456"
    title: str                   # course title
    staging_dir: Path            # absolute path to .staging/
    output_path: Path            # absolute path for the .imscc output file
    resources: List[ExportResource] = field(default_factory=list)
    org_items: List[ExportOrgItem] = field(default_factory=list)
    settings_resource_files: List[str] = field(default_factory=list)

    def append_resource(self, r: ExportResource) -> None:
        self.resources.append(r)

    def append_org_item(self, m: ExportOrgItem) -> None:
        self.org_items.append(m)

    def save(self, path: Path) -> None:
        """Serialize manifest to JSON at *path*."""
        data = {
            "identifier": self.identifier,
            "title": self.title,
            "staging_dir": str(self.staging_dir),
            "output_path": str(self.output_path),
            "resources": [r.to_dict() for r in self.resources],
            "org_items": [m.to_dict() for m in self.org_items],
            "settings_resource_files": self.settings_resource_files,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> ExportManifest:
        """Load manifest from JSON at *path*."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            identifier=data["identifier"],
            title=data["title"],
            staging_dir=Path(data["staging_dir"]),
            output_path=Path(data["output_path"]),
            resources=[ExportResource.from_dict(r) for r in data.get("resources", [])],
            org_items=[ExportOrgItem.from_dict(m) for m in data.get("org_items", [])],
            settings_resource_files=data.get("settings_resource_files", []),
        )
