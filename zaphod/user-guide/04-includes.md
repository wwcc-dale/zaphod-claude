# Includes

> Includes let you share larger blocks of content across multiple pages. Write it once, use it everywhere.

---

## Why Use Includes?

Some content appears on many pages:
- Late work policies
- Academic integrity statements
- Office hours information
- Assignment submission instructions

Instead of copying this text to every page (and updating 20 files when it changes), create an include and reference it:

```markdown
{{include:late_policy}}
```

---

## Basic Usage

### 1. Create an Include File

Create a file in your `includes/` folder:

```
my-course/
└── includes/
    └── late_policy.md
```

**includes/late_policy.md:**
```markdown
## Late Work Policy

Assignments submitted late will receive a 10% penalty per day, up to a maximum of 3 days. After 3 days, late submissions will not be accepted without prior arrangement.

If you need an extension, please contact the instructor **before** the due date.
```

### 2. Use It in Your Pages

```markdown
---
name: "Essay 1"
---

# Essay 1

Write a 500-word essay...

{{include:late_policy}}
```

### 3. Result

The `{{include:late_policy}}` is replaced with the entire contents of `late_policy.md`.

---

## Include Syntax

```
{{include:name}}
```

- `name` corresponds to `includes/name.md`
- Names can contain letters, numbers, underscores, and hyphens
- The `.md` extension is added automatically

---

## Where to Put Include Files

Includes are searched in this order:

### 1. Course Pages Includes (Highest Priority)

```
my-course/
└── pages/
    └── includes/
        └── late_policy.md    # Found first
```

### 2. Course Root Includes

```
my-course/
└── includes/
    └── late_policy.md        # Found second
```

### 3. Shared Across All Courses (Lowest Priority)

```
courses/
├── _all_courses/
│   └── includes/
│       └── late_policy.md    # Found last (fallback)
├── CS101/
└── CS102/
```

This lets you:
- Share common content across all courses
- Override at the course level when needed
- Override at the page level for special cases

---

## Variables in Includes

Includes can use variables! The variables come from the page that's using the include.

**includes/contact_info.md:**
```markdown
## Contact Your Instructor

- **Name:** {{var:instructor_name}}
- **Email:** {{var:instructor_email}}
- **Office Hours:** {{var:office_hours}}
```

**pages/syllabus.page/index.md:**
```yaml
---
name: "Syllabus"
instructor_name: "Dr. Smith"
instructor_email: "smith@university.edu"
office_hours: "Monday/Wednesday 2-4pm"
---

# Course Syllabus

{{include:contact_info}}
```

**Result:**
```markdown
# Course Syllabus

## Contact Your Instructor

- **Name:** Dr. Smith
- **Email:** smith@university.edu
- **Office Hours:** Monday/Wednesday 2-4pm
```

---

## Nested Includes

Includes can contain other includes (recursive):

**includes/policies.md:**
```markdown
## Course Policies

{{include:late_policy}}

{{include:academic_integrity}}

{{include:attendance_policy}}
```

**Your page:**
```markdown
{{include:policies}}
```

This pulls in all three policy files through one include.

---

## Common Include Patterns

### Policy Statements

```
includes/
├── academic_integrity.md
├── accommodation_statement.md
├── attendance_policy.md
├── grading_scale.md
└── late_policy.md
```

### Contact Blocks

```
includes/
├── contact_instructor.md
├── contact_ta.md
├── office_hours.md
└── tutoring_info.md
```

### Assignment Templates

```
includes/
├── submission_instructions.md
├── file_naming_convention.md
└── peer_review_guidelines.md
```

### Reusable Warnings/Notes

```
includes/
├── important_deadline.md
├── required_reading.md
└── technology_requirements.md
```

---

## Example: Building a Syllabus

**includes/course_description.md:**
```markdown
## Course Description

This course introduces fundamental concepts of computer programming...
```

**includes/learning_objectives.md:**
```markdown
## Learning Objectives

By the end of this course, you will be able to:

1. Write simple programs in Python
2. Debug and test your code
3. ...
```

**pages/syllabus.page/index.md:**
```yaml
---
name: "Course Syllabus"
instructor_name: "Dr. Smith"
office_hours: "MW 2-4pm"
---

# CS 101 Syllabus

{{include:course_description}}

{{include:learning_objectives}}

{{include:contact_info}}

{{include:policies}}

{{include:grading_scale}}
```

One syllabus page, built from reusable pieces!

---

## Tips

✅ **Keep includes focused** — One topic per file

✅ **Use clear names** — `late_policy.md` not `policy1.md`

✅ **Put shared content in _all_courses** — For institution-wide policies

✅ **Use variables for customization** — Same template, different values

✅ **Don't over-nest** — Keep it readable (2-3 levels max)

---

## Debugging

If an include isn't working:

1. Check the filename matches (case-sensitive): `{{include:Late_Policy}}` ≠ `late_policy.md`
2. Check the file exists in one of the include folders
3. Look for warnings when running `zaphod sync`

Missing includes show a warning and remain as `{{include:name}}` in the output.

---

## Next Steps

- [Variables](03-variables.md) — Dynamic values in includes
- [Pages](01-pages.md) — Using includes in pages
