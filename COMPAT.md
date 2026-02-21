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

| Key       | Location        | Purpose                          |
|-----------|-----------------|----------------------------------|
| `name`    | `index.md`      | Content item display name        |
| `title`   | `module.yaml`   | Module display name              |
| `position`| `index.md`      | Item sort order                  |

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

## Versioning Approach

When a set of changes is stable enough to converge:

1. Tag this repo: `git tag v0.x.0`
2. Verify `zaphod-app` subprocess calls work against the tag
3. Update the convergence history table in both `COMPAT.md` files
4. Tag `zaphod-app` with the same version number

No strict schedule — converge when a meaningful set of features has stabilized.
