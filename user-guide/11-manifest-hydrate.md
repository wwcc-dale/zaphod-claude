# Large media manifest system
### Keep Git repos clean by excluding large media files
   - **Problem**: Large video/audio files bloat Git repos and make cloning slow
   - **Solution**: Manifest-based system with hydrate script for shared media store
   - **Design principles**:
     - File-type based `.gitignore` (e.g., `*.mp4`, `*.mov`, `*.wav`) - not directory-based
     - Local asset handling unchanged - Zaphod works exactly as now for authors
     - Manifest built after prune step - snapshot of large media for later hydration
     - Hydrate checks local first - only pulls what's missing from shared store
     - Manifest is just a bill of materials - source location supplied at hydrate time
   - **Components**:
     - `.gitignore` patterns for large media extensions
     - `_course_metadata/media_manifest.json` - lists large files (tracked in Git)
     - `build_media_manifest.py` - Runs after prune, scans for large media types
     - `hydrate_media.py --source PATH` - For instructors: checks local, pulls missing
   - **Manifest format**:
     ```json
     {
       "version": "1.0",
       "generated_at": "2026-01-18T18:05:00Z",
       "items": [
         {
           "relative_path": "assets/videos/lecture01.mp4",
           "checksum": "sha256:abcd1234...",
           "size_bytes": 123456789
         }
       ]
     }
     ```
   - **Author workflow**: No change - work normally, manifest auto-generated after prune
   - **Instructor workflow**: Clone repo → run `hydrate_media.py --source "\\server\share"` → done
   - **Backend options**: SMB file server, local path, or HTTP(S) URL