# Zaphod — App Compatibility Document

> Companion document: `zaphod-app/COMPAT.md`
> Last converged: initial (pre-v0.1)

This document tracks the interface between `zaphod` (the CLI/library) and `zaphod-app`
(the desktop app that wraps it). It exists to make convergence intentional rather than accidental.

---

## Convergence History

| zaphod-dev Version | App Version | Date       | Notes                          |
|-------------------|-------------|------------|--------------------------------|
| (pre-v0.1)        | (pre-v0.1)  | 2026-02    | Initial — subprocess boundary established |

---

## How zaphod-app Consumes This Codebase

`zaphod-app` interacts with `zaphod` in two ways:

**1. Subprocess (current)**
The app shells out to `cli.py` for sync and validate operations:
```
zaphod sync       →  POST /api/sync
zaphod validate   →  POST /api/validate
zaphod sync --watch → POST /api/watch
```

**2. Direct file management (always)**
The app reads and writes course files directly (it does not call the CLI for these):
- `zaphod.yaml` — course settings
- `modules/module_order.yaml` — module ordering
- `position:` frontmatter in `index.md` — item ordering
- `shared/variables.yaml` — template variables

---

## Conventions the App Relies On

The following are treated as a **stable contract**. Changes here require a matching update in `zaphod-app/src-python/api/course.py`. Flag these in commit messages and bump the version.

### Folder/file conventions

- Content items live in `pages/` (zaphod-dev) / `content/` (as seen by the app — same path)
- Each item is a folder with a typed suffix: `.page`, `.assignment`, `.quiz`, `.link`, `.file`, `.module`
- Each item folder contains `index.md` as the primary content file
- Companion files (rubrics, media) live alongside `index.md` in the same folder

### Item ordering priority (must stay in sync with `sync_modules.py`)

1. `position:` key in `index.md` frontmatter
2. Numeric folder prefix (`01-`, `02-`, etc.)
3. Alphabetical fallback

### Module ordering priority

1. `modules/module_order.yaml`
2. Numeric prefix on `.module` folders
3. Alphabetical fallback

### Frontmatter keys read by the app

| Key       | Purpose                  |
|-----------|--------------------------|
| `title`   | Content item display name |
| `position`| Item sort order           |
| `name`    | Module display name       |

### zaphod.yaml keys read/written by the app

`course_name`, `course_id`, `api_url`, `term`

---

## Versioning Approach

When a set of changes is stable enough to converge:

1. Tag this repo: `git tag v0.x.0`
2. Verify `zaphod-app` subprocess calls work against the tag
3. Update the convergence history table in both `COMPAT.md` files
4. Tag `zaphod-app` with the same version number

No strict schedule — converge when a meaningful set of features has stabilized.
