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

| Key        | Location        | Purpose                                        |
|------------|-----------------|------------------------------------------------|
| `name`     | `index.md`      | Content item display name                      |
| `title`    | `module.yaml`   | Module display name                            |
| `position` | `index.md`      | Item sort order within its module              |
| `session`  | `index.md`      | Session number (int, template variable)        |
| `module`   | `index.md`      | Module number (int, from `.module` folder prefix, template variable) |
| `modules`  | `index.md`      | Explicit module membership list (legacy — not needed when item is inside a `.module` folder) |

`position:`, `session:`, and `module:` can be auto-stamped from folder names after import — see `zaphod reorder` below.

`title:` in `index.md` is accepted as a legacy alias for `name:` by both zaphod-dev
(`frontmatter_to_meta.py`) and zaphod-app. New content should always use `name:`.

### `type` is NOT required in frontmatter

Content type is inferred from the folder suffix (`.page`, `.assignment`, `.quiz`, `.link`,
`.file`) by `frontmatter_to_meta.py`. The `type:` key is **never required** in `index.md`.

If `type:` is present it must be a valid value — the validator will flag unknown types.

`zaphod-app` uses `validate.py` for validation, so this behaviour is shared automatically.

### zaphod.yaml keys read/written by the app

`course_name`, `course_id`, `api_url`, `term`

---

## Question Bank + Quiz Workflow

### The problem: Canvas auto-generates quizzes on bank import

When `sync_banks.py` imports a question bank via the QTI content migration API, Canvas
**automatically creates a quiz** with the same title as the bank. This is Canvas behaviour
that cannot be suppressed — it is a side-effect of the QTI `assessment` format.

These auto-generated quizzes must be deleted before the real quiz instances (defined in
`.quiz/` folders) are synced, otherwise they collide with or shadow the real ones.

### The solution: prune between banks and quizzes

The sync pipeline handles this automatically:

```
sync_banks.py          → upload .bank.md files to Canvas (Canvas auto-creates quizzes)
prune_quizzes.py       → delete all Canvas quizzes not backed by a local .quiz/ folder
sync_quizzes.py        → create real quiz instances linked to the banks by bank_id
```

`prune_quizzes.py` runs with `--quizzes-only` in the pipeline (skips bank pruning, which
requires an API endpoint Canvas does not reliably expose).

### Bank ID bootstrapping: manual once, automated after

Canvas does not expose bank IDs through its public API. The workflow to obtain them:

1. In Canvas: **Quizzes → Manage Question Banks** — save the full page HTML
2. Run `bank_scrape.py banks.html` from the course directory
   → writes `question-banks/bank-mappings.yaml` (filename → Canvas bank ID)
3. Quiz frontmatter references banks by filename: `bank: s1-foo.bank`
4. `sync_quizzes.py` reads `bank-mappings.yaml` at sync time and resolves IDs automatically

`bank-mappings.yaml` should be committed to the course repo. It only needs to be
regenerated if banks are re-imported (which changes their Canvas IDs).

### Quiz frontmatter for bank-linked quizzes

```yaml
question_groups:
  - bank: s1-javascript-basics.bank   # filename in question-banks/
    pick: 16                          # number of questions to draw
    points_per_question: 1
```

`bank_id:` may also be present (stamped by `apply_bank_ids.py` utility) — if both are
present, `bank_id:` takes priority. `bank_id:` is optional when `bank-mappings.yaml` exists.

### CLI commands

| Command | Effect |
|---------|--------|
| `zaphod sync` | Full pipeline including bank-generated quiz cleanup |
| `zaphod sync --no-prune` | Skip all prune steps (including quiz cleanup) |
| `zaphod sync --quizzes-only` | Run only quiz steps (prune + sync_quizzes) |
| `zaphod sync --quizzes-only --force-quizzes` | Re-instantiate all quizzes from scratch |
| `zaphod prune --quizzes` | Manually delete orphan + bank-generated quizzes |
| `zaphod prune --quizzes --dry-run` | Preview quiz deletions |
| `zaphod scrape banks <html_file>` | Extract bank IDs → `question-banks/bank-mappings.yaml` |
| `zaphod scrape outcomes <html_file>` | Extract outcome IDs → `outcomes/outcome-mappings.yaml` |

### What zaphod-app needs to expose

#### "Link Banks" setup step (after first bank import)

1. Prompt user to open Canvas → **Quizzes → Manage Question Banks** and save the page HTML
2. Accept the HTML file via file picker
3. Run `zaphod scrape banks <file>` (i.e. `POST /api/scrape/banks` with `{html_path: "..."}`)
4. Show result: count of banks matched, any unmatched banks
5. If successful, run `zaphod sync --quizzes-only` to instantiate quiz instances with bank links

This step is one-time per course. Once `bank-mappings.yaml` is committed, subsequent
`zaphod sync` runs are fully automatic.

#### "Link Outcomes" setup step (after outcomes are created in Canvas)

1. Prompt user to open Canvas → **Outcomes** and save the page HTML
2. Accept the HTML file via file picker
3. Run `zaphod scrape outcomes <file>` (i.e. `POST /api/scrape/outcomes` with `{html_path: "..."}`)
4. Show result: count of outcomes matched, any unmatched outcomes
5. Run `zaphod sync` to sync outcomes with Canvas IDs

#### API endpoints to add to FastAPI (`src-python/api/`)

```
POST /api/scrape/banks      body: {html_path: str}  → runs scrape banks, returns {matched, unmatched_local, unmatched_canvas}
POST /api/scrape/outcomes   body: {html_path: str}  → runs scrape outcomes, returns {matched, unmatched_local, unmatched_canvas}
```

Both endpoints accept either an absolute path to a saved HTML file or (better for UX) a
base64-encoded HTML blob so the user doesn't need the file saved to a known path — the app
can accept the file via a native file picker and POST the content directly.

---

## `zaphod reorder` — Stamp derived values from folder structure

After `zaphod import`, content items are placed in `.module` folders with the naming
convention `{nn:02d}-s{mm:02d}-{name}.{ext}`. `zaphod reorder` reads these folder
names and the course root name, then stamps the derived values as explicit frontmatter
and shared variables:

### Frontmatter keys stamped into each `index.md`

| Key | Type | Source | Notes |
|-----|------|--------|-------|
| `position:` | int | 1-based rank within module after sorting | Always written when it differs |
| `session:` | int | `s{nn}` component in item folder name | Only written when token detected |
| `module:` | int | Numeric prefix of the nearest `.module` ancestor dir | Only written when prefix present |

Sort order used: `position:` frontmatter (if already set) → numeric folder prefix → alphabetical.
This mirrors `export_modules.py` and `sync_modules.py`, so the stamped values are stable.

`module:` is a template variable (use as `{{var:module}}`). It is **not** the same as
`modules:` (list) — the legacy key for explicit Canvas module membership. `modules:` is
left untouched; module membership continues to be inferred from directory structure at
build time via `infer_module_from_path()`.

### Shared variable stamped into `shared/variables.yaml`

| Key | Type | Source | Notes |
|-----|------|--------|-------|
| `course_order:` | int | Numeric prefix of course root directory name | e.g. `07-javascript-cards` → `7` |

Merges into existing `shared/variables.yaml`; creates the file and `shared/` dir if absent.

### Usage

```bash
zaphod reorder --dry-run --verbose   # preview
zaphod reorder                        # apply
```

Idempotent — safe to re-run. Run once after `zaphod import`, then commit the changes.

**What zaphod-app needs:** expose a "Reorder" action (or run it automatically post-import)
that calls `zaphod reorder`.

---

## Variable Filters

Variable expressions now support an optional filter chain applied left-to-right:

```
{{var:variable_name | filter1 | filter2:arg}}
```

### Supported filters

| Filter | Arg | Behaviour |
|--------|-----|-----------|
| `default:value` | fallback string | Use value when variable is missing or empty |
| `required` | — | Emit build-time warning if variable is not set |
| `upcase` | — | UPPERCASE |
| `downcase` | — | lowercase |
| `titlecase` | — | Title Case |
| `replace:old,new` | two values, comma-separated | Substring replacement; quote values containing spaces |
| `ordinal` | — | Integer → ordinal string: `7` → `"7th"` |
| `decimals:n` | integer | Float formatted to n decimal places |

Full reference: `docs/user-guide/variable-filters.md`

### Round-trip markers include the filter chain

The filter chain is preserved in HTML comment markers:
```html
<!-- {{var:session | ordinal}} -->7th<!-- {{/var:session | ordinal}} -->
```
`restore_zaphod_markers()` restores the full expression including filters — no changes
needed in the import pipeline. The existing `_VAR_MARKER_RE` pattern (`[^}]+`) already
matches filter chains.

### What zaphod-app needs to handle

- **Template authoring UI** — if the app provides a variable picker or expression editor,
  it must allow the `| filter` suffix in the expression field. Expressions are plain text;
  no special UI handling is required beyond not stripping the `|` syntax.
- **No other changes** — filters are resolved transparently by `frontmatter_to_meta.py`
  at publish time. The app's sync pipeline (`zaphod sync`) picks this up automatically.
- **Import** — `restore_zaphod_markers()` requires no changes; it already round-trips
  filter chains correctly.

---

## Template Variables & Includes

### What zaphod supports

`header.md` and `footer.md` inside `templates/{name}/` now support full
variable and include interpolation — the same syntax as `index.md` body content:

```markdown
<!-- header.md -->
{{include:progress_dashboard}}

Welcome to {{var:course_title}}
```

### Variable resolution order (3-tier, lowest → highest)

| Tier | Source | Notes |
|------|--------|-------|
| 1 | `_all_courses/shared/variables.yaml` | Program-level defaults |
| 2 | `<course>/shared/variables.yaml` | Course-level overrides |
| 3 | `index.md` frontmatter | Per-item overrides |

All three tiers are merged and available in both `source.md` content and templates.
Page frontmatter is the highest priority — intentionally, so per-page context
(e.g. session number, progress position) can flow into template widgets.

### Include resolution order

For `{{include:name}}`:

1. `<course>/shared/name.md` — course-specific
2. `_all_courses/shared/name.md` — program-level fallback
3. `<course>/content/includes/name.md` — legacy
4. `<course>/includes/name.md` — legacy
5. `_all_courses/includes/name.md` — legacy

### `_all_courses/` location

`_all_courses/` is found by **walking up from `cwd`** (the course directory) until
a `_all_courses/` directory is encountered. It does not need to be at a fixed
location relative to zaphod's install path. Typical structure:

```
courselab/
  _all_courses/
    shared/
      variables.yaml    ← program-wide variable defaults
      progress_dashboard.md  ← shared include files
  courses/
    07-javascript-cards/   ← cwd when running zaphod
    08-python-intro/
```

### Round-trip HTML comment markers

When zaphod publishes content to Canvas, it wraps resolved variables, includes,
and template sections in HTML comment markers so they can be faithfully restored
on import.

**Format:**

| Marker | Meaning |
|--------|---------|
| `<!-- {{var:name}} -->value<!-- {{/var:name}} -->` | Resolved variable — restore as `{{var:name}}` on import |
| `<!-- {{include:name}} -->...<!-- {{/include:name}} -->` | Rendered include block — restore as `{{include:name}}` on import |
| `<!-- {{template:header}} -->...<!-- {{/template:header}} -->` | Rendered template header — **strip entirely** on import |
| `<!-- {{template:footer}} -->...<!-- {{/template:footer}} -->` | Rendered template footer — **strip entirely** on import |

**What zaphod-app needs to do for preview rendering:**

If the app renders Canvas HTML for local preview, it should apply `restore_zaphod_markers()`
(exported from `zaphod.frontmatter_to_meta`) before displaying — or replicate its logic:

1. Strip `<!-- {{template:*}} -->...<!-- {{/template:*}} -->` blocks
2. Replace `<!-- {{include:name}} -->...<!-- {{/include:name}} -->` → `{{include:name}}`
3. Replace `<!-- {{var:name}} -->...<!-- {{/var:name}} -->` → `{{var:name}}`

**Caveat:** HTML comment markers survive Canvas API round-trips but are stripped if a
user manually edits the page in Canvas's rich content editor (RCE). The import pipeline
falls back to converting raw HTML to markdown in that case.

### Frontmatter keys used for template context

These per-item frontmatter keys are commonly used in template widgets (e.g. a progress
dashboard) and flow into template rendering at publish time:

| Key | Purpose |
|-----|---------|
| `position` | Item position within its module (1-based) |
| `session` | Session/module number (set manually or via import) |
| `session_total` | Total number of sessions in the course |
| Any other key | Available as `{{var:key}}` in templates |

---

## Sync ↔ Export Parity Rule

**When a frontmatter field or content feature is added or changed in one pipeline, it must be reflected in the other.**

| Pipeline | Files |
|----------|-------|
| Sync | `sync_modules.py`, `canvas_publish.py` |
| Export | `export_assignments.py`, `export_quizzes.py`, `export_pages.py`, `export_modules.py` |

### Why this matters

Sync pushes live data to Canvas. Export generates a portable cartridge for Canvas import. A course round-tripped through export→import should behave identically to one that was synced directly. If a field is honoured by sync but silently dropped by export (or vice versa), the cartridge becomes a lossy representation of the course.

### Known gaps fixed

| Field | Fixed in |
|-------|----------|
| `indent` | `export_modules.py` — was hardcoded `"0"`; now reads from `meta.json` |
| `due_at` / `lock_at` / `unlock_at` | `export_assignments.py` — were hardcoded empty; now reads from `meta.json` |

### Checklist when adding a new frontmatter field

- [ ] `frontmatter_to_meta.py` passes it through to `meta.json`
- [ ] `canvas_publish.py` or `sync_modules.py` sends it to Canvas API (sync path)
- [ ] Appropriate `export_*.py` reads it from `meta` and writes it to XML (export path)
- [ ] Documented in `user-guide/`

---

## Versioning Approach

When a set of changes is stable enough to converge:

1. Tag this repo: `git tag v0.x.0`
2. Verify `zaphod-app` subprocess calls work against the tag
3. Update the convergence history table in both `COMPAT.md` files
4. Tag `zaphod-app` with the same version number

No strict schedule — converge when a meaningful set of features has stabilized.
