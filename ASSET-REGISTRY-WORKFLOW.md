# Complete Asset Registry Workflow

## File Structure: Source of Truth

```
pages/
  welcome.page/
    index.md          ← SOURCE OF TRUTH (you edit this)
    meta.json         ← Derived (temporary, regenerated each sync)
    source.md         ← Derived (temporary, regenerated each sync)
```

**Key principle:** `index.md` is the only permanent file. The others are temporary build artifacts.

---

## Complete Sync Workflow

Full pipeline order (from `watch_and_publish.py`):

1. **frontmatter_to_meta.py** - Parse index.md → meta.json + source.md
2. **publish_all.py** - Publish pages/assignments with Asset Registry
3. **sync_banks.py** - Import question banks
4. **sync_quizzes.py** - Create/update quizzes
5. **sync_modules.py** - Sync module structure
6. **sync_clo_via_csv.py** - Sync learning outcomes
7. **sync_rubrics.py** - Sync rubrics
8. **prune_canvas_content.py** - Prune Canvas + cleanup work files ← **Removes meta.json + source.md**
9. **prune_quizzes.py** - Prune quizzes
10. **build_media_manifest.py** - Build media manifest
11. **export_cartridge.py** - Export to Common Cartridge (optional)

### Step 1: Parse index.md → Generate Derived Files

**Script:** `frontmatter_to_meta.py`

```python
# Read index.md with frontmatter
post = frontmatter.load("index.md")
# → metadata: {name: "Welcome", type: "page", ...}
# → content: "# Welcome\n![Photo](../../assets/photo.jpg)"

# Write derived files
meta.json ← metadata
source.md ← content
```

**Result:**
```
pages/welcome.page/
  index.md      ← "![Photo](../../assets/photo.jpg)" (unchanged)
  meta.json     ← {"name": "Welcome", "type": "page"}
  source.md     ← "![Photo](../../assets/photo.jpg)" (clean, local refs)
```

### Step 2: Upload Assets & Transform in Memory

**Script:** `publish_all.py`

```python
# Read derived files
obj = make_zaphod_obj(folder)  # Reads meta.json + source.md
text = source_md.read_text()   # "![Photo](../../assets/photo.jpg)"

# Upload assets and track in registry
text = replace_video_placeholders(text, ..., registry)
text = replace_local_asset_references(text, ..., registry)
# → "![Photo](https://canvas.../files/456/preview)"

# Pass transformed text to object (IN MEMORY ONLY)
obj.source_md = transformed_markdown

# Publish to Canvas
obj.publish(course)
# → Canvas gets: "![Photo](https://canvas.../files/456/preview)"
```

**Registry tracks:**
```json
{
  "assets": {
    "content-hash-abc123": {
      "local_paths": ["assets/images/photo.jpg"],
      "canvas_file_id": 456,
      "canvas_url": "https://canvas.../files/456/preview"
    }
  }
}
```

**Result:**
- ✅ Asset uploaded to Canvas
- ✅ Registry tracking local → Canvas mapping
- ✅ Canvas page has Canvas URL
- ⚠️ source.md still has local refs (not mutated!)

### Step 3: Continue Pipeline (modules, rubrics, etc.)

**Scripts:**
- `sync_banks.py` - Uses meta.json
- `sync_quizzes.py` - Uses meta.json
- `sync_modules.py` - Uses meta.json
- `sync_rubrics.py`

All scripts use meta.json for content metadata and module mappings.

### Step 4: Prune Derived Files & Canvas Content

**Script:** `prune_canvas_content.py` (runs at end of pipeline)

```python
# 1. Uses meta.json for module pruning decisions
# 2. Prunes extra Canvas content (pages, assignments)
# 3. Cleans up work files including meta.json + source.md

cleanup_work_files()
# → Deletes meta.json
# → Deletes source.md
# → Deletes other work files (styled_source.md, etc.)
```

**Result:**
```
pages/welcome.page/
  index.md      ← SOURCE OF TRUTH (only file remaining)
```

### Step 4: Next Sync

```
Repeat from Step 1:
  index.md → regenerate meta.json + source.md
            → publish (with fresh local refs)
            → prune derived files
```

---

## What Happens to Each File

### index.md
- ✅ **Permanent** - Never deleted
- ✅ **Source of truth** - You edit this
- ✅ **Version controlled** - Track in Git
- ✅ **Always clean** - Local references only
- ✅ **Canvas-agnostic** - No Canvas URLs

### meta.json
- 🔄 **Temporary** - Regenerated each sync
- 🗑️ **Pruned** - Deleted after publish
- ❌ **Not tracked** - Add to .gitignore
- 📦 **Build artifact** - Extracted frontmatter

### source.md
- 🔄 **Temporary** - Regenerated each sync
- 🗑️ **Pruned** - Deleted after publish
- ❌ **Not tracked** - Add to .gitignore
- 📦 **Build artifact** - Content with variables/includes expanded
- ✅ **Stays clean** - No Canvas URLs written back

### asset_registry.json
- ✅ **Persistent** - Survives across syncs
- 📍 **Location** - `_course_metadata/asset_registry.json`
- 🔑 **Purpose** - Tracks local → Canvas mappings
- ❌ **Not tracked** - Add to .gitignore (contains Canvas URLs)
- 💾 **Cache-like** - Can be deleted and rebuilt

---

## .gitignore Configuration

Add to your `.gitignore`:

```gitignore
# Derived files (temporary build artifacts)
**/meta.json
**/source.md

# Course metadata (contains Canvas-specific data)
_course_metadata/
```

**Track in Git:**
```gitignore
# Track these files
!**/*.page/index.md
!**/*.assignment/index.md
!assets/**
!shared/**
```

---

## Workflow Comparison

### OLD Workflow (Broken)

```
1. index.md → parse → meta.json + source.md
2. Transform source.md → Add Canvas URLs
3. WRITE BACK to source.md ← MUTATION!
4. Publish using mutated source.md
5. Leave files around (never prune)

Next sync:
6. source.md already has Canvas URLs
7. Export creates cartridge with Canvas URLs
8. Cartridge tied to Canvas instance ✗
```

**Problems:**
- ❌ source.md polluted with Canvas URLs
- ❌ index.md eventually gets Canvas URLs too
- ❌ Git diffs show Canvas URL changes
- ❌ Cartridge exports not portable
- ❌ Round-trip import/export broken

### NEW Workflow (Fixed)

```
1. index.md → parse → meta.json + source.md
2. Transform IN MEMORY → Add Canvas URLs
3. DON'T write back to source.md ← STAYS CLEAN!
4. Track mappings in registry
5. Publish using transformed version
6. Prune meta.json + source.md ← CLEANUP!

Next sync:
7. Regenerate from index.md (always fresh)
8. Export reads index.md (local refs only)
9. Cartridge portable across Canvas instances ✅
```

**Benefits:**
- ✅ index.md stays pure (source of truth)
- ✅ source.md regenerated clean each time
- ✅ No Canvas URLs in tracked files
- ✅ Clean Git history
- ✅ Portable cartridge exports
- ✅ Perfect round-trip import/export

---

## Verification

After sync, verify the workflow:

### Check 1: Only index.md Remains
```bash
ls pages/welcome.page/
# Should show: index.md (only!)
# Should NOT show: meta.json, source.md
```

### Check 2: index.md Still Clean
```bash
cat pages/welcome.page/index.md
# Should have: ![Photo](../../assets/photo.jpg)
# Should NOT have: Canvas URLs
```

### Check 3: Registry Has Mappings
```bash
cat _course_metadata/asset_registry.json | jq .
# Should show asset mappings with Canvas URLs
```

### Check 4: Canvas Has Content
```
Visit Canvas page → Should show image correctly
HTML in Canvas → Should have Canvas URL
```

---

## Troubleshooting

### meta.json or source.md Still Present After Sync

**Problem:** Derived files not being pruned

**Cause:** Publish failed or pruning logic not running

**Check:**
```bash
# Did publish succeed?
zaphod sync 2>&1 | grep "✓\|SUCCESS"

# Are derived files present?
find pages -name "meta.json" -o -name "source.md"
```

**Solution:**
```bash
# Manual cleanup
find pages -name "meta.json" -delete
find pages -name "source.md" -delete

# Re-sync
zaphod sync
```

### Canvas URLs Appearing in index.md

**Problem:** Old workflow mutated index.md

**Cause:** Running old version of Zaphod or manual edits

**Solution:**
```bash
# Revert to clean state
git checkout HEAD -- pages/**/*.page/index.md

# Delete registries
rm _course_metadata/upload_cache.json
rm _course_metadata/asset_registry.json

# Re-sync
zaphod sync
```

### Derived Files Not Created

**Problem:** meta.json + source.md missing, publish fails

**Cause:** frontmatter_to_meta.py not run before publish

**Solution:**
```bash
# Manually run frontmatter parsing
python3 zaphod/frontmatter_to_meta.py

# Then publish
python3 zaphod/publish_all.py
```

---

## Migration from Old System

If you have existing courses with mutated files:

### Step 1: Identify Mutated Files
```bash
# Find source.md files with Canvas URLs
grep -r "canvas.instructure.com" pages/*/source.md

# Find index.md files with Canvas URLs
grep -r "canvas.instructure.com" pages/*/index.md
```

### Step 2: Clean Up
```bash
# Delete all derived files
find pages -name "meta.json" -delete
find pages -name "source.md" -delete

# Revert index.md to clean state (if mutated)
git log --all -- "pages/*/index.md" | grep -B5 "before asset"
git checkout <commit-hash> -- pages/

# Clear caches
rm _course_metadata/upload_cache.json
rm _course_metadata/asset_registry.json
```

### Step 3: Re-sync
```bash
# Generate fresh derived files
python3 zaphod/frontmatter_to_meta.py

# Publish with new workflow
python3 zaphod/publish_all.py

# Verify cleanup happened
find pages -name "meta.json" -o -name "source.md"
# Should return nothing
```

---

## Summary

### The Three Files

| File | Role | Lifetime | Track in Git? |
|------|------|----------|---------------|
| **index.md** | Source of truth | Permanent | ✅ Yes |
| **meta.json** | Build artifact | Temporary | ❌ No |
| **source.md** | Build artifact | Temporary | ❌ No |

### The Flow

```
index.md
   ↓
Parse frontmatter
   ↓
meta.json + source.md (temporary)
   ↓
Transform in memory
   ↓
Publish to Canvas
   ↓
Prune meta.json + source.md (cleanup)
   ↓
index.md (only file remaining)
```

### Key Points

✅ **index.md is the source of truth** - Only permanent file
✅ **meta.json + source.md are temporary** - Regenerated each sync
✅ **Pruning happens after publish** - Cleanup derived files
✅ **Asset Registry tracks mappings** - Local refs → Canvas URLs
✅ **No mutation of source files** - index.md stays clean forever
✅ **Portable exports** - Cartridges contain local refs only
✅ **Perfect round-trip** - Export → Import preserves local refs

---

**Implementation Date:** February 6, 2026
**Files Modified:** publish_all.py (added pruning)
**New Functions:** `prune_derived_files()`
**Workflow:** Complete and tested ✅
