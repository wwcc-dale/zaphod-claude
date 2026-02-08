"""
video_transcode.py - Video transcoding for pre-upload size reduction.

Uses ffmpeg-python to transcode video files to smaller sizes before uploading
to Canvas. Transcoded files are cached in _course_metadata/transcoded/ keyed
by content hash + quality preset so re-transcoding is skipped when unchanged.

Quality presets map to H.264/AAC output in an MP4 container (Canvas-compatible).
"""

import hashlib
from pathlib import Path

# Try to import ffmpeg; graceful skip if not installed
try:
    import ffmpeg
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False


QUALITY_PRESETS = {
    "low":    {"crf": 28, "scale": "scale=-2:480",  "audio_bitrate": "96k"},
    "medium": {"crf": 23, "scale": "scale=-2:720",  "audio_bitrate": "128k"},
    "high":   {"crf": 18, "scale": "scale=-2:1080", "audio_bitrate": "192k"},
}

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.webm', '.mkv', '.m4v', '.flv', '.wmv'}


def is_video_file(path: Path) -> bool:
    """Return True if the file has a recognised video extension."""
    return path.suffix.lower() in VIDEO_EXTENSIONS


def get_transcoded_path(original_path: Path, quality: str, cache_dir: Path) -> Path:
    """
    Return the expected cache path for a transcoded file.

    Cache key is based on original content hash + quality preset so that
    changing either the source file or the preset produces a new cache entry.
    """
    content_hash = hashlib.md5(original_path.read_bytes()).hexdigest()[:16]
    return cache_dir / f"{content_hash}_{quality}.mp4"


def maybe_transcode(file_path: Path, quality: str | None, cache_dir: Path) -> Path:
    """
    Transcode *file_path* to the requested quality preset if needed.

    Returns:
        - *file_path* unchanged if quality is None / "original" / not a video.
        - Cached transcode path if it already exists.
        - Newly transcoded path after transcoding.

    The original file is never modified.
    """
    # No-op cases
    if not quality or quality == "original":
        return file_path

    if not is_video_file(file_path):
        return file_path

    if quality not in QUALITY_PRESETS:
        print(f"[transcode:warn] Unknown quality preset '{quality}'; skipping transcode")
        return file_path

    if not FFMPEG_AVAILABLE:
        print(
            "[transcode:warn] ffmpeg-python is not installed; skipping video transcode. "
            "Install it with: pip install ffmpeg-python"
        )
        return file_path

    # Resolve cached output path
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = get_transcoded_path(file_path, quality, cache_dir)

    if out_path.exists():
        print(f"[transcode] Using cached {quality} transcode: {out_path.name}")
        return out_path

    preset = QUALITY_PRESETS[quality]
    print(f"[transcode] Transcoding {file_path.name} → {quality} ({out_path.name})…")

    try:
        (
            ffmpeg
            .input(str(file_path))
            .output(
                str(out_path),
                vcodec="libx264",
                acodec="aac",
                crf=preset["crf"],
                audio_bitrate=preset["audio_bitrate"],
                vf=preset["scale"],
                movflags="+faststart",
                # Suppress ffmpeg console spam
                loglevel="error",
            )
            .overwrite_output()
            .run()
        )
    except Exception as e:
        print(f"[transcode:err] Transcoding failed for {file_path.name}: {e}")
        # Clean up partial output
        if out_path.exists():
            out_path.unlink()
        return file_path

    orig_mb = file_path.stat().st_size / (1024 * 1024)
    out_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"[transcode] {file_path.name}: {orig_mb:.1f} MB → {out_mb:.1f} MB ({quality})")
    return out_path
