# Zaphod Project - Claude Onboarding Document

**Last Updated:** February 7, 2026
**Purpose:** Comprehensive reference for AI assistants working on this project

---

## Project Overview

**Zaphod** is a local-first course authoring workspace for Canvas LMS. Instructors write course content in plain-text markdown files with YAML frontmatter, and Zaphod syncs everything to Canvas via API.

**Core Philosophy:** Local files are the single source of truth. Canvas is the reflection.

**Primary Benefits:**
- Version control (Git-friendly plain text)
- Faster authoring (text editor > Canvas UI)
- Content reusability (copy/paste between terms)
- Course portability (Common Cartridge export)
- Collaboration (multiple instructors via Git)

---

## Quick Architecture Reference

### Directory Naming Convention

**NEW (current):** `content/` and `shared/`
**LEGACY (supported):** `pages/` and `includes/`

All scripts check for new names first, then fall back to legacy names for backward compatibility. **Use new names for all examples and new courses.**

### Content Types
| Extension | Canvas Type | Description |
|-----------|-------------|-------------|
| `.page/` | Canvas Page | Informational content |
| `.assignment/` | Canvas Assignment | Gradable submissions with rubrics |
| `.quiz/` | Canvas Quiz | Classic quizzes only |
| `.link/` | External URL | Links to external resources |
| `.file/` | File Download | Downloadable files |
| `.bank.md` | Question Bank | Quiz question pools |

### Directory Structure
```
course/
├── zaphod.yaml                 # Course config (course_id, API credentials)
├── content/                    # All content items (legacy: content/)
│   ├── 01-Intro.module/       # Module folder organization
│   │   ├── 01-welcome.page/
│   │   │   └── index.md       # Frontmatter + markdown
│   │   ├── 02-hw.assignment/
│   │   │   ├── index.md
│   │   │   └── rubric.yaml
│   │   └── 03-quiz.quiz/
│   │       └── index.md
├── question-banks/             # Question bank sources (.bank.md)
├── assets/                     # Shared media (images, videos, PDFs)
├── shared/                     # Variables and includes (legacy: shared/)
│   ├── variables.yaml
│   └── *.md                   # Include snippets
├── modules/
│   └── module_order.yaml      # Explicit module ordering
├── rubrics/                    # Shared rubrics
│   └── rows/                  # Reusable rubric rows
├── outcomes/
│   └── outcomes.yaml          # Learning outcomes
└── _course_metadata/           # Generated state (gitignored)
    ├── upload_cache.json      # Asset upload cache
    ├── asset_registry.json    # New: Canvas URL mappings
    ├── bank_cache.json
    └── outcome_map.json
```

**Note:** Legacy folder names (`content/` and `shared/`) are still supported for backward compatibility. All scripts check for new names first, then fall back to legacy names.

### Sync Pipeline (8+ steps)
```
1. frontmatter_to_meta.py   → Parse YAML → meta.json + source.md
2. publish_all.py           → Create/update Canvas pages, assignments
3. sync_banks.py            → Import question banks via QTI
4. sync_quizzes.py          → Create/update quizzes
5. sync_modules.py          → Organize content into modules
6. sync_clo_via_csv.py      → Import learning outcomes
7. sync_rubrics.py          → Create/attach rubrics
8. prune_canvas_content.py  → Remove orphaned content, clean work files
   [Watch mode only]:
   9. prune_quizzes.py      → Remove orphaned quizzes
   10. build_media_manifest.py → Track large files
   11. export_cartridge.py  → Optional auto-export (if ZAPHOD_EXPORT_ON_SYNC=1)
```

---

## Critical Files & Their Roles

### CLI & Entry Points
- **`cli.py`** - Main CLI interface (unified command system)
- **`watch_and_publish.py`** - Watch mode orchestrator (auto-sync on changes)

### Content Processing
- **`frontmatter_to_meta.py`** - Parses index.md → extracts frontmatter, expands variables/includes
- **`publish_all.py`** - Main publishing script (pages, assignments, links, files)
- **`canvas_publish.py`** - Canvas API publishing abstractions (ZaphodPage, ZaphodAssignment, etc.)

### Specialized Sync Scripts
- **`sync_banks.py`** - Question bank imports (QTI migration)
- **`sync_quizzes.py`** - Quiz creation/updates
- **`sync_modules.py`** - Module organization
- **`sync_rubrics.py`** - Rubric creation/attachment
- **`sync_clo_via_csv.py`** - Outcome imports

### Cleanup & Maintenance
- **`prune_canvas_content.py`** - Remove orphaned Canvas content, clean derived files (meta.json, source.md)
- **`prune_quizzes.py`** - Remove orphaned quizzes

### Import/Export
- **`export_cartridge.py`** - Common Cartridge (IMSCC) export
- **`import_cartridge.py`** - Import from IMSCC files
- **`import_from_canvas.py`** - Import directly from Canvas API

### Asset Management (NEW - Feb 2026)
- **`asset_registry.py`** - Tracks local → Canvas URL mappings
- **`build_media_manifest.py`** - Track large media files
- **`hydrate_media.py`** - Download large files from shared storage

### Utilities
- **`canvas_client.py`** - Canvas API client and credential loading
- **`security_utils.py`** - Security functions (path validation, SSRF protection)
- **`config_utils.py`** - Configuration loading (zaphod.yaml, env vars)
- **`html_to_markdown.py`** - HTML → Markdown conversion for imports
- **`path_utils.py`** - Path resolution and validation
- **`errors.py`** - Custom exception classes with rich error messages
- **`icons.py`** - Centralized CLI icons/emoji constants
- **`scaffold_course.py`** - Course directory scaffolding (`zaphod init`)
- **`validate.py`** - Pre-sync validation (`zaphod validate`)

---

## Key Features & How They Work

### 1. Variables (`{{var:...}}`)
**Syntax:** `{{var:instructor_name}}`

**Precedence:** Page frontmatter > Course shared/variables.yaml > Global _all_courses/shared/variables.yaml

**Example:**
```yaml
# shared/variables.yaml
instructor_name: "Dr. Smith"
instructor_email: "smith@edu"

# In index.md content:
Contact {{var:instructor_name}} at {{var:instructor_email}}
```

**Processing:** `frontmatter_to_meta.py` expands variables during parsing.

### 2. Includes (`{{include:...}}`)
**Syntax:** `{{include:late_policy}}`

**Search order:** `<course>/shared/` → `_all_courses/shared/`

**Example:**
```markdown
# shared/late_policy.md
Late submissions lose {{var:late_penalty}}.

# In page content:
{{include:late_policy}}
```

**Processing:** `frontmatter_to_meta.py` inserts include content, then expands variables within includes.

### 3. Templates (Automatic Headers/Footers)

**Location:** `canvas_publish.py` (lines 53-187)

**Status:** ✅ **FULLY IMPLEMENTED**

**Structure:**
```
course/
└── templates/
    ├── default/            # Default template set
    │   ├── header.html
    │   ├── header.md
    │   ├── footer.md
    │   └── footer.html
    └── fancy/              # Alternative template set
        └── ...
```

**Application Order:**
1. header.html (raw HTML)
2. header.md → converted to HTML
3. [Your page content]
4. footer.md → converted to HTML
5. footer.html (raw HTML)

**Frontmatter Control:**
```yaml
---
template: "fancy"      # Use templates/fancy/
# OR
template: null         # Skip templates entirely
---
```

**Security:** Template names validated, path traversal prevented

**Integration:** Used by `ZaphodPage.to_canvas_html()` and `ZaphodAssignment.to_canvas_html()`

### 4. Video Embedding (`{{video:...}}`)
**Syntax:** `{{video:lecture.mp4}}`

**Processing:**
1. `publish_all.py` finds video file in assets/
2. Uploads to Canvas if not cached
3. Replaces placeholder with Canvas iframe embed
4. Caches upload to avoid re-uploads

### 4. Module Organization
**Two methods:**

**A. Folder-based (recommended):**
```
content/01-Week 1.module/
      02-Week 2.module/
```

**B. Frontmatter-based:**
```yaml
modules:
  - "Week 1"
  - "Week 2"
```

**Ordering:** Numeric prefixes (01-, 02-) or `modules/module_order.yaml`

### 5. Question Banks (Two-Layer Quiz System)
**Layer 1: Question Banks** (`.bank.md` files)
- Store reusable question pools
- NYIT format (compact, readable)
- Imported to Canvas via QTI migration

**Layer 2: Quizzes** (`.quiz/` folders)
- Reference banks or contain inline questions
- Control settings (time limit, attempts, shuffling)

**Workflow:**
1. Create `question-banks/chapter1.bank.md`
2. Sync → uploads bank, get Canvas bank ID
3. Create `quiz.quiz/index.md` with `bank_id: 12345`
4. Sync → creates quiz pulling from bank

### 6. Content-Hash Caching
**Purpose:** Avoid redundant uploads of unchanged files

**How it works:**
- Compute MD5 hash of file content
- Cache key: `{course_id}:{filename}:{content_hash}`
- If hash matches cached entry, skip upload
- If file changed, hash differs → re-upload

**Cache locations:**
- `upload_cache.json` - Media/asset uploads
- `bank_cache.json` - Question bank imports
- `asset_registry.json` - NEW: Canvas URL mappings

### 7. Asset Registry System (NEW - Feb 2026)
**Purpose:** Track local → Canvas URL mappings WITHOUT mutating source files

**Key concepts:**
- Content-hash based deduplication
- Same file in multiple places = one upload
- Source files stay pure (no Canvas URLs written to markdown)
- Enables portable cartridge exports

**Workflow:**
1. `publish_all.py` uploads asset to Canvas
2. Tracks mapping in `asset_registry.json`:
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
3. Transform happens in-memory (Canvas gets Canvas URLs)
4. Local files never mutated (preserve `../../assets/photo.jpg`)
5. Export reads `index.md` (local refs) → portable cartridge

**Benefits:**
- Git diffs don't show Canvas URL noise
- Round-trip export/import works perfectly
- Content-hash deduplication across entire course

### 8. Round-Trip Editing (PRODUCTION-READY - Feb 2026)

**Status:** ✅ **98%+ Fidelity Achieved**

Zaphod provides complete bidirectional sync between Canvas, local files, and Common Cartridge format with near-perfect content preservation.

**What Was Tested (Feb 6, 2026):**
- Full round-trip: Local → Canvas → Export → Import → Compare
- Tested with real course containing all content types
- 6 major issues found and fixed
- Production-ready with documented limitations

**Fidelity Results:**

| Content Type | Fidelity | Notes |
|--------------|----------|-------|
| Assignments | 100% | Perfect preservation |
| Rubrics | 100% | All criteria/ratings |
| Quiz Questions | 100% | All Q&A intact |
| Quiz Metadata | 100% | Time limits, attempts, settings |
| Modules | 100% | Structure preserved |
| Nested Lists | 100% | With 4-space indentation |
| Pages | 98% | Minor list spacing normalization |
| Quiz Descriptions | 95% | Minor formatting differences |
| Code Blocks | 95% | Work perfectly, language hints lost |

**Key Features:**
1. **Asset Registry** keeps source files clean (no Canvas URLs)
2. **Custom QTI fields** preserve quiz metadata (6 fields added)
3. **Quiz descriptions** preserved via QTI objectives element
4. **Code block conversion** from `[code]` tags to fenced blocks
5. **Markdown extensions** upgraded ('extra' for better list handling)

**Known Acceptable Limitations:**
1. Code language hints lost (Canvas doesn't export them)
2. Boolean formatting (`true` → `True` - both valid)
3. Nested lists require 4 spaces (Python-Markdown requirement)
4. Minor list indentation normalization
5. Template stripping (Canvas templates removed)

**Testing Round-Trip:**
```bash
# Export → Import → Compare
zaphod export --output test.imscc
zaphod import test.imscc --output ./roundtrip
diff -r content/ roundtrip/content/
# Expect 98%+ match with only minor formatting differences
```

**Why It Works:**
- Export reads `index.md` (has local refs like `../../assets/photo.jpg`)
- Asset Registry tracks: local path → Canvas URL (separate file)
- Import converts Canvas HTML → clean markdown
- Result: Source files never polluted with Canvas URLs

**Reference:** `docs/changelogs/CHANGELOG-2026-02-06.md` - Complete testing documentation

### 9. Derived File Workflow (NEW - Feb 2026)
**Temporary build artifacts:**
- `meta.json` - Extracted frontmatter metadata
- `source.md` - Expanded markdown content (variables/includes resolved)

**Lifecycle:**
1. Created by `frontmatter_to_meta.py` (step 1)
2. Used by all sync scripts (steps 2-8)
3. Deleted by `prune_canvas_content.py` (step 8)

**Result:** Only `index.md` remains (source of truth)

**Critical:** Never commit meta.json or source.md to Git (add to .gitignore)

---

## Common Workflows

### Full Sync
```bash
cd ~/courses/my-course
zaphod sync
```

**What happens:**
1. Parses all index.md files
2. Creates/updates Canvas content
3. Organizes into modules
4. Prunes orphaned content
5. Cleans up work files

**Duration:** 2-5 minutes for typical course

### Watch Mode (Incremental)
```bash
zaphod sync --watch
```

**What happens:**
1. Initial full sync
2. Watches for file changes
3. On change: sync ONLY changed folders
4. Duration: 10-30 seconds per edit

**Key:** Sets `ZAPHOD_CHANGED_FILES` env var, scripts process only those folders

### Dry Run (Preview)
```bash
zaphod sync --dry-run
zaphod prune --dry-run
```

**What happens:**
- Runs full logic
- Logs what WOULD happen
- Makes NO API calls to Canvas
- Safe preview before destructive changes

### Export Cartridge
```bash
zaphod export
zaphod export -o my-course.imscc
```

**What happens:**
1. Reads `index.md` files (NOT source.md)
2. Builds IMS Common Cartridge structure
3. Includes assets from `assets/` folder
4. Outputs .imscc file (ZIP format)

**Key:** Uses local asset references → portable across LMS platforms

### Import from Canvas
```bash
zaphod import 12345 --output ./imported-course
```

**What happens:**
1. Downloads content via Canvas API
2. Converts HTML → Markdown
3. Creates directory structure
4. Writes index.md files with frontmatter

---

## Environment Variables

```bash
# Canvas credentials (required)
CANVAS_API_KEY=your_token_here
CANVAS_API_URL=https://canvas.institution.edu
COURSE_ID=12345

# Or use credential file
CANVAS_CREDENTIAL_FILE=~/.canvas/credentials.txt

# Watch mode options
ZAPHOD_WATCH_DEBOUNCE=2000          # Milliseconds
ZAPHOD_CHANGED_FILES="content/01-welcome.page,content/02-quiz.quiz"

# Prune options
ZAPHOD_PRUNE_APPLY=1                # Actually delete (default: dry-run)
ZAPHOD_PRUNE_ASSIGNMENTS=1          # Include assignments in prune

# Export options
ZAPHOD_EXPORT_ON_SYNC=1             # Auto-export after sync
```

---

## Security Posture (Updated Feb 2026)

**Status: EXCELLENT (Production-Ready)**

### Implemented Protections
- ✅ Path traversal protection (all file operations)
- ✅ SSRF protection (HTTP downloads + Canvas API redirects)
- ✅ XXE protection (defusedxml for XML parsing)
- ✅ Symlink validation (asset collection)
- ✅ Command injection protection (subprocess docs)
- ✅ Rate limiting (Canvas API calls)
- ✅ Credential safety (no exec(), safe parsing)
- ✅ HTTPS enforcement
- ✅ Certificate validation

### Recent Fixes (Feb 2026)
1. **SSRF in sync_banks.py** - 3 Canvas API URLs validated
2. **XXE in export_cartridge.py** - Migrated to defusedxml
3. **Symlink validation** - Added to asset collection
4. **Subprocess documentation** - Explained command injection safety

**Reference:** `zaphod/99-SECURITY-AUDIT-V2.md`

---

## Known Issues & Limitations

### Critical Issues
1. **No Conflict Resolution** - Last-write-wins if Canvas is edited
   - **Mitigation:** Always edit locally, never in Canvas

2. **Upload Cache Staleness** - Cache can get out of sync
   - **Workaround:** Delete `_course_metadata/*.json` to rebuild

3. **No Undo for Prune** - Deletions are immediate
   - **Mitigation:** Always `--dry-run` first

### Limitations
- **Classic Quizzes Only** - No New Quizzes support (Canvas API doesn't support it)
- **Single Course at a Time** - One course per sync
- **Module Reordering Can Fail** - Canvas API quirk, verify after sync
- **No Discussion Topics** - Not yet implemented
- **No Announcements** - Not yet implemented

### By Design (Not Bugs)
- Last-write-wins (local-first philosophy)
- No cloud sync (use Git for collaboration)
- Single-user at a time (script-based pipeline)
- Command-line interface (web UI in development)

---

## Documentation vs Reality (Critical Findings)

### ✅ Template System - FULLY IMPLEMENTED
**Documentation:** Extensive user guide (`13-templates.md`)

**Reality:** ✅ **Completely implemented** in `canvas_publish.py` (lines 53-187)
- `load_template_files()` - loads from `templates/{name}/` directory
- `apply_templates()` - applies header/footer wrapping
- Supports: header.html, header.md, footer.md, footer.html
- `template:` frontmatter field works
- Security validated (path traversal prevented)
- Used by ZaphodPage and ZaphodAssignment classes

**Status:** Production-ready, well-documented, secure.

### ⚠️ QTI Export - Not Working
**Documentation:** `zaphod export --format qti`

**Reality:** CLI accepts flag but immediately errors "not yet implemented"

### ✅ Offline Export - Fixed
`--offline` flag removed from docs; export already works offline by default.

### ✅ Extra Pipeline Steps - Documented
Watch mode steps 9-11 now documented in `user-guide/10-pipeline.md`.

### ✅ Asset Registry - Documented
Covered in `user-guide/15-asset-registry.md` and `user-guide/16-asset-workflow.md`.

---

## Recent Major Changes (Feb 2026)

### 1. Round-Trip Editing - Production Ready (Feb 6, 2026)

**Achievement:** 98%+ fidelity round-trip conversion

**Issues Fixed:**
1. Content items export (metadata merging fix)
2. Quiz metadata preservation (6 custom QTI fields)
3. Nested lists rendering (markdown extensions upgrade)
4. Code blocks import (`[code]` → fenced blocks)
5. Quiz descriptions preservation (QTI objectives)
6. Dependency cleanup (removed markdownify)

**Files Modified:**
- `export_cartridge.py` (~90 lines) - Quiz descriptions, metadata export
- `import_cartridge.py` (~130 lines) - Enhanced parsing, code conversion
- `canvas_publish.py` (~5 lines) - Markdown extensions upgrade
- `sync_quizzes.py` (~10 lines) - Description HTML conversion
- `import_from_canvas.py` (~30 lines removed) - Dependency cleanup

**Testing:** Comprehensive test with real course, all content types, multiple iterations

**Documentation:** Complete changelog in `CHANGELOG-2026-02-06.md`

### 2. Asset Registry Implementation
- **New file:** `asset_registry.py`
- **Purpose:** Track Canvas URL mappings separately from source files
- **Impact:** Source files stay pure, perfect round-trip export/import
- **Modified:** `publish_all.py` integrates registry
- **Testing:** `test_asset_registry.py`, `test_integration_workflow.py`

### 2. Pruning Standardization
- **Modified:** `prune_canvas_content.py`
- **Change:** Added `meta.json` to `AUTO_WORK_FILES`
- **Impact:** Derived files cleaned up at end of pipeline
- **Docs:** `PRUNING-STANDARDIZATION.md`

### 3. Security Hardening (Audit v3)
- **SSRF:** 3 protections in `sync_banks.py`
- **XXE:** Migrated to defusedxml in `export_cartridge.py`
- **Symlink:** Validation in `collect_assets()`
- **Subprocess:** Documentation in `cli.py`, `watch_and_publish.py`
- **Dependencies:** Added `defusedxml>=0.7.1`

---

## File Patterns to Know

### Files to ALWAYS Track in Git
```
**/*.page/index.md
**/*.assignment/index.md
**/*.quiz/index.md
**/*.link/index.md
**/*.file/index.md
**/rubric.yaml
*.bank.md
zaphod.yaml
modules/module_order.yaml
outcomes/outcomes.yaml
shared/variables.yaml
shared/*.md
```

### Files to NEVER Track in Git
```
_course_metadata/        # All generated state
**/meta.json            # Derived from index.md
**/source.md            # Derived from index.md
**/styled_source.md     # Build artifact
**/result.html          # Build artifact
**/*.mp4                # Large media (use manifest instead)
**/*.mov
```

### Standard `.gitignore`
```gitignore
# Generated metadata
_course_metadata/

# Derived files (temporary build artifacts)
**/meta.json
**/source.md
**/styled_source.md
**/extra_styled_source.md
**/extra_styled_source.html
**/result.html

# Large media files (track manifest instead)
assets/**/*.mp4
assets/**/*.mov
assets/**/*.avi
assets/**/*.webm
```

---

## Common Commands Reference

```bash
# Setup
zaphod init --course-id 12345

# Content creation
zaphod new --type page --name "Welcome"
zaphod new --type assignment --name "Essay 1"
zaphod new --type quiz --name "Week 1 Quiz"
zaphod new --type link --name "Syllabus"

# List content
zaphod list
zaphod list --type quiz
zaphod list --type page

# Sync
zaphod sync                          # Full sync
zaphod sync --watch                  # Watch mode
zaphod sync --dry-run                # Preview
zaphod sync --no-prune               # Skip cleanup
zaphod sync --export                 # Auto-export after sync

# Maintenance
zaphod prune                         # Remove orphaned content
zaphod prune --dry-run               # Preview deletions
zaphod prune --assignments           # Include assignments
zaphod validate                      # Check for errors
zaphod info                          # Course stats

# Media management
zaphod manifest                      # Build media manifest
zaphod hydrate --source /path        # Download media files

# Export/Import
zaphod export                        # Export to IMSCC
zaphod export -o course.imscc        # Custom filename
zaphod export --title "CS 101"       # Custom title
zaphod import 12345                  # Import from Canvas
zaphod import course.imscc           # Import from cartridge
```

---

## Testing Strategy

### Unit Tests
- **`test_asset_registry.py`** - Asset Registry functionality (9/10 passing)
- Framework: pytest (in development)

### Integration Tests
- **`test_integration_workflow.py`** - Full pipeline validation
- Tests: Parsing → Publishing → Pruning → Export
- Status: All critical checks passing

### Manual Testing Checklist
1. ✅ Create test course in Canvas sandbox
2. ✅ Initialize with `zaphod init`
3. ✅ Create content with `zaphod new`
4. ✅ Run `zaphod sync --dry-run`
5. ✅ Run `zaphod sync`
6. ✅ Verify Canvas content matches
7. ✅ Edit file, run `zaphod sync --watch`
8. ✅ Verify incremental sync works
9. ✅ Export with `zaphod export`
10. ✅ Import exported cartridge to new course

---

## Development Tips for AI Assistants

### When Asked to Add Features
1. **Check documentation first** - Feature might already exist
2. **Search codebase** - Don't duplicate existing functionality
3. **Follow pipeline pattern** - Most features fit into existing steps
4. **Update all docs** - README, user guides, architecture docs
5. **Add tests** - Unit test + integration test

### When Asked to Fix Bugs
1. **Reproduce first** - Understand the issue
2. **Check known issues** - Might already be documented
3. **Test with real course** - Don't rely on dry-run alone
4. **Verify with watch mode** - Incremental sync can behave differently
5. **Update DEVELOPMENT.md** - Log the fix

### When Asked to Debug
1. **Check caches** - Many issues are stale cache
2. **Read logs** - Scripts print detailed progress
3. **Run dry-run first** - See what would happen
4. **Check Canvas directly** - Verify API responses
5. **Clear metadata** - Delete `_course_metadata/` to start fresh

### Code Style Patterns
- **Imports:** Standard library → Third-party → Local
- **Logging:** Use `print()` with prefixes like `[sync]`, `[prune]`, `[export]`
- **Error handling:** Graceful degradation, clear error messages
- **Comments:** Explain WHY, not WHAT (code is self-documenting)
- **Security:** Always use `is_safe_path()`, `is_safe_url()` for user paths/URLs

---

## Key Files for Common Tasks

### To understand CLI commands:
→ Read `cli.py` (all commands defined here)

### To understand sync pipeline:
→ Read `watch_and_publish.py` (orchestrator)

### To understand content parsing:
→ Read `frontmatter_to_meta.py` (YAML → JSON conversion)

### To understand Canvas publishing:
→ Read `publish_all.py` (main upload logic)
→ Read `canvas_publish.py` (Canvas API abstractions)

### To understand modules:
→ Read `sync_modules.py` (module organization)

### To understand quizzes:
→ Read `sync_banks.py` (question bank imports)
→ Read `sync_quizzes.py` (quiz creation)

### To understand exports:
→ Read `export_cartridge.py` (IMSCC generation)

### To understand imports:
→ Read `import_cartridge.py` (IMSCC parsing)
→ Read `import_from_canvas.py` (Canvas API downloading)
→ Read `html_to_markdown.py` (HTML conversion)

### To understand course init / scaffolding:
→ Read `scaffold_course.py`

### To understand validation:
→ Read `validate.py`

### To understand error messages:
→ Read `errors.py` (all custom exception classes)

### To understand security:
→ Read `security_utils.py` (path validation, SSRF protection)
→ Read `99-SECURITY-AUDIT-V2.md` (comprehensive audit)

---

## Glossary of Key Terms

- **Canvas** - Learning Management System (LMS) by Instructure
- **IMSCC** - IMS Common Cartridge file format (.imscc files are ZIP archives)
- **QTI** - Question & Test Interoperability format for quizzes
- **Frontmatter** - YAML metadata block at top of markdown files
- **Content Item** - Generic term for pages, assignments, quizzes, etc.
- **Module** - Canvas organizational container (like folders)
- **Question Bank** - Pool of quiz questions
- **Outcome** - Learning objective (CLO = Course Learning Outcome)
- **Rubric** - Grading criteria with point values
- **Asset** - Media file (image, video, PDF, etc.)
- **Registry** - Asset Registry system for Canvas URL tracking
- **Derived File** - Temporary file (meta.json, source.md) generated during sync
- **Work File** - Another term for derived files (cleaned up after sync)
- **Prune** - Delete orphaned Canvas content not in local files
- **Watch Mode** - Auto-sync when files change
- **Dry Run** - Preview mode (no actual changes)
- **Content Hash** - MD5 hash of file content for deduplication

---

## Project Status

**Maturity:** Production-ready
**Version:** Evolving (no formal releases yet)
**Active Development:** Yes
**Security:** Hardened (audit v3 complete)
**Documentation:** Comprehensive (but has gaps - see above)
**Testing:** In progress (pytest framework being added)

---

## Quick Reference: Where Things Are

```
/Users/dale/zaphod-dev/
├── README.md                           # Project overview
├── CLAUDE-ONBOARDING.md                # This file
├── docs/changelogs/                    # Session changelogs
├── tests/                              # Test files
└── zaphod/                             # Main source code
    ├── cli.py                          # CLI interface
    ├── watch_and_publish.py            # Watch mode
    ├── frontmatter_to_meta.py          # Parsing
    ├── publish_all.py                  # Publishing
    ├── sync_*.py                       # Specialized syncs (banks, quizzes, modules, rubrics, clo)
    ├── prune_*.py                      # Cleanup (canvas_content, quizzes)
    ├── export_cartridge.py             # IMSCC export
    ├── import_*.py                     # Import features (cartridge, from_canvas)
    ├── scaffold_course.py              # zaphod init scaffolding
    ├── validate.py                     # zaphod validate
    ├── asset_registry.py               # URL tracking
    ├── video_transcode.py              # Pre-upload transcoding
    ├── canvas_client.py                # API client
    ├── security_utils.py               # Security functions
    ├── config_utils.py                 # Config loading (zaphod.yaml)
    ├── errors.py                       # Custom exceptions
    ├── icons.py                        # CLI output icons
    ├── 00-README.md                    # Internal doc index
    ├── 01-ARCHITECTURE.md              # Architecture docs
    ├── 02-DECISIONS.md                 # Design decisions
    ├── 03-GLOSSARY.md                  # Term definitions
    ├── 04-KNOWN-ISSUES.md              # Known issues
    ├── 05-QUICK-START.md               # Quick start for devs
    ├── 06-IDEAS.md                     # Future ideas
    ├── 07-TODO.md                      # Pending work
    ├── 08-DEPRECATED.md                # Removed features
    ├── 99-SECURITY-AUDIT-V2.md         # Security audit
    └── user-guide/                     # User documentation
        ├── 00-overview.md
        ├── 08-assets.md                # Assets + video quality presets
        ├── 10-pipeline.md              # Sync pipeline (all 11 steps)
        ├── 12-cli-reference.md         # CLI + zaphod.yaml config ref
        ├── 14-import-export.md         # Import/export + round-trip
        ├── 15-asset-registry.md        # Asset Registry reference
        ├── 15-file-layout.md           # Course directory layout
        └── 16-asset-workflow.md        # Asset workflow guide
```

---

## When You Need to Get Up to Speed Quickly

**Read these files in this order:**

1. **This file** (`CLAUDE-ONBOARDING.md`) - You're reading it!
2. **`README.md`** - User-facing overview
3. **`zaphod/01-ARCHITECTURE.md`** - Technical architecture
4. **`zaphod/04-KNOWN-ISSUES.md`** - Current limitations
5. **`docs/changelogs/`** - Recent session logs if you need history
6. **Specific user guide** for the feature you're working on

**Or ask the user:** "Point me to the specific feature/file you want me to work on, and I'll explore from there."

### When Auditing Documentation

**ALWAYS check changelogs first!** They document:
- Recent features that may not be in user guides yet
- Testing results (like 98% round-trip fidelity)
- Known limitations
- What actually works vs what's planned

**Common mistakes to avoid:**
1. ❌ Assuming a feature doesn't exist because you can't find the obvious implementation
   - Example: Templates are in `canvas_publish.py`, not a separate file
2. ❌ Not reading changelogs before claiming something isn't implemented
   - Example: Round-trip testing was completed and documented in changelog
3. ❌ Trusting README over actual code
   - README may lag behind implementation
4. ❌ Not checking all variations of a feature name
   - Example: "content/" vs "pages/" - both supported with fallback logic

---

## Final Notes

### Critical Principles

- **Local files are ALWAYS the source of truth** - Never edit in Canvas
- **Derived files (meta.json, source.md) are temporary** - Never commit to Git
- **Asset Registry keeps source files pure** - Canvas URLs tracked separately
- **Pipeline order matters** - prune_canvas_content.py must run AFTER modules
- **Caches are helpers, not truth** - Delete to rebuild when in doubt
- **Security is paramount** - Always use validation functions

### Round-Trip Editing (IMPORTANT!)

- **98%+ fidelity achieved** - Production-ready as of Feb 6, 2026
- **Templates ARE implemented** - Fully functional in canvas_publish.py
- **Quiz metadata preserved** - All settings, descriptions, questions intact
- **Code blocks work** - Language hints lost (Canvas limitation), but code displays
- **Nested lists require 4 spaces** - Python-Markdown requirement, not a bug
- **Export uses index.md** - Always has clean local refs, never Canvas URLs
- **Cartridges are portable** - Work across any Canvas instance

### Recent Testing

- Comprehensive round-trip tested with real course (Feb 2026)
- 6 major issues found and fixed
- All content types tested and verified
- Known limitations documented and acceptable
- See `docs/changelogs/CHANGELOG-2026-02-06.md` for complete details

---

**This document will be updated as the project evolves. Last verified: February 7, 2026**
