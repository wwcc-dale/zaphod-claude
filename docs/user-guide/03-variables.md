# Variables

> Variables let you define values once and reuse them throughout your course. Change it in one place, and it updates everywhere.

---

## The Basics

## Why Use Variables?

Imagine you mention your office hours on 10 different pages. Without variables, updating your office hours means editing 10 files. With variables, you change it in one place:

```yaml
# shared/variables.yaml
office_hours: "Monday/Wednesday 2-4pm, Room 301"
```

Then every page using `{{var:office_hours}}` updates automatically.

---

## Where Variables Come From

Variables are defined in `shared/variables.yaml` in your course folder:

```
my-course/
└── shared/
    └── variables.yaml
```

Create `shared/variables.yaml` in your course:

```yaml
# shared/variables.yaml
course_code: "CS 101"
course_title: "Introduction to Programming"
instructor_name: "Dr. Smith"
instructor_email: "smith@university.edu"
office_hours: "MW 2-4pm"
```

Best for: Course-specific values used across many pages.

---

## Variable Syntax

```
{{var:variable_name}}
```

- Names can contain letters, numbers, underscores, and hyphens
- Names are case-sensitive (`{{var:Email}}` ≠ `{{var:email}}`)
- If a variable isn't found, the placeholder stays as-is (helpful for debugging)

---

## Setting Up Course Variables

### Step 1: Create the shared folder

```
my-course/
└── shared/
    └── variables.yaml
```

### Step 2: Add your variables

```yaml
# shared/variables.yaml

# Course information
course_code: "CS 101"
course_title: "Introduction to Computer Science"
semester: "Spring 2026"

# Instructor information
instructor_name: "Dr. Ada Lovelace"
instructor_email: "lovelace@university.edu"
instructor_office: "Engineering Building, Room 142"
office_hours: "Tuesday/Thursday 2-4pm"

# Common phrases
late_penalty: "10% per day, up to 3 days"
academic_integrity: "University Academic Integrity Policy"
```

### Step 3: Use them in your pages

```markdown
---
name: "Syllabus"
---

# {{var:course_code}}: {{var:course_title}}

**Semester:** {{var:semester}}

## Instructor

**Name:** {{var:instructor_name}}  
**Email:** {{var:instructor_email}}  
**Office:** {{var:instructor_office}}  
**Office Hours:** {{var:office_hours}}

## Late Work

Late submissions receive a penalty of {{var:late_penalty}}.
```

---

## Variables in Includes

Variables work inside included content too! This is powerful for creating reusable templates.

**shared/contact_info.md:**
```markdown
**Instructor:** {{var:instructor_name}}  
**Email:** {{var:instructor_email}}  
**Office Hours:** {{var:office_hours}}
```

**Your page:**
```markdown
---
name: "Syllabus"
---

# Syllabus

## Contact Information

{{include:contact_info}}
```

The include uses the variables from shared/variables.yaml (or page frontmatter if overridden).

---

## Common Use Cases

### Course Details

```yaml
# shared/variables.yaml
course_code: "CS 101"
course_title: "Introduction to Programming"
semester: "Spring 2026"
section: "Section 001"
credits: "3"
```

### Contact Information

```yaml
# shared/variables.yaml
instructor_name: "Dr. Ada Lovelace"
instructor_email: "lovelace@university.edu"
ta_name: "Charles Babbage"
ta_email: "babbage@university.edu"
office_hours: "Tuesday/Thursday 3-5pm"
office_location: "Engineering Building, Room 142"
```

### External Links

```yaml
# shared/variables.yaml
lms_help: "https://help.canvas.edu"
library_link: "https://library.university.edu"
tutoring_link: "https://tutoring.university.edu/cs"
```

### Reusable Phrases

```yaml
# shared/variables.yaml
late_penalty: "10% per day, up to 3 days"
academic_integrity: "See the University Academic Integrity Policy"
```

---

## Tips

✅ **Use descriptive names** — `instructor_email` is clearer than `email`

✅ **Put shared values in shared/variables.yaml** — Less repetition

✅ **Override in frontmatter when needed** — Guest lectures, special cases

✅ **Combine with includes** — Create reusable templates with variable placeholders

✅ **Variables are text only** — They can't contain multi-line markdown

---

## Digging Deeper

## Global Level (`_all_courses/`)

For values shared across all your courses, create `_all_courses/shared/variables.yaml`:

```
courses/
├── _all_courses/
│   └── shared/
│       └── variables.yaml    # Shared across ALL courses
├── CS101/
└── CS102/
```

Best for: Institution name, standard policies, common links.

## Page Level Overrides

Define a variable in frontmatter to override the course-level value for that page only:

```yaml
---
name: "Guest Lecture"
instructor_name: "Dr. Jones"    # Overrides course-level for this page only
---

Today's lecture by {{var:instructor_name}}
```

Result: "Today's lecture by Dr. Jones"

---

## Debugging

If a variable isn't being replaced:

1. Check the spelling matches exactly (case-sensitive)
2. Check it's defined in shared/variables.yaml or page frontmatter
3. Run `zaphod sync` and look for warnings
4. Make sure dependencies are installed (`pip install -r requirements.txt`)

Variables that aren't found remain as `{{var:name}}` in the output, making them easy to spot.

---

## Variable Precedence Summary

| Level | Location | Priority |
|-------|----------|----------|
| Global | `_all_courses/shared/variables.yaml` | Lowest |
| Course | `<course>/shared/variables.yaml` | Medium |
| Page | Frontmatter | Highest |

Each level overrides values from lower levels.

---

## Variable Filters

Variables support an optional filter chain that transforms the value at publish time. Filters are separated by `|` and applied left-to-right:

```
{{var:variable_name | filter1 | filter2:arg}}
```

### `default:value`

Use a fallback value when the variable is not defined at any tier.

```
{{var:bg_color | default:#ffffff}}
{{var:instructor | default:TBA}}
```

Pairs well with `required` to surface misconfiguration while still providing a fallback:
```
{{var:course_code | required | default:UNKNOWN}}
```

### `required`

Emit a build-time warning if the variable is not set. The placeholder is left in place rather than crashing the build.

```
{{var:course_name | required}}
```

Terminal output:
```
⚠️  {{var:course_name | required}}: required variable 'course_name' is not set
```

### `upcase` / `downcase` / `titlecase`

```
{{var:course_name | upcase}}       -> JAVASCRIPT CARDS
{{var:course_name | downcase}}     -> javascript cards
{{var:course_name | titlecase}}    -> Javascript Cards
```

### `replace:old,new`

Replace a substring. Wrap values in quotes when they contain commas or spaces:

```
{{var:course_code | replace:_,' '}}     -> replaces _ with space
{{var:course_code | replace:-,_}}       -> replaces - with _
{{var:label | replace:',',' / '}}       -> replaces comma with ' / '
```

Omitting `new` deletes the matched string:
```
{{var:course_code | replace:COURSE-,}}  -> strips prefix
```

### `ordinal`

Render an integer as an ordinal string.

```
{{var:course_order | ordinal}}   -> "7th"
{{var:session | ordinal}}        -> "11th"
```

Works for 1st, 2nd, 3rd … 11th, 12th, 13th … 21st, 22nd, etc.

### `decimals:n`

Format a number to `n` decimal places.

```
{{var:gpa | decimals:2}}         -> "3.80"
{{var:progress | decimals:0}}    -> "75"
```

### Chaining

Filters compose naturally — each receives the output of the previous one:

```
{{var:course_name | replace:_,' ' | titlecase}}
-> "Javascript Cards"

{{var:missing_var | default:3 | ordinal}}
-> "3rd"

{{var:gpa | required | decimals:2}}
-> warns if missing, otherwise formats to 2 decimal places
```

### Round-trip behaviour

When a filtered variable is published to Canvas, the full expression is preserved in an HTML comment marker so that import restores it faithfully:

```html
<!-- {{var:course_name | replace:_,' ' | titlecase}} -->Javascript Cards<!-- {{/var:course_name | replace:_,' ' | titlecase}} -->
```

Comment markers survive Canvas API round-trips but are stripped if a user edits the page in the Canvas rich content editor. In that case the import pipeline falls back to plain text.

### Type coercion

All variable values are strings internally. Numeric filters (`ordinal`, `decimals`) attempt to parse the string and warn if they cannot:

```
⚠️  {{var:session | ordinal}}: 'ordinal' requires an integer, got 'eleven' — skipped
```

When a filter fails, the value passes through unchanged rather than crashing the build.

---

## Next Steps

- [Includes](04-includes.md) — Share larger content blocks
- [Pages](01-pages.md) — Using variables in pages
