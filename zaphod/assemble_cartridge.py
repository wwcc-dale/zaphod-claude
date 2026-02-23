#!/usr/bin/env python3
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

"""
assemble_cartridge.py — Step 8: Build imsmanifest.xml and zip the .imscc.

Reads:  EXPORT_MANIFEST_PATH  (fully populated by previous steps)
        assets/               (binary media files; copied into staging)

Writes: {staging_dir}/imsmanifest.xml
        {output_path}.imscc   (ZIP of all staging files)

This is the only step that produces the final .imscc file. All content files
must have been written to staging_dir by earlier steps before this runs.

imsmanifest.xml structure:
  <manifest>
    <metadata>   — schema + LOM title
    <organizations>
      <organization>
        <item identifier="LearningModules">  ← Canvas requires this root wrapper
          <item>..module..</item>            ← one per ExportOrgItem
    <resources>
      <resource type="associatedcontent/...">  ← settings bundle
        <file href="course_settings/..."/>
      <resource type="webcontent">           ← pages, files, assets
      <resource type="assoc...">             ← assignments
      <resource type="imsqti_xmlv1p2/...">   ← quiz QTI
      <resource type="assoc..." href="...meta.xml">  ← quiz meta

Standalone:
    python -m zaphod.assemble_cartridge
"""

from __future__ import annotations

import hashlib
import os
import shutil
import zipfile
from pathlib import Path
from typing import List
from xml.etree import ElementTree as ET

from zaphod.export_types import ExportManifest, ExportResource, prettify_xml
from zaphod.security_utils import is_safe_path

COURSE_ROOT = Path.cwd()
ASSETS_DIR = COURSE_ROOT / "assets"
METADATA_DIR = COURSE_ROOT / "_course_metadata"
EXPORTS_DIR = METADATA_DIR / "exports"
DEFAULT_MANIFEST_PATH = EXPORTS_DIR / ".export_manifest.json"

# Common Cartridge 1.1 namespaces (Canvas exports in 1.1)
NS_IMSCC = "http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1"
NS_LOM = "http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource"
NS_LOMIMSCC = "http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"


def get_manifest_path() -> Path:
    env_path = os.environ.get("EXPORT_MANIFEST_PATH")
    return Path(env_path) if env_path else DEFAULT_MANIFEST_PATH


# ============================================================================
# Asset collection
# ============================================================================

_EXCLUDE_PATTERNS = {
    ":Zone.Identifier",  # Windows security metadata
    ".DS_Store",         # macOS
    "Thumbs.db",         # Windows thumbnails
    ".gitkeep",          # Git placeholder
    "desktop.ini",       # Windows folder settings
}


def collect_assets() -> List[Path]:
    """Collect all asset files from assets/ for inclusion in the cartridge."""
    assets = []
    if not ASSETS_DIR.exists():
        return assets

    for file_path in ASSETS_DIR.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.name.startswith("."):
            continue
        if any(pattern in file_path.name for pattern in _EXCLUDE_PATTERNS):
            continue
        # SECURITY: Validate path is within assets/ (prevent symlink traversal)
        if not is_safe_path(ASSETS_DIR, file_path):
            print(f"[assemble:warn] Skipping file outside assets/: {file_path.name}")
            continue
        assets.append(file_path)

    return assets


def _asset_resource_id(asset: Path) -> str:
    """Generate a deterministic identifier for an asset file."""
    return f"asset_{hashlib.md5(str(asset).encode()).hexdigest()[:12]}"


# ============================================================================
# imsmanifest.xml builder
# ============================================================================

def build_imsmanifest(manifest: ExportManifest,
                      asset_resources: List[ExportResource]) -> str:
    """
    Build imsmanifest.xml XML from the fully-populated manifest.

    Returns a pretty-printed XML string.
    """
    # Register namespaces so ElementTree serializes with the right prefixes
    ET.register_namespace("", NS_IMSCC)
    ET.register_namespace("lom", NS_LOM)
    ET.register_namespace("lomimscc", NS_LOMIMSCC)
    ET.register_namespace("xsi", NS_XSI)

    root = ET.Element(f"{{{NS_IMSCC}}}manifest")
    root.set("identifier", manifest.identifier)
    root.set(
        f"{{{NS_XSI}}}schemaLocation",
        "http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1 "
        "http://www.imsglobal.org/profile/cc/ccv1p1/ccv1p1_imscp_v1p2_v1p0.xsd "
        "http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource "
        "http://www.imsglobal.org/profile/cc/ccv1p1/LOM/ccv1p1_lomresource_v1p0.xsd "
        "http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest "
        "http://www.imsglobal.org/profile/cc/ccv1p1/LOM/ccv1p1_lommanifest_v1p0.xsd",
    )

    # Metadata
    metadata = ET.SubElement(root, f"{{{NS_IMSCC}}}metadata")
    ET.SubElement(metadata, f"{{{NS_IMSCC}}}schema").text = "IMS Common Cartridge"
    ET.SubElement(metadata, f"{{{NS_IMSCC}}}schemaversion").text = "1.1.0"

    lom = ET.SubElement(metadata, f"{{{NS_LOMIMSCC}}}lom")
    general = ET.SubElement(lom, f"{{{NS_LOMIMSCC}}}general")
    title_elem = ET.SubElement(general, f"{{{NS_LOMIMSCC}}}title")
    ET.SubElement(title_elem, f"{{{NS_LOMIMSCC}}}string").text = manifest.title

    # Organizations
    organizations = ET.SubElement(root, f"{{{NS_IMSCC}}}organizations")
    organization = ET.SubElement(organizations, f"{{{NS_IMSCC}}}organization")
    organization.set("identifier", "org_1")
    organization.set("structure", "rooted-hierarchy")

    # Canvas requires a single root item "LearningModules" wrapping all modules.
    # Without this, Canvas ignores module structure and puts everything in Misc.
    root_item = ET.SubElement(organization, f"{{{NS_IMSCC}}}item")
    root_item.set("identifier", "LearningModules")

    for org_item in manifest.org_items:
        mod_item = ET.SubElement(root_item, f"{{{NS_IMSCC}}}item")
        mod_item.set("identifier", org_item.identifier)
        ET.SubElement(mod_item, f"{{{NS_IMSCC}}}title").text = org_item.title

        for child in org_item.children:
            child_elem = ET.SubElement(mod_item, f"{{{NS_IMSCC}}}item")
            child_elem.set("identifier", child.identifier)
            child_elem.set("identifierref", child.identifierref)
            ET.SubElement(child_elem, f"{{{NS_IMSCC}}}title").text = child.title

    # Resources
    resources = ET.SubElement(root, f"{{{NS_IMSCC}}}resources")

    # Settings resource block — Canvas CE importer expects this to activate the
    # full import path (pages, quizzes, assignments, modules).
    if manifest.settings_resource_files:
        settings_res = ET.SubElement(resources, f"{{{NS_IMSCC}}}resource")
        settings_res.set("identifier", f"{manifest.identifier}_settings")
        settings_res.set(
            "type",
            "associatedcontent/imscc_xmlv1p1/learning-application-resource",
        )
        # href points to canvas_export.txt (the CE trigger file)
        settings_href = next(
            (f for f in manifest.settings_resource_files
             if "canvas_export.txt" in f),
            manifest.settings_resource_files[0],
        )
        settings_res.set("href", settings_href)
        for fname in manifest.settings_resource_files:
            fe = ET.SubElement(settings_res, f"{{{NS_IMSCC}}}file")
            fe.set("href", fname)

    # Content + quiz resources
    for resource in manifest.resources:
        res_elem = ET.SubElement(resources, f"{{{NS_IMSCC}}}resource")
        res_elem.set("identifier", resource.identifier)
        res_elem.set("type", resource.type)

        if resource.href is not None:
            res_elem.set("href", resource.href)

        for fpath in resource.files:
            fe = ET.SubElement(res_elem, f"{{{NS_IMSCC}}}file")
            fe.set("href", fpath)

        if resource.dependency:
            dep = ET.SubElement(res_elem, f"{{{NS_IMSCC}}}dependency")
            dep.set("identifierref", resource.dependency)

    # Asset resources
    for asset_res in asset_resources:
        res_elem = ET.SubElement(resources, f"{{{NS_IMSCC}}}resource")
        res_elem.set("identifier", asset_res.identifier)
        res_elem.set("type", asset_res.type)
        if asset_res.href:
            res_elem.set("href", asset_res.href)
        for fpath in asset_res.files:
            fe = ET.SubElement(res_elem, f"{{{NS_IMSCC}}}file")
            fe.set("href", fpath)

    return prettify_xml(root)


# ============================================================================
# Main step logic
# ============================================================================

def assemble(manifest: ExportManifest) -> None:
    """
    Collect assets, write imsmanifest.xml, and zip staging into .imscc.
    """
    staging_dir = manifest.staging_dir
    output_path = manifest.output_path

    # Collect and copy assets into staging
    assets = collect_assets()
    asset_resources: List[ExportResource] = []

    if assets:
        assets_staging_dir = staging_dir / "web_resources" / "assets"
        assets_staging_dir.mkdir(parents=True, exist_ok=True)

        for asset in assets:
            rel_path = asset.relative_to(ASSETS_DIR)
            dest_path = assets_staging_dir / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset, dest_path)

            asset_id = _asset_resource_id(asset)
            href = f"web_resources/assets/{rel_path}"
            asset_resources.append(ExportResource(
                identifier=asset_id,
                type="webcontent",
                href=href,
                files=[href],
            ))

        print(f"[assemble] Copied {len(assets)} asset files")

    # Write imsmanifest.xml
    manifest_xml = build_imsmanifest(manifest, asset_resources)
    (staging_dir / "imsmanifest.xml").write_text(manifest_xml, encoding="utf-8")
    print("[assemble] Generated imsmanifest.xml")

    # Zip all staging files into .imscc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in staging_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(staging_dir)
                zf.write(file_path, arcname)

    size_kb = output_path.stat().st_size / 1024
    print(f"[assemble] Created {output_path}")
    print(f"[assemble] Size: {size_kb:.1f} KB")


def main() -> None:
    manifest_path = get_manifest_path()
    if not manifest_path.is_file():
        print(f"[assemble] ERROR: manifest not found at {manifest_path}")
        print("[assemble] Run 'zaphod export' first to initialise the export.")
        raise SystemExit(1)

    manifest = ExportManifest.load(manifest_path)
    assemble(manifest)


if __name__ == "__main__":
    main()
