# Assignments

> Assignments are gradable content items — homework, essays, projects, and anything students submit for a grade.

---

## Creating an Assignment

Assignments live in folders ending with `.assignment`:

```
pages/
└── essay-1.assignment/
    ├── index.md
    └── rubric.yaml      # Optional grading rubric
```

---

## Basic Assignment Structure

```markdown
---
name: "Essay 1: Introduction"
modules:
  - "Week 2"
published: false

# Grading
points_possible: 100
grading_type: points

# Submissions
submission_types:
  - online_upload
allowed_extensions:
  - pdf
  - docx
---

# Essay 1: Introduction

Write a 500-word essay introducing yourself and your goals for this course.

## Requirements

- 500 words minimum
- PDF or Word format
- Due by Sunday 11:59pm

## Grading Criteria

See the rubric attached to this assignment.
```

---

## Frontmatter Options

### Required

| Field | Description |
|-------|-------------|
| `name:` | Assignment title in Canvas |

### Grading

| Field | Description | Default |
|-------|-------------|---------|
| `points_possible:` | Maximum points | `0` |
| `grading_type:` | `points`, `pass_fail`, `percent`, `letter_grade`, `not_graded` | `points` |

### Submission Settings

| Field | Description | Default |
|-------|-------------|---------|
| `submission_types:` | List of allowed types (see below) | `none` |
| `allowed_extensions:` | File extensions for uploads | Any |

**Submission types:**
- `online_upload` — File upload
- `online_text_entry` — Text box
- `online_url` — URL submission
- `media_recording` — Audio/video
- `none` — No submission (announcements, etc.)

### Due Dates

| Field | Description |
|-------|-------------|
| `due_at:` | Due date/time (ISO format) |
| `lock_at:` | Lock date (no more submissions) |
| `unlock_at:` | When assignment becomes available |

Example:
```yaml
due_at: "2026-02-15T23:59:00Z"
unlock_at: "2026-02-08T00:00:00Z"
lock_at: "2026-02-16T23:59:00Z"
```

### Other Options

| Field | Description | Default |
|-------|-------------|---------|
| `published:` | Visible to students | `false` |
| `modules:` | Module placement | None |
| `position:` | Order in module | Auto |
| `description:` | Canvas description (if different from body) | Body content |

---

## Adding a Rubric

Create a `rubric.yaml` file alongside your `index.md`:

```
essay-1.assignment/
├── index.md
└── rubric.yaml
```

### Basic Rubric

```yaml
title: "Essay Rubric"

criteria:
  - description: "Thesis"
    points: 25
    ratings:
      - description: "Excellent"
        points: 25
      - description: "Good"
        points: 20
      - description: "Needs Work"
        points: 10
      - description: "Missing"
        points: 0
  
  - description: "Organization"
    points: 25
    ratings:
      - description: "Clear structure"
        points: 25
      - description: "Some structure"
        points: 15
      - description: "Unclear"
        points: 5
```

### Rubric Options

```yaml
title: "Essay Rubric"
free_form_criterion_comments: true   # Allow freeform comments

criteria:
  - description: "Content"
    long_description: "The quality and depth of the content"  # Optional detail
    points: 50
    use_range: true    # Enable range scoring (e.g., 40-50 points)
    ratings:
      - description: "Excellent"
        long_description: "Exceeds all expectations"
        points: 50
      - description: "Satisfactory"
        points: 35
      - description: "Needs Improvement"
        points: 20
```

See [Rubrics](06-rubrics.md) for more details on shared rubrics and reusable rows.

---

## Assignment Types

### File Upload Assignment

```yaml
---
name: "Lab Report"
points_possible: 50
submission_types:
  - online_upload
allowed_extensions:
  - pdf
---
```

### Text Entry Assignment

```yaml
---
name: "Discussion Response"
points_possible: 10
submission_types:
  - online_text_entry
---
```

### Multiple Submission Types

```yaml
---
name: "Final Project"
points_possible: 100
submission_types:
  - online_upload
  - online_url    # Students can submit file OR link
---
```

### No Submission (Announcement-Style)

```yaml
---
name: "Course Policies"
grading_type: not_graded
submission_types:
  - none
---
```

---

## Complete Example

```markdown
---
name: "Research Paper Draft"
modules:
  - "Week 4"
  - "Assignments"
published: false

points_possible: 50
grading_type: points

submission_types:
  - online_upload
allowed_extensions:
  - pdf
  - docx
  - doc

due_at: "2026-02-20T23:59:00Z"
unlock_at: "2026-02-13T00:00:00Z"
---

# Research Paper Draft

Submit your first draft for peer review.

## Requirements

- **Length:** 5-7 pages, double-spaced
- **Format:** APA style
- **Due:** February 20 by 11:59pm

## What to Include

1. Introduction with thesis statement
2. At least 3 body paragraphs
3. Preliminary conclusion
4. Works cited (minimum 5 sources)

## How You'll Be Graded

This draft is graded on completion and effort, not final quality. 
Use the rubric as a guide for what we're looking for.

{{include:late_policy}}
```

---

## Tips

✅ **Start unpublished** — Set `published: false` until ready

✅ **Add rubrics** — Makes grading faster and clearer

✅ **Use modules** — Put in "Week X" and "All Assignments" modules

✅ **Set due dates** — Students see them in their calendars

✅ **Include instructions in the body** — Canvas shows this to students

---

## Next Steps

- [Rubrics](06-rubrics.md) — Advanced rubric features
- [Variables](03-variables.md) — Reuse text like policies
- [Modules](05-modules.md) — Organize assignments
