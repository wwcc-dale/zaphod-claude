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
- Round-trip conversion (Canvas → Local → Canvas)
- Automatic export after sync operations
- Offline export without Canvas connection

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

### Offline Export

Export without requiring Canvas credentials:

```bash
zaphod export --offline
```

This mode:
- Uses only local markdown files
- Doesn't fetch Canvas metadata
- Perfect for air-gapped environments

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
- ✅ Pages (HTML → Markdown)
- ✅ Assignments (with descriptions, rubrics, settings)
- ✅ Quizzes (structure and metadata)
- ✅ Modules (organization preserved)
- ✅ Learning Outcomes
- ⚠️ Question banks (limited by Canvas API)
- ❌ Student submissions (not accessible)

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
- ✅ Pages (HTML → Markdown)
- ✅ Assignments (with rubrics)
- ✅ Quizzes (QTI → Zaphod format)
- ✅ Web links
- ✅ Module structure from manifest
- ✅ Embedded media files
- ⚠️ Canvas-specific features may not transfer

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
- Preserves formatting and structure
- Handles tables, code blocks, lists
- Extracts media references
- Removes template headers/footers

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

# 2. Export as template
zaphod export --offline --output course-template.imscc

# 3. Distribute to instructors
# Each instructor imports and customizes:
zaphod import course-template.imscc --output ./my-section
```

### Workflow 4: Round-Trip Testing

Verify that export/import preserves your content:

```bash
# 1. Export current state
zaphod export --output test.imscc

# 2. Import to new directory
zaphod import test.imscc --output ./roundtrip

# 3. Compare
diff -r content/ roundtrip/content/

# 4. Check for differences
git diff --no-index content/ roundtrip/content/
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
# Solution: Install html2text
pip install html2text

# Or use markdownify as alternative
pip install markdownify
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

✅ **Bidirectional sync** between Canvas and local files
✅ **Format conversion** (HTML ↔ Markdown)
✅ **Portable exports** (IMSCC Common Cartridge)
✅ **Automated backups** with sync integration
✅ **Course migration** between Canvas instances
✅ **Collaborative development** with version control

This enables a complete closed-loop workflow for Canvas course management with full local control.
