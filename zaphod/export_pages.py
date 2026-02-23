#!/usr/bin/env python3
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

"""
export_pages.py — Step 2: Export pages, files, and links to wiki_content/.

Reads:  .page/meta.json  + .page/source.md   (produced by frontmatter_to_meta.py)
        .file/meta.json  + .file/source.md
        .link/meta.json  (external URL — no file written)

Writes: wiki_content/{id}.html  (pages and files)
        (links: manifest entry only — no staging file)

Updates EXPORT_MANIFEST_PATH with one ExportResource per item.

Standalone:
    python -m zaphod.export_pages
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Optional

import markdown

from zaphod.export_types import (
    ExportManifest,
    ExportResource,
    generate_content_id,
)

COURSE_ROOT = Path.cwd()
METADATA_DIR = COURSE_ROOT / "_course_metadata"
EXPORTS_DIR = METADATA_DIR / "exports"
DEFAULT_MANIFEST_PATH = EXPORTS_DIR / ".export_manifest.json"


def get_content_dir() -> Path:
    content_dir = COURSE_ROOT / "content"
    pages_dir = COURSE_ROOT / "pages"
    return content_dir if content_dir.exists() else pages_dir


def get_manifest_path() -> Path:
    env_path = os.environ.get("EXPORT_MANIFEST_PATH")
    return Path(env_path) if env_path else DEFAULT_MANIFEST_PATH


# ============================================================================
# HTML generation
# ============================================================================

def generate_page_html(identifier: str, title: str, source_html: str,
                       published: bool) -> str:
    """Generate wiki_content/{id}.html for a page or file.

    Canvas CE importer uses <meta name="identifier"> to match the file back to
    its manifest resource, and <meta name="workflow_state"> for pub status.
    """
    workflow_state = "active" if published else "unpublished"
    return (
        "<html>\n"
        "<head>\n"
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>\n'
        f'<meta name="identifier" content="{identifier}"/>\n'
        '<meta name="editing_roles" content="teachers"/>\n'
        f'<meta name="workflow_state" content="{workflow_state}"/>\n'
        f"<title>{html.escape(title)}</title>\n"
        "</head>\n"
        "<body>\n"
        f"{source_html}\n"
        "</body>\n"
        "</html>\n"
    )


# ============================================================================
# Main step logic
# ============================================================================

def export_pages(manifest: ExportManifest) -> None:
    """Export pages, files, and links to staging."""
    staging_dir = manifest.staging_dir
    wiki_dir = staging_dir / "wiki_content"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    content_dir = get_content_dir()
    if not content_dir.exists():
        print("[export:pages] No content directory found, skipping")
        return

    counts = {"page": 0, "file": 0, "link": 0}

    for ext in [".page", ".link", ".file"]:
        item_type = ext[1:]  # strip leading dot
        for folder in sorted(content_dir.rglob(f"*{ext}")):
            if not folder.is_dir():
                continue

            meta_path = folder / "meta.json"
            if not meta_path.is_file():
                print(f"[export:pages:warn] No meta.json in {folder.name}, skipping")
                continue

            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[export:pages:warn] Failed to load {meta_path}: {e}")
                continue

            title = meta.get("name") or meta.get("title")
            if not title:
                print(f"[export:pages:warn] No name in {folder.name}, skipping")
                continue

            identifier = generate_content_id(folder, COURSE_ROOT)

            if item_type == "link":
                external_url = meta.get("external_url", "")
                resource = ExportResource(
                    identifier=identifier,
                    type="imswl_xmlv1p1",
                    href=external_url,
                    files=[],
                )
                manifest.append_resource(resource)
                counts["link"] += 1
                print(f"[export:pages] link: {title}")
                continue

            # page or file → wiki_content/{id}.html
            source_content = ""
            source_path = folder / "source.md"
            if source_path.is_file():
                source_content = source_path.read_text(encoding="utf-8")

            source_html = markdown.markdown(
                source_content, extensions=["extra", "codehilite"]
            )
            published = meta.get("published", True)
            html_content = generate_page_html(identifier, title, source_html, published)

            out_file = wiki_dir / f"{identifier}.html"
            out_file.write_text(html_content, encoding="utf-8")

            resource = ExportResource(
                identifier=identifier,
                type="webcontent",
                href=f"wiki_content/{identifier}.html",
                files=[f"wiki_content/{identifier}.html"],
            )
            manifest.append_resource(resource)
            counts[item_type] += 1
            print(f"[export:pages] {item_type}: {title}")

    print(
        f"[export:pages] Done — "
        f"{counts['page']} pages, {counts['file']} files, {counts['link']} links"
    )


def main() -> None:
    manifest_path = get_manifest_path()
    if not manifest_path.is_file():
        print(f"[export:pages] ERROR: manifest not found at {manifest_path}")
        print("[export:pages] Run 'zaphod export' first to initialise the export.")
        raise SystemExit(1)

    manifest = ExportManifest.load(manifest_path)
    export_pages(manifest)
    manifest.save(manifest_path)


if __name__ == "__main__":
    main()
