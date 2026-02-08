# Import & Export - Closed-Loop Course Management

This guide covers Zaphod's bidirectional import/export system, enabling you to move courses between Canvas, local markdown files, and Common Cartridge format.

---

## Table of Contents

- [Overview](#overview)
- [Export Features](#export-features)
- [Import Features](#import-features)
- [Common Workflows](#common-workflows)
- [File Formats](#file-formats)
- [Troubleshooting](#troubleshooting)

---

## Overview

Zaphod provides a complete closed-loop system for managing Canvas courses:

```
Canvas Course
     ↓ (import)
Local Markdown Files
     ↓ (sync)
Canvas Course
     ↓ (export)
IMSCC Cartridge
     ↓ (import)
Local Markdown Files
```

**Key Capabilities:**
- Export courses to Common Cartridge (IMSCC) format
- Import courses from Canvas by ID
- Import courses from IMSCC cartridge files
- **98%+ fidelity round-trip** conversion (Canvas → Local → Canvas)
- Automatic export after sync operations
- Works offline (no Canvas credentials needed for export)
- Asset Registry keeps source files clean (local refs only)

---

## Export Features

### Basic Export

Export your local course to Common Cartridge format:

```bash
zaphod export
```

This creates an `.imscc` file in `_course_metadata/exports/` with a timestamp:
```
_course_metadata/exports/20260204_153045_export.imscc
```

### Custom Output Path

Specify where to save the export:

```bash
zaphod export --output my-course.imscc
zaphod export -o ~/Desktop/course_backup.imscc
```

### Custom Title

Override the course title in the export:

```bash
zaphod export --title "Spring 2026 - Chemistry 101"
```

### Export After Sync

Automatically export after each sync operation:

```bash
# Single sync with export
zaphod sync --export

# Watch mode with auto-export
zaphod sync --watch --export
```

This is useful for:
- Creating automatic backups
- Generating distribution packages
- Testing round-trip conversion

### Offline Mode

Export works offline by default - it only reads local markdown files and doesn't fetch Canvas metadata. No special flag needed:

```bash
zaphod export  # Already works offline
```

This means exports:
- Use only local files (index.md)
- Don't require Canvas credentials
- Work in air-gapped environments
- Are portable across Canvas instances

### Watch Mode Integration

For continuous export during development:

```bash
zaphod sync --watch --export
```

Every time you save a file, Zaphod will:
1. Sync changes to Canvas
2. Export to timestamped cartridge
3. Wait for next change

---

## Import Features

### Import from Canvas

Download an entire Canvas course by ID:

```bash
zaphod import 12345
```

This will:
1. Fetch all pages, assignments, quizzes, modules
2. Convert HTML to markdown
3. Generate YAML frontmatter
4. Create local directory structure
5. Save rubrics as YAML files
6. Extract learning outcomes

**Specify output directory:**

```bash
zaphod import 12345 --output ./my-course
cd my-course
```

**What gets imported:**
- ✅ Pages (HTML → Markdown, 98% fidelity)
- ✅ Assignments (descriptions, rubrics, points, due dates)
- ✅ Quizzes (questions, answers, all metadata)
- ✅ Quiz descriptions (instructions, formatted text)
- ✅ Quiz settings (time limits, attempts, shuffle, points)
- ✅ Modules (organization and ordering preserved)
- ✅ Learning Outcomes
- ⚠️ Question banks (limited by Canvas API)
- ❌ Student submissions (not accessible via API)

### Import from Cartridge

Import from an IMSCC Common Cartridge file:

```bash
zaphod import course.imscc
zaphod import course.imscc --output ./imported-course
```

This will:
1. Extract and parse the IMSCC zip file
2. Read the manifest.xml
3. Convert HTML to markdown
4. Parse QTI quiz format
5. Recreate directory structure
6. Extract embedded media files

**What gets imported:**
- ✅ Pages (HTML → Markdown, 98% fidelity)
- ✅ Assignments (with rubrics and all settings)
- ✅ Quizzes (QTI → Zaphod format, 100% questions)
- ✅ Quiz descriptions and instructions (preserved via QTI objectives)
- ✅ Quiz metadata (time limits, attempts, shuffle, points)
- ✅ Web links
- ✅ Module structure from manifest
- ✅ Embedded media files (extracted to assets/)
- ⚠️ Code language hints not preserved (Canvas limitation)
- ⚠️ Some Canvas-specific features may not transfer

### HTML to Markdown Conversion

Both import methods automatically convert HTML to clean markdown:

**Before (Canvas HTML):**
```html
<div class="user_content">
  <h1>Week 1: Introduction</h1>
  <p>Welcome to the course!</p>
  <ul>
    <li>Read Chapter 1</li>
    <li>Complete assignment</li>
  </ul>
</div>
```

**After (Markdown):**
```markdown
# Week 1: Introduction

Welcome to the course!

- Read Chapter 1
- Complete assignment
```

The converter:
- Strips Canvas wrapper divs
- Preserves formatting and structure (98% fidelity)
- Handles tables, code blocks, nested lists
- Converts `[code]` tags to fenced code blocks (` ``` `)
- Extracts media references to local paths
- Removes template headers/footers
- Uses html2text with optimized settings
- Normalizes list indentation (4 spaces for nesting)

---

## Common Workflows

### Workflow 1: Course Migration

Move a course from one Canvas instance to another:

```bash
# 1. Import from source Canvas
zaphod import 12345 --output ./migrated-course
cd migrated-course

# 2. Edit zaphod.yaml with new Canvas credentials
nano zaphod.yaml
# Update: course_id, canvas_api_url, canvas_api_key

# 3. Preview changes
zaphod validate
zaphod sync --dry-run

# 4. Sync to destination Canvas
zaphod sync
```

### Workflow 2: Backup and Restore

Create versioned backups of your course:

```bash
# Daily backup
zaphod sync --export
# Creates: _course_metadata/exports/20260204_090000_export.imscc

# Restore from backup
zaphod import _course_metadata/exports/20260204_090000_export.imscc \
  --output ./restored-course
```

### Workflow 3: Course Template Distribution

Create reusable course templates:

```bash
# 1. Create and polish a course
cd template-course
zaphod sync

# 2. Export as portable template (works offline)
zaphod export --output course-template.imscc

# 3. Distribute to instructors
# Each instructor imports and customizes:
zaphod import course-template.imscc --output ./my-section
cd my-section

# 4. Customize and sync to their Canvas
nano zaphod.yaml  # Set their course_id
zaphod sync
```

### Workflow 4: Round-Trip Verification

Verify 98%+ fidelity preservation:

```bash
# 1. Export current state
zaphod export --output test.imscc

# 2. Import to new directory
zaphod import test.imscc --output ./roundtrip

# 3. Compare structure
diff -r content/ roundtrip/content/ | grep -v "^Only in"

# 4. Check content differences (expect minor formatting only)
git diff --no-index content/ roundtrip/content/

# Expected minor differences:
# - Boolean capitalization (true → True)
# - List spacing normalization
# - Code blocks missing language hints
# - Minor whitespace adjustments

# Unexpected differences (investigate):
# - Missing content
# - Changed questions/answers
# - Lost rubric criteria
# - Broken module structure
```

### Workflow 5: Collaborative Development

Share course development with team members:

```bash
# Developer A: Export from Canvas
zaphod import 12345 --output ./shared-course
cd shared-course
git init
git add .
git commit -m "Initial course import"
git push origin main

# Developer B: Clone and work
git clone repo-url
cd shared-course
# Make changes to markdown files
zaphod sync --dry-run
zaphod sync

# Developer A: Pull changes
git pull
zaphod sync  # Updates their Canvas
```

---

## Round-Trip Fidelity

Zaphod achieves **98%+ fidelity** in round-trip conversion (tested February 2026).

### What's Preserved (100%)

| Content Type | Fidelity | Notes |
|--------------|----------|-------|
| **Assignments** | 100% | All metadata, points, due dates, settings |
| **Rubrics** | 100% | All criteria, ratings, points |
| **Quizzes (questions)** | 100% | All question types and answers |
| **Quizzes (metadata)** | 100% | Time limits, attempts, shuffle settings |
| **Modules** | 100% | Organization and ordering |
| **Nested Lists** | 100% | With 4-space indentation |

### What's Mostly Preserved (95-98%)

| Content Type | Fidelity | Minor Differences |
|--------------|----------|-------------------|
| **Pages** | 98% | List indentation may normalize |
| **Quiz Descriptions** | 95% | Minor HTML→Markdown formatting |
| **Code Blocks** | 95% | Work perfectly, but language hints lost |

### Asset Registry & Clean Source Files

The **Asset Registry** system ensures your source files stay clean:

**How it works:**
1. **Local files** contain relative asset references: `![Photo](../../assets/photo.jpg)`
2. **Asset Registry** tracks: `assets/photo.jpg` → `https://canvas.../files/456/preview`
3. **During sync**: Canvas URLs inserted in-memory only (source files never mutated)
4. **During export**: index.md used (has clean local refs)
5. **Result**: Exported cartridges are portable, work on any Canvas instance

**Why this matters:**
- ✅ Version control shows real content changes (not Canvas URL noise)
- ✅ Cartridges work across Canvas instances
- ✅ Perfect round-trip: export → import → local files match original
- ✅ No Canvas-specific URLs pollute your markdown

See [Asset Registry Guide](15-asset-registry.md) for details.

### Known Acceptable Limitations

These minor differences don't affect functionality:

1. **Code block language hints lost**
   - Fenced blocks work: ` ```code here``` `
   - But language specifier lost: ` ```python` → ` ``` `
   - Reason: Canvas HTML doesn't export language class
   - Impact: No syntax highlighting hint, but code displays correctly

2. **Boolean formatting changes**
   - YAML: `true` may become `True`
   - Both valid YAML, no functional difference
   - Python's YAML library uses capitalized booleans

3. **Nested lists require 4 spaces**
   - Python-Markdown library requirement
   - Use 4 spaces for nested items:
     ```markdown
     - Parent item
         - Child item (4 spaces)
         - Another child
     ```
   - 2-space indentation won't nest properly

4. **List indentation normalization**
   - HTML→Markdown may adjust spacing slightly
   - Structure preserved, formatting may differ
   - Example: `  * ` might become `- `

5. **Template stripping**
   - Canvas templates removed during import
   - Clean content extracted
   - Apply Zaphod templates after import if desired

### Testing Round-Trip

Verify your content round-trips correctly:

```bash
# 1. Export current state
zaphod export --output test.imscc

# 2. Import to new directory
zaphod import test.imscc --output ./roundtrip

# 3. Compare (expect 98%+ match)
diff -r content/ roundtrip/content/

# 4. Check what changed
git diff --no-index content/ roundtrip/content/
```

**Expected differences:**
- List spacing normalization
- Boolean capitalization (`true` → `True`)
- Code blocks missing language hints
- Minor whitespace differences

**Unexpected differences** (report if found):
- Content missing
- Questions lost
- Rubric criteria changed
- Module structure broken

---

## File Formats

### Common Cartridge (IMSCC)

Zaphod exports to IMS Common Cartridge 1.3 format, which is compatible with:

- ✅ Canvas LMS
- ✅ Moodle
- ✅ Blackboard
- ✅ Brightspace (D2L)
- ✅ Sakai
- ✅ Other CC 1.3 compliant systems

**IMSCC Structure:**
```
course_export.imscc (ZIP file)
├── imsmanifest.xml          # Course structure
├── web_resources/           # Pages and assignments
│   ├── page_001/
│   │   └── content.html
│   ├── assignment_001/
│   │   ├── assignment.xml
│   │   ├── content.html
│   │   └── rubric.xml
│   └── assets/              # Media files
├── assessments/             # Quizzes (QTI format)
│   └── quiz_001/
│       └── assessment.xml
└── outcomes/                # Learning outcomes
```

### Zaphod Local Format

After import, your course will have this structure:

```
imported-course/
├── zaphod.yaml              # Configuration
├── content/                 # All course content
│   ├── 01-welcome.page/
│   │   └── index.md
│   ├── 02-assignment.assignment/
│   │   ├── index.md
│   │   └── rubric.yaml
│   └── 03-quiz.quiz/
│       └── index.md
├── shared/
│   └── variables.yaml       # Course variables
├── modules/
│   └── module_order.yaml    # Module organization
├── outcomes/
│   └── outcomes.yaml        # Learning outcomes
├── question-banks/          # Quiz question banks
├── assets/                  # Media files
└── _course_metadata/        # System state
    └── exports/             # Exported cartridges
```

---

## Advanced Features

### Environment Variables

Control export behavior via environment variables:

```bash
# Auto-export after sync (watch mode)
export ZAPHOD_EXPORT_ON_SYNC=1
zaphod sync --watch

# Disable auto-export
unset ZAPHOD_EXPORT_ON_SYNC
```

### Programmatic Usage

Import the modules directly:

```python
from zaphod.import_from_canvas import import_canvas_course
from zaphod.import_cartridge import import_cartridge
from zaphod.html_to_markdown import convert_canvas_html_to_markdown

# Import from Canvas
import_canvas_course(
    course_id=12345,
    output_dir=Path("./my-course"),
    skip_quizzes=False
)

# Import from cartridge
import_cartridge(
    cartridge_path=Path("course.imscc"),
    output_dir=Path("./imported"),
    clean=False
)

# Convert HTML to Markdown
markdown, media = convert_canvas_html_to_markdown(
    html_content="<h1>Hello</h1>",
    course_root=Path("./course")
)
```

### HTML Conversion Options

The HTML to Markdown converter can be tested standalone:

```bash
# Test conversion
python -m zaphod.html_to_markdown < input.html > output.md

# Extract media references
python -m zaphod.html_to_markdown --extract-media input.html

# Strip templates
python -m zaphod.html_to_markdown --strip-templates input.html
```

---

## Troubleshooting

### Import Issues

**Problem:** Import fails with "No write permissions"

```bash
# Solution: Check output directory permissions
ls -ld ./output-dir
chmod u+w ./output-dir
```

**Problem:** HTML not converting to markdown

```bash
# Solution: Ensure html2text is installed
pip install html2text

# This is required for import functionality
# Check if installed:
python -c "import html2text; print('html2text installed')"
```

**Problem:** Canvas API timeout

```bash
# Solution: Large courses may timeout. Try:
# 1. Import without quizzes first
zaphod import 12345 --skip-quizzes --output ./course

# 2. Increase timeout (if supported by Canvas)
export CANVAS_API_TIMEOUT=300
zaphod import 12345
```

### Export Issues

**Problem:** Export creates empty cartridge

```bash
# Solution: Ensure content exists
ls -R content/

# Run sync first
zaphod sync
zaphod export
```

**Problem:** Canvas rejects imported cartridge

```bash
# Solution: Check format compatibility
# Canvas may not support all IMSCC 1.3 features
# Try importing to a test course first
```

**Problem:** Watch mode export not triggering

```bash
# Solution: Check environment variable
echo $ZAPHOD_EXPORT_ON_SYNC

# Or use CLI flag directly
zaphod sync --watch --export
```

### Conversion Issues

**Problem:** Markdown formatting lost

```bash
# Solution: Check HTML source quality
# Some Canvas HTML may have malformed markup
# Manual cleanup may be needed after import
```

**Problem:** Media files missing after import

```bash
# Solution: Media files may be:
# 1. Stored in Canvas Files (not embedded)
# 2. External links (won't be downloaded)
# 3. Protected by permissions

# Check Canvas file permissions
# Download manually if needed
```

**Problem:** Module structure not preserved

```bash
# Solution: Check modules/module_order.yaml
cat modules/module_order.yaml

# Edit if needed
nano modules/module_order.yaml
```

### Round-Trip Issues

**Problem:** Content differs after round-trip

```bash
# Solution: Some conversions are lossy:
# - HTML → Markdown → HTML may differ
# - Canvas-specific features won't transfer
# - Templates are stripped/reapplied

# Use diff to identify differences
diff -r original/ roundtrip/
```

---

## Best Practices

### 1. Always Test First

```bash
# Preview before making changes
zaphod sync --dry-run
zaphod validate
```

### 2. Use Version Control

```bash
# Track changes
git init
git add .
git commit -m "Imported from Canvas"

# Track exports
git add _course_metadata/exports/
git commit -m "Backup: $(date)"
```

### 3. Regular Backups

```bash
# Daily export
zaphod sync --export

# Keep dated backups
cp _course_metadata/exports/latest.imscc \
   backups/course_$(date +%Y%m%d).imscc
```

### 4. Review After Import

After importing, always:
1. Check `content/` structure
2. Verify `modules/module_order.yaml`
3. Review `rubrics/` if present
4. Test with `zaphod validate`
5. Preview with `zaphod sync --dry-run`

### 5. Handle Large Courses

For courses with 100+ items:
```bash
# Import in stages
zaphod import 12345 --skip-quizzes -o ./course
# Review and test
# Then import quizzes separately if needed
```

---

## Examples

### Example 1: Import and Customize

```bash
# Import existing Canvas course
zaphod import 12345 --output ./my-course
cd my-course

# Customize in markdown
find content/ -name "index.md" -exec sed -i 's/old/new/g' {} +

# Add templates
mkdir -p templates/default
echo "<header>My Course</header>" > templates/default/header.html

# Sync changes back to Canvas
zaphod sync
```

### Example 2: Multi-Section Distribution

```bash
# Create master course
zaphod import 12345 --output ./master-course
cd master-course

# Export as template
zaphod export --offline --output course-template.imscc

# For each section
for section in 101 102 103; do
  zaphod import course-template.imscc --output ./section-$section
  cd section-$section
  # Customize section-specific content
  echo "course_id: ${section}000" >> zaphod.yaml
  zaphod sync
  cd ..
done
```

### Example 3: Content Review Workflow

```bash
# Import for review
zaphod import 12345 --output ./review
cd review

# Generate HTML preview
for md in content/**/*.page/index.md; do
  pandoc "$md" -o "${md%.md}.html"
done

# Review in browser
open content/**/index.html

# Make edits in markdown
nano content/01-welcome.page/index.md

# Sync approved changes
zaphod sync
```

---

## See Also

- [Sync Guide](06-syncing.md) - Publishing to Canvas
- [Templates](13-templates.md) - Header/footer templates
- [Modules](08-modules.md) - Module organization
- [Rubrics](11-rubrics.md) - Grading rubrics

---

## Summary

Zaphod's import/export system provides:

✅ **98%+ round-trip fidelity** (tested and verified)
✅ **Bidirectional sync** between Canvas and local files
✅ **Clean source files** (Asset Registry keeps local refs)
✅ **Format conversion** (HTML ↔ Markdown, optimized)
✅ **Portable exports** (IMSCC Common Cartridge, works anywhere)
✅ **Complete metadata preservation** (quizzes, rubrics, settings)
✅ **Automated backups** with sync integration
✅ **Course migration** between Canvas instances
✅ **Collaborative development** with version control

This enables a complete closed-loop workflow for Canvas course management with full local control and near-perfect content preservation.
