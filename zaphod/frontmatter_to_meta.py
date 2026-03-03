#!/usr/bin/env python3

# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

"""
frontmatter_to_meta.py - Process index.md frontmatter into meta.json + source.md

Features:
- Supports both content/ (preferred) and pages/ (legacy) directories
- Course-wide variables via shared/variables.yaml
- Cross-course variables via _all_courses/shared/variables.yaml
- Includes via shared/*.md files
- Backward compatible with includes/ and pages/includes/ folders
"""

from pathlib import Path
import json
import os
import re
import frontmatter

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from zaphod.errors import (
    FrontmatterError,
    invalid_frontmatter_error,
    FileNotFoundError as ZaphodFileNotFoundError,
)
from zaphod.icons import SUCCESS


SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_ROOT = SCRIPT_DIR.parent
COURSES_ROOT = SHARED_ROOT.parent
COURSE_ROOT = Path.cwd()          # always "current course"


def find_all_courses_dir() -> Path | None:
    """
    Locate the _all_courses/ program-level directory by walking up from the
    current course root.

    This approach is independent of where the zaphod module is installed,
    so it works correctly whether zaphod is a symlink, editable install, or
    anywhere else on the filesystem.

    Returns the first _all_courses/ directory found, or None.
    """
    current = COURSE_ROOT
    while current != current.parent:
        candidate = current / "_all_courses"
        if candidate.is_dir():
            return candidate
        current = current.parent
    return None


# =============================================================================
# Content and Shared Directory Resolution
# =============================================================================

def get_content_dir() -> Path:
    """
    Get the content directory for this course.
    
    Checks in order:
    1. content/ (preferred)
    2. pages/ (legacy, backward compatible)
    
    Returns the first directory that exists, or content/ if neither exists.
    """
    content_dir = COURSE_ROOT / "content"
    pages_dir = COURSE_ROOT / "pages"
    
    if content_dir.exists():
        return content_dir
    if pages_dir.exists():
        return pages_dir
    return content_dir  # Default for new courses


def get_content_dir_name() -> str:
    """Get just the name of the content directory ('content' or 'pages')."""
    return get_content_dir().name


# Module-level for use in other functions (set in main)
_CONTENT_DIR = None


def _get_cached_content_dir() -> Path:
    """Lazy getter for cached content directory."""
    global _CONTENT_DIR
    if _CONTENT_DIR is None:
        _CONTENT_DIR = get_content_dir()
    return _CONTENT_DIR


# =============================================================================
# Module Inference from Path
# =============================================================================


def infer_module_from_path(folder: Path) -> str | None:
    """
    Given a content folder path, walk up the directory tree looking for
    a parent directory that is a module folder.
    
    Module folder patterns (in order of precedence):
    1. NEW: Ends with '.module' suffix (case-insensitive)
       - Numeric prefix (##-) is stripped for sorting purposes
       - Examples:
         - '05-Donkey Training.module' -> 'Donkey Training'
         - 'Week 1.module' -> 'Week 1'
    
    2. LEGACY: Starts with 'module-' prefix (case-insensitive)
       - Examples:
         - 'module-Week 1' -> 'Week 1'
         - 'module-Credit 1' -> 'Credit 1'
    
    Returns the module name, or None if no module directory is found
    before reaching the content root.
    """
    content_root = get_content_dir()
    current = folder.parent  # start with parent of content folder
    
    while current != content_root and current != current.parent:
        name = current.name
        name_lower = name.lower()
        
        # NEW pattern: .module suffix
        if name_lower.endswith(".module"):
            # Strip the .module suffix
            module_name = name[:-7]  # len(".module") == 7
            
            # Strip numeric prefix (##- pattern) used for sorting
            if len(module_name) >= 3 and module_name[:2].isdigit() and module_name[2] == '-':
                module_name = module_name[3:]
            
            return module_name.strip()
        
        # LEGACY pattern: module- prefix (for backward compatibility)
        if name_lower.startswith("module-"):
            # Extract module name (preserving original case after 'module-')
            return name[7:]  # len("module-") == 7
        
        current = current.parent
    
    return None


# {{var:key}} and {{var:key | filter...}} interpolation
# Group 1: variable name
# Group 2: optional filter chain (e.g. " | upcase | default:x"), empty string if none
VAR_RE = re.compile(r"\{\{var:([a-zA-Z_][a-zA-Z0-9_-]*)([^}]*)\}\}")


# {{include:name}} interpolation
INCLUDE_RE = re.compile(r"\{\{include:([a-zA-Z_][a-zA-Z0-9_-]*)\}\}")

# Matches a complete double-quoted HTML attribute value (may span multiple lines).
# Used by interpolate_body to resolve vars inside attributes without emitting
# HTML comment markers (which are invalid inside attribute values).
_ATTR_VALUE_RE = re.compile(r'(=")(.*?)(")', re.DOTALL)


# =============================================================================
# Variables Loading
# =============================================================================

def load_shared_variables() -> dict:
    """
    Load variables from shared/variables.yaml files with 3-tier precedence.
    
    Loading order (later overrides earlier):
    1. _all_courses/shared/variables.yaml (global defaults)
    2. <course>/shared/variables.yaml (course-specific)
    
    Page frontmatter overrides both (applied in process_folder).
    """
    if not YAML_AVAILABLE:
        return {}
    
    variables = {}
    
    # Tier 1: _all_courses/shared/variables.yaml (lowest priority)
    all_courses = find_all_courses_dir()
    if all_courses:
        all_courses_paths = [
            all_courses / "shared" / "variables.yaml",
            all_courses / "shared" / "variables.yml",
        ]
        for path in all_courses_paths:
            if path.is_file():
                try:
                    data = yaml.safe_load(path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        variables.update(data)
                        print(f"ℹ️ Loaded global variables from {path}")
                except Exception as e:
                    print(f"[variables:warn] Failed to load {path}: {e}")
                break
    
    # Tier 2: <course>/shared/variables.yaml (course-specific, overrides global)
    course_paths = [
        COURSE_ROOT / "shared" / "variables.yaml",
        COURSE_ROOT / "shared" / "variables.yml",
    ]
    for path in course_paths:
        if path.is_file():
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    variables.update(data)
                    print(f"ℹ️ Loaded course variables from {path}")
            except Exception as e:
                print(f"[variables:warn] Failed to load {path}: {e}")
            break
    
    return variables


# Cache for shared variables (loaded once per run)
_shared_variables_cache: dict | None = None


def get_shared_variables() -> dict:
    """Get shared variables, loading them once and caching."""
    global _shared_variables_cache
    if _shared_variables_cache is None:
        _shared_variables_cache = load_shared_variables()
    return _shared_variables_cache


# =============================================================================
# Includes Resolution
# =============================================================================

def resolve_include_path(folder: Path, name: str) -> Path | None:
    """
    Resolve an include name to a concrete file path following precedence:
    
    NEW (preferred):
    1) <course>/shared/name.md
    2) <root>/_all_courses/shared/name.md
    
    LEGACY (backward compatibility):
    3) <course>/content/includes/name.md (or pages/includes/)
    4) <course>/includes/name.md
    5) <root>/_all_courses/includes/name.md
    """
    content_root = get_content_dir()
    
    all_courses = find_all_courses_dir()
    candidates = [
        # NEW: shared/ folder (preferred)
        COURSE_ROOT / "shared" / f"{name}.md",
        *(([all_courses / "shared" / f"{name}.md"]) if all_courses else []),

        # LEGACY: includes/ folders (backward compatibility)
        content_root / "includes" / f"{name}.md",
        COURSE_ROOT / "includes" / f"{name}.md",
        *(([all_courses / "includes" / f"{name}.md"]) if all_courses else []),
    ]
    
    for path in candidates:
        if path.is_file():
            return path
    return None


def interpolate_body(body: str, metadata: dict) -> str:
    """
    Replace {{var:key}} and {{var:key | filter...}} in the body with values from metadata.

    Filters are applied left-to-right. Supported filters: default, required,
    upcase, downcase, titlecase, replace, ordinal, decimals. See var_filters.py.

    Two-pass approach:
    - Pass 1: vars inside HTML attribute values (="...") → raw value, no markers.
      HTML comment markers are invalid inside attribute values and are mangled by
      Canvas's HTML sanitizer.
    - Pass 2: vars in text content → wrapped in round-trip HTML comment markers so
      the import pipeline can restore the original expression.

    If a key is missing and no default filter provides a value, the placeholder
    is left as-is.
    """
    from zaphod.var_filters import parse_filter_chain, apply_filters

    def _resolve(var_name, filter_raw):
        full_expr = var_name + filter_raw
        filters = parse_filter_chain(filter_raw)
        raw_value = str(metadata[var_name]) if var_name in metadata else None
        result = apply_filters(raw_value, filters, var_name, full_expr)
        return result, full_expr

    # Pass 1: attribute values — replace vars with raw value only
    def replace_in_attr(attr_match):
        def replace_var(m):
            result, _ = _resolve(m.group(1), m.group(2))
            return result if result is not None else m.group(0)
        return attr_match.group(1) + VAR_RE.sub(replace_var, attr_match.group(2)) + attr_match.group(3)

    body = _ATTR_VALUE_RE.sub(replace_in_attr, body)

    # Pass 2: text content — replace vars with round-trip comment markers
    def replace_in_text(m):
        result, full_expr = _resolve(m.group(1), m.group(2))
        if result is None:
            return m.group(0)
        return f"<!-- {{{{var:{full_expr}}}}} -->{result}<!-- {{{{/var:{full_expr}}}}} -->"

    return VAR_RE.sub(replace_in_text, body)


def interpolate_includes(body: str, folder: Path, metadata: dict) -> str:
    """
    Replace {{include:name}} in the body with the contents of the first
    matching include file, wrapped in HTML comment markers for round-trip import.
    Each included file is also processed with {{var:...}} interpolation.
    """
    def replace(match):
        name = match.group(1)
        inc_path = resolve_include_path(folder, name)
        if not inc_path:
            print(f"⚠️ {folder.name}: include '{name}' not found")
            return match.group(0)
        try:
            inc_content = inc_path.read_text(encoding="utf-8").strip()
            inc_content = interpolate_includes(inc_content, folder, metadata)
            return f"<!-- {{{{include:{name}}}}} -->\n{inc_content}\n<!-- {{{{/include:{name}}}}} -->"
        except Exception as e:
            print(f"⚠️ {folder.name}: failed to read include '{name}': {e}")
            return match.group(0)

    return INCLUDE_RE.sub(replace, body)


# =============================================================================
# Round-trip marker restoration (used by import pipeline)
# =============================================================================

_TEMPLATE_MARKER_RE = re.compile(
    r'<!--\s*\{\{template:[^}]+\}\}\s*-->.*?<!--\s*\{\{/template:[^}]+\}\}\s*-->',
    re.DOTALL,
)
_INCLUDE_MARKER_RE = re.compile(
    r'<!--\s*\{\{include:([^}]+)\}\}\s*-->.*?<!--\s*\{\{/include:\1\}\}\s*-->',
    re.DOTALL,
)
_VAR_MARKER_RE = re.compile(
    r'<!--\s*\{\{var:([^}]+)\}\}\s*-->.*?<!--\s*\{\{/var:\1\}\}\s*-->',
    re.DOTALL,
)


def restore_zaphod_markers(html: str) -> str:
    """
    Pre-process Canvas HTML before html_to_markdown conversion on import.

    Strips template wrapper sections (header/footer applied at publish time)
    and restores {{include:name}} and {{var:name}} call syntax from the
    HTML comment markers added during variable/include resolution.

    Processing order matters: includes first so any nested var markers
    inside include blocks are removed in one shot with the include block.
    """
    html = _TEMPLATE_MARKER_RE.sub("", html)
    html = _INCLUDE_MARKER_RE.sub(r"{{include:\1}}", html)
    html = _VAR_MARKER_RE.sub(r"{{var:\1}}", html)
    return html


# =============================================================================
# Changed Files Detection (for incremental mode)
# =============================================================================

def get_changed_files() -> list[Path]:
    """
    Read ZAPHOD_CHANGED_FILES and return them as Path objects.
    If the env var is missing/empty, return an empty list.
    """
    raw = os.environ.get("ZAPHOD_CHANGED_FILES", "").strip()
    if not raw:
        return []
    return [Path(p) for p in raw.splitlines() if p.strip()]


def iter_all_content_dirs():
    """
    Existing full-scan behavior: yield every content folder under content/ (or pages/)
    ending in one of the known extensions.
    """
    content_root = get_content_dir()
    for ext in [".page", ".assignment", ".link", ".file", ".quiz"]:
        for folder in content_root.rglob(f"*{ext}"):
            yield folder


def iter_changed_content_dirs(changed_files: list[Path]):
    """
    From the changed files, yield the content folders that should be
    processed by this script.

    Rules:
    - Only care about index.md files.
    - Only if they live inside content/** (or pages/**) and inside a folder whose
      name ends with one of .page / .assignment / .link / .file / .quiz.
    """
    exts = {".page", ".assignment", ".link", ".file", ".quiz"}

    seen: set[Path] = set()

    for path in changed_files:
        if path.name != "index.md":
            continue

        try:
            # Only consider files under this COURSE_ROOT
            rel = path.relative_to(COURSE_ROOT)
        except ValueError:
            continue

        # Must be under content/ or pages/
        if not rel.parts or rel.parts[0] not in ("content", "pages"):
            continue

        # Folder is the parent of index.md
        folder = path.parent

        if folder.suffix not in exts:
            continue

        if folder not in seen:
            seen.add(folder)
            yield folder


# =============================================================================
# Main Processing
# =============================================================================

def process_folder(folder: Path):
    """
    Process a content folder: read index.md, merge variables, expand includes,
    and write meta.json + source.md.
    """
    index_path = folder / "index.md"
    meta_path = folder / "meta.json"
    source_path = folder / "source.md"

    has_index = index_path.is_file()
    has_meta = meta_path.is_file()
    has_source = source_path.is_file()

    # 1) Preferred: index.md with frontmatter
    if has_index:
        try:
            post = frontmatter.load(index_path)
            
            # Build metadata: shared variables < page frontmatter
            # (page frontmatter overrides shared variables)
            shared_vars = get_shared_variables()
            page_metadata = dict(post.metadata)
            metadata = {**shared_vars, **page_metadata}
            
            content = post.content.strip() + "\n"

            # First: expand includes, with {{var:...}} applied to each include
            content = interpolate_includes(content, folder, metadata)

            # Then: {{var:...}} in the main body
            content = interpolate_body(content, metadata)

        except Exception as e:
            print(f"⚠️ {folder.name}: {e}")
        else:
            # Infer type from folder extension if not set
            if "type" not in metadata:
                ext_to_type = {
                    ".page": "page",
                    ".assignment": "assignment",
                    ".link": "link",
                    ".file": "file",
                    ".quiz": "quiz",
                }
                inferred_type = ext_to_type.get(folder.suffix)
                if inferred_type:
                    metadata["type"] = inferred_type
                    print(f"inferred type: '{inferred_type}'")

            # Infer name from folder if not set (title: accepted as legacy alias)
            if "name" not in metadata:
                if "title" in metadata:
                    metadata["name"] = metadata["title"]
                    print(f"inferred name from title: '{metadata['name']}'")
                else:
                    folder_stem = folder.stem
                    nice_name = re.sub(r'^\d+-', '', folder_stem)
                    nice_name = nice_name.replace('-', ' ').replace('_', ' ').title()
                    metadata["name"] = nice_name
                    print(f"inferred name: '{nice_name}'")
            
            # Require minimum keys for a valid Canvas object
            for k in ["name", "type"]:
                if k not in metadata:
                    print(f"⚠️ {folder.name}: missing '{k}', using meta.json if present")
                    break
            else:
                # Infer module from directory structure if not explicitly set
                if "modules" not in metadata or not metadata["modules"]:
                    inferred = infer_module_from_path(folder)
                    if inferred:
                        metadata["modules"] = [inferred]
                        print(f"inferred module: '{inferred}'")
                
                with meta_path.open("w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                with source_path.open("w", encoding="utf-8") as f:
                    f.write(content)
                print(f"{SUCCESS} {folder.name}")
                print()  # Blank line after each folder
                return

    # 2) Fallback: existing meta.json + source.md
    if has_meta and has_source:
        print(f"⏭️ {folder.name} (using existing meta.json)")
        print()  # Blank line after each folder
        return

    # 3) Nothing usable
    print(f"❌ {folder.name}: no usable metadata (index.md or meta.json/source.md)")


if __name__ == "__main__":
    # Set global content directory 
    _CONTENT_DIR = get_content_dir()
    
    if not _CONTENT_DIR.exists():
        raise SystemExit(f"No content directory found. Create content/ or pages/ in {COURSE_ROOT}")

    print(f"Using content directory: {_CONTENT_DIR.name}/")
    
    changed_files = get_changed_files()

    if changed_files:
        # Incremental mode: only process content folders for changed index.md files
        content_dirs = list(iter_changed_content_dirs(changed_files))
        if not content_dirs:
            print("No relevant changed index.md files; nothing to do.")
    else:
        # Full mode: no env var => process everything (existing behavior)
        content_dirs = list(iter_all_content_dirs())

    for folder in content_dirs:
        process_folder(folder)
