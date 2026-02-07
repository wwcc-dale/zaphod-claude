# Asset Workflow for Course Authors

A practical guide to managing images, videos, documents, and other media files in your Zaphod course with the Asset Registry system.

---

## Quick Answer: Where Should I Put My Files?

**TL;DR:**
- 📄 **Page-specific assets** → Put in the `.page/` or `.assignment/` folder
- 🌍 **Shared assets** (logos, common images) → Put in `assets/` folder
- 🎬 **Videos** → Put in `assets/videos/`
- 📦 **Don't worry about duplicates** → Registry automatically handles them!

---

## How Asset Registry Works

### The Magic: Content-Hash Deduplication

The Asset Registry identifies files by their **content** (not filename or location). This means:

**Same file = One upload to Canvas, no matter where it lives locally**

```
Example:
  pages/page1.page/logo.png     ← School logo (hash: abc123)
  pages/page2.page/logo.png     ← Same logo (hash: abc123)
  assets/images/logo.png        ← Same logo (hash: abc123)

  Result: One upload to Canvas, all three references work!
```

### What This Means for You

✅ **Put files wherever makes sense** - Organization is about your workflow, not efficiency
✅ **Copy files freely** - Identical files aren't uploaded twice
✅ **Move files later** - Change organization without re-uploading
✅ **Update once, affect all** - Change a shared file, all pages get the update

---

## Scenario Guide: What Happens When...

### Scenario 1: Same File in Multiple Pages

**Setup:**
```
pages/
  chapter1.page/
    index.md         → ![Campus Photo](campus.jpg)
    campus.jpg       ← Photo of library
  chapter2.page/
    index.md         → ![Campus Photo](campus.jpg)
    campus.jpg       ← Identical photo
  chapter3.page/
    index.md         → ![Campus Photo](campus.jpg)
    campus.jpg       ← Identical photo
```

**What happens on sync:**
1. chapter1 uploads `campus.jpg` → Canvas file ID: 456
2. Registry tracks: `content-hash-abc123 → file_456`
3. chapter2 finds identical file (same hash) → Reuses file_456 ✅
4. chapter3 finds identical file (same hash) → Reuses file_456 ✅

**Result:**
- One upload to Canvas
- All three pages show the same image
- No wasted storage or bandwidth

---

### Scenario 2: File in .page Folder AND assets/ Folder

**Setup:**
```
pages/
  welcome.page/
    index.md         → ![Logo](logo.png)
    logo.png         ← School logo
  policies.page/
    index.md         → ![Logo](../../assets/images/logo.png)
assets/
  images/
    logo.png         ← Same school logo
```

**What happens on sync:**
1. welcome.page uploads from `.page/logo.png` → Canvas file_456
2. Registry: `content-hash-def789 → file_456`
3. policies.page references `../../assets/images/logo.png`
4. Same content hash → Reuses file_456 ✅

**Result:**
- One upload
- Both pages reference the same Canvas file
- Different local paths, same result

---

### Scenario 3: Different Files, Same Name

**Setup:**
```
pages/
  chapter1.page/
    index.md         → ![Screenshot](screenshot.png)
    screenshot.png   ← Chapter 1 interface
  chapter2.page/
    index.md         → ![Screenshot](screenshot.png)
    screenshot.png   ← Chapter 2 interface (different image)
```

**What happens on sync:**
1. chapter1 uploads screenshot.png → Hash: aaa111 → Canvas file_100
2. chapter2 uploads screenshot.png → Hash: bbb222 → Canvas file_101
3. Different content = Different uploads ✅

**Result:**
- Two uploads (different content)
- Each page shows its own screenshot
- Registry tracks both separately

---

### Scenario 4: File Updated

**Setup:**
```
assets/images/banner.jpg   ← Original banner

Multiple pages reference:
  ![Banner](../../assets/images/banner.jpg)
```

**You update the file:**
```bash
cp new-banner.jpg assets/images/banner.jpg
zaphod sync
```

**What happens:**
1. Content hash changes (abc123 → xyz789)
2. New upload triggered automatically
3. New registry entry created
4. **All pages now show the new banner** ✅
5. Old registry entry kept (historical record)

**Result:**
- Update file once
- All references automatically updated
- No manual intervention needed

---

## File Search Priority

When you reference a file, Zaphod searches in this order:

### 1. Content Folder Itself
```markdown
<!-- pages/welcome.page/index.md -->
![Logo](logo.png)
```
Looks for: `pages/welcome.page/logo.png` ← **Found first**

### 2. Explicit Relative Path
```markdown
![Logo](../../assets/images/logo.png)
```
Resolves from content folder location ← **Explicit path wins**

### 3. Assets Directory (Relative)
```markdown
![Logo](images/logo.png)
```
Looks for: `assets/images/logo.png` ← **Searches assets/**

### 4. Auto-Discover in assets/
```markdown
![Photo](campus-photo.jpg)
```
Searches all `assets/` subfolders for `campus-photo.jpg`

**Warning:** If multiple files have the same name:
```
[assets:warn] Multiple files named 'photo.jpg' found:
        - assets/chapter1/photo.jpg
        - assets/chapter2/photo.jpg
        Use explicit path, e.g., ../assets/chapter1/photo.jpg
```

---

## Best Practices

### Strategy 1: Hybrid Organization (Recommended)

**Shared assets in assets/, page-specific in .page folders**

```
my-course/
  assets/
    images/
      school-logo.png           ← Used everywhere
      default-banner.jpg        ← Course-wide banner
    documents/
      syllabus.pdf              ← Referenced from multiple pages
      course-policies.pdf
    videos/
      intro-lecture.mp4         ← Embedded in multiple pages
    css/
      custom-styles.css         ← Global styling

  pages/
    01-welcome.module/
      01-welcome.page/
        index.md
        welcome-banner.jpg      ← Unique to this page
        orientation-map.png     ← Only used here
      02-syllabus.page/
        index.md
        # References shared assets via ../../assets/
```

**In your markdown:**
```markdown
<!-- Page-specific asset (same folder) -->
![Welcome Banner](welcome-banner.jpg)

<!-- Shared assets (assets/ folder) -->
![School Logo](../../assets/images/school-logo.png)
[Download Syllabus](../../assets/documents/syllabus.pdf)
{{video:intro-lecture.mp4}}
```

**Advantages:**
- ✅ Clear which assets are shared vs. unique
- ✅ Easy to find page-specific content
- ✅ Shared assets easy to update globally
- ✅ Self-contained page folders

---

### Strategy 2: All Assets Centralized

**Everything in assets/ folder**

```
my-course/
  assets/
    module-1/
      welcome-banner.jpg
      orientation-map.png
    module-2/
      chapter-diagram.png
    shared/
      school-logo.png
      default-banner.jpg
    videos/
      lecture-01.mp4
      lecture-02.mp4
    documents/
      syllabus.pdf

  pages/
    01-welcome.module/
      01-welcome.page/
        index.md    ← All references to ../../assets/
```

**Advantages:**
- ✅ All media in one place
- ✅ Easy to manage asset library
- ✅ Clear separation: content vs. media
- ✅ Good for large courses with many assets

**Disadvantages:**
- ⚠️ Less obvious which pages use which assets
- ⚠️ More complex references (../../assets/...)

---

### Strategy 3: Media-Type Organization

**Organize by file type**

```
assets/
  images/
    logos/
      school.png
      department.png
    diagrams/
      cell-structure.png
      dna-replication.png
      ecosystem-flow.png
    photos/
      lab-equipment-01.jpg
      lab-equipment-02.jpg
  videos/
    lectures/
      week-01-intro.mp4
      week-02-basics.mp4
    demonstrations/
      lab-procedure-01.mp4
  documents/
    handouts/
      study-guide-ch1.pdf
      study-guide-ch2.pdf
    templates/
      lab-report-template.docx
```

**Advantages:**
- ✅ Assets grouped by type
- ✅ Easy to find all images, videos, etc.
- ✅ Good for asset management

---

## Practical Workflows

### Workflow 1: Start Simple, Organize Later

**Phase 1: Initial Creation (Fast & Easy)**
```
pages/
  my-first-page.page/
    index.md
    photo1.jpg        ← Drop files here while drafting
    photo2.jpg
    diagram.png
```

```markdown
<!-- Quick references, no path complexity -->
![Photo 1](photo1.jpg)
![Photo 2](photo2.jpg)
![Diagram](diagram.png)
```

```bash
zaphod sync
# ✅ Everything works, fast iteration
```

**Phase 2: Identify Shared Assets**

After creating several pages, notice patterns:
- `school-logo.png` appears in 5 pages
- `default-banner.jpg` used in 3 pages
- Page-specific screenshots stay unique

**Phase 3: Organize for Reuse**
```bash
# Move shared assets to assets/
mkdir -p assets/images
mv pages/page1.page/school-logo.png assets/images/
mv pages/page2.page/school-logo.png assets/images/  # Duplicate, will merge
```

**Phase 4: Update References**
```markdown
<!-- Update from: -->
![Logo](school-logo.png)

<!-- To: -->
![Logo](../../assets/images/school-logo.png)
```

**Phase 5: Sync**
```bash
zaphod sync
# Registry automatically handles:
# - Deduplication of identical files
# - Updating Canvas references
# - No redundant uploads
```

---

### Workflow 2: Shared Assets from Day One

**Phase 1: Setup Structure**
```bash
mkdir -p assets/{images,videos,documents}
mkdir -p pages
```

**Phase 2: Add Shared Assets First**
```bash
# Add course-wide assets
cp ~/branding/university-logo.png assets/images/
cp ~/videos/course-intro.mp4 assets/videos/
cp ~/documents/syllabus.pdf assets/documents/
```

**Phase 3: Create Pages with References**
```markdown
<!-- pages/welcome.page/index.md -->
# Welcome to Biology 101

![University Logo](../../assets/images/university-logo.png)

{{video:course-intro.mp4}}

[Download Syllabus](../../assets/documents/syllabus.pdf)
```

**Phase 4: Sync Once**
```bash
zaphod sync
# All shared assets uploaded
# All pages reference the same Canvas files
```

**Phase 5: Add Page-Specific Content**
```bash
# Add unique diagrams to individual pages
cp ~/diagrams/cell-diagram.png pages/chapter-1.page/
```

```markdown
<!-- Combine shared and unique -->
![University Logo](../../assets/images/university-logo.png)
![Cell Diagram](cell-diagram.png)
```

---

### Workflow 3: Video-Heavy Course

**Setup:**
```
assets/
  videos/
    lectures/
      week-01-introduction.mp4
      week-02-fundamentals.mp4
      week-03-applications.mp4
    demos/
      lab-setup.mp4
      safety-procedures.mp4
    supplemental/
      expert-interview-01.mp4
```

**Reference Videos:**
```markdown
<!-- Simple reference by filename -->
{{video:week-01-introduction.mp4}}

<!-- Or explicit path -->
{{video:videos/lectures/week-01-introduction.mp4}}

<!-- Both work! -->
```

**Auto-discovery finds:**
- Searches `assets/` for `week-01-introduction.mp4`
- Finds it in `assets/videos/lectures/`
- Uploads and embeds automatically

---

## Common Questions

### Q: What if I accidentally copy the same file to multiple pages?

**A: No problem! Registry handles it automatically.**

```
pages/
  page1.page/logo.png    ← Same file
  page2.page/logo.png    ← Same file
  page3.page/logo.png    ← Same file
```

**Result:**
- First sync: Uploads once
- Subsequent pages: Reuse existing Canvas file
- No wasted uploads or storage

### Q: Can I mix strategies?

**A: Yes! Registry doesn't care about organization.**

```
pages/
  module-1/
    page1.page/
      diagram.png         ← Page-specific
    page2.page/
      index.md            → References ../../assets/logo.png

assets/
  logo.png               ← Shared
```

**Result:** Both approaches work together seamlessly.

### Q: What happens when I move a file?

**A: Update the reference, sync again.**

```bash
# Before
pages/welcome.page/logo.png
# Reference: ![Logo](logo.png)

# Move to assets
mv pages/welcome.page/logo.png assets/images/

# Update reference
# Old: ![Logo](logo.png)
# New: ![Logo](../../assets/images/logo.png)

zaphod sync
# Registry recognizes same file (same hash)
# No new upload needed ✅
```

### Q: Can I rename a file?

**A: Yes, but update references.**

```bash
# Rename file
mv assets/old-name.png assets/new-name.png

# Update markdown
# Old: ![Image](../../assets/old-name.png)
# New: ![Image](../../assets/new-name.png)

zaphod sync
# Registry tracks by content hash
# Same file, new name = reuses existing Canvas file ✅
```

### Q: What if I have the same filename but different content?

**A: Registry tracks both separately.**

```
pages/
  chapter1.page/screenshot.png   ← Different content
  chapter2.page/screenshot.png   ← Different content
```

**Result:**
- Two different uploads
- Two different Canvas files
- Each page gets its correct screenshot

### Q: How do I share an asset between courses?

**Option 1: Copy to each course**
```bash
cp ~/shared-assets/university-logo.png course-1/assets/images/
cp ~/shared-assets/university-logo.png course-2/assets/images/
```

Each course uploads independently (Canvas courses are separate).

**Option 2: Use a shared assets repository**
```bash
# Create shared location
mkdir ~/course-assets/

# Symlink in each course (advanced)
ln -s ~/course-assets/university-logo.png course-1/assets/images/
ln -s ~/course-assets/university-logo.png course-2/assets/images/
```

Each course still uploads to its own Canvas instance.

---

## File Types Supported

### Images
```
.png, .jpg, .jpeg, .gif, .svg, .bmp, .webp, .ico, .tiff
```

**Usage:**
```markdown
![Description](image.png)
```

### Videos
```
.mp4, .mov, .avi, .webm, .mkv, .m4v, .flv, .wmv
```

**Usage:**
```markdown
{{video:lecture.mp4}}
```

### Documents
```
.pdf, .doc, .docx, .txt, .rtf, .odt
```

**Usage:**
```markdown
[Download Handout](handout.pdf)
```

### Spreadsheets
```
.xls, .xlsx, .csv, .ods
```

### Presentations
```
.ppt, .pptx, .odp
```

### Audio
```
.mp3, .wav, .ogg, .m4a, .flac
```

### Archives
```
.zip, .tar, .gz, .rar, .7z
```

### Other
```
.json, .xml, .yaml, .yml, .html, .htm
```

---

## Troubleshooting

### File Not Found

**Error:**
```
[assets:warn] Local asset not found: photo.jpg
```

**Solutions:**

1. **Check filename (case-sensitive on Linux/macOS)**
   ```
   ✗ Photo.jpg vs photo.jpg
   ✓ Exact match required
   ```

2. **Check file location**
   ```bash
   # Is the file where you think it is?
   ls pages/my-page.page/
   ls assets/images/
   ```

3. **Use explicit path**
   ```markdown
   <!-- Instead of auto-discovery -->
   ![Photo](photo.jpg)

   <!-- Use explicit path -->
   ![Photo](../../assets/images/photo.jpg)
   ```

### Ambiguous Filename

**Warning:**
```
[assets:warn] Multiple files named 'diagram.png' found:
        - assets/chapter1/diagram.png
        - assets/chapter2/diagram.png
        Use explicit path, e.g., ../assets/chapter1/diagram.png
```

**Solution: Use explicit path**
```markdown
<!-- Ambiguous (multiple files) -->
![Diagram](diagram.png)

<!-- Explicit (unambiguous) -->
![Diagram](../../assets/chapter1/diagram.png)
```

### Asset Not Updating in Canvas

**Problem:** Changed file locally but Canvas still shows old version

**Cause:** Browser cache or Canvas cache

**Solutions:**

1. **Hard refresh browser**
   - Chrome/Firefox: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
   - Clears browser cache

2. **Check if file actually changed**
   ```bash
   # Verify file was modified
   ls -lh assets/images/banner.jpg
   # Check modification time
   ```

3. **Verify sync happened**
   ```bash
   zaphod sync
   # Look for upload message
   # [upload] Uploaded banner.jpg (id=456, hash=abc123)
   ```

4. **Check registry**
   ```bash
   cat _course_metadata/asset_registry.json | grep banner.jpg
   # Verify latest hash is present
   ```

### Canvas Shows Broken Image

**Problem:** Image reference in Canvas but shows broken

**Cause:** File was deleted from Canvas or permissions changed

**Solution:**
```bash
# Clear caches to force re-upload
rm _course_metadata/upload_cache.json
rm _course_metadata/asset_registry.json

# Re-sync
zaphod sync
# Files will be re-uploaded
```

---

## Migration from Old System

If your source.md files contain Canvas URLs from before the registry:

### Check for Canvas URLs

```bash
# Find files with Canvas URLs
grep -r "canvas.instructure.com/files" pages/*/source.md
```

### Option 1: Revert with Git

```bash
# Find commit before Canvas URL pollution
git log --all -- "pages/*/source.md" | grep -B5 "before sync"

# Revert to clean state
git checkout <commit-hash> -- pages/

# Clear caches
rm _course_metadata/upload_cache.json
rm _course_metadata/asset_registry.json

# Re-sync (builds clean registry)
zaphod sync
```

### Option 2: Manual Cleanup

For each source.md with Canvas URLs:

1. **Identify the original filename**
   ```markdown
   <!-- Current (has Canvas URL) -->
   ![Photo](https://canvas.../files/12345/download?download_frd=1&verifier=abc)

   <!-- Filename is likely: photo.jpg, photo.png, etc. -->
   ```

2. **Locate the file in assets/ or download from Canvas**

3. **Update reference**
   ```markdown
   <!-- Replace with local reference -->
   ![Photo](../../assets/images/photo.jpg)
   ```

4. **Sync**
   ```bash
   zaphod sync
   ```

---

## Summary

### The Registry Makes Your Life Easier

✅ **Organize however you want** - Semantic (.page) or centralized (assets/)
✅ **Don't think about efficiency** - Registry handles deduplication
✅ **Copy files freely** - Identical content = one upload
✅ **Move files anytime** - Update references, registry adapts
✅ **Update once, affect all** - Change shared file, all pages update
✅ **Version control friendly** - No Canvas URLs in source files

### Recommended Starting Point

```
my-course/
  assets/
    images/
      # Shared logos, banners, common images
    videos/
      # Course videos, demos, lectures
    documents/
      # PDFs, handouts, templates
  pages/
    module-name.module/
      page-name.page/
        index.md
        # Page-specific screenshots, diagrams
```

### Remember

**The registry gives you flexibility without sacrificing efficiency. Your organizational choices are about human workflow, not technical constraints.**

---

**Related Documentation:**
- [08-assets.md](08-assets.md) - Asset management technical guide
- [15-asset-registry.md](15-asset-registry.md) - Asset Registry technical reference
- [14-import-export.md](14-import-export.md) - Import/export workflows
- [05-QUICK-START.md](../05-QUICK-START.md) - Getting started guide
