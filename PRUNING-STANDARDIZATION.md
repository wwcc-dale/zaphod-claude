# Pruning Standardization Summary

## What Changed

Standardized the cleanup of derived files (meta.json + source.md) to use the existing `prune_canvas_content.py` infrastructure instead of creating redundant pruning logic.

---

## Changes Made

### 1. Added meta.json to AUTO_WORK_FILES

**File:** `zaphod/prune_canvas_content.py` (line 68-75)

**Before:**
```python
AUTO_WORK_FILES = {
    "styled_source.md",
    "extra_styled_source.md",
    "extra_styled_source.html",
    "result.html",
    "source.md",  # ← Only source.md was cleaned up
}
```

**After:**
```python
AUTO_WORK_FILES = {
    "styled_source.md",
    "extra_styled_source.md",
    "extra_styled_source.html",
    "result.html",
    "source.md",
    "meta.json",  # ← Added: Derived from index.md, cleaned up after use
}
```

### 2. Removed Redundant Pruning from publish_all.py

**File:** `zaphod/publish_all.py`

**Removed:**
- `prune_derived_files()` function (~35 lines)
- Call to `prune_derived_files(d)` in publishing loop

**Reason:** `prune_canvas_content.py` already handles this at the end of the pipeline.

---

## Complete Pipeline Order

From `watch_and_publish.py` (lines 196-291):

```
1. frontmatter_to_meta.py
   → Parses index.md with frontmatter
   → Creates meta.json (metadata)
   → Creates source.md (content with variables/includes expanded)

2. publish_all.py
   → Reads meta.json + source.md
   → Transforms in memory (adds Canvas URLs)
   → Tracks uploads in Asset Registry
   → Publishes to Canvas
   → Does NOT write back to source.md ✅

3. sync_banks.py
   → Imports question banks
   → Uses meta.json for metadata

4. sync_quizzes.py
   → Creates/updates quizzes
   → Uses meta.json for quiz data

5. sync_modules.py
   → Syncs module structure
   → Uses meta.json for module assignments

6. sync_clo_via_csv.py
   → Syncs learning outcomes

7. sync_rubrics.py
   → Syncs rubrics

8. prune_canvas_content.py ← CLEANUP HAPPENS HERE
   → Uses meta.json to determine module mappings
   → Prunes extra Canvas content (pages, assignments)
   → Prunes module items no longer in meta.json
   → cleanup_work_files():
     - Deletes source.md ✅
     - Deletes meta.json ✅
     - Deletes styled_source.md
     - Deletes other work files

9. prune_quizzes.py
   → Prunes orphaned quizzes

10. build_media_manifest.py
    → Builds media manifest

11. export_cartridge.py (optional)
    → Exports to Common Cartridge
    → Uses index.md (clean local refs) ✅
```

---

## Why This Order Matters

### meta.json Lifecycle

```
Created:  Step 1 (frontmatter_to_meta.py)
          ↓
Used by:  Steps 2-8 (publish, sync_*, prune_canvas_content)
          ↓
Deleted:  Step 8 (prune_canvas_content.py cleanup_work_files)
```

**Key Point:** meta.json must exist through Step 8 because `prune_canvas_content.py` uses it to determine which module items to keep/remove.

### source.md Lifecycle

```
Created:  Step 1 (frontmatter_to_meta.py)
          ↓
Used by:  Step 2 (publish_all.py reads it)
          ↓
Deleted:  Step 8 (prune_canvas_content.py cleanup_work_files)
```

**Key Point:** source.md stays clean (local refs only) because publish_all.py transforms in memory without writing back.

---

## File States After Each Step

### After Step 1 (frontmatter_to_meta.py):
```
pages/welcome.page/
  index.md      ← Source of truth (permanent)
  meta.json     ← Derived (temporary)
  source.md     ← Derived (temporary, clean local refs)
```

### After Step 2 (publish_all.py):
```
pages/welcome.page/
  index.md      ← Unchanged
  meta.json     ← Still exists
  source.md     ← Still exists, STILL CLEAN (not mutated) ✅

_course_metadata/
  asset_registry.json  ← Updated with Canvas URL mappings
```

### After Steps 3-7 (sync_*):
```
pages/welcome.page/
  index.md      ← Unchanged
  meta.json     ← Still exists (used by scripts)
  source.md     ← Still exists
```

### After Step 8 (prune_canvas_content.py):
```
pages/welcome.page/
  index.md      ← Only file remaining! ✅

_course_metadata/
  asset_registry.json  ← Persists (not a work file)
```

---

## Benefits of Standardized Approach

### ✅ Single Responsibility
- All cleanup logic in one place (`prune_canvas_content.py`)
- No duplicate cleanup code
- Easier to maintain

### ✅ Correct Timing
- meta.json cleaned up AFTER all scripts use it
- source.md cleaned up after publishing
- Runs at end of pipeline (after modules)

### ✅ Consistent Behavior
- Same cleanup whether running:
  - Full sync (`zaphod sync`)
  - Watch mode (`zaphod sync --watch`)
  - Individual scripts
  - Manual pipeline

### ✅ Asset Registry Integration
- source.md stays clean (no Canvas URLs)
- Asset Registry tracks mappings separately
- Export uses index.md (always clean)
- Perfect round-trip import/export

---

## What to Track in Git

### ✅ Track These (Permanent)
```gitignore
# Source files
**/*.page/index.md
**/*.assignment/index.md
**/*.link/index.md
**/*.file/index.md
**/*.quiz/index.md

# Shared content
shared/
assets/

# Configuration
zaphod.yaml
modules/module_order.yaml
```

### ❌ Don't Track These (Temporary/Generated)
```gitignore
# Derived files (regenerated each sync)
**/meta.json
**/source.md
**/styled_source.md
**/extra_styled_source.md
**/extra_styled_source.html
**/result.html

# Course metadata (contains Canvas-specific data)
_course_metadata/
```

---

## Verification

After sync, verify cleanup worked:

```bash
# Should return NO results (all cleaned up)
find pages -name "meta.json" -o -name "source.md"

# Only index.md should remain
find pages -type f -name "*.md"
# Should show only index.md files

# Asset Registry should exist (it's persistent)
ls _course_metadata/asset_registry.json
```

---

## Testing the Workflow

### Test 1: Basic Cleanup
```bash
# Run sync
zaphod sync

# Verify only index.md remains
ls pages/welcome.page/
# Should show: index.md (only!)

# Verify source is clean
cat pages/welcome.page/index.md
# Should have: ![Photo](../../assets/photo.jpg)
# Should NOT have: Canvas URLs
```

### Test 2: Pipeline Order
```bash
# Watch mode shows complete order
zaphod sync --watch

# Output should show:
# 1. frontmatter_to_meta.py
# 2. publish_all.py
# 3-7. sync_*
# 8. prune_canvas_content.py ← Cleanup happens here
```

### Test 3: Asset Registry
```bash
# Check registry has mappings
cat _course_metadata/asset_registry.json | jq .

# Check Canvas page has Canvas URLs
# (Visit Canvas to verify image shows correctly)

# Check local files stay clean
grep -r "canvas.instructure.com" pages/
# Should return NO results
```

---

## Summary

### What We Standardized

1. **Added meta.json to cleanup** - Now properly removed after pipeline
2. **Removed redundant pruning** - Eliminated duplicate code in publish_all.py
3. **Centralized cleanup** - All work file removal in prune_canvas_content.py
4. **Correct timing** - Cleanup runs AFTER all scripts use derived files

### Workflow Now

```
index.md (permanent)
   ↓
Generate meta.json + source.md (temporary)
   ↓
Use them through pipeline (Steps 2-8)
   ↓
Clean them up (Step 8)
   ↓
index.md only (back to start)
```

### Key Benefits

✅ **Single source of truth** - index.md only
✅ **No file mutation** - source.md stays clean
✅ **Asset Registry tracks mappings** - Separately from source files
✅ **Portable exports** - Cartridges have local refs
✅ **Clean Git history** - No Canvas URL noise
✅ **Standardized cleanup** - One place, correct timing

---

**Implementation Date:** February 6, 2026
**Files Modified:** 2
- `zaphod/prune_canvas_content.py` - Added meta.json to AUTO_WORK_FILES
- `zaphod/publish_all.py` - Removed redundant pruning function
**Syntax Validated:** ✅
**Workflow Documented:** ✅
**Ready for Testing:** ✅
