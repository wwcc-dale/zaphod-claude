# Rubrics

> Rubrics define grading criteria for assignments. Write them once in YAML, and Zaphod creates them in Canvas and attaches them to assignments.

---

## Basic Rubric

Create a `rubric.yaml` file inside your `.assignment` folder:

```
pages/
└── essay-1.assignment/
    ├── index.md
    └── rubric.yaml
```

**rubric.yaml:**
```yaml
title: "Essay Rubric"

criteria:
  - description: "Thesis Statement"
    points: 25
    ratings:
      - description: "Clear and compelling thesis"
        points: 25
      - description: "Thesis present but unclear"
        points: 15
      - description: "No clear thesis"
        points: 0

  - description: "Supporting Evidence"
    points: 25
    ratings:
      - description: "Strong, relevant evidence"
        points: 25
      - description: "Some evidence provided"
        points: 15
      - description: "Little or no evidence"
        points: 0

  - description: "Organization"
    points: 25
    ratings:
      - description: "Logical flow throughout"
        points: 25
      - description: "Some organizational issues"
        points: 15
      - description: "Disorganized"
        points: 0

  - description: "Writing Quality"
    points: 25
    ratings:
      - description: "Clear, error-free writing"
        points: 25
      - description: "Minor errors"
        points: 15
      - description: "Significant errors"
        points: 0
```

---

## Rubric Structure

```yaml
title: "Rubric Name"           # Required

criteria:                       # Required - list of criteria
  - description: "..."          # Required - criterion name
    points: 25                  # Required - maximum points
    long_description: "..."     # Optional - detailed description
    use_range: true             # Optional - enable range scoring
    ratings:                    # Required - list of rating levels
      - description: "..."      # Required - rating name  
        points: 25              # Required - points for this level
        long_description: "..." # Optional - detailed description
```

---

## Rating Levels

Ratings should go from highest to lowest points:

```yaml
criteria:
  - description: "Content Quality"
    points: 40
    ratings:
      - description: "Exemplary"
        points: 40
      - description: "Proficient"
        points: 32
      - description: "Developing"
        points: 24
      - description: "Beginning"
        points: 16
      - description: "Not Demonstrated"
        points: 0
```

**Tips:**
- Include a 0-point rating for incomplete/missing work
- Use consistent rating names across criteria
- Points don't have to be evenly spaced

---

## Advanced Options

### Long Descriptions

Add detailed explanations for criteria and ratings:

```yaml
criteria:
  - description: "Analysis"
    long_description: "The depth and quality of analytical thinking"
    points: 30
    ratings:
      - description: "Excellent"
        long_description: "Demonstrates sophisticated analysis with multiple perspectives and original insights"
        points: 30
      - description: "Good"
        long_description: "Shows solid analysis with clear reasoning"
        points: 22
```

### Range Scoring

Enable range scoring to allow any point value within a range:

```yaml
criteria:
  - description: "Participation"
    points: 20
    use_range: true    # Allows scoring like 17/20
    ratings:
      - description: "Full Participation"
        points: 20
      - description: "Partial Participation"
        points: 10
      - description: "No Participation"
        points: 0
```

### Free-Form Comments

Allow free-form comments on each criterion:

```yaml
title: "Project Rubric"
free_form_criterion_comments: true

criteria:
  - ...
```

---

## Shared Rubrics

If you use the same rubric for multiple assignments, create a shared rubric:

### 1. Create the Shared Rubric

```
my-course/
└── rubrics/
    └── essay_rubric.yaml
```

**rubrics/essay_rubric.yaml:**
```yaml
title: "Standard Essay Rubric"

criteria:
  - description: "Thesis"
    points: 25
    ratings:
      - description: "Excellent"
        points: 25
      - description: "Satisfactory"
        points: 15
      - description: "Needs Work"
        points: 5
  # ... more criteria
```

### 2. Reference It in Your Assignment

**pages/essay-1.assignment/rubric.yaml:**
```yaml
use_rubric: "essay_rubric"
```

That's it! Zaphod loads the shared rubric and attaches it to the assignment.

---

## Reusable Rubric Rows

For even more reuse, create individual criterion rows that can be mixed and matched:

### 1. Create Rubric Rows

```
my-course/
└── rubrics/
    └── rows/
        ├── thesis.yaml
        ├── evidence.yaml
        ├── organization.yaml
        └── writing_quality.yaml
```

**rubrics/rows/thesis.yaml:**
```yaml
description: "Thesis Statement"
points: 25
ratings:
  - description: "Clear and compelling thesis"
    points: 25
  - description: "Thesis present but unclear"
    points: 15
  - description: "No clear thesis"
    points: 0
```

### 2. Use Rows in Your Rubric

**pages/essay-1.assignment/rubric.yaml:**
```yaml
title: "Essay 1 Rubric"

criteria:
  - "{{rubric_row:thesis}}"
  - "{{rubric_row:evidence}}"
  - "{{rubric_row:organization}}"
  - "{{rubric_row:writing_quality}}"
```

### 3. Mix Custom and Reusable

```yaml
title: "Research Paper Rubric"

criteria:
  - "{{rubric_row:thesis}}"
  - "{{rubric_row:evidence}}"
  - description: "Research Sources"      # Custom criterion
    points: 30
    ratings:
      - description: "5+ scholarly sources"
        points: 30
      - description: "3-4 scholarly sources"
        points: 20
      - description: "1-2 sources or non-scholarly"
        points: 10
  - "{{rubric_row:writing_quality}}"
```

---

## Complete Example

**rubrics/rows/writing_mechanics.yaml:**
```yaml
description: "Writing Mechanics"
long_description: "Grammar, spelling, punctuation, and sentence structure"
points: 20
use_range: true
ratings:
  - description: "Polished"
    long_description: "Nearly error-free, professional quality"
    points: 20
  - description: "Competent"
    long_description: "Minor errors that don't impede understanding"
    points: 15
  - description: "Developing"
    long_description: "Noticeable errors that occasionally impede understanding"
    points: 10
  - description: "Needs Revision"
    long_description: "Frequent errors that impede understanding"
    points: 5
  - description: "Unacceptable"
    points: 0
```

**pages/essay-1.assignment/rubric.yaml:**
```yaml
title: "Persuasive Essay Rubric"
free_form_criterion_comments: true

criteria:
  - description: "Argument Quality"
    points: 40
    ratings:
      - description: "Compelling"
        points: 40
      - description: "Convincing"
        points: 32
      - description: "Adequate"
        points: 24
      - description: "Weak"
        points: 12
      - description: "No clear argument"
        points: 0
  
  - description: "Use of Evidence"
    points: 40
    ratings:
      - description: "Excellent"
        points: 40
      - description: "Good"
        points: 30
      - description: "Adequate"
        points: 20
      - description: "Insufficient"
        points: 10
      - description: "Missing"
        points: 0
  
  - "{{rubric_row:writing_mechanics}}"
```

---

## Tips

✅ **Use consistent point totals** — 100 points makes grading intuitive

✅ **Include a 0-point rating** — For incomplete/missing work

✅ **Use long descriptions** — Clearer expectations for students

✅ **Create reusable rows** — Common criteria like "writing quality"

✅ **Sync before the assignment** — Rubric must exist after assignment is created

---

## File Formats

Rubrics can be YAML or JSON:

- `rubric.yaml` or `rubric.yml` (recommended)
- `rubric.json`

---

## Next Steps

- [Assignments](02-assignments.md) — Creating assignments with rubrics
- [Variables](03-variables.md) — Dynamic content
