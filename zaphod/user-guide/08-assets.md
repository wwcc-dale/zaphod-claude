# Assets

> Assets are the images, videos, PDFs, and other files you include in your course. Zaphod handles uploading them to Canvas and keeping track of them.

---

## Where to Put Assets

You have two options:

### 1. Shared Assets Folder

For files used on multiple pages:

```
my-course/
└── assets/
    ├── course-logo.png
    ├── syllabus.pdf
    └── videos/
        └── intro.mp4
```

### 2. Content Folder

For files used only on one page:

```
pages/
└── welcome.page/
    ├── index.md
    └── welcome-banner.png    # Only used here
```

---

## Using Images

### Basic Image

```markdown
![Description](image-name.png)
```

Zaphod looks for the image in:
1. The same folder as `index.md`
2. The `assets/` folder (including subfolders)

### From Assets Folder

```markdown
![Course Logo](course-logo.png)
```

Zaphod finds it in `assets/course-logo.png`.

### From Subfolder

```markdown
![Chart](charts/figure1.png)
```

Zaphod finds it in `assets/charts/figure1.png`.

### Explicit Path

```markdown
![Banner](../assets/images/banner.png)
```

Use explicit paths when you need precision.

---

## Using Videos

### Video Placeholder

For videos that should become Canvas media players:

```markdown
{{video:lecture1.mp4}}
```

**What happens:**
1. Zaphod finds `lecture1.mp4` in assets or content folder
2. Uploads it to Canvas (with caching)
3. Replaces the placeholder with a Canvas media iframe

### Result in Canvas

The video appears as an embedded player, not a download link.

---

## File Downloads

### Link to a File

```markdown
Download the [worksheet](worksheet.pdf).
```

Zaphod uploads `worksheet.pdf` and converts the link.

### Dedicated File Item

For important downloads, create a `.file` folder:

```
pages/
└── syllabus.file/
    ├── index.md
    └── CS101-Syllabus-Spring2026.pdf
```

**index.md:**
```yaml
---
name: "Course Syllabus"
filename: "CS101-Syllabus-Spring2026.pdf"
modules:
  - "Course Resources"
---
```

This creates a dedicated file item that appears in Canvas modules view alongside pages, assignments and quizzes allowing students to download it directly.

---

## Asset Organization

### Recommended Structure

```
assets/
├── images/
│   ├── diagrams/
│   ├── photos/
│   └── icons/
├── documents/
│   ├── handouts/
│   └── templates/
├── videos/
│   ├── lectures/
│   └── tutorials/
└── data/
    └── datasets/
```

### Flat Structure (Also Fine)

```
assets/
├── logo.png
├── syllabus.pdf
├── lecture1.mp4
└── dataset.csv
```

---

## Caching

Zaphod caches uploaded files to avoid re-uploading:

**Cache location:** `_course_metadata/upload_cache.json`

**Cache key:** `{course_id}:{filename}:{content_hash}`

**This means:**
- Same file, same content → skip upload (uses cache)
- Same filename, different content → re-upload
- Different course → upload again

### Clearing the Cache

If you need to force re-upload:

```bash
rm _course_metadata/upload_cache.json
zaphod sync
```

---

## Large Media Files

For very large files (videos, high-res images), consider:

### Option 1: Keep in Git

Fine for files under ~50MB. Just add to `assets/`.

### Option 2: Git LFS

For larger files, use Git Large File Storage:

```bash
git lfs track "*.mp4"
git lfs track "*.mov"
```

### Option 3: Media Manifest

For very large files, keep them out of Git entirely:

1. Add large extensions to `.gitignore`:
   ```
   assets/*.mp4
   assets/*.mov
   ```

2. Build a manifest:
   ```bash
   python zaphod/build_media_manifest.py
   ```

3. Share the original files via network drive or cloud storage

4. Team members hydrate from the shared source:
   ```bash
   python zaphod/hydrate_media.py --source "\\server\courses\CS101"
   ```

See [Manifest & Hydrate](11-manifest-hydrate.md) for details.

---

## Supported File Types

### Images
- `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg`

### Videos
- `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`

### Documents
- `.pdf`, `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, `.xlsx`

### Data
- `.csv`, `.json`, `.xml`

### Archives
- `.zip`, `.tar`, `.gz`

---

## Troubleshooting

### Image Not Showing

1. Check the filename matches exactly (case-sensitive)
2. Make sure the file exists in assets or content folder
3. Run `zaphod sync --dry-run` to see what Zaphod finds

### Video Not Playing

1. Check the file format is supported (.mp4 works best)
2. Make sure you're using `{{video:...}}` not regular markdown
3. Check the upload completed (look for messages during sync)

### Duplicate Filenames

If you have `assets/logo.png` and `assets/images/logo.png`:
- Zaphod will warn about the duplicate
- Use explicit paths to resolve: `images/logo.png`

---

## Tips

✅ **Use descriptive filenames** — `week1-diagram.png` not `image1.png`

✅ **Organize in subfolders** — Easier to find things

✅ **Keep originals** — Store high-res versions outside assets

✅ **Use .mp4 for video** — Best Canvas compatibility

✅ **Check file sizes** — Compress large images before adding

---

## Next Steps

- [Pages](01-pages.md) — Using assets in pages
- [Manifest & Hydrate](11-manifest-hydrate.md) — Managing large files
