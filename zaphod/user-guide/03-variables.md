# Variables

> Variables let you define content once and reuse it throughout your course. Change it in one place, and it updates everywhere.

---

## Why Use Variables?

Imagine you mention your office hours on 10 different pages. Without variables, updating your office hours means editing 10 files. With variables:

```yaml
---
office_hours: "Monday/Wednesday 2-4pm, Room 301"
---

Come to office hours: {{var:office_hours}}
```

Change the frontmatter once, and every instance of `{{var:office_hours}}` updates automatically.

---

## Basic Usage

### Define in Frontmatter

```yaml
---
name: "Syllabus"
instructor: "Dr. Smith"
email: "smith@university.edu"
office: "Building A, Room 301"
---

# Course Syllabus

**Instructor:** {{var:instructor}}  
**Email:** {{var:email}}  
**Office:** {{var:office}}
```

### Result in Canvas

```
# Course Syllabus

**Instructor:** Dr. Smith  
**Email:** smith@university.edu  
**Office:** Building A, Room 301
```

---

## Variable Syntax

```
{{var:variable_name}}
```

- Variable names can contain letters, numbers, underscores, and hyphens
- Names are case-sensitive (`{{var:Email}}` ≠ `{{var:email}}`)
- If a variable isn't found, the placeholder stays as-is (helpful for debugging)

---

## Where to Define Variables

Variables can be defined at multiple levels:

### 1. Page Level (frontmatter)

```yaml
---
name: "Week 1 Overview"
week_number: 1
topic: "Introduction"
---

# Week {{var:week_number}}: {{var:topic}}
```

Used for: Page-specific values

### 2. Course Level (variables.yaml)

Create `variables.yaml` in your course root:

```yaml
# variables.yaml
instructor: "Dr. Smith"
email: "smith@university.edu"
office_hours: "MW 2-4pm"
semester: "Spring 2026"
```

Now any page can use `{{var:instructor}}` without defining it in frontmatter.

### 3. Shared Across Courses

Create `_all_courses/variables.yaml` in your courses root:

```
courses/
├── _all_courses/
│   └── variables.yaml    # Shared variables
├── CS101/
│   └── variables.yaml    # Course-specific overrides
└── CS102/
```

Best for: Institution name, standard policies, shared links

---

## Variable Resolution Order

When Zaphod sees `{{var:name}}`, it looks for `name` in this order:

1. **Page frontmatter** (highest priority)
2. **Course `variables.yaml`**
3. **Shared `_all_courses/variables.yaml`**

This means you can define defaults at the course level and override them on specific pages.

### Example: Override Pattern

```yaml
# Course variables.yaml
instructor: "Dr. Smith"

# Page frontmatter for guest lecture
---
name: "Guest Lecture"
instructor: "Dr. Jones"    # Overrides course-level
---

Today's lecture by {{var:instructor}}
```

Result: "Today's lecture by Dr. Jones"

---

## Common Use Cases

### Contact Information

```yaml
# variables.yaml
instructor_name: "Dr. Ada Lovelace"
instructor_email: "lovelace@university.edu"
ta_name: "Charles Babbage"
ta_email: "babbage@university.edu"
office_hours: "Tuesday/Thursday 3-5pm"
office_location: "Engineering Building, Room 142"
```

### Course Details

```yaml
# variables.yaml
course_code: "CS 101"
course_title: "Introduction to Programming"
semester: "Spring 2026"
section: "Section 001"
credits: "3"
```

### External Links

```yaml
# variables.yaml
lms_help: "https://help.canvas.edu"
library_link: "https://library.university.edu"
tutoring_link: "https://tutoring.university.edu/cs"
```

### Reusable Phrases

```yaml
# variables.yaml
late_penalty: "10% per day, up to 3 days"
academic_integrity: "University Academic Integrity Policy"
```

---

## Variables in Includes

Variables work inside included content too!

**includes/contact.md:**
```markdown
## Contact Information

- **Instructor:** {{var:instructor_name}}
- **Email:** {{var:instructor_email}}
- **Office Hours:** {{var:office_hours}}
```

**Your page:**
```markdown
---
name: "Syllabus"
instructor_name: "Dr. Smith"
instructor_email: "smith@u.edu"
office_hours: "MW 2-4pm"
---

# Syllabus

{{include:contact}}
```

The include gets the variables from the page's frontmatter.

---

## Tips

✅ **Use descriptive names** — `instructor_email` is clearer than `email`

✅ **Define course-wide values in variables.yaml** — Less repetition

✅ **Check for typos** — `{{var:emial}}` won't match `email`

✅ **Variables are text only** — They can't contain markdown formatting that spans multiple lines

---

## Debugging

If a variable isn't being replaced:

1. Check the spelling matches exactly (case-sensitive)
2. Check it's defined somewhere (frontmatter, variables.yaml, or _all_courses)
3. Run `zaphod sync` and look for warnings

Variables that aren't found remain as `{{var:name}}` in the output, making them easy to spot.

---

## Next Steps

- [Includes](04-includes.md) — Share larger content blocks
- [Pages](01-pages.md) — Using variables in pages
