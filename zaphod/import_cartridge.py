#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

import_cartridge.py

Import an IMS Common Cartridge 1.3 file into Zaphod's local structure.

This script extracts and converts:
- Canvas LMS exports
- Moodle exports
- Blackboard exports
- Brightspace (D2L) exports
- Sakai exports
- And other CC-compliant LMS exports

The import includes:
- Pages (web content) -> .page folders
- Assignments (with rubrics) -> .assignment folders
- Quizzes (QTI 1.2 format) -> .quiz.txt files
- Learning Outcomes -> outcomes.yaml
- Module structure -> numbered folder structure
- Media files and assets -> assets/

Usage:
    python import_cartridge.py <cartridge.imscc> [--output PATH] [--clean]

Options:
    --output    Output directory (default: current directory)
    --clean     Remove existing content before import
    --dry-run   Show what would be imported without making changes
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

# SECURITY: Use defusedxml to protect against XXE attacks
from defusedxml import ElementTree as DefusedET

import yaml
import frontmatter

from zaphod.security_utils import is_safe_path
from zaphod.icons import SUCCESS, WARNING, ERROR
from zaphod.html_to_markdown import convert_canvas_html_to_markdown


# ============================================================================
# Constants and Paths
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = Path.cwd()

# Common Cartridge namespaces
NS = {
    "imscc": "http://www.imsglobal.org/xsd/imsccv1p3/imscp_v1p1",
    "lom": "http://ltsc.ieee.org/xsd/imsccv1p3/LOM/resource",
    "lomimscc": "http://ltsc.ieee.org/xsd/imsccv1p3/LOM/manifest",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

# QTI namespaces
QTI_NS = {
    "qti": "http://www.imsglobal.org/xsd/ims_qtiasiv1p2",
    "": "http://www.imsglobal.org/xsd/ims_qtiasiv1p2",
}


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ResourceItem:
    """Represents a resource from the cartridge."""
    identifier: str
    resource_type: str
    href: str
    title: str = ""
    files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentItem:
    """Represents a content item to be imported."""
    identifier: str
    title: str
    item_type: str  # page, assignment, link, quiz
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    module_path: str = ""
    position: int = 0
    rubric: Optional[Dict[str, Any]] = None


@dataclass
class QuizItem:
    """Represents a quiz to be imported."""
    identifier: str
    title: str
    questions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    module_path: str = ""
    position: int = 0


@dataclass
class ModuleItem:
    """Represents a module/unit in the course."""
    identifier: str
    title: str
    position: int
    items: List[str] = field(default_factory=list)  # List of content identifiers


@dataclass
class QuestionBankItem:
    """Represents a question bank to be imported."""
    identifier: str
    title: str
    questions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CartridgeImport:
    """Container for all import data."""
    title: str
    content_items: List[ContentItem] = field(default_factory=list)
    quizzes: List[QuizItem] = field(default_factory=list)
    question_banks: List[QuestionBankItem] = field(default_factory=list)
    modules: List[ModuleItem] = field(default_factory=list)
    assets: Dict[str, str] = field(default_factory=dict)  # Map source -> dest
    shared_rubrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # Map rubric_name -> rubric_data


# ============================================================================
# XML Helpers
# ============================================================================

def find_ns(elem: ET.Element, tag: str, ns_map: Dict[str, str] = None) -> Optional[ET.Element]:
    """Find element with namespace handling."""
    if ns_map is None:
        ns_map = NS

    for prefix, uri in ns_map.items():
        if prefix:
            result = elem.find(f"{{{uri}}}{tag}")
        else:
            result = elem.find(tag)

        if result is not None:
            return result

    # Try without namespace
    return elem.find(tag)


def findall_ns(elem: ET.Element, tag: str, ns_map: Dict[str, str] = None) -> List[ET.Element]:
    """Find all elements with namespace handling."""
    if ns_map is None:
        ns_map = NS

    results = []
    for prefix, uri in ns_map.items():
        if prefix:
            results.extend(elem.findall(f"{{{uri}}}{tag}"))
        else:
            results.extend(elem.findall(tag))

    # Try without namespace
    results.extend(elem.findall(tag))

    # Remove duplicates
    seen = set()
    unique = []
    for r in results:
        elem_id = id(r)
        if elem_id not in seen:
            seen.add(elem_id)
            unique.append(r)

    return unique


def get_text(elem: Optional[ET.Element], default: str = "") -> str:
    """Safely get text from an element."""
    if elem is not None and elem.text:
        return elem.text.strip()
    return default


# ============================================================================
# Cartridge Extraction
# ============================================================================

def is_safe_member_name(member: str) -> bool:
    """
    Validate zip member name for path traversal attempts.

    SECURITY: Prevents malicious cartridges from writing outside target directory.

    Args:
        member: Zip member name to validate

    Returns:
        True if safe, False if dangerous

    Blocks:
        - Absolute paths (/, C:, etc.)
        - Parent directory references (..)
        - Dangerous characters (\\, \0, etc.)
    """
    if not member:
        return False

    # Reject absolute paths
    if member.startswith('/') or member.startswith('\\'):
        return False

    # Reject drive letters (Windows: C:, D:, etc.)
    if len(member) >= 2 and member[1] == ':':
        return False

    # Reject parent directory references in path components
    parts = member.replace('\\', '/').split('/')
    if '..' in parts:
        return False

    # Reject null bytes and other dangerous characters
    dangerous_chars = ['\0', '<', '>', '|', '?', '*']
    if any(char in member for char in dangerous_chars):
        return False

    return True


def extract_cartridge(cartridge_path: Path, output_dir: Path) -> Path:
    """
    Extract cartridge to a temporary directory.

    SECURITY:
    - Validates paths to prevent path traversal
    - Enforces size limits to prevent zip bombs
    - Checks compression ratios for suspicious files
    - Uses Python 3.12+ safe extraction when available
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="zaphod_import_"))

    # SECURITY: Size limits to prevent zip bombs and DoS
    MAX_TOTAL_SIZE = 500 * 1024 * 1024  # 500 MB total
    MAX_FILE_SIZE = 50 * 1024 * 1024    # 50 MB per file
    MAX_FILES = 10000                    # Maximum file count
    MAX_COMPRESSION_RATIO = 100          # Maximum compression ratio

    try:
        with zipfile.ZipFile(cartridge_path, 'r') as zf:
            # SECURITY: Check number of files
            if len(zf.namelist()) > MAX_FILES:
                raise RuntimeError(f"Cartridge contains too many files: {len(zf.namelist())}")

            # SECURITY: Check total uncompressed size
            total_size = sum(info.file_size for info in zf.infolist())
            if total_size > MAX_TOTAL_SIZE:
                raise RuntimeError(f"Cartridge too large: {total_size / (1024*1024):.1f} MB (max {MAX_TOTAL_SIZE / (1024*1024):.0f} MB)")

            extracted_size = 0

            # Try Python 3.12+ safe extraction first, fall back to manual validation
            use_filter = False
            try:
                # Test if filter parameter is supported
                if sys.version_info >= (3, 12):
                    # Still need to check sizes even with safe extraction
                    for member in zf.namelist():
                        info = zf.getinfo(member)

                        # SECURITY: Check individual file size
                        if info.file_size > MAX_FILE_SIZE:
                            print(f"[import:warn] {WARNING} Skipping large file: {member} ({info.file_size / (1024*1024):.1f} MB)")
                            continue

                        # SECURITY: Check compression ratio (zip bomb detection)
                        if info.file_size > 0 and info.compress_size > 0:
                            ratio = info.file_size / info.compress_size
                            if ratio > MAX_COMPRESSION_RATIO:
                                print(f"[import:warn] {WARNING} Suspicious compression: {member} ({ratio:.0f}x)")
                                continue

                        extracted_size += info.file_size
                        if extracted_size > MAX_TOTAL_SIZE:
                            raise RuntimeError("Extracted size exceeds limit during extraction")

                    # Use safe extraction with data filter (blocks dangerous paths)
                    zf.extractall(temp_dir, filter='data')
                    use_filter = True
            except TypeError:
                # filter parameter not supported, fall back to manual validation
                pass

            if not use_filter:
                # Manual validation for Python < 3.12
                for member in zf.namelist():
                    info = zf.getinfo(member)

                    # SECURITY: Check individual file size
                    if info.file_size > MAX_FILE_SIZE:
                        print(f"[import:warn] {WARNING} Skipping large file: {member} ({info.file_size / (1024*1024):.1f} MB)")
                        continue

                    # SECURITY: Check compression ratio (zip bomb detection)
                    if info.file_size > 0 and info.compress_size > 0:
                        ratio = info.file_size / info.compress_size
                        if ratio > MAX_COMPRESSION_RATIO:
                            print(f"[import:warn] {WARNING} Suspicious compression: {member} ({ratio:.0f}x)")
                            continue

                    # SECURITY: Validate member name before extraction
                    if not is_safe_member_name(member):
                        print(f"[import:warn] {WARNING} Skipping unsafe member name: {member}")
                        continue

                    # Construct and validate target path
                    member_path = (temp_dir / member).resolve()

                    # Ensure resolved path is still within temp_dir
                    try:
                        member_path.relative_to(temp_dir.resolve())
                    except ValueError:
                        print(f"[import:warn] {WARNING} Path escapes temp directory: {member}")
                        continue

                    # Extract file safely
                    zf.extract(member, temp_dir)

                    # Track cumulative size
                    extracted_size += info.file_size
                    if extracted_size > MAX_TOTAL_SIZE:
                        raise RuntimeError("Extracted size exceeds limit during extraction")

        print(f"[import] Extracted cartridge to: {temp_dir}")
        return temp_dir

    except Exception as e:
        # Cleanup on error
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise RuntimeError(f"Failed to extract cartridge: {e}")


# ============================================================================
# Manifest Parsing
# ============================================================================

def parse_manifest(temp_dir: Path) -> Tuple[ET.Element, Dict[str, ResourceItem]]:
    """
    Parse the imsmanifest.xml file.

    SECURITY: Uses defusedxml to protect against XXE attacks.
    """
    manifest_path = temp_dir / "imsmanifest.xml"

    if not manifest_path.is_file():
        raise RuntimeError("No imsmanifest.xml found in cartridge")

    try:
        # SECURITY: Use defusedxml for parsing
        tree = DefusedET.parse(manifest_path)
        root = tree.getroot()

        # Extract resources
        resources = {}
        resources_elem = find_ns(root, "resources")

        if resources_elem is not None:
            for resource_elem in findall_ns(resources_elem, "resource"):
                resource = parse_resource(resource_elem)
                if resource:
                    resources[resource.identifier] = resource

        print(f"[import] Found {len(resources)} resources in manifest")
        return root, resources

    except Exception as e:
        raise RuntimeError(f"Failed to parse manifest: {e}")


def parse_resource(resource_elem: ET.Element) -> Optional[ResourceItem]:
    """Parse a single resource element."""
    identifier = resource_elem.get("identifier", "")
    resource_type = resource_elem.get("type", "")
    href = resource_elem.get("href", "")

    if not identifier:
        return None

    # Collect file references
    files = []
    for file_elem in findall_ns(resource_elem, "file"):
        file_href = file_elem.get("href", "")
        if file_href:
            files.append(file_href)

    return ResourceItem(
        identifier=identifier,
        resource_type=resource_type,
        href=href,
        files=files,
    )


# ============================================================================
# Module Structure Parsing
# ============================================================================

def parse_modules(manifest_root: ET.Element) -> List[ModuleItem]:
    """Parse module structure from organization element."""
    modules = []

    organizations_elem = find_ns(manifest_root, "organizations")
    if organizations_elem is None:
        return modules

    organization_elem = find_ns(organizations_elem, "organization")
    if organization_elem is None:
        return modules

    position = 0
    for item_elem in findall_ns(organization_elem, "item"):
        module = parse_module_item(item_elem, position)
        if module:
            modules.append(module)
            position += 1

    print(f"[import] Found {len(modules)} modules")
    return modules


def parse_module_item(item_elem: ET.Element, position: int) -> Optional[ModuleItem]:
    """Parse a single module item."""
    identifier = item_elem.get("identifier", "")
    identifierref = item_elem.get("identifierref", "")

    if not identifier:
        return None

    title_elem = find_ns(item_elem, "title")
    title = get_text(title_elem, identifier)

    # Collect sub-items (content references)
    items = []
    for sub_item in findall_ns(item_elem, "item"):
        sub_ref = sub_item.get("identifierref", "")
        if sub_ref:
            items.append(sub_ref)

    return ModuleItem(
        identifier=identifier,
        title=title,
        position=position,
        items=items,
    )


# ============================================================================
# Content Processing
# ============================================================================

def process_resources(
    resources: Dict[str, ResourceItem],
    modules: List[ModuleItem],
    temp_dir: Path,
) -> CartridgeImport:
    """Process all resources and convert to Zaphod format."""
    cartridge = CartridgeImport(title="Imported Course")

    # Build module lookup
    module_lookup = {}
    for module in modules:
        for item_id in module.items:
            module_lookup[item_id] = module

    # Process each resource
    for identifier, resource in resources.items():
        module = module_lookup.get(identifier)
        module_path = ""
        position = 0

        if module:
            module_path = sanitize_filename(module.title)
            position = module.items.index(identifier)

        # Determine resource type and process accordingly
        if is_page_resource(resource):
            item = process_page(resource, temp_dir, module_path, position)
            if item:
                cartridge.content_items.append(item)

        elif is_assignment_resource(resource):
            item = process_assignment(resource, temp_dir, module_path, position)
            if item:
                cartridge.content_items.append(item)

        elif is_quiz_resource(resource):
            quiz, bank = process_quiz(resource, temp_dir, module_path, position)
            if quiz:
                cartridge.quizzes.append(quiz)
            if bank:
                cartridge.question_banks.append(bank)

        elif is_link_resource(resource):
            item = process_link(resource, module_path, position)
            if item:
                cartridge.content_items.append(item)

        elif is_asset_resource(resource):
            # Track assets for copying
            for file_path in resource.files:
                src_path = temp_dir / file_path
                if src_path.is_file():
                    # Remove web_resources/assets/ prefix if present
                    dest_path = file_path.replace("web_resources/assets/", "")
                    cartridge.assets[str(src_path)] = dest_path

    cartridge.modules = modules

    print(f"[import] Processed {len(cartridge.content_items)} content items")
    print(f"[import] Processed {len(cartridge.quizzes)} quizzes")
    print(f"[import] Tracked {len(cartridge.assets)} asset files")

    return cartridge


def is_page_resource(resource: ResourceItem) -> bool:
    """Check if resource is a page/webcontent."""
    return "webcontent" in resource.resource_type.lower()


def is_assignment_resource(resource: ResourceItem) -> bool:
    """Check if resource is an assignment."""
    # Check resource type
    if "assignment" in resource.resource_type.lower():
        return True
    if "learning-application-resource" in resource.resource_type.lower():
        return True
    # Check if has assignment.xml file
    return any(f.endswith("assignment.xml") for f in resource.files)


def is_quiz_resource(resource: ResourceItem) -> bool:
    """Check if resource is a quiz/assessment."""
    return "assessment" in resource.resource_type.lower() or \
           "imsqti" in resource.resource_type.lower()


def is_link_resource(resource: ResourceItem) -> bool:
    """Check if resource is a web link."""
    return "imswl" in resource.resource_type.lower() or \
           "weblink" in resource.resource_type.lower()


def is_asset_resource(resource: ResourceItem) -> bool:
    """Check if resource is an asset file."""
    # Don't treat assignments as assets
    if is_assignment_resource(resource):
        return False
    return "associatedcontent" in resource.resource_type.lower() or \
           resource.resource_type == "webcontent"


# ============================================================================
# Page Processing
# ============================================================================

def process_page(
    resource: ResourceItem,
    temp_dir: Path,
    module_path: str,
    position: int,
) -> Optional[ContentItem]:
    """Process a page resource."""
    content_html = ""

    # Load HTML content
    if resource.href:
        content_path = temp_dir / resource.href
        if content_path.is_file():
            content_html = content_path.read_text(encoding="utf-8", errors="ignore")

    # Convert HTML to Markdown
    content_md = html_to_markdown(content_html)

    # Extract title from resource or HTML
    title = resource.title or extract_title_from_html(content_html) or resource.identifier

    return ContentItem(
        identifier=resource.identifier,
        title=title,
        item_type="page",
        content=content_md,
        module_path=module_path,
        position=position,
    )


# ============================================================================
# Assignment Processing
# ============================================================================

def process_assignment(
    resource: ResourceItem,
    temp_dir: Path,
    module_path: str,
    position: int,
) -> Optional[ContentItem]:
    """Process an assignment resource."""
    metadata = {}
    content_html = ""
    rubric = None

    # Parse assignment.xml if present
    assignment_xml_path = None
    for file_path in resource.files:
        if file_path.endswith("assignment.xml"):
            assignment_xml_path = temp_dir / file_path
            break

    if assignment_xml_path and assignment_xml_path.is_file():
        metadata = parse_assignment_xml(assignment_xml_path)

    # Load HTML content
    for file_path in resource.files:
        if file_path.endswith("content.html") or file_path.endswith(".html"):
            content_path = temp_dir / file_path
            if content_path.is_file():
                content_html = content_path.read_text(encoding="utf-8", errors="ignore")
                break

    # Parse rubric if present
    rubric_xml_path = None
    for file_path in resource.files:
        if file_path.endswith("rubric.xml"):
            rubric_xml_path = temp_dir / file_path
            break

    if rubric_xml_path and rubric_xml_path.is_file():
        rubric = parse_rubric_xml(rubric_xml_path)

    # Convert HTML to Markdown
    content_md = html_to_markdown(content_html)

    title = metadata.get("title") or resource.title or resource.identifier

    return ContentItem(
        identifier=resource.identifier,
        title=title,
        item_type="assignment",
        content=content_md,
        metadata=metadata,
        module_path=module_path,
        position=position,
        rubric=rubric,
    )


def parse_assignment_xml(xml_path: Path) -> Dict[str, Any]:
    """Parse assignment.xml file."""
    try:
        tree = DefusedET.parse(xml_path)
        root = tree.getroot()

        metadata = {}

        # Handle namespace if present
        ns = {"cc": "http://canvas.instructure.com/xsd/cccv1p0"}
        ns_prefix = "{http://canvas.instructure.com/xsd/cccv1p0}"

        # Helper to find elements with or without namespace
        def find_text(path: str) -> Optional[str]:
            # Try with namespace
            elem = root.find(f".//cc:{path}", ns)
            if elem is not None and elem.text:
                return elem.text.strip()
            # Try without namespace
            elem = root.find(f".//{path}")
            if elem is not None and elem.text:
                return elem.text.strip()
            # Try with namespace prefix directly
            elem = root.find(f".//{ns_prefix}{path}")
            if elem is not None and elem.text:
                return elem.text.strip()
            return None

        # Extract title
        title = find_text("title")
        if title:
            metadata["title"] = title

        # Extract points
        points = find_text("points_possible")
        if points:
            try:
                metadata["points_possible"] = float(points)
            except ValueError:
                pass

        # Extract submission types (handle as single element with comma-separated values)
        submission_types_text = find_text("submission_types")
        if submission_types_text:
            metadata["submission_types"] = [s.strip() for s in submission_types_text.split(",")]

        # Extract grading type
        grading_type = find_text("grading_type")
        if grading_type:
            metadata["grading_type"] = grading_type

        return metadata

    except Exception as e:
        print(f"[import:warn] Failed to parse assignment XML: {e}")
        return {}


def parse_rubric_xml(xml_path: Path) -> Optional[Dict[str, Any]]:
    """Parse rubric.xml file."""
    try:
        tree = DefusedET.parse(xml_path)
        root = tree.getroot()

        rubric = {}

        # Handle Canvas rubric namespace
        ns = {"r": "http://canvas.instructure.com/xsd/rubric"}

        # Helper to find elements with or without namespace
        def find_elem(parent, path: str):
            # Try with namespace
            elem = parent.find(f".//r:{path}", ns)
            if elem is not None:
                return elem
            # Try without namespace
            elem = parent.find(f".//{path}")
            return elem

        def find_all(parent, path: str):
            # Try with namespace
            elems = parent.findall(f".//r:{path}", ns)
            if elems:
                return elems
            # Try without namespace
            return parent.findall(f".//{path}")

        # Extract title
        title_elem = find_elem(root, "title")
        if title_elem is not None and title_elem.text:
            rubric["title"] = title_elem.text.strip()

        # Extract description
        desc_elem = find_elem(root, "description")
        if desc_elem is not None and desc_elem.text:
            rubric["description"] = desc_elem.text.strip()

        # Extract criteria
        criteria = []
        for crit_elem in find_all(root, "criterion"):
            criterion = {}

            desc = find_elem(crit_elem, "description")
            if desc is not None and desc.text:
                criterion["description"] = desc.text.strip()

            long_desc = find_elem(crit_elem, "long_description")
            if long_desc is not None and long_desc.text:
                criterion["long_description"] = long_desc.text.strip()

            points = find_elem(crit_elem, "points")
            if points is not None and points.text:
                try:
                    criterion["points"] = float(points.text)
                except ValueError:
                    pass

            # Extract ratings
            ratings = []
            for rating_elem in find_all(crit_elem, "rating"):
                rating = {}

                r_desc = find_elem(rating_elem, "description")
                if r_desc is not None and r_desc.text:
                    rating["description"] = r_desc.text.strip()

                r_points = find_elem(rating_elem, "points")
                if r_points is not None and r_points.text:
                    try:
                        rating["points"] = float(r_points.text)
                    except ValueError:
                        pass

                if rating:
                    ratings.append(rating)

            if ratings:
                criterion["ratings"] = ratings

            if criterion:
                criteria.append(criterion)

        if criteria:
            rubric["criteria"] = criteria

        return rubric if rubric else None

    except Exception as e:
        print(f"[import:warn] Failed to parse rubric XML: {e}")
        return None


# ============================================================================
# Quiz Processing
# ============================================================================

def is_question_bank(resource: ResourceItem, title: str) -> bool:
    """
    Determine if a QTI assessment is a question bank rather than a quiz.

    Heuristics:
    - Title/identifier contains 'bank', 'pool', 'item_bank'
    - Not associated with any module (standalone)
    - Resource type indicates objectbank
    """
    # Check identifier and title
    check_text = f"{resource.identifier.lower()} {title.lower()}"
    bank_keywords = ['bank', 'pool', 'item_bank', 'question_bank', 'qti_bank']

    if any(keyword in check_text for keyword in bank_keywords):
        return True

    # Check resource type
    if 'objectbank' in resource.resource_type.lower():
        return True

    return False


def process_quiz(
    resource: ResourceItem,
    temp_dir: Path,
    module_path: str,
    position: int,
) -> Tuple[Optional[QuizItem], Optional[QuestionBankItem]]:
    """
    Process a quiz/assessment resource.

    Returns tuple of (quiz, bank) where one will be None.
    """
    # Find assessment XML
    assessment_path = None
    for file_path in resource.files:
        if file_path.endswith("assessment.xml") or file_path.endswith(".xml"):
            assessment_path = temp_dir / file_path
            break

    if not assessment_path or not assessment_path.is_file():
        return None, None

    try:
        tree = DefusedET.parse(assessment_path)
        root = tree.getroot()

        # Extract quiz metadata
        assessment_elem = root.find(".//{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}assessment")
        if assessment_elem is None:
            assessment_elem = root.find(".//assessment")

        if assessment_elem is None:
            return None, None

        title = assessment_elem.get("title", resource.identifier)

        # Extract quiz metadata from qtimetadata
        metadata = {}
        qtimetadata = assessment_elem.find(".//{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}qtimetadata")
        if qtimetadata is None:
            qtimetadata = assessment_elem.find(".//qtimetadata")

        if qtimetadata is not None:
            for field in qtimetadata.findall(".//{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}qtimetadatafield"):
                if field is None:
                    for field in qtimetadata.findall(".//qtimetadatafield"):
                        label_elem = field.find("fieldlabel")
                        entry_elem = field.find("fieldentry")
                        if label_elem is not None and entry_elem is not None:
                            label = label_elem.text
                            entry = entry_elem.text
                            if label and entry:
                                metadata[label] = entry
                else:
                    label_elem = field.find("{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}fieldlabel")
                    entry_elem = field.find("{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}fieldentry")
                    if label_elem is None:
                        label_elem = field.find("fieldlabel")
                    if entry_elem is None:
                        entry_elem = field.find("fieldentry")
                    if label_elem is not None and entry_elem is not None:
                        label = label_elem.text
                        entry = entry_elem.text
                        if label and entry:
                            metadata[label] = entry

        # Extract quiz description from objectives element
        description = ""
        objectives = assessment_elem.find(".//{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}objectives")
        if objectives is None:
            objectives = assessment_elem.find(".//objectives")

        if objectives is not None:
            mattext = objectives.find(".//{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}mattext")
            if mattext is None:
                mattext = objectives.find(".//mattext")
            if mattext is not None and mattext.text:
                # Convert HTML back to markdown
                description_html = mattext.text
                description = html_to_markdown(description_html)

        # Extract questions
        questions = parse_qti_questions(root)

        # Determine if this is a question bank or a content quiz with inline questions
        is_inline_quiz = metadata.get("zaphod_inline_questions") == "True"

        if is_inline_quiz or not is_question_bank(resource, title):
            # This is a quiz in content (not a question bank)
            quiz_item = QuizItem(
                identifier=resource.identifier,
                title=title,
                questions=questions,
                metadata=metadata,
                module_path=module_path,
                position=position,
            )
            # Store description in metadata for later use
            if description:
                quiz_item.metadata['description'] = description
            return quiz_item, None
        else:
            # This is a question bank
            return None, QuestionBankItem(
                identifier=resource.identifier,
                title=title,
                questions=questions,
            )

    except Exception as e:
        print(f"[import:warn] Failed to parse quiz {resource.identifier}: {e}")
        return None, None


def parse_qti_questions(root: ET.Element) -> List[Dict[str, Any]]:
    """Parse QTI questions from assessment XML."""
    questions = []

    # Define QTI namespace
    qti_ns = {"qti": "http://www.imsglobal.org/xsd/ims_qtiasiv1p2"}

    # Find all item elements (try with namespace first, then without)
    items = root.findall(".//qti:item", qti_ns)
    if not items:
        items = root.findall(".//item")

    for idx, item in enumerate(items, 1):
        question = parse_qti_item(item, idx)
        if question:
            questions.append(question)

    return questions


def parse_qti_item(item: ET.Element, number: int) -> Optional[Dict[str, Any]]:
    """Parse a single QTI item."""
    try:
        # Define QTI namespace
        qti_ns = {"qti": "http://www.imsglobal.org/xsd/ims_qtiasiv1p2"}

        # Helper to find with or without namespace
        def find_elem(parent, path: str):
            # Try with namespace
            elem = parent.find(f".//qti:{path}", qti_ns)
            if elem is not None:
                return elem
            # Try without namespace
            return parent.find(f".//{path}")

        def find_all(parent, path: str):
            # Try with namespace
            elems = parent.findall(f".//qti:{path}", qti_ns)
            if elems:
                return elems
            # Try without namespace
            return parent.findall(f".//{path}")

        # Extract title
        title = item.get("title", f"Question {number}")

        # Extract question type from metadata
        qtype = "multiple_choice"
        qtimetadata = find_elem(item, "qtimetadata")
        if qtimetadata is not None:
            for field in find_all(qtimetadata, "qtimetadatafield"):
                label = find_elem(field, "fieldlabel")
                entry = find_elem(field, "fieldentry")

                if label is not None and entry is not None:
                    if label.text and "cc_profile" in label.text.lower():
                        if entry.text:
                            qtype = map_qti_type(entry.text)

        # Extract question text
        mattext = find_elem(item, "mattext")
        if mattext is None or not mattext.text:
            return None

        stem = strip_html_tags(mattext.text)

        # Extract points
        points = 1.0
        for field in find_all(item, "qtimetadatafield"):
            label = find_elem(field, "fieldlabel")
            entry = find_elem(field, "fieldentry")
            if label is not None and label.text and "cc_weighting" in label.text:
                if entry is not None and entry.text:
                    try:
                        points = float(entry.text)
                    except ValueError:
                        pass

        # Extract answers based on type
        answers = []
        if qtype in ["multiple_choice", "multiple_answers", "true_false"]:
            answers = parse_choice_answers(item, qti_ns)
        elif qtype == "short_answer":
            answers = parse_short_answers(item, qti_ns)

        return {
            "number": number,
            "stem": stem,
            "type": qtype,
            "answers": answers,
            "points": points,
        }

    except Exception as e:
        print(f"[import:warn] Failed to parse QTI item: {e}")
        return None


def map_qti_type(qti_type: str) -> str:
    """Map QTI question type to Zaphod type."""
    qti_lower = qti_type.lower()

    if "multiple_choice" in qti_lower:
        return "multiple_choice"
    elif "multiple_answer" in qti_lower:
        return "multiple_answers"
    elif "true_false" in qti_lower:
        return "true_false"
    elif "short_answer" in qti_lower or "fill_in" in qti_lower:
        return "short_answer"
    elif "essay" in qti_lower:
        return "essay"
    elif "file_upload" in qti_lower:
        return "file_upload"
    else:
        return "multiple_choice"


def parse_choice_answers(item: ET.Element, qti_ns: Dict[str, str]) -> List[Dict[str, Any]]:
    """Parse multiple choice/answers from QTI item."""
    answers = []

    # Helper to find with or without namespace
    def find_all(parent, path: str):
        elems = parent.findall(f".//qti:{path}", qti_ns)
        if elems:
            return elems
        return parent.findall(f".//{path}")

    def find_elem(parent, path: str):
        elem = parent.find(f".//qti:{path}", qti_ns)
        if elem is not None:
            return elem
        return parent.find(f".//{path}")

    # Find response labels
    for label in find_all(item, "response_label"):
        answer_id = label.get("ident", "")

        # Get answer text
        mattext = find_elem(label, "mattext")
        if mattext is None or not mattext.text:
            continue

        text = strip_html_tags(mattext.text)

        # Check if correct
        is_correct = is_correct_answer(item, answer_id, qti_ns)

        answers.append({
            "text": text,
            "correct": is_correct,
        })

    return answers


def is_correct_answer(item: ET.Element, answer_id: str, qti_ns: Dict[str, str]) -> bool:
    """Check if an answer is marked as correct in QTI."""
    # Helper to find with or without namespace
    def find_elem(parent, path: str):
        elem = parent.find(f".//qti:{path}", qti_ns)
        if elem is not None:
            return elem
        return parent.find(f".//{path}")

    def find_all(parent, path: str):
        elems = parent.findall(f".//qti:{path}", qti_ns)
        if elems:
            return elems
        return parent.findall(f".//{path}")

    # Find response processing
    resprocessing = find_elem(item, "resprocessing")
    if resprocessing is None:
        return False

    # Look for conditions that set score to 100 for this answer
    for respcondition in find_all(resprocessing, "respcondition"):
        varequal = find_elem(respcondition, "varequal")
        setvar = find_elem(respcondition, "setvar")

        if varequal is not None and setvar is not None:
            if varequal.text and varequal.text.strip() == answer_id:
                if setvar.text and "100" in setvar.text:
                    return True

    return False


def parse_short_answers(item: ET.Element, qti_ns: Dict[str, str]) -> List[Dict[str, Any]]:
    """Parse short answer responses from QTI item."""
    answers = []

    # Helper to find with or without namespace
    def find_elem(parent, path: str):
        elem = parent.find(f".//qti:{path}", qti_ns)
        if elem is not None:
            return elem
        return parent.find(f".//{path}")

    def find_all(parent, path: str):
        elems = parent.findall(f".//qti:{path}", qti_ns)
        if elems:
            return elems
        return parent.findall(f".//{path}")

    # Find all varequal elements in response processing
    resprocessing = find_elem(item, "resprocessing")
    if resprocessing is not None:
        for varequal in find_all(resprocessing, "varequal"):
            if varequal.text:
                text = varequal.text.strip()
                if text:
                    answers.append({
                        "text": text,
                        "correct": True,
                    })

    return answers


# ============================================================================
# Link Processing
# ============================================================================

def process_link(
    resource: ResourceItem,
    module_path: str,
    position: int,
) -> Optional[ContentItem]:
    """Process a web link resource."""
    url = resource.href

    # Also check for weblink.xml
    if not url and resource.files:
        # URL might be in metadata
        pass

    title = resource.title or url or resource.identifier

    return ContentItem(
        identifier=resource.identifier,
        title=title,
        item_type="link",
        metadata={"external_url": url},
        module_path=module_path,
        position=position,
    )


# ============================================================================
# HTML to Markdown Conversion
# ============================================================================

def html_to_markdown(html_content: str) -> str:
    """Convert HTML to Markdown using Zaphod's optimized converter."""
    if not html_content or not html_content.strip():
        return ""

    # Clean up HTML
    html_content = html_content.strip()

    # Preprocess: Convert code blocks with language hints to data attributes
    # This helps preserve language identifiers through the conversion
    html_content = preserve_code_language_hints(html_content)

    # Convert to markdown using Zaphod's html2text-based converter
    try:
        markdown_text, _ = convert_canvas_html_to_markdown(
            html_content,
            strip_template=False,  # Don't strip templates during import
            course_root=None       # No course root during import
        )

        # Post-process: Convert html2text's [code]...[/code] to fenced blocks
        markdown_text = convert_code_tags_to_fences(markdown_text)

        # Clean up extra whitespace
        markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)
        markdown_text = markdown_text.strip()

        return markdown_text

    except Exception as e:
        print(f"[import:warn] Failed to convert HTML to Markdown: {e}")
        # Return original HTML as fallback
        return html_content


def convert_code_tags_to_fences(markdown_text: str) -> str:
    """
    Convert html2text's [code]...[/code] tags to fenced code blocks.

    html2text outputs code blocks as [code]...[/code], but we want
    standard markdown fenced code blocks (```).
    """
    # Pattern to match [code]...[/code] blocks
    pattern = r'\[code\](.*?)\[/code\]'

    def replace_with_fence(match):
        code = match.group(1)
        # Remove leading/trailing whitespace but preserve internal formatting
        code = code.strip()
        return f'```\n{code}\n```'

    markdown_text = re.sub(pattern, replace_with_fence, markdown_text, flags=re.DOTALL)

    return markdown_text


def preserve_code_language_hints(html_content: str) -> str:
    """
    Preprocess HTML to preserve code block language hints.

    Converts <pre><code class="language-python"> to fenced code blocks
    before markdown conversion.
    """
    # Pattern 1: language-python (CommonMark/Canvas standard)
    pattern1 = r'<pre[^>]*>\s*<code\s+class="[^"]*language-(\w+)[^"]*"[^>]*>(.*?)</code>\s*</pre>'

    # Pattern 2: Just class="python" (alternative format)
    pattern2 = r'<pre[^>]*>\s*<code\s+class="(\w+)"[^>]*>(.*?)</code>\s*</pre>'

    # Pattern 3: Canvas codehilite format
    pattern3 = r'<div\s+class="codehilite"[^>]*>\s*<pre[^>]*><code[^>]*>(.*?)</code></pre>\s*</div>'

    def replace_code_block(match):
        if len(match.groups()) >= 2:
            language = match.group(1)
            code = match.group(2)
        else:
            language = ""
            code = match.group(1)
        # Decode HTML entities
        code = html.unescape(code)
        # Return as markdown fenced code block
        if language and language not in ['codehilite', 'highlight']:
            return f'```{language}\n{code}\n```'
        else:
            return f'```\n{code}\n```'

    # Try all patterns
    html_content = re.sub(pattern1, replace_code_block, html_content, flags=re.DOTALL)
    html_content = re.sub(pattern2, replace_code_block, html_content, flags=re.DOTALL)
    html_content = re.sub(pattern3, replace_code_block, html_content, flags=re.DOTALL)

    return html_content


def strip_html_tags(html_text: str) -> str:
    """Strip HTML tags from text."""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', html_text)
    # Decode HTML entities
    text = html.unescape(text)
    return text.strip()


def extract_title_from_html(html_content: str) -> Optional[str]:
    """Extract title from HTML content."""
    if not html_content:
        return None

    # Try to find h1 tag
    match = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.IGNORECASE | re.DOTALL)
    if match:
        return strip_html_tags(match.group(1))

    # Try title tag
    match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
    if match:
        return strip_html_tags(match.group(1))

    return None


# ============================================================================
# File System Operations
# ============================================================================

def write_content_item(item: ContentItem, output_dir: Path):
    """Write a content item to the file system."""
    # Determine folder name
    folder_name = f"{sanitize_filename(item.title)}.{item.item_type}"
    folder_path = output_dir / "content" / folder_name

    if item.module_path:
        module_folder = f"{item.position:02d}-{sanitize_filename(item.module_path)}.module"
        folder_path = output_dir / "content" / module_folder / folder_name

    folder_path.mkdir(parents=True, exist_ok=True)

    # Write index.md with frontmatter
    frontmatter_data = {
        "name": item.title,
        "type": item.item_type,
    }

    # Add metadata
    if item.metadata:
        if "points_possible" in item.metadata:
            frontmatter_data["points_possible"] = item.metadata["points_possible"]
        if "submission_types" in item.metadata:
            frontmatter_data["submission_types"] = item.metadata["submission_types"]
        if "external_url" in item.metadata:
            frontmatter_data["external_url"] = item.metadata["external_url"]

    # Create frontmatter post
    post = frontmatter.Post(item.content, **frontmatter_data)

    # Write index.md
    index_path = folder_path / "index.md"
    index_path.write_text(frontmatter.dumps(post), encoding="utf-8")

    # Write rubric if present
    if item.rubric:
        # Check if it's a reference to a shared rubric
        if "reference" in item.rubric:
            # Just store the reference in a comment
            rubric_ref = item.rubric["reference"]
            rubric_path = folder_path / "rubric.yaml"
            rubric_path.write_text(f"# Reference to shared rubric\nreference: {rubric_ref}\n", encoding="utf-8")
        else:
            # Inline rubric
            rubric_path = folder_path / "rubric.yaml"
            rubric_path.write_text(yaml.dump(item.rubric, sort_keys=False), encoding="utf-8")

    print(f"[import] Created {item.item_type}: {folder_path.name}")


def write_question_bank(bank: QuestionBankItem, output_dir: Path):
    """Write a question bank to a .bank.md file."""
    question_banks_dir = output_dir / "question-banks"
    question_banks_dir.mkdir(parents=True, exist_ok=True)

    # Generate bank file
    filename = f"{sanitize_filename(bank.title)}.bank.md"
    bank_path = question_banks_dir / filename

    # Build bank content
    lines = []

    # Header comment
    lines.append(f"# {bank.title}")
    lines.append("")
    lines.append(f"<!-- Question Bank imported from cartridge -->")
    lines.append(f"<!-- {len(bank.questions)} questions -->")
    lines.append("")

    # Questions
    for q in bank.questions:
        lines.append(f"{q['number']}. {q['stem']}")
        lines.append("")

        if q["type"] == "multiple_choice":
            for i, answer in enumerate(q.get("answers", [])):
                letter = chr(ord('a') + i)
                prefix = f"*{letter})" if answer.get("correct") else f"{letter})"
                lines.append(f"{prefix} {answer['text']}")
            lines.append("")

        elif q["type"] == "multiple_answers":
            for answer in q.get("answers", []):
                checkbox = "[*]" if answer.get("correct") else "[ ]"
                lines.append(f"{checkbox} {answer['text']}")
            lines.append("")

        elif q["type"] == "true_false":
            lines.append("*a) True" if q.get("answers", [{}])[0].get("correct") else "a) True")
            lines.append("*b) False" if len(q.get("answers", [])) > 1 and q["answers"][1].get("correct") else "b) False")
            lines.append("")

        elif q["type"] == "short_answer":
            for answer in q.get("answers", []):
                lines.append(f"* {answer['text']}")
            lines.append("")

        elif q["type"] == "essay":
            lines.append("####")
            lines.append("")

        elif q["type"] == "file_upload":
            lines.append("^^^^")
            lines.append("")

    bank_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[import] Created question bank: {filename} ({len(bank.questions)} questions)")


def write_quiz(quiz: QuizItem, output_dir: Path):
    """Write a quiz to the file system."""
    # Check if this is an inline quiz (should go in content/) or a question bank
    is_inline = quiz.metadata.get("zaphod_inline_questions") == "True"

    if is_inline:
        # Write as .quiz/ folder in content directory
        content_dir = output_dir / "content"

        # Determine module path
        if quiz.module_path:
            module_dir = content_dir / quiz.module_path
        else:
            module_dir = content_dir / f"{str(quiz.position).zfill(2)}-module.module"

        module_dir.mkdir(parents=True, exist_ok=True)

        # Create quiz folder
        quiz_folder_name = f"{sanitize_filename(quiz.title)}.quiz"
        quiz_folder = module_dir / quiz_folder_name
        quiz_folder.mkdir(parents=True, exist_ok=True)
        quiz_path = quiz_folder / "index.md"
    else:
        # Write as .quiz.txt file in question-banks
        question_banks_dir = output_dir / "question-banks"
        question_banks_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{sanitize_filename(quiz.title)}.quiz.txt"
        quiz_path = question_banks_dir / filename

    # Build quiz content
    lines = []

    # Frontmatter with all metadata
    lines.append("---")
    lines.append(f"name: {quiz.title}")

    # Add Zaphod-specific metadata if present
    if quiz.metadata.get("zaphod_points_possible"):
        lines.append(f"points_possible: {quiz.metadata['zaphod_points_possible']}")
    if quiz.metadata.get("qmd_timelimit"):
        lines.append(f"time_limit: {quiz.metadata['qmd_timelimit']}")
    if quiz.metadata.get("zaphod_quiz_type"):
        lines.append(f"quiz_type: {quiz.metadata['zaphod_quiz_type']}")
    if quiz.metadata.get("zaphod_allowed_attempts"):
        lines.append(f"allowed_attempts: {quiz.metadata['zaphod_allowed_attempts']}")
    if quiz.metadata.get("zaphod_shuffle_answers"):
        lines.append(f"shuffle_answers: {quiz.metadata['zaphod_shuffle_answers']}")
    if quiz.metadata.get("zaphod_published"):
        lines.append(f"published: {quiz.metadata['zaphod_published']}")
    if is_inline:
        lines.append(f"inline_questions: true")

    # Default points_per_question for question banks
    if not is_inline:
        lines.append("points_per_question: 1.0")

    lines.append("---")
    lines.append("")

    # Add description if present
    if quiz.metadata.get("description"):
        lines.append(quiz.metadata["description"])
        lines.append("")

    # Questions
    for q in quiz.questions:
        lines.append(f"{q['number']}. {q['stem']}")
        lines.append("")

        if q["type"] == "multiple_choice":
            for i, answer in enumerate(q.get("answers", [])):
                letter = chr(ord('a') + i)
                prefix = f"*{letter})" if answer.get("correct") else f"{letter})"
                lines.append(f"{prefix} {answer['text']}")
            lines.append("")

        elif q["type"] == "multiple_answers":
            for answer in q.get("answers", []):
                checkbox = "[*]" if answer.get("correct") else "[ ]"
                lines.append(f"{checkbox} {answer['text']}")
            lines.append("")

        elif q["type"] == "true_false":
            lines.append("*a) True" if q["answers"][0].get("correct") else "a) True")
            lines.append("*b) False" if q["answers"][1].get("correct") else "b) False")
            lines.append("")

        elif q["type"] == "short_answer":
            for answer in q.get("answers", []):
                lines.append(f"* {answer['text']}")
            lines.append("")

        elif q["type"] == "essay":
            lines.append("####")
            lines.append("")

        elif q["type"] == "file_upload":
            lines.append("^^^^")
            lines.append("")

    quiz_path.write_text("\n".join(lines), encoding="utf-8")

    if is_inline:
        print(f"[import] Created inline quiz: {quiz_folder_name} ({len(quiz.questions)} questions)")
    else:
        print(f"[import] Created question bank: {filename} ({len(quiz.questions)} questions)")


def write_shared_rubrics(shared_rubrics: Dict[str, Dict[str, Any]], output_dir: Path):
    """Write shared rubrics to the rubrics/ directory."""
    if not shared_rubrics:
        return

    rubrics_dir = output_dir / "rubrics"
    rubrics_dir.mkdir(parents=True, exist_ok=True)

    for rubric_name, rubric_data in shared_rubrics.items():
        rubric_path = rubrics_dir / f"{rubric_name}.yaml"
        rubric_path.write_text(yaml.dump(rubric_data, sort_keys=False), encoding="utf-8")
        print(f"[import] Created shared rubric: {rubric_name}.yaml")


def copy_assets(assets: Dict[str, str], output_dir: Path):
    """Copy asset files to the assets directory."""
    if not assets:
        return

    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for src_path_str, dest_rel_path in assets.items():
        src_path = Path(src_path_str)

        if not src_path.is_file():
            continue

        dest_path = assets_dir / dest_rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.copy2(src_path, dest_path)
            copied += 1
        except Exception as e:
            print(f"[import:warn] Failed to copy asset {dest_rel_path}: {e}")

    print(f"[import] Copied {copied} asset files")


def sanitize_filename(name: str) -> str:
    """Sanitize a filename for file system use."""
    # Remove/replace invalid characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace spaces with hyphens
    name = re.sub(r'\s+', '-', name)
    # Remove multiple hyphens
    name = re.sub(r'-+', '-', name)
    # Trim hyphens from ends
    name = name.strip('-')
    # Limit length
    if len(name) > 100:
        name = name[:100]
    return name or "untitled"


def rubric_hash(rubric: Dict[str, Any]) -> str:
    """Generate a hash for a rubric to detect duplicates."""
    # Create a stable string representation
    rubric_str = json.dumps(rubric, sort_keys=True)
    return hashlib.md5(rubric_str.encode()).hexdigest()[:12]


def extract_shared_rubrics(cartridge: CartridgeImport) -> None:
    """
    Detect and extract shared rubrics from assignments.

    Rubrics that appear multiple times (identical content) are extracted
    to the shared_rubrics collection and replaced with references.
    """
    # Count rubric occurrences by hash
    rubric_usage: Dict[str, List[ContentItem]] = {}

    for item in cartridge.content_items:
        if item.rubric and item.item_type == "assignment":
            rhash = rubric_hash(item.rubric)
            if rhash not in rubric_usage:
                rubric_usage[rhash] = []
            rubric_usage[rhash].append(item)

    # Extract rubrics used by multiple assignments
    for rhash, items in rubric_usage.items():
        if len(items) > 1:  # Used by multiple assignments
            # Use first item's rubric as the canonical version
            rubric = items[0].rubric

            # Generate a shared rubric name
            rubric_title = rubric.get("title", "Shared Rubric")
            rubric_name = f"shared-rubric-{rhash}"

            # Store in shared collection
            cartridge.shared_rubrics[rubric_name] = rubric

            # Replace inline rubrics with references
            for item in items:
                item.rubric = {"reference": rubric_name}

            print(f"[import] Extracted shared rubric: {rubric_title} (used by {len(items)} assignments)")


# ============================================================================
# Import Orchestration
# ============================================================================

def import_cartridge(
    cartridge_path: Path,
    output_dir: Path,
    clean: bool = False,
    dry_run: bool = False,
):
    """Import a Common Cartridge file."""
    print(f"[import] Importing cartridge: {cartridge_path}")
    print(f"[import] Output directory: {output_dir}")
    print()

    # Clean output directory if requested
    if clean and not dry_run:
        for subdir in ["content", "question-banks", "assets"]:
            dir_path = output_dir / subdir
            if dir_path.exists():
                shutil.rmtree(dir_path)
                print(f"[import] Cleaned: {subdir}/")

    # Extract cartridge
    temp_dir = extract_cartridge(cartridge_path, output_dir)

    try:
        # Parse manifest
        print("[import] Parsing manifest...")
        manifest_root, resources = parse_manifest(temp_dir)

        # Parse modules
        print("[import] Parsing module structure...")
        modules = parse_modules(manifest_root)

        # Process resources
        print("[import] Processing resources...")
        cartridge = process_resources(resources, modules, temp_dir)

        # Extract shared rubrics
        print("[import] Analyzing rubrics...")
        extract_shared_rubrics(cartridge)

        if dry_run:
            print("\n[import] DRY RUN - No files written")
            print(f"[import] Would create {len(cartridge.content_items)} content items")
            print(f"[import] Would create {len(cartridge.question_banks)} question banks")
            print(f"[import] Would create {len(cartridge.quizzes)} quizzes")
            print(f"[import] Would create {len(cartridge.shared_rubrics)} shared rubrics")
            print(f"[import] Would copy {len(cartridge.assets)} assets")
            return

        # Write content items
        print("\n[import] Writing content items...")
        for item in cartridge.content_items:
            write_content_item(item, output_dir)

        # Write question banks
        print("\n[import] Writing question banks...")
        for bank in cartridge.question_banks:
            write_question_bank(bank, output_dir)

        # Write quizzes
        print("\n[import] Writing quizzes...")
        for quiz in cartridge.quizzes:
            write_quiz(quiz, output_dir)

        # Write shared rubrics
        if cartridge.shared_rubrics:
            print("\n[import] Writing shared rubrics...")
            write_shared_rubrics(cartridge.shared_rubrics, output_dir)

        # Copy assets
        print("\n[import] Copying assets...")
        copy_assets(cartridge.assets, output_dir)

        # Post-processing: extract shared rubric rows to rubrics/rows/
        from zaphod.rubric_dedup import deduplicate_rubric_rows
        n_rows = deduplicate_rubric_rows(output_dir)
        if n_rows > 0:
            print(f"[import] {SUCCESS} Extracted {n_rows} shared rubric row(s) to rubrics/rows/")

        print(f"\n[import] {SUCCESS} Import complete!")
        print(f"[import]   {len(cartridge.content_items)} content items")
        print(f"[import]   {len(cartridge.question_banks)} question banks")
        print(f"[import]   {len(cartridge.quizzes)} quizzes")
        if cartridge.shared_rubrics:
            print(f"[import]   {len(cartridge.shared_rubrics)} shared rubrics")
        print(f"[import]   {len(cartridge.assets)} assets")

    finally:
        # Cleanup temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Import IMS Common Cartridge file to Zaphod format"
    )
    parser.add_argument(
        "cartridge",
        type=Path,
        help="Path to .imscc cartridge file"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory (default: current directory)"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove existing content before import"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without making changes"
    )

    args = parser.parse_args()

    # Validate input
    if not args.cartridge.is_file():
        print(f"{ERROR} Cartridge file not found: {args.cartridge}")
        return 1

    if not args.cartridge.suffix.lower() == ".imscc":
        print(f"{WARNING} Warning: File does not have .imscc extension")

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    try:
        import_cartridge(
            args.cartridge,
            args.output,
            clean=args.clean,
            dry_run=args.dry_run,
        )
        return 0

    except Exception as e:
        print(f"\n{ERROR} Import failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
