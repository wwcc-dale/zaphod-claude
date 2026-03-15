# Authoring Quick Start

> Everything you need to start publishing course content to Canvas — no technical experience required.

---

Zaphod lets you write your course content in simple text files on your computer and then push it all to Canvas with one command. Think of it like this: instead of clicking through Canvas's web editor every time, you write your content in a text file (similar to writing a document), then run `zaphod sync` and Canvas updates automatically.

This guide walks you through every content type with the simplest possible examples. Once you've done it once, the pattern repeats for everything.

---

## The Pattern (This Is All You Need to Know)

Every piece of content follows the same pattern:

1. **Create a folder** with a special ending that tells Zaphod what it is
2. **Create a file inside** called `index.md`
3. **Write your content** — a small settings block at the top, your text below
4. **Run `zaphod sync`** — it appears in Canvas

That's it. Everything in this guide is a variation on those four steps.

---

## The Two Parts of Every File

Every `index.md` file has two sections separated by `---` lines:

```
---
name: "My Page Title"
published: true
---

Your content goes here.
```

**The settings block** (between the `---` lines) — called "frontmatter" — is where you tell Zaphod things like the title, which module it belongs in, and whether students can see it yet.

**The content** (after the second `---`) — this is the actual text students will read, written in a simple format called Markdown. It's mostly just plain text with a few special characters for formatting.

---

## Markdown in 30 Seconds

You don't need to learn much. Here's everything you'll use day-to-day:

```markdown
# Big Heading

## Smaller Heading

Regular paragraph text. Just type normally.

**Bold text**  and  *italic text*

- Bullet point
- Another bullet point

1. Numbered list
2. Second item

[Link text](https://example.com)

![Image description](my-image.png)
```

That's genuinely all most instructors ever need.

---

## Pages

Pages are for anything students need to read — welcome messages, lecture notes, weekly overviews, resource lists.

**Create the folder and file:**
```
content/
└── week-1-overview.page/
    └── index.md
```

**Write your index.md:**
```markdown
---
name: "Week 1 Overview"
modules:
  - "Week 1"
published: true
---

# Welcome to Week 1

This week we're diving into the foundations of the course.

## What You'll Do This Week

- Read the introduction chapter
- Watch the welcome video
- Introduce yourself in the discussion forum

## Resources

- [Course Textbook](https://library.example.edu/textbook)
- [Office Hours Sign-Up](https://calendly.com/instructor)

Questions? Email me at instructor@college.edu
```

**Then run:**
```bash
zaphod sync
```

Your page appears in Canvas inside the "Week 1" module.

---

## Assignments

Assignments are anything with a grade attached — essays, projects, homework, discussions.

**Create the folder and file:**
```
content/
└── essay-1.assignment/
    └── index.md
```

**Write your index.md:**
```markdown
---
name: "Essay 1: Personal Introduction"
modules:
  - "Week 1"
published: true
points_possible: 50
due_at: "2026-09-14T23:59:00"
submission_types:
  - online_upload
allowed_extensions:
  - pdf
  - docx
---

# Essay 1: Personal Introduction

Write a short essay (400–600 words) introducing yourself and what you hope to get
out of this course.

## What to Include

- Your background and what brought you to this subject
- One goal you have for the semester
- Any experience you already have with the topic

## Submission

Upload your essay as a PDF or Word document before the due date.
```

**Due date format:** `"2026-09-14T23:59:00"` means September 14, 2026 at 11:59pm. Just swap in your date.

**Submission types** you can use:
- `online_upload` — students upload a file (most common)
- `online_text_entry` — students type directly in Canvas
- `online_url` — students submit a link
- `none` — no online submission (for in-class work)

---

## Quizzes

Quizzes use a two-step setup: first you create a "question bank" with the questions, then you create the quiz that draws from it.

### Step 1 — Create a Question Bank

```
question-banks/
└── week-1-review.bank.md
```

```markdown
---
bank_name: "Week 1 Review Questions"
---

1. What is the main theme of Chapter 1?
a) The history of the subject
b) Key terminology *
c) Real-world applications
d) None of the above

2. True or False: The first chapter introduces core concepts.
a) True *
b) False
```

The `*` marks the correct answer.

### Step 2 — Create the Quiz

```
content/
└── week-1-quiz.quiz/
    └── index.md
```

```markdown
---
name: "Week 1 Review Quiz"
modules:
  - "Week 1"
published: true
points_possible: 10
allowed_attempts: 2
time_limit: 15
---

Test your understanding of Week 1 material.

---
questions:
  - group: "Week 1 Questions"
    bank: "Week 1 Review Questions"
    pick: 5
    points_per_question: 2
```

This quiz picks 5 random questions from the bank and gives 2 points each, for 10 points total. Students get 2 attempts and 15 minutes.

---

## External Links

Use a link item when you want a Canvas module entry that takes students directly to an external website — a video, a reading, a tool.

```
content/
└── textbook-reading.link/
    └── index.md
```

```markdown
---
name: "This Week's Reading — Chapter 1"
modules:
  - "Week 1"
published: true
url: "https://openstax.org/books/your-textbook/chapter-1"
---
```

Students click it in the module and go straight to the URL. No page content needed.

---

## Downloadable Files

Use a file item when you want students to download something — a PDF handout, a spreadsheet template, a data file.

```
content/
└── course-syllabus.file/
    ├── index.md
    └── syllabus.pdf
```

```markdown
---
name: "Course Syllabus"
modules:
  - "Start Here"
published: true
file: "syllabus.pdf"
---
```

Zaphod uploads `syllabus.pdf` to Canvas and creates a module entry students can click to download it.

---

## Images

To include an image on a page or assignment, put the image file in the same folder as `index.md` and reference it in your content:

```
content/
└── week-1-overview.page/
    ├── index.md
    └── diagram.png
```

```markdown
---
name: "Week 1 Overview"
---

Here's a diagram showing how everything connects:

![Concept diagram showing the relationship between key ideas](diagram.png)

The text in the square brackets is the description for screen readers —
always fill it in.
```

For images used on many different pages, put them in the shared `assets/` folder at the top of your course and reference them by filename from anywhere.

---

## Organising Into Modules

Modules keep your content organised into weeks, units, or topics. The recommended approach is module folders — each module is a folder with a `.module` ending, and everything inside it automatically belongs to that module.

```
content/
├── 01-Start Here.module/
│   ├── 01-welcome.page/
│   │   └── index.md
│   └── 02-syllabus.file/
│       ├── index.md
│       └── syllabus.pdf
├── 02-Week 1.module/
│   ├── 01-overview.page/
│   │   └── index.md
│   ├── 02-reading.link/
│   │   └── index.md
│   └── 03-quiz.quiz/
│       └── index.md
└── 03-Week 2.module/
    └── ...
```

The numbers at the front (`01-`, `02-`) set the order. Zaphod strips them from the names — so `01-Start Here.module` becomes a module called "Start Here" in Canvas.

If you prefer, you can skip the module folder structure and just put the module name in each file's frontmatter:

```markdown
---
name: "Week 1 Overview"
modules:
  - "Week 1"
published: true
---
```

Both approaches work fine.

---

## Variables — Write Once, Update Everywhere

If you find yourself typing the same thing on many pages (your email address, office hours, a due date policy), define it once as a variable and reference it everywhere.

**Create `shared/variables.yaml` in your course folder:**

```yaml
instructor_name: "Dr. Rivera"
instructor_email: "rivera@college.edu"
office_hours: "Tuesday and Thursday, 2–4pm"
late_policy: "10% deducted per day, up to 3 days late"
```

**Use it in any page:**

```markdown
Questions? Reach {{var:instructor_name}} at {{var:instructor_email}}.

Office hours: {{var:office_hours}}
```

When you update the variable, every page that uses it updates the next time you sync. No hunting through files.

---

## Includes — Reuse Whole Sections

If you have a paragraph or section that appears on many pages — a late work policy, a note about accessibility services, submission instructions — write it once as an include file and drop it in wherever you need it.

**Create `shared/late-policy.md`:**

```markdown
## Late Work Policy

Assignments submitted after the due date receive a deduction of {{var:late_policy}}.
No work accepted more than 3 days late without prior arrangement.
```

**Reference it in any page:**

```markdown
---
name: "Essay 1"
---

# Essay 1: Personal Introduction

Write a 400–600 word introduction essay.

{{include:late-policy}}
```

Zaphod drops the include content in at that spot when it publishes the page.

---

## The Publishing Workflow

Day-to-day, this is all you do:

```bash
# See what's changed (without touching Canvas)
zaphod sync --dry-run

# Publish to Canvas
zaphod sync
```

**Watch mode** — if you're making several changes at once, this syncs automatically every time you save a file:

```bash
zaphod sync --watch
```

**Check for problems before syncing:**

```bash
zaphod validate
```

---

## Quick Reference — Content Type Endings

| Folder ending | Creates in Canvas |
|---------------|-------------------|
| `my-page.page/` | A Page |
| `my-assignment.assignment/` | An Assignment |
| `my-quiz.quiz/` | A Quiz |
| `my-link.link/` | An External Link |
| `my-file.file/` | A Downloadable File |
| `My Module.module/` | A Module |

---

## Quick Reference — Common Frontmatter Fields

| Field | What it does | Example |
|-------|-------------|---------|
| `name:` | Title shown in Canvas | `"Week 1 Overview"` |
| `published:` | Whether students can see it | `true` or `false` |
| `modules:` | Which module(s) it belongs to | `- "Week 1"` |
| `points_possible:` | Point value (assignments/quizzes) | `100` |
| `due_at:` | Due date and time | `"2026-09-14T23:59:00"` |
| `submission_types:` | How students submit | `- online_upload` |

---

## Something Isn't Working?

**Nothing appeared in Canvas:**
- Did you run `zaphod sync`?
- Is `published: true` in the frontmatter?
- Check the terminal output for any error messages

**The page appeared but looks wrong:**
- Check for typos in your YAML (frontmatter is sensitive to indentation)
- Run `zaphod validate` to catch common issues

**A variable isn't being replaced:**
- Check the spelling — variable names are case-sensitive
- Make sure `shared/variables.yaml` exists and is valid YAML

---

You're ready to go. Start with one page, sync it, check Canvas — then add more when you're comfortable. The more you use it, the more natural it becomes.
