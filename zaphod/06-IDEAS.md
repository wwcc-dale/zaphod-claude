# Ideas & Future Enhancements

> Ideas under consideration. When an idea is approved for implementation, move it to TODO.md.

---

## Content & Structure

### Rename `pages/` to `content/`

**Rationale:** The `pages/` directory contains pages, assignments, quizzes, links, and files - not just pages.

**Considerations:**
- Need backward compatibility (support both names)
- Update all documentation
- Update all scripts that reference `PAGES_DIR`

**Status:** Under consideration

---

### Nested Module Folders

**Idea:** Allow modules within modules for complex course structures.

```
pages/
├── 01-Unit 1.module/
│   ├── 01-Week 1.module/
│   │   └── intro.page/
│   └── 02-Week 2.module/
│       └── review.page/
```

**Challenges:**
- Canvas doesn't support nested modules
- Would need flattening logic
- May complicate module inference

**Status:** Under consideration

---

### Discussion Topics & Announcements

**Idea:** Add support for Canvas Discussions and Announcements as content types.

```
pages/
├── week1-discussion.discussion/
│   └── index.md
└── welcome.announcement/
    └── index.md
```

**Challenges:**
- Different Canvas API endpoints
- Discussion-specific features (threading, grading)
- CC export would need extensions

**Status:** Under consideration

---

## Quiz Enhancements

### New Quizzes Support

**Idea:** Add support for Canvas New Quizzes (beyond Classic).

**Challenges:**
- New Quizzes API is limited and different
- Item banks vs question banks
- Different question types

**Status:** Blocked by Canvas API limitations

---

### Quiz Item Analysis Import

**Idea:** Import quiz item analysis data for reporting.

**Potential:**
- Track question performance
- Identify problematic questions
- Inform bank updates

**Status:** Idea only

---

### Question Tagging/Categorization

**Idea:** Add tags to questions for filtering in banks.

```markdown
1. What is 2+2?
tags: [arithmetic, basic]
*a) 4
```

**Status:** Under consideration

---

## Export & Import

### CC Import Capability

**Idea:** Import Common Cartridge packages into Zaphod structure.

**Use cases:**
- Migrate from other LMS
- Import shared content packages
- Round-trip editing

**Status:** Under consideration

---

### QTI 2.1 Support

**Idea:** Add QTI 2.1 export alongside QTI 1.2.

**Benefits:**
- Better compatibility with modern LMS
- More question types supported

**Status:** Under consideration

---

### Selective Export

**Idea:** Export only specific modules or content types.

```bash
zaphod export --modules "Week 1,Week 2" --types page,quiz
```

**Status:** Under consideration

---

## Developer Experience

### Testing Infrastructure

**Idea:** Comprehensive pytest test suite.

**Scope:**
- Unit tests for parsing functions
- Integration tests for Canvas API
- Mock Canvas responses

**Status:** Planned for implementation

---

### Web UI for Non-Technical Users

**Idea:** Browser-based interface for managing courses.

**Features:**
- Visual content editor
- Drag-drop module organization
- Preview before publish

**Challenges:**
- Significant development effort
- Maintaining sync with file-based workflow

**Status:** Under consideration

---

### VS Code Extension

**Idea:** VS Code extension for Zaphod workflows.

**Features:**
- Syntax highlighting for frontmatter
- Snippets for content types
- Integrated sync commands
- Preview pane

**Status:** Idea only

---

## Validation & Safety

### Pre-Sync Validation

**Idea:** Validate all content before syncing to catch errors early.

```bash
zaphod validate --strict
```

**Checks:**
- Required frontmatter fields
- Valid module references
- Asset file existence
- Bank references valid

**Status:** Partially implemented (`validate.py` exists)

---

### Conflict Detection

**Idea:** Detect when Canvas content is newer than local.

**Workflow:**
1. Check Canvas timestamps before sync
2. Warn if Canvas is newer
3. Option to pull changes or force push

**Challenges:**
- Canvas API timestamp limitations
- Defining "conflict"

**Status:** Under consideration

---

### Backup Before Prune

**Idea:** Automatically backup content before deletion.

```bash
zaphod prune --backup
# Creates _backups/2026-01-25-prune.json
```

**Status:** Under consideration

---

## Performance

### Parallel Upload

**Idea:** Upload multiple files concurrently.

**Potential:**
- 3-5x faster bulk uploads
- Better utilization of API limits

**Challenges:**
- Canvas rate limiting
- Error handling complexity

**Status:** Under consideration

---

### Selective Sync

**Idea:** Sync only specific content on demand.

```bash
zaphod sync pages/intro.page/
zaphod sync --module "Week 1"
```

**Status:** Under consideration

---

## Multi-Course

### Multi-Course Workspaces

**Idea:** Manage multiple courses from one workspace.

```
workspace/
├── course-101/
├── course-102/
└── shared/
    └── includes/
```

**Features:**
- Shared includes across courses
- Batch operations
- Course templates

**Status:** Under consideration

---

### Course Templates

**Idea:** Create new courses from templates.

```bash
zaphod new-course --template programming-101
```

**Status:** Under consideration

---

## Integration

### GitHub Actions Integration

**Idea:** Official GitHub Action for CI/CD.

```yaml
- uses: zaphod/sync-action@v1
  with:
    course_id: ${{ secrets.COURSE_ID }}
    api_key: ${{ secrets.CANVAS_API_KEY }}
```

**Status:** Idea only

---

### Outcome Alignment Automation

**Idea:** Auto-align content with outcomes based on keywords/tags.

**Status:** Idea only

---

## Documentation

### Interactive Tutorial

**Idea:** Guided walkthrough for new users.

```bash
zaphod tutorial
```

**Status:** Idea only

---

### Video Documentation

**Idea:** Screen recordings of common workflows.

**Status:** Idea only

---

---

## Moving Ideas to TODO

When an idea is approved:
1. Add to `07-TODO.md` with clear scope
2. Add time estimate if known
3. Remove from this file or mark as "In Progress → TODO"

---

*Last updated: January 2026*
