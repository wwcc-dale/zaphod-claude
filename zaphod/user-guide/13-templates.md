# Templates - Automatic Headers & Footers

Zaphod templates provide automatic header/footer wrapping for pages and assignments. This eliminates repetitive copying and pasting of common content.

---

## Overview

**Templates** wrap your content with consistent headers and footers during publishing. Unlike includes (which you manually insert), templates are applied automatically to all pages.

### When to Use Templates

✅ **Use templates for:**
- Course-wide headers (navigation, announcements)
- Consistent footers (contact info, policies)
- Branding and styling
- Content that appears on *every* page

❌ **Use includes for:**
- Content inserted in *some* pages
- Conditional content blocks
- Reusable snippets within content

---

## Directory Structure

Templates live in `templates/` at your course root:

```
my-course/
├── templates/
│   ├── default/              # Used by default
│   │   ├── header.html
│   │   ├── header.md
│   │   ├── footer.md
│   │   └── footer.html
│   ├── fancy/                # Alternative template set
│   │   ├── header.html
│   │   ├── header.md
│   │   ├── footer.md
│   │   └── footer.html
│   └── minimal/              # Another option
│       └── footer.md
├── pages/
└── ...
```

---

## Template Files

Each template set can have up to 4 files:

| File | Purpose | Format |
|------|---------|--------|
| `header.html` | HTML header | Raw HTML |
| `header.md` | Markdown header | Markdown → HTML |
| `footer.md` | Markdown footer | Markdown → HTML |
| `footer.html` | HTML footer | Raw HTML |

**All files are optional.** If a file doesn't exist, it's skipped.

---

## Application Order

Templates wrap your content in this order:

```
1. header.html
2. header.md (converted to HTML)
3. [YOUR PAGE CONTENT]
4. footer.md (converted to HTML)
5. footer.html
```

**Example output:**
```html
<!-- header.html -->
<div class="course-banner">Welcome to CS101</div>

<!-- header.md → HTML -->
<p><strong>Important:</strong> All assignments due by midnight.</p>

<!-- Your page content -->
<h1>Lesson 1: Variables</h1>
<p>Variables store data...</p>

<!-- footer.md → HTML -->
<hr>
<p>Questions? Email your instructor.</p>

<!-- footer.html -->
<div class="footer">© 2026 Your University</div>
```

---

## Using Templates

### Default Behavior

Pages automatically use `templates/default/`:

```yaml
---
name: "My Page"
# Uses templates/default/ automatically
---

Your content here.
```

### Choosing a Template Set

Use `template:` in frontmatter to choose a different set:

```yaml
---
name: "Fancy Page"
template: "fancy"         # Uses templates/fancy/
---

This page gets the fancy template.
```

### Skipping Templates

Disable templates for individual pages:

```yaml
---
name: "Plain Page"
template: null            # No wrapping
---

This page has no header or footer.
```

---

## Example: Course Navigation Header

**Create:** `templates/default/header.md`

```markdown
**Navigation:** [Home](/) | [Syllabus](/syllabus) | [Assignments](/assignments) | [Grades](/grades)

---
```

**Result:** Every page gets this navigation bar at the top.

**Update once, changes everywhere.** Edit `header.md` and re-sync—all pages update.

---

## Example: Contact Footer

**Create:** `templates/default/footer.md`

```markdown
---

## Need Help?

- **Email:** instructor@university.edu
- **Office Hours:** Mon/Wed 2-4pm, Room 301
- **Discussion Forum:** [Canvas Discussions](/discussions)
```

**Result:** Every page gets consistent contact info.

---

## Example: HTML Branding

**Create:** `templates/default/header.html`

```html
<div style="background: #003366; color: white; padding: 10px; margin-bottom: 20px;">
  <img src="/logo.png" alt="University Logo" height="40">
  <span style="font-size: 1.2em; margin-left: 10px;">CS 101 - Intro to Programming</span>
</div>
```

**Result:** Professional branded header on every page.

---

## Multiple Template Sets

Create different templates for different content types:

### Example Setup

**templates/default/** - Standard pages
```
default/
├── header.md     # Simple navigation
└── footer.md     # Contact info
```

**templates/fancy/** - Special events
```
fancy/
├── header.html   # Full banner with graphics
├── header.md     # Event announcement
├── footer.md     # Event details
└── footer.html   # Styled footer
```

**templates/minimal/** - Clean pages
```
minimal/
└── footer.md     # Just copyright
```

### Using in Pages

```yaml
# pages/lesson.page/index.md
---
name: "Regular Lesson"
# Uses default template
---

# pages/hackathon.page/index.md
---
name: "Hackathon Event"
template: "fancy"        # Special styling
---

# pages/reference.page/index.md
---
name: "API Reference"
template: "minimal"      # Less clutter
---
```

---

## Templates vs Includes

| Feature | Templates | Includes |
|---------|-----------|----------|
| **Application** | Automatic | Manual |
| **Location** | `templates/` | `shared/` |
| **Syntax** | Frontmatter: `template: "name"` | Content: `{{include:name}}` |
| **Scope** | Whole page (wrap) | Inline (insert) |
| **Best for** | Headers/footers | Content blocks |

**Can use both together:**

```yaml
---
name: "Course Syllabus"
template: "default"      # Gets header/footer automatically
---

# Syllabus

{{include:grading_policy}}

{{include:late_policy}}
```

---

## Template Variables

Templates can use variables! Define once, use everywhere.

**templates/default/header.md:**
```markdown
**Course:** {{var:course_name}} | **Instructor:** {{var:instructor}}

---
```

**pages/lesson.page/index.md:**
```yaml
---
name: "Lesson 1"
course_name: "CS 101"
instructor: "Dr. Smith"
---
```

**Result:** Header shows "Course: CS 101 | Instructor: Dr. Smith"

**Global variables:** Put them in `shared/variables.yaml` to share across all pages.

---

## Common Use Cases

### 1. Course-Wide Announcements

**templates/default/header.md:**
```markdown
> **📢 Midterm Exam:** Friday, March 15 @ 2pm

---
```

Change once → updates all pages.

### 2. Late Policy Footer

**templates/default/footer.md:**
```markdown
---

**Late Policy:** Assignments accepted up to 48 hours late with 10% penalty per day.
```

### 3. Canvas Theme Integration

**templates/default/header.html:**
```html
<link rel="stylesheet" href="https://cdn.example.com/canvas-theme.css">
<div class="canvas-header-wrapper">
  <!-- Your header content -->
</div>
```

### 4. Accessibility Notices

**templates/default/footer.md:**
```markdown
---

**Accessibility:** Need accommodations? Contact [Disability Services](mailto:access@university.edu)
```

---

## Best Practices

### ✅ Do This

- **Keep templates simple** - Complex HTML can break in Canvas
- **Test in sandbox** - Preview before publishing to live course
- **Use semantic HTML** - `<header>`, `<footer>`, `<nav>` tags
- **Mobile-friendly** - Avoid fixed widths, use responsive design
- **Version control** - Track template changes in git

### ❌ Avoid This

- **Heavy JavaScript** - Canvas sanitizes scripts
- **External dependencies** - Keep CSS/images local or in Canvas
- **Template-specific content** - Don't put lesson content in templates
- **Overusing HTML templates** - Markdown is easier to maintain

---

## Troubleshooting

### Templates not appearing

**Check:**
1. Template files exist in `templates/default/`
2. Files are named correctly (e.g., `header.md` not `header.markdown`)
3. Template set name matches: `template: "fancy"` → `templates/fancy/`
4. Re-sync after changing templates

### Markdown not rendering

**Issue:** Template files must be UTF-8 encoded.

**Fix:**
```bash
file templates/default/header.md
# Should show: UTF-8 Unicode text
```

### Template applies to wrong pages

**Check frontmatter:**
```yaml
---
name: "My Page"
template: null     # Explicitly skip templates
---
```

---

## Migration from markdown2canvas

If you used markdown2canvas's "styles" folder:

**Old (markdown2canvas):**
```
styles/
├── header.html
└── footer.html
```

**New (Zaphod):**
```
templates/
└── default/
    ├── header.html
    ├── header.md
    ├── footer.md
    └── footer.html
```

**Changes:**
1. Rename `styles/` → `templates/default/`
2. All pages use `default` template automatically
3. Can now have multiple template sets

---

## Summary

**Templates provide automatic header/footer wrapping:**

- ✅ Consistent styling across all pages
- ✅ Update once, changes propagate everywhere
- ✅ Multiple template sets for different content types
- ✅ Optional per-page (can skip with `template: null`)
- ✅ Works with variables and includes

**Quick start:**
```bash
# 1. Create template directory
mkdir -p templates/default

# 2. Add a footer
cat > templates/default/footer.md << 'EOF'
---

Questions? Email instructor@university.edu
EOF

# 3. Sync to Canvas
zaphod sync

# All pages now have the footer!
```

---

**Next:** [File Layout](15-file-layout.md)
