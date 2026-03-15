# Asset Registry System

The Asset Registry keeps source files pure by tracking Canvas URL mappings separately, eliminating the need to mutate source.md files with Canvas-specific URLs.

## Overview

### Problem Solved

Previously, Zaphod would:
1. Read `source.md` with local asset references: `![photo](../../assets/photo.jpg)`
2. Upload assets to Canvas
3. **Write Canvas URLs back to source.md**: `![photo](https://canvas.../files/456/preview)`

This caused:
- ❌ Source files polluted with Canvas-specific URLs
- ❌ Poor version control (source.md changes every sync)
- ❌ Exported cartridges tied to specific Canvas instance
- ❌ Round-trip import/export broken

### New Approach

With Asset Registry:
1. Read `source.md` with local references: `![photo](../../assets/photo.jpg)` ← Stays unchanged
2. Upload assets to Canvas
3. **Track mappings in registry**: `../../assets/photo.jpg → https://canvas.../files/456/preview`
4. Transform references during HTML rendering (in-memory only)
5. source.md never modified ✅

## Benefits

✅ **Source files stay pure** - Local references never change
✅ **Version control friendly** - No Canvas URLs in tracked files
✅ **Portable cartridges** - Exports contain local refs, work across Canvas instances
✅ **Perfect round-trip** - Export → Import preserves local references
✅ **Content-hash deduplication** - Same file uploaded once, referenced many times

## How It Works

### Registry Structure

The registry is stored at `_course_metadata/asset_registry.json`:

```json
{
  "version": "1.0",
  "assets": {
    "content-hash-abc123": {
      "local_paths": [
        "assets/images/photo.jpg",
        "../../assets/images/photo.jpg"
      ],
      "canvas_file_id": 456,
      "canvas_url": "https://canvas.../files/456/download?download_frd=1",
      "content_hash": "abc123def456...",
      "uploaded_at": "2026-02-05T12:34:56Z",
      "file_size": 12345,
      "filename": "photo.jpg"
    }
  },
  "path_lookup": {
    "assets/images/photo.jpg": "content-hash-abc123",
    "../../assets/images/photo.jpg": "content-hash-abc123"
  }
}
```

### Content-Hash Deduplication

Files are tracked by content hash, not filename. This means:
- Same file in different locations → One upload, multiple path mappings
- Updated file with same name → New upload automatically (hash changed)
- Copy-paste asset between pages → Reuses existing Canvas file

### Workflow

**During Sync:**
```python
# 1. Read source.md (unchanged)
text = source_md.read_text()
# → "![photo](../../assets/photo.jpg)"

# 2. Upload asset, track in registry
registry.track_upload(
    local_path="assets/images/photo.jpg",
    canvas_file_id=456,
    canvas_url="https://canvas.../files/456/download"
)

# 3. Transform in memory
canvas_url = registry.get_canvas_url("../../assets/photo.jpg")
# → "https://canvas.../files/456/download"

# 4. Render to HTML with Canvas URLs
html = render_with_canvas_urls(text, registry)

# 5. Publish to Canvas
course.create_page(html)

# source.md NEVER modified!
```

**During Export:**
```python
# 1. Read source.md (has local refs)
text = source_md.read_text()
# → "![photo](../../assets/photo.jpg)"

# 2. Convert to HTML
html = markdown_to_html(text)
# → "<img src='../../assets/photo.jpg'>"

# 3. Package in cartridge with local references
# Assets copied to web_resources/assets/
# HTML contains relative paths → Portable!
```

**During Import:**
```python
# 1. Extract HTML from cartridge
html = "<img src='../../assets/photo.jpg'>"

# 2. Convert to markdown
md = html_to_markdown(html)
# → "![photo](../../assets/photo.jpg)"

# 3. Write to source.md
# Local references preserved!
```

## API Reference

### AssetRegistry Class

```python
from zaphod.asset_registry import AssetRegistry

# Initialize
registry = AssetRegistry(course_root)

# Track an upload
registry.track_upload(
    local_path="assets/images/photo.jpg",
    canvas_file_id=456,
    canvas_url="https://canvas.../files/456/download"
)

# Query for Canvas URL
canvas_url = registry.get_canvas_url("assets/images/photo.jpg")
canvas_url = registry.get_canvas_url("../../assets/images/photo.jpg")  # Also works!

# Check if tracked
if registry.is_tracked("assets/photo.jpg"):
    print("Already uploaded")

# Get file ID
file_id = registry.get_canvas_file_id("assets/photo.jpg")

# Statistics
stats = registry.get_stats()
# → {"total_assets": 42, "total_size_mb": 123.45, ...}

# Prune missing files
removed = registry.prune_missing()
# → Removes entries for deleted local files

# Save registry
registry.save()
```

### Automatic Tracking

The registry is automatically used by `zaphod sync`:

```bash
# Normal sync - registry updated automatically
zaphod sync

# Check registry stats
python3 -c "from zaphod.asset_registry import AssetRegistry; \
            r = AssetRegistry('.'); r.print_stats()"
```

## Maintenance

### Prune Missing Assets

Remove registry entries for files that no longer exist locally:

```python
from zaphod.asset_registry import AssetRegistry

registry = AssetRegistry('.')
removed = registry.prune_missing()
print(f"Pruned {removed} missing assets")
registry.save()
```

### View Registry Contents

```bash
cat _course_metadata/asset_registry.json | jq .
```

### Clear Registry

To start fresh (will re-upload all assets on next sync):

```bash
rm _course_metadata/asset_registry.json
```

## Migration from Old System

If your source.md files contain Canvas URLs from the old system:

### Option 1: Clean Re-sync (Recommended)

1. Revert source.md files to local references using Git
2. Delete old upload cache: `rm _course_metadata/upload_cache.json`
3. Run sync: `zaphod sync`
4. Registry will be built automatically

### Option 2: Manual Conversion

Create a script to convert Canvas URLs back to local references:

```python
import re
from pathlib import Path

def revert_to_local_refs(source_md: Path):
    """Convert Canvas URLs back to local asset references."""
    text = source_md.read_text()

    # Find Canvas file URLs
    # Replace with local references
    # (Implementation depends on your URL patterns)

    source_md.write_text(text)

# Process all source.md files
for source_md in Path('.').rglob('source.md'):
    revert_to_local_refs(source_md)
```

## Troubleshooting

### Asset Not Found

If an asset reference can't be resolved:

1. **Check the path** - Paths are resolved relative to course root
2. **Check assets/ directory** - Should contain the file
3. **Check filename** - Case-sensitive on Linux/macOS
4. **Check for duplicates** - Multiple files with same name require explicit path

### Registry Out of Sync

If Canvas files were deleted manually:

```bash
# Prune invalid entries
python3 -c "from zaphod.asset_registry import AssetRegistry; \
            AssetRegistry('.').prune_missing()"

# Or rebuild from scratch
rm _course_metadata/asset_registry.json
zaphod sync
```

### Large Registry File

The registry grows with unique file versions. To reduce size:

1. **Prune missing entries** (see above)
2. **Remove old versions** - Edit JSON to remove old content-hash entries
3. **Consider asset organization** - Consolidate duplicate files

## Technical Details

### Content Hashing

Uses MD5 hash (12-character prefix) of file contents:
- Fast computation
- Collision probability negligible for typical course sizes
- Automatically handles file updates

### Path Normalization

Multiple path formats resolve to same asset:
- `assets/images/photo.jpg` (absolute from course root)
- `../../assets/images/photo.jpg` (relative from content folder)
- `images/photo.jpg` (relative to assets/)

All tracked in registry and queryable.

### Performance

- Registry loads once at sync start
- In-memory lookups (no disk I/O during transformation)
- Saves once at sync end
- Minimal overhead (~1ms per asset lookup)

## Security

The registry has the same security properties as the upload cache:
- Stored in `_course_metadata/` (should be in `.gitignore`)
- Contains Canvas file IDs and URLs
- No credentials or tokens stored
- Safe to delete (will rebuild on next sync)

## Future Enhancements

Potential improvements:
- [ ] CLI command to view registry: `zaphod registry stats`
- [ ] Migration tool to convert old Canvas URLs to local refs
- [ ] Garbage collection for unused Canvas files
- [ ] Registry compression for large courses
- [ ] Registry sync across course copies

---

**Related Documentation:**
- [08-assets.md](08-assets.md) - Asset management guide
- [14-import-export.md](14-import-export.md) - Import/export workflows
- [10-pipeline.md](10-pipeline.md) - Publishing pipeline

**Implementation Files:**
- `zaphod/asset_registry.py` - Registry manager class
- `zaphod/publish_all.py` - Integration with publishing workflow
