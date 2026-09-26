import os


DRIVE_ROOT = "/content/drive/MyDrive"
VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")
SKIP_DIRS = {".git", ".local", "android", "node_modules", ".cache", "tmp", "lost.dir", "lost+found", ".ipynb_checkpoints"}

_DRIVE_CACHE = []
_DRIVE_CACHE_TIME = 0
_CACHE_TTL = 60.0  # Cache scan results for 60 seconds to prevent FUSE freeze


def is_colab_drive_available():
    return os.path.isdir(DRIVE_ROOT)


def list_drive_videos(search_query="", limit=200, max_depth=3, force_refresh=False):
    global _DRIVE_CACHE, _DRIVE_CACHE_TIME
    import time

    if not is_colab_drive_available():
        raise FileNotFoundError(
            "Google Drive is not mounted. In Colab, run drive.mount('/content/drive') before starting WebUI."
        )

    now = time.time()
    query = (search_query or "").strip().lower()

    # Fast path: check in-memory cache if available and not forced
    if not force_refresh and _DRIVE_CACHE and (now - _DRIVE_CACHE_TIME < _CACHE_TTL):
        all_videos = _DRIVE_CACHE
    else:
        all_videos = []
        drive_root_depth = len(os.path.abspath(DRIVE_ROOT).rstrip(os.sep).split(os.sep))

        for root, dirs, files in os.walk(DRIVE_ROOT):
            # Prune hidden or massive non-video system directories
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".") and d.lower() not in SKIP_DIRS
            ]

            # Limit recursion depth to prevent crawling entire personal Drive
            current_depth = len(os.path.abspath(root).rstrip(os.sep).split(os.sep)) - drive_root_depth
            if current_depth >= max_depth:
                dirs[:] = []

            for filename in files:
                if not filename.lower().endswith(VIDEO_EXTENSIONS):
                    continue

                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, DRIVE_ROOT)

                try:
                    size_mb = os.path.getsize(full_path) / (1024 * 1024)
                except OSError:
                    size_mb = 0

                label = f"{rel_path} — {size_mb:.1f} MB"
                all_videos.append((label, full_path, rel_path.lower(), filename.lower()))

                if len(all_videos) >= limit * 2:
                    break

        _DRIVE_CACHE = all_videos
        _DRIVE_CACHE_TIME = now

    # Filter by query
    filtered = []
    for item in all_videos:
        label, full_path, rel_lower, file_lower = item
        if query and query not in file_lower and query not in rel_lower:
            continue
        filtered.append((label, full_path))
        if len(filtered) >= limit:
            break

    return filtered