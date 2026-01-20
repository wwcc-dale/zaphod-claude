# To Do List

## Completed
- [x] **Asset manifest and hydrate** - Large Media files can be ignored by git but compiled to a manifest. Files can be stored in a shared web location from which other users may rehydrate media files. 
- [x] **Asset subfolder resolution** - Users can organize assets in subdirectories
  - Auto-discovers assets from any subfolder in `assets/`
  - Supports explicit paths like `../assets/images/logo.png`
  - Warns and fails on duplicate filenames (requires explicit path)
  - Fixed path resolution with `../` relative paths using `.resolve()`
- [x] **Module inference from directory** - `module-` prefix convention
  - Directories like `pages/module-Week 1/` auto-assign contents to "Week 1" module
  - Explicit `modules:` in frontmatter always overrides
  - Reduces repetitive frontmatter for module-organized courses
- [x] **Content-hash caching** - All upload functions now use content hash
  - Cache key format: `{course_id}:{filename}:{content_hash}`
  - Updated files with same name get re-uploaded (different hash)
  - Same filename in different locations handled correctly
  - Applied to: video uploads, local assets, bulk uploads
- [x] **Initial sync on watch startup** - Full sync runs when watch mode starts
- [x] **Prune cleanup** - `meta.json` added to auto-cleaned work files
- [x] **Simplified prune in watch** - Uses script defaults, no extra env vars needed
- [x] **Unicode cleanup** - Fixed corrupted unicode in all Python files

## In Progress
- [ ] **Common Cartridge export** (`export_cartridge.py`) - Exports full course to .imscc format. ***(Produces exports but unsuccessful import)***
- [ ] **Outcome ratings file** with replacement pattern {{ratings:default}} or would it be better to simply rely on an extension of includes? ***(It's unclear what was intended here)***

## Future Enhancements
1. Rename `pages/` to `content/` for clarity (contains pages, assignments, links, files)
2. Add Canvas-specific extensions to CC export (discussion topics, announcements)
3. Add QTI 2.1 support as alternative to QTI 1.2
4. Add CC import capability (reverse of export)
5. Add selective export (--modules flag to export only specific modules)
6. Add export validation against CC 1.3 schema
7. Testing infrastructure - pytest tests for core functions
8. Web UI for non-technical users
