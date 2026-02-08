# Modules

> Modules organize your course content into logical groups — weeks, units, topics, or whatever structure works for your course.

---

## Two Ways to Organize

Zaphod supports two approaches to module organization:

1. **Module Folders** — Group content in `.module` directories (recommended)
2. **Frontmatter Lists** — Specify modules in each page's frontmatter

You can mix both approaches!

---

## Method 1: Module Folders (Recommended)

Create folders ending in `.module` to automatically organize content:

```
content/
├── 01-Getting Started.module/
│   ├── 01-welcome.page/
│   │   └── index.md
│   ├── 02-syllabus.page/
│   │   └── index.md
│   └── 03-first-quiz.quiz/
│       └── index.md
├── 02-Week 1.module/
│   ├── 01-lecture.page/
│   │   └── index.md
│   └── 02-homework.assignment/
│       └── index.md
└── 03-Week 2.module/
    └── ...
```

**How it works:**

- Folders ending in `.module` become Canvas modules
- The numeric prefix (`01-`, `02-`) sets the module order
- The prefix is stripped from the module name
- Content inside automatically goes into that module
- Content is ordered by its own numeric prefix

**Example:**
- `01-Getting Started.module/` → Module "Getting Started" (position 1)
- `02-Week 1.module/` → Module "Week 1" (position 2)
- Inside: `01-welcome.page/` appears before `02-syllabus.page/`

### Legacy Format

The older `module-Name/` format still works:

```
content/
└── module-Week 1/
    └── intro.page/
```

But `.module` suffix is now preferred.

---

## Method 2: Frontmatter Lists

Specify modules directly in each page's frontmatter:

```yaml
---
name: "Course Introduction"
modules:
  - "Getting Started"
  - "Course Resources"    # Can be in multiple modules!
---
```

**When to use this:**
- Content that belongs in multiple modules
- Content that doesn't fit the folder structure
- Overriding the folder-based module assignment

---

## Module Ordering

### Automatic (from folders)

If you don't have a `module_order.yaml`, Zaphod infers order from folder prefixes:

```
content/
├── 01-Week 1.module/     → position 1
├── 02-Week 2.module/     → position 2
├── 05-Midterm.module/    → position 3 (gaps are okay)
└── Resources.module/     → position 4 (no prefix = last)
```

### Explicit (module_order.yaml)

For precise control, create `modules/module_order.yaml`:

```yaml
# modules/module_order.yaml
modules:
  - "Start Here"
  - "Week 1"
  - "Week 2"
  - "Week 3"
  - "Midterm"
  - "Week 4"
  - "Final Project"
  - "Course Resources"    # Appears last
```

Modules are ordered exactly as listed. Any modules not in this list appear after.

---

## Item Ordering Within Modules

Items inside a module are ordered by:

1. **Explicit `position:` in frontmatter** (highest priority)
2. **Numeric prefix** from folder name
3. **Alphabetical** by folder name (last resort)

### Using Folder Prefixes

```
01-Getting Started.module/
├── 01-welcome.page/        # First
├── 02-intro-video.page/    # Second
├── 03-syllabus.page/       # Third
└── quiz.quiz/              # Last (no prefix)
```

### Using Position Frontmatter

```yaml
---
name: "Important Announcement"
modules:
  - "Week 1"
position: -1    # Negative = floats to top
---
```

**Position values:**
- Negative numbers (`-10`, `-1`) sort before numbered content
- Zero or positive numbers sort by value
- Items without position use folder prefix or sort last

---

## Item Indentation

Canvas modules support indentation to show hierarchy:

```yaml
---
name: "Reading: Chapter 1"
modules:
  - "Week 1"
indent: 1    # Indented under previous item
---
```

**Indent levels:** 0 (none), 1, or 2

---

## Multiple Modules

Content can appear in multiple modules:

```yaml
---
name: "Late Work Policy"
modules:
  - "Start Here"
  - "Course Resources"
  - "Syllabus"
---
```

This creates a module item in each listed module, all pointing to the same page.

---

## Protecting Empty Modules

Sometimes you want to keep a module even if it's temporarily empty. Two ways:

### 1. Module Folders

Any `.module` folder is protected automatically:

```
content/
└── 10-Final Project.module/    # Won't be deleted even if empty
```

### 2. module_order.yaml

List it explicitly:

```yaml
# modules/module_order.yaml
modules:
  - "Week 1"
  - "Week 2"
  - "Final Project"    # Protected
```

---

## Complete Example

**Directory structure:**
```
my-course/
├── modules/
│   └── module_order.yaml
└── content/
    ├── 01-Start Here.module/
    │   ├── 01-welcome.page/
    │   ├── 02-syllabus.page/
    │   └── 03-getting-help.page/
    ├── 02-Week 1.module/
    │   ├── 01-overview.page/
    │   ├── 02-reading.page/
    │   ├── 03-discussion.assignment/
    │   └── 04-quiz.quiz/
    └── Course Resources.module/
        ├── writing-guide.page/
        └── technology-help.page/
```

**modules/module_order.yaml:**
```yaml
modules:
  - "Start Here"
  - "Week 1"
  - "Week 2"
  - "Midterm"
  - "Week 3"
  - "Week 4"
  - "Final"
  - "Course Resources"
```

---

## Tips

✅ **Use module folders** — Less frontmatter to maintain

✅ **Use numeric prefixes** — Makes ordering clear and predictable

✅ **Protect future modules** — Add them to module_order.yaml early

✅ **Put shared resources last** — "Course Resources" at the bottom

✅ **Use frontmatter for multi-module items** — Syllabus in "Start Here" AND "Resources"

---

## Common Patterns

### Weekly Structure

```
content/
├── 00-Course Info.module/
├── 01-Week 1.module/
├── 02-Week 2.module/
├── ...
├── 15-Final.module/
└── 99-Resources.module/
```

### Unit Structure

```
content/
├── 01-Unit 1 - Foundations.module/
├── 02-Unit 2 - Applications.module/
├── 03-Unit 3 - Advanced Topics.module/
└── 04-Review and Assessment.module/
```

### Topic Structure

```
content/
├── 01-Introduction.module/
├── 02-Core Concepts.module/
├── 03-Techniques.module/
├── 04-Projects.module/
└── 05-Resources.module/
```

---

## Next Steps

- [Pages](01-pages.md) — Creating page content
- [Assignments](02-assignments.md) — Creating assignments
- [Quizzes](09-quizzes.md) — Creating quizzes
