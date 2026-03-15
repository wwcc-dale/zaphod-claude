# Pages

> Pages are the basic building blocks of your course content — welcome messages, lecture notes, resource lists, and anything that students need to read.

---

## Creating a Page

Every page lives in its own folder with an `index.md` file:

```
content/
└── my-first-page.page/
    └── index.md
```

The folder name ends in `.page` to tell Zaphod this is a Canvas Page.

---

## Basic Page Structure

Here's a simple page:

```markdown
---
name: "Welcome to Week 1"
modules:
  - "Week 1"
published: true
---

# Welcome to Week 1!

This week we'll cover the fundamentals.

## Topics

- Introduction to the subject
- Key concepts
- Your first assignment

## Reading

Please read chapters 1-3 before class.
```

### The Parts Explained

**Frontmatter** (between the `---` lines):
- `name:` — The title shown in Canvas
- `modules:` — Which module(s) to place this page in
- `published:` — Whether students can see it (true/false)

**Body** (after the second `---`):
- Your actual content in Markdown format
- Headings, lists, bold, links — whatever you need

---

## Frontmatter Options

### Required

| Field | Description |
|-------|-------------|
| `name:` | The page title in Canvas |

### Recommended

| Field | Description | Default |
|-------|-------------|---------|
| `modules:` | List of modules to place the page in | None |
| `published:` | Students can see it | `false` |

### Optional

| Field | Description |
|-------|-------------|
| `position:` | Order within module (-1 for first, etc.) |
| `indent:` | Indent level in module (0-2) |

---

## Putting Pages in Modules

### Method 1: Frontmatter

Specify modules explicitly:

```yaml
---
name: "Syllabus"
modules:
  - "Start Here"
  - "Course Resources"    # Can be in multiple modules!
---
```

### Method 2: Module Folders

Put the page inside a `.module` folder:

```
content/
└── 01-Start Here.module/
    └── syllabus.page/
        └── index.md        # Automatically in "Start Here" module
```

When using module folders, you don't need the `modules:` line in your frontmatter — Zaphod figures it out from the folder structure.

---

## Page Ordering

Pages appear in modules in a predictable order:

### Using Folder Prefixes

```
content/
└── 01-Week 1.module/
    ├── 01-introduction.page/     # First
    ├── 02-concepts.page/         # Second
    └── 03-summary.page/          # Third
```

The number prefix (01-, 02-) sets the order. The prefix is stripped from the page name.

### Using Position Frontmatter

For fine-grained control:

```yaml
---
name: "Important Announcement"
modules:
  - "Week 1"
position: -1    # Appears before numbered items
---
```

Negative positions float items to the top.

---

## Formatting Content

Pages are written in Markdown. Here are the most common elements:

### Headings

```markdown
# Main Heading
## Section
### Subsection
```

### Text Formatting

```markdown
This is **bold** and this is *italic*.

This is a [link](https://example.com).
```

### Lists

```markdown
Bullet list:
- Item one
- Item two
- Item three

Numbered list:
1. First
2. Second
3. Third
```

### Code

```markdown
Inline `code` looks like this.

Code blocks:
```python
def hello():
    print("Hello, world!")
```
```

### Images

```markdown
![Description](image.png)
```

Put the image file in the same folder as your `index.md`, or in the `assets/` folder.

---

## Adding Images and Files

### Local Images

Put the image in the same folder:

```
content/
└── welcome.page/
    ├── index.md
    └── welcome-banner.png     # Referenced as welcome-banner.png
```

In your `index.md`:
```markdown
![Welcome Banner](welcome-banner.png)
```

### Shared Assets

For images used on multiple pages, put them in `assets/`:

```
my-course/
├── assets/
│   └── course-logo.png
└── content/
    └── welcome.page/
        └── index.md
```

In your `index.md`:
```markdown
![Logo](course-logo.png)
```

Zaphod automatically finds it in `assets/`.

---

## Using Variables

Variables let you define content once and reuse it:

```yaml
---
name: "Contact Information"
instructor_name: "Dr. Smith"
office_hours: "MW 2-4pm"
---

Contact {{var:instructor_name}} during office hours ({{var:office_hours}}).
```

See [Variables](03-variables.md) for more.

---

## Using Includes

Includes let you share whole blocks of content:

```markdown
---
name: "Syllabus"
---

# Course Syllabus

{{include:late_policy}}

{{include:academic_integrity}}
```

See [Includes](04-includes.md) for more.

---

## Example: Complete Page

```markdown
---
name: "Week 1: Getting Started"
modules:
  - "Week 1"
published: true
instructor: "Dr. Smith"
---

# Welcome to Week 1!

Hello and welcome to the course. I'm {{var:instructor}}, and I'll be your instructor this semester.

## This Week's Goals

By the end of this week, you should be able to:

1. Navigate the course site
2. Understand the syllabus
3. Complete your first reading

## Materials

- Read: Chapter 1
- Watch: [Intro Video](intro.mp4)
- Complete: Week 1 Quiz

## Questions?

{{include:office_hours}}

---

![Week 1 Overview](week1-overview.png)
```

---

## Tips

✅ **Use descriptive folder names** — You'll thank yourself later

✅ **Start with `published: false`** — Publish when ready

✅ **Use module folders** — Less frontmatter to maintain

✅ **Put shared images in `assets/`** — Easier to manage

✅ **Preview with `zaphod sync --dry-run`** — Before publishing

---

## Next Steps

- [Assignments](02-assignments.md) — Add gradable content
- [Variables](03-variables.md) — Reuse content efficiently
- [Modules](05-modules.md) — Organize your course
