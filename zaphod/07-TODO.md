# To Do List

> Active development tasks. See `IDEAS.md` for future enhancements under consideration.

---

## Completed ✅

### January 2026

- [x] **Quiz ecosystem overhaul**
  - Two-layer model: banks (*.bank.md) → quizzes (*.quiz/)
  - Content-hash caching for banks and quizzes
  - Quiz folders as first-class content (alongside pages/assignments)
  - Bank name from frontmatter (`bank_name:`)

- [x] **Module inference from directory structure**
  - NEW: `.module` suffix pattern (`01-Week 1.module/`)
  - LEGACY: `module-` prefix still supported
  - Numeric prefix for ordering (strips prefix from module name)
  - Order inference when no `module_order.yaml`

- [x] **CLI improvements**
  - `zaphod sync --dry-run` preview mode
  - `zaphod sync --no-prune` skip cleanup
  - `zaphod new --type quiz` scaffold support
  - `zaphod list --type quiz` filter
  - Fixed `list` command name shadowing Python builtin

- [x] **Prune enhancements**
  - Quiz awareness (doesn't delete quiz-backed assignments)
  - `meta.json` added to auto-cleaned work files
  - Empty module protection for `.module` folders

- [x] **Security hardening**
  - Replaced all `exec()` credential loading with safe parsing
  - Environment variable support for credentials
  - Path traversal protection in CLI
  - Request timeouts on all API calls
  - File permission checks for credentials

- [x] **Asset handling**
  - Subfolder resolution in `assets/`
  - Content-hash caching for all uploads
  - `{{video:...}}` placeholder replacement

- [x] **Configuration**
  - `zaphod.yaml` support for course_id
  - Priority: env → zaphod.yaml → defaults.json

- [x] **Common Cartridge export** (`export_cartridge.py`)
  - Exports to IMS CC 1.3 format
  - Includes pages, assignments, quizzes, outcomes, modules

### Earlier

- [x] Initial sync on watch startup
- [x] Unicode cleanup in Python files
- [x] Incremental processing via `ZAPHOD_CHANGED_FILES`
- [x] Rubric shared rows and `{{rubric_row:...}}`

---

## In Progress 🔄

### Common Cartridge Export Issues

**Problem:** Export produces files but import into Canvas fails.

**Status:** Investigating CC compliance issues

**Tasks:**
- [ ] Test import into fresh Canvas course
- [ ] Validate manifest against CC 1.3 schema
- [ ] Check QTI assessment format
- [ ] Review Canvas-specific extensions

---

### Documentation Update

**Status:** In progress (this session)

**Tasks:**
- [x] Update ARCHITECTURE.md with current functionality
- [x] Create DEPRECATED.md for old scripts
- [x] Create IDEAS.md for future enhancements
- [x] Update TODO.md (this file)
- [ ] Review and update user guide (00-15 files)

---

## Planned 📋

### Testing Infrastructure

**Priority:** High
**Estimate:** 2-3 days

- [ ] Set up pytest framework
- [ ] Unit tests for quiz parsing
- [ ] Unit tests for frontmatter processing
- [ ] Integration tests with mock Canvas
- [ ] CI/CD pipeline

---

### Validation Command Enhancement

**Priority:** Medium
**Estimate:** 1 day

- [ ] Validate bank_id references exist
- [ ] Validate module names are consistent
- [ ] Validate asset file existence
- [ ] Add `--strict` mode

---

### Watch Mode Improvements

**Priority:** Low
**Estimate:** 1 day

- [ ] Better handling of file renames
- [ ] Debounce improvements
- [ ] Status display during sync

---

## Known Issues 🐛

### Module Reordering Inconsistent

**Problem:** Sometimes modules don't reorder correctly.
**Cause:** Canvas API timing issues.
**Workaround:** Check Canvas after sync, manually adjust if needed.

### Bank Migration Timeouts

**Problem:** Large banks can timeout during Canvas processing.
**Mitigation:** Added timeout warning and post-migration verification.
**Future:** Consider chunking large banks.

### Video Cache Filename-Based

**Problem:** Same filename with different content uses cache.
**Status:** FIXED - Now uses content-hash caching.

---

## Backlog (Not Scheduled)

See `IDEAS.md` for full list. Key items:

1. Rename `pages/` to `content/`
2. New Quizzes support (blocked by Canvas API)
3. CC import capability
4. Web UI for non-technical users
5. Multi-course workspaces

---

*Last updated: January 2026*
