# Zaphod — Architecture Decisions

Decisions that shaped the codebase. Each entry records what was decided,
why, and what was rejected — so future work doesn't re-litigate settled ground.

---

## Export Architecture

### Decision: export_cartridge.py should run frontmatter_to_meta.py first (2026-02)

**Context**

`export_cartridge.py` builds an IMS Common Cartridge package from local course
files. It was originally written as a standalone script that re-implemented
content loading: reading `index.md` frontmatter, inferring type from folder
extension, promoting `title:` to `name:`, resolving module membership, etc.
This duplicated logic that already lives correctly in `frontmatter_to_meta.py`.

**Problem**

- Content type is inferred from the folder extension (`.page`, `.assignment`,
  `.quiz`, etc.) by the pipeline — it is never required in frontmatter.
- `meta.json` and `source.md` are build artifacts created by
  `frontmatter_to_meta.py` and removed in the prune step. They are absent in
  a clean checkout, so export must not rely on them being present.
- Any time the pipeline evolves (new frontmatter key, new content type, include
  resolution change), the export silently diverges from the sync behaviour.

**Decision**

In the near term: `zaphod export` should invoke `frontmatter_to_meta.py` as
the first step before building the cartridge. This is a purely local step
(no Canvas credentials needed) and produces `meta.json` / `source.md` as
correctly-processed build artifacts. The cartridge builder then reads those
instead of re-implementing the logic.

**Longer-term target architecture** ← *implemented 2026-02*

Mirror the sync pipeline exactly, with an export twin for each sync step.
**This architecture has now been implemented.** See next decision entry.

**Rejected alternatives**

- Keep `export_cartridge.py` as a self-contained loader: fragile — diverges
  from pipeline behaviour every time the pipeline gains a new feature.
- Run the full sync pipeline in "dry-run" mode: the sync steps have Canvas API
  dependencies and are not designed for offline use.

---

## Canvas CC Export Format

### Decision: target Canvas Course Export Package format, not standard CC 1.x (2026-02)

**Context**

Canvas can import two formats: "Common Cartridge 1.x Package" (standard CC)
and "Canvas Course Export Package" (Canvas CE — a CC 1.1 superset).

**Decision**

Target Canvas CE format. Discovered through systematic comparison against a
real Canvas CE export and Canvas open-source importer code.

**Key format requirements** (Canvas CE importer source — `lib/cc/importer/canvas/`):

| Content type | Requirement |
|---|---|
| Pages (WikiPage) | `wiki_content/{id}.html` with `<meta name="identifier" content="{id}"/>` in `<head>` — importer reads this to match the file to its module entry |
| Assignments | `web_resources/{id}/content.html` + `assignment_settings.xml` companion |
| Quizzes | `assessments/{id}/assessment_qti.xml` + `assessment_meta.xml` **AND** `non_cc_assessments/{id}.xml.qti` — `convert_quizzes()` looks ONLY in `non_cc_assessments/` and returns early (no quizzes created at all) if that folder is absent |
| Modules | `course_settings/module_meta.xml` with `<content_type>` per item |
| CE detection | `course_settings/canvas_export.txt` triggers CE import mode |
| CE activation | `course_settings/course_settings.xml` required for CE importer to process pages and quizzes — without it, only assignments import |
| Assignment groups | `course_settings/assignment_groups.xml` required |

**All four `course_settings/` files must be listed as `<file>` entries under
the settings resource in `imsmanifest.xml`.**

**Rejected alternatives**

- Standard CC 1.x: imports pages as file attachments, not Canvas Pages; no
  native quiz support; module structure limited.

---

## Step-by-step Export Pipeline

### Decision: refactor export into independent per-step modules (2026-02)

**Context**

The original `export_cartridge.py` was a monolithic ~1900-line script that
re-implemented content loading, variable/include expansion, module resolution,
and question parsing — all logic that already lives correctly in the sync
pipeline. Every pipeline improvement (new frontmatter key, new content type,
include resolution change) had to be manually replicated in the export and
could silently diverge.

**Decision**

Refactor the export into a step-by-step pipeline that mirrors the sync pipeline
exactly. Shared state is passed via a staging directory and a manifest JSON file
(`_course_metadata/exports/.export_manifest.json`).

**New file layout:**

| File | Role |
|------|------|
| `export_types.py` | `ExportManifest`, `ExportResource`, `ExportOrgItem` dataclasses + shared utilities |
| `export_pages.py` | Step 2 — `wiki_content/{id}.html` for pages/files/links |
| `export_assignments.py` | Step 3 — `web_resources/{id}/` for assignments + rubrics |
| `export_quizzes.py` | Step 4 — `assessments/` + `non_cc_assessments/` |
| `export_modules.py` | Step 5 — `course_settings/module_meta.xml` + org items in manifest |
| `export_settings.py` | Step 6 — `course_settings/` CE files |
| `export_outcomes.py` | Step 7 — `{name}.outcomes.csv` alongside .imscc (not in zip) |
| `assemble_cartridge.py` | Step 8 — `imsmanifest.xml` + zip → `.imscc` |
| `export_cartridge.py` | Orchestrator only: init → step 1 (optional) → steps 2–8 |

**Key design invariants:**

- `frontmatter_to_meta.py` is always step 1 when running standalone. Export
  steps never read raw `index.md` — only `meta.json` + `source.md`.
- Staging dir is a clean rebuild: each `export_cartridge.py` invocation wipes
  and recreates `.staging/`. Incremental export is a future concern.
- No Canvas API calls in any export step.
- `assemble_cartridge.py` is the only step that writes `imsmanifest.xml` and
  the `.imscc`.
- Each step is idempotent — re-running overwrites its prior staging files.
- Each step reads the manifest JSON to discover `staging_dir`; writes it back
  with new entries appended.
- Quiz identifiers are now deterministic (`generate_content_id(folder)` instead
  of random `generate_id("quiz")`), giving stable IDs across export runs.
- `--watch-mode` and `--skip-meta` flags skip step 1 (the sync pipeline already
  ran `frontmatter_to_meta.py`).

**Shared state: manifest JSON schema:**

```json
{
  "identifier": "cc_abc123def456",
  "title": "JavaScript Cards",
  "staging_dir": "/abs/.../exports/.staging",
  "output_path": "/abs/.../exports/20260222_153045_export.imscc",
  "resources": [
    {"identifier": "i1234", "type": "webcontent",
     "href": "wiki_content/i1234.html", "files": [...], "dependency": null}
  ],
  "org_items": [
    {"identifier": "m1", "title": "Week 1", "position": 1,
     "children": [{"identifier": "item_i1234", "identifierref": "i1234", "title": "Intro"}]}
  ],
  "settings_resource_files": [
    "course_settings/canvas_export.txt",
    "course_settings/course_settings.xml",
    "course_settings/module_meta.xml",
    "course_settings/assignment_groups.xml"
  ]
}
```

**Rejected alternatives:**

- Keep `export_cartridge.py` as a self-contained loader: fragile — diverges
  from pipeline behaviour every time the pipeline gains a new feature.
- Subprocess per step (like `watch_and_publish.py`): unnecessary overhead for
  a fully local pipeline; direct module import is simpler and equally debuggable.

---

## `zaphod schedule` — Course Flow Generator

### Decision: planned, not yet implemented (2026-03-15)

**Problem**

Syllabi need a course schedule table showing week-by-week topics and due dates. Writing it by hand is tedious and goes stale. Zaphod already has all the required data in the content tree (module names, page/assignment names, session numbers, due dates from frontmatter).

**Proposed approach**

A `zaphod schedule` command that walks the content tree and emits a generated include:

```
shared/course-schedule.md   ← generated, committed, referenced via {{include:course-schedule}}
```

The syllabus template (or any page) pulls it in with `{{include:course-schedule}}`.

**Two output layouts — same data, different presentation:**

*Flat table* — best for credit courses with clear weekly pacing:

```markdown
| Week | Session | Topic | Due |
|------|---------|-------|-----|
| 1 | 1 | Introduction | — |
| 1 | 2 | Core Concepts | Essay 1 — Sep 14 |
```

*Tab layout* — best for self-paced or module-heavy courses. Each module becomes a tab via a Trillian `trl-schedule` component using the standard `<ul>/<li>` pipe-delimited pattern:

```markdown
- trl-schedule
- module: Week 1 — Introduction
- item: Introduction | page
- item: Essay 1 | assignment | Sep 14
- module: Week 2 — Core Concepts
- item: Deep Dive | page
```

Layout chosen by which include/component the template uses — the command outputs whichever is requested.

**Data sources (all already available):**

| Column | Source |
|--------|--------|
| Week / Module | Module folder name (numeric prefix stripped) |
| Session | `session:` frontmatter (stamped by `zaphod reorder`) |
| Topic / item name | `name:` frontmatter |
| Content type | Folder extension (`.page`, `.assignment`, etc.) |
| Due date | `due_at:` frontmatter (assignments only) |

**Open design questions:**

1. Multi-session modules — does the flat table group items under a sub-header or repeat the week number per row?
2. Unscheduled items (no `session:`) — omit, list at end, or warn?
3. Due date formatting — format `due_at` ISO string automatically, or support a `due_label:` frontmatter override for display?
4. Command flags — `--format flat|tabs`, or infer from `zaphod.yaml`?
5. `trl-schedule` Trillian component — needs to be specced and built alongside this command.
6. Auto-run — explicit `zaphod schedule` call only, or also triggered by `zaphod sync`?

**Relationship to syllabus template**

Intended to pair with a `_all_courses/templates/syllabus/` template set using WWCC boilerplate includes + `{{include:course-schedule}}`. The schedule include is the dynamic part; boilerplate includes (policies, contact info, etc.) are static.
