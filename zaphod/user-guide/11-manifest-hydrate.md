# Manifest & Hydrate

> Managing large media files that are too big for Git.

---

## The Problem

Video files and other large media can make your Git repository unwieldy:
- Slow clones
- Large repository size  
- Git not designed for large binaries

**Solution:** Keep large files out of Git, but track what's needed in a manifest.

---

## How It Works

1. **Manifest** — A JSON file listing all large media files with checksums
2. **Hydrate** — Download missing files from a shared location

```
┌─────────────────┐     ┌──────────────────┐
│ Your Computer   │     │ Shared Storage   │
│ (Git repo)      │     │ (SMB/HTTP/local) │
│                 │     │                  │
│ manifest.json ──┼────▶│ lecture1.mp4     │
│ (tracked)       │     │ lecture2.mp4     │
│                 │     │ demo.mov         │
│ assets/         │◀────┼──────────────────│
│ (gitignored)    │     │                  │
└─────────────────┘     └──────────────────┘
```

---

## Setup

### Step 1: Gitignore Large Files

Add to `.gitignore`:

```gitignore
# Large media files
assets/*.mp4
assets/*.mov
assets/*.avi
assets/*.mkv
assets/**/*.mp4
assets/**/*.mov
```

### Step 2: Build the Manifest

After adding your media files:

```bash
python zaphod/build_media_manifest.py
```

This creates `_course_metadata/media_manifest.json`:

```json
{
  "version": "1.0",
  "generated_at": "2026-01-25T10:30:00Z",
  "items": [
    {
      "relative_path": "assets/videos/lecture1.mp4",
      "checksum": "sha256:abc123...",
      "size_bytes": 524288000
    },
    {
      "relative_path": "assets/videos/lecture2.mp4",
      "checksum": "sha256:def456...",
      "size_bytes": 612000000
    }
  ]
}
```

### Step 3: Store Original Files

Copy your large files to a shared location:

- **SMB share:** `\\fileserver\courses\CS101\`
- **HTTP server:** `https://media.university.edu/courses/CS101/`
- **Local path:** `/mnt/shared/courses/CS101/`

The file structure should mirror your course:

```
\\fileserver\courses\CS101\
└── assets/
    └── videos/
        ├── lecture1.mp4
        └── lecture2.mp4
```

### Step 4: Commit the Manifest

```bash
git add _course_metadata/media_manifest.json
git commit -m "Add media manifest"
```

---

## Hydrating Files

When you (or a collaborator) clone the repo, the large files are missing. Hydrate them:

### From SMB Share

```bash
python zaphod/hydrate_media.py --source "\\\\fileserver\\courses\\CS101"
```

### From HTTP Server

```bash
python zaphod/hydrate_media.py --source "https://media.university.edu/courses/CS101"
```

### From Local Path

```bash
python zaphod/hydrate_media.py --source "/mnt/shared/courses/CS101"
```

---

## Hydrate Options

### Preview (Dry Run)

See what would be downloaded:

```bash
python zaphod/hydrate_media.py --source "..." --dry-run
```

### Skip Verification

Skip checksum verification (faster, less safe):

```bash
python zaphod/hydrate_media.py --source "..." --no-verify
```

---

## Workflow Example

### Initial Setup (You)

```bash
# 1. Add video files to assets/videos/
cp ~/Desktop/lecture1.mp4 assets/videos/

# 2. Update gitignore
echo "assets/**/*.mp4" >> .gitignore

# 3. Build manifest
python zaphod/build_media_manifest.py

# 4. Copy files to shared storage
cp -r assets/videos/ "\\\\fileserver\\courses\\CS101\\assets\\videos\\"

# 5. Commit manifest (files are gitignored)
git add _course_metadata/media_manifest.json .gitignore
git commit -m "Add lecture videos (manifest only)"
git push
```

### Collaborator Setup

```bash
# 1. Clone the repo
git clone https://github.com/university/CS101.git

# 2. Hydrate media files
cd CS101
python zaphod/hydrate_media.py --source "\\\\fileserver\\courses\\CS101"

# 3. Verify
ls assets/videos/
# lecture1.mp4  lecture2.mp4
```

---

## Updating Media Files

When you update a video:

```bash
# 1. Replace the file
cp ~/Desktop/lecture1-updated.mp4 assets/videos/lecture1.mp4

# 2. Rebuild manifest (new checksum)
python zaphod/build_media_manifest.py

# 3. Update shared storage
cp assets/videos/lecture1.mp4 "\\\\fileserver\\courses\\CS101\\assets\\videos\\"

# 4. Commit new manifest
git add _course_metadata/media_manifest.json
git commit -m "Update lecture 1 video"
git push
```

Collaborators run hydrate again — it detects the checksum mismatch and re-downloads.

---

## File Types Tracked

By default, the manifest tracks:

**Video:**
- `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.m4v`, `.wmv`, `.flv`

**Audio:**
- `.mp3`, `.wav`, `.flac`, `.m4a`, `.ogg`, `.aac`, `.wma`

You can customize `LARGE_MEDIA_EXTENSIONS` in `build_media_manifest.py`.

---

## Tips

✅ **Mirror the folder structure** — Shared storage should match your course

✅ **Update manifest when files change** — Checksums detect changes

✅ **Use SMB for local teams** — Faster than HTTP

✅ **Use HTTP for distributed teams** — Works from anywhere

✅ **Document the source URL** — In your README or team docs

---

## Troubleshooting

### "Source not found"

- Check the source path is correct
- Check network connectivity
- Check permissions on the share

### "Checksum mismatch"

The file on the shared storage differs from what's expected:
- Re-upload the correct file to shared storage
- Or rebuild the manifest if the shared version is correct

### Files Still Missing After Hydrate

- Check `.gitignore` includes the file extensions
- Check the manifest includes the files
- Check the files exist at the source location

---

## Alternative: Git LFS

For simpler setups, consider Git LFS instead:

```bash
git lfs install
git lfs track "*.mp4"
git add .gitattributes
git add assets/videos/lecture1.mp4
git commit -m "Add video with LFS"
```

**Pros:** Simpler workflow, integrated with Git  
**Cons:** Requires LFS support, storage limits

---

## Next Steps

- [Assets](08-assets.md) — Using assets in your course
- [Pipeline](10-pipeline.md) — How syncing works
