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

**Longer-term target architecture**

Mirror the sync pipeline exactly, with an export twin for each sync step:

```
frontmatter_to_meta.py   →  meta.json per item          (shared with sync)
export_pages.py          →  wiki_content/{id}.html
export_assignments.py    →  web_resources/{id}/
export_banks.py          →  non_cc_assessments/
export_quizzes.py        →  assessments/{id}/
export_modules.py        →  module_meta.xml, imsmanifest.xml, course_settings/
assemble_cartridge.py    →  zip everything into .imscc
```

Each export step mirrors its sync counterpart. The manifest assembly happens
last once all content files are written. This makes the export robust to
pipeline changes and removes all duplicated loading logic from
`export_cartridge.py`.

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
